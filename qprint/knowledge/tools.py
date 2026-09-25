"""Transport-neutral JSON tool API for MCP/agent hosts."""
import inspect

from ..paths import WorkspaceError
from ..agent_paths import relative_output

_FIELDS = {
    "query": {"type": "string"}, "node": {"type": "string"},
    "scope": {"type": "string"}, "kinds": {"type": "array", "items": {"type": "string"}},
    "limit": {"type": "integer", "minimum": 1}, "radius": {"type": "integer", "minimum": 0, "maximum": 3},
    "source": {"type": "string"}, "target": {"type": "string"},
    "start": {"type": "string"}, "end": {"type": "string"}, "type": {"type": "string"},
    "depth": {"type": "integer", "minimum": 0, "maximum": 20},
    "direction": {"type": "string", "enum": ["out", "in", "both"]},
    "types": {"type": "array", "items": {"type": "string"}},
    "lines": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2},
    "max_lines": {"type": "integer", "minimum": 1, "maximum": 1000},
    "max_chars": {"type": "integer", "minimum": 1, "maximum": 100000},
    "max_depth": {"type": "integer", "minimum": 0, "maximum": 50},
    "token_budget": {"type": "integer", "minimum": 128, "maximum": 100000},
}
DESCRIPTIONS = {
    "kb_state": "Read current browser/host node, project, view, selection, index status and session history. Does not change focus. Start here for questions about the current page.",
    "kb_search": "Search exact symbols, aliases, lexical text, graph neighbors, then optional semantic matches.",
    "kb_resolve": "Resolve a symbol to metadata and source locations; return ambiguity rather than guessing.",
    "kb_open": "Read a compact node summary, dependencies and source locations without opening source files.",
    "kb_source": "Read bounded original TeX, Markdown or formal source fragments, checking index freshness.",
    "kb_dependencies": "Follow typed dependency edges with a depth bound; out means this node uses the target.",
    "kb_backlinks": "Find nodes that use, reference or mention this result, optionally transitively.",
    "kb_path": "Find a shortest bounded graph path, preserving edge types and direction.",
    "kb_context": "Prepare current node, direct dependencies, necessary definitions and session working set within a budget.",
    "kb_explain_edge": "Retrieve reviewed explanations and source evidence for a directed edge; never invent reasons.",
}


def tool_definitions():
    from .navigator import KnowledgeNavigator
    result = []
    for name, description in DESCRIPTIONS.items():
        properties, required = {}, []
        for key, parameter in inspect.signature(getattr(KnowledgeNavigator, name)).parameters.items():
            if key == "self":
                continue
            properties[key] = dict(_FIELDS[key])
            if parameter.default is inspect.Parameter.empty:
                required.append(key)
            elif parameter.default is not None:
                properties[key]["default"] = parameter.default
        result.append({"name": name, "description": description,
                       "inputSchema": {"type": "object", "properties": properties,
                                       "required": required, "additionalProperties": False}})
    return result


def call_tool(navigator, name, arguments):
    if name not in DESCRIPTIONS:
        raise WorkspaceError(f"Unknown knowledge tool: {name}")
    if not isinstance(arguments, dict):
        raise WorkspaceError("Tool arguments must be an object")
    method = getattr(navigator, name)
    try:
        inspect.signature(method).bind(**arguments)
    except TypeError as exc:
        raise WorkspaceError(str(exc)) from exc
    parameters = inspect.signature(method).parameters
    for key, value in arguments.items():
        if value is None and parameters[key].default is None:
            continue
        field = _FIELDS[key]
        expected = {"string": str, "integer": int, "array": list}[field["type"]]
        if type(value) is not expected:
            raise WorkspaceError(f"{key} must be {field['type']}")
        if expected is list:
            item_type = {"string": str, "integer": int}[field["items"]["type"]]
            if any(type(item) is not item_type for item in value):
                raise WorkspaceError(f"{key} contains invalid items")
    return relative_output(method(**arguments), navigator.runtime_root)
