"""Collect measured clean-subagent trials without exposing evaluator rubrics.

Reads only logs with an exact /root/nav_eval_<case> recipient. It exports tool
calls for human scope auditing; it does not guess correctness or token counts.
Run after all cases finish. Full tool outputs are stored separately as evidence.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def text_output(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(part.get("text", "")) for part in value if isinstance(part, dict))
    return json.dumps(value, ensure_ascii=False)


def terminal_results(output):
    """Unwrap exec results, including batched Promise.allSettled responses."""
    def visit(value):
        if isinstance(value, dict):
            if "wall_time_seconds" in value and "output" in value:
                yield value
            else:
                for child in value.values():
                    yield from visit(child)
        elif isinstance(value, list):
            for child in value:
                yield from visit(child)
    for line in output.splitlines():
        try:
            yield from visit(json.loads(line))
        except json.JSONDecodeError:
            continue


def collect(case, path, entries):
    complete = next((e for e in reversed(entries) if e.get("type") == "event_msg"
                     and e["payload"].get("type") == "task_complete"), None)
    if not complete:
        return None, None
    completion = complete["payload"]
    turn_id = completion["turn_id"]
    context = next((e["payload"] for e in entries if e.get("type") == "turn_context"), {})
    usage = next((e["payload"]["turn_token_usage"] for e in reversed(entries)
                  if e.get("type") == "token_usage_record" and e["payload"].get("turn_id") == turn_id), None)
    calls, outputs, raw = [], {}, []
    initial = None
    for entry in entries:
        payload = entry.get("payload", {})
        if entry.get("type") != "response_item":
            continue
        kind = payload.get("type")
        if kind == "agent_message" and payload.get("recipient") == "/root/nav_eval_" + case["id"].lower():
            initial = entry["timestamp"]
        if kind in {"function_call", "custom_tool_call"}:
            calls.append({"timestamp": entry["timestamp"], "call_id": payload["call_id"],
                          "tool": payload["name"], "input": payload.get("input", payload.get("arguments", ""))})
        elif kind in {"function_call_output", "custom_tool_call_output"}:
            output = text_output(payload.get("output", ""))
            outputs[payload["call_id"]] = output
            raw.append({"timestamp": entry["timestamp"], "call_id": payload["call_id"], "output": output})
    for call in calls:
        output = outputs.get(call["call_id"], "")
        call["output_characters"] = len(output)
        call["output_sha256"] = hashlib.sha256(output.encode("utf-8")).hexdigest() if output else None
        call["database_open_error"] = "unable to open database file" in output
    actions = [action for call in calls for action in re.findall(r"qprint agent ([a-z-]+)", call["input"])]
    terminal = [result for evidence in raw for result in terminal_results(evidence["output"])]
    # The only permitted non-query command is the single skill read. Exclude it
    # by its content, not by a fixed invocation count. Loop-expanded commands
    # are counted from actual shell results, rather than source-code matches.
    queries = [r for r in terminal if not r["output"].lstrip().startswith("---\nname: knowledge-navigator")
               and not r["output"].lstrip().startswith("---\r\nname: knowledge-navigator")]
    logical_queries, state_reads, history_warnings = 0, 0, 0
    for query in queries:
        try:
            payload = json.loads(query["output"])
        except json.JSONDecodeError:
            payload = None
        batch = payload.get("results") if isinstance(payload, dict) else None
        if isinstance(batch, list) and all(isinstance(c, dict) and "tool" in c for c in batch):
            logical_queries += len(batch)
            bodies = [c.get("result", {}) for c in batch]
        else:
            logical_queries += 1
            bodies = [payload]
        for body in bodies:
            if isinstance(body, dict):
                state_reads += all(key in body for key in ("current_node", "session", "focus_origin"))
                history_warnings += "state_warning" in body
    result = {"case_id": case["id"], "original_case_id": case.get("original_case_id", case["id"]),
              "project": case["project"], "question": case["question"],
              "model": context.get("model"), "reasoning_effort": context.get("effort"),
              "agent": "/root/nav_eval_" + case["id"].lower(), "log_file": path.name,
              "started_at": completion.get("started_at"), "completed_at": completion.get("completed_at"),
              "wall_seconds": completion.get("duration_ms", 0) / 1000,
              "time_to_first_token_seconds": completion.get("time_to_first_token_ms", 0) / 1000,
              "prompt_to_completion_seconds": round((timestamp(complete["timestamp"]) - timestamp(initial)).total_seconds(), 3) if initial else None,
              "first_tool_to_completion_seconds": round((timestamp(complete["timestamp"]) - timestamp(calls[0]["timestamp"])).total_seconds(), 3) if calls else None,
              "token_usage": usage,
              "uncached_input_plus_output_tokens": usage["input_tokens"] - usage["cached_input_tokens"] + usage["output_tokens"] if usage else None,
              "navigator_command_templates": actions, "navigator_command_count": len(queries),
              "navigator_query_count": logical_queries, "state_reads": state_reads,
              "history_write_warnings": history_warnings,
              "query_exit_codes": [q.get("exit_code") for q in queries],
              "database_open_errors": sum(c["database_open_error"] for c in calls),
              "tool_calls": calls, "answer": completion.get("last_agent_message", ""),
              "scope_audit": "pending_manual_review", "answer_review": "pending_manual_review"}
    return result, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("tests/scenarios/knowledge_navigator.json"))
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--rerun", action="append", default=[], metavar="RUN_ID=CASE_ID",
                        help="Collect an additional fresh agent with unchanged original question")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    originals = {c["id"]: c for c in cases}
    for mapping in args.rerun:
        run_id, original = mapping.split("=", 1)
        if run_id in {c["id"] for c in cases}:
            parser.error(f"Duplicate run ID: {run_id}")
        cases.append({**originals[original], "id": run_id, "original_case_id": original})
    wanted = {"/root/nav_eval_" + case["id"].lower(): case for case in cases}
    results = {}
    for path in sorted(args.logs.glob("*.jsonl")):
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # An active log may end with an incomplete append.
        recipients = {e.get("payload", {}).get("recipient") for e in entries if e.get("type") == "response_item"}
        for recipient in recipients & wanted.keys():
            case = wanted[recipient]
            result, evidence = collect(case, path, entries)
            if result:
                results[case["id"]] = result
                args.evidence.mkdir(parents=True, exist_ok=True)
                (args.evidence / (case["id"] + ".json")).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ordered = [results[c["id"]] for c in cases if c["id"] in results]
    args.output.write_text(json.dumps({"metric_source": "Codex task_complete and token_usage_record; cumulative input includes cached replay",
                                       "completed_cases": len(ordered), "results": ordered}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"completed": list(results), "missing": [c["id"] for c in cases if c["id"] not in results]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
