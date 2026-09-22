"""Language-specific build and declaration probes."""
import json
from pathlib import Path
import re
import tempfile
from typing import Protocol
import uuid
from .formal_environment import FormalExecutionContext
from .formal_runner import Check, Runner
from .formal_sources import module_name
from .formal_agda import command as agda_command, source_options, write_registry
from .paths import WorkspaceError

def _lean_name(name: str) -> str:
    # Deliberately accept identifiers, never Lean expressions or commands.
    if not isinstance(name, str) or not re.fullmatch(r"[^\W\d]\w*(?:'\w*)*(?:\.[^\W\d]\w*(?:'\w*)*)*", name):
        raise WorkspaceError("Lean 验证需要普通点分限定名（不支持表达式或 «转义名»）")
    return name


def _agda_name(name: str) -> str:
    if (not isinstance(name, str) or not name or any(not part for part in name.split("."))
            or any(c.isspace() or ord(c) < 32 or c in ';(){}"\\@`?' for c in name)
            or any(s in name for s in ("--", "{-", "-}"))):
        raise WorkspaceError("Agda 验证需要点分声明名，不能包含表达式、注释或指令")
    return name


class VerificationAdapter(Protocol):
    language: str

    def verify(self, project: FormalExecutionContext, source: Path, declaration: str,
               runner: Runner, timeout: float) -> list[Check]: ...


class LeanAdapter:
    language = "lean"

    def verify(self, project, source, declaration, runner, timeout):
        declaration = _lean_name(declaration)
        module = _lean_name(module_name(source, project.source_root, "lean"))
        if not any((project.project_root / f"lakefile.{ext}").is_file() for ext in ("lean", "toml")):
            raise WorkspaceError("Lean 验证需要 Lake 项目（lakefile.lean 或 lakefile.toml）")
        # Build the bound module explicitly: it might not be a default target.
        checks = [runner("build", [str(project.driver), "build", f"+{module}"], project.project_root, timeout)]
        if checks[-1].status != "passed":
            return checks
        name_expr = "Lean.Name.anonymous"
        for part in declaration.split("."):
            name_expr = f"(Lean.Name.mkStr {name_expr} {json.dumps(part, ensure_ascii=False)})"
        probe = (f"import Lean\nimport {module}\n"
                 "run_cmd do\n"
                 f"  unless (← Lean.getEnv).contains {name_expr} do\n"
                 '    throwError "Qprint: declaration not found"\n')
        with tempfile.TemporaryDirectory(prefix="qprint-verify-", dir=project.project_root) as temporary:
            path = Path(temporary) / "QprintVerify.lean"
            path.write_text(probe, encoding="utf-8")
            checks.append(runner("declaration", [str(project.driver), "env", str(project.compiler), str(path)], project.project_root, timeout))
        return checks


class AgdaAdapter:
    language = "agda"

    def verify(self, project, source, declaration, runner, timeout):
        declaration = _agda_name(declaration)
        module = _agda_name(module_name(source, project.source_root, "agda"))
        relative = declaration.removeprefix(module + ".")
        prefix, _, name = relative.rpartition(".")
        scope = module + ("." + prefix if prefix else "")
        # Missing names in 'using' can be warnings; explicitly make them errors.
        # Cubical/guardedness are module options,
        # not global CLI flags: forcing them onto Agda's primitive modules breaks
        # their erased/full Cubical boundaries on the supported 2.8.0 distribution.
        probe_flags = [*project.flags, *source_options(source)]
        if project.mode != "standard":
            probe_flags.append("--" + project.mode)
        with tempfile.TemporaryDirectory(prefix="qprint-verify-", dir=project.project_root) as temporary:
            # Preserve library-scoped options while excluding global library lists.
            registry = write_registry(project, temporary)
            command = agda_command(project, registry)
            checks = [runner("typecheck", [*command, str(source)], project.project_root, timeout)]
            if checks[-1].status != "passed":
                return checks
            probe_module = "QprintVerify" + uuid.uuid4().hex
            path = Path(temporary) / (probe_module + ".agda")
            options = "{-# OPTIONS " + " ".join(probe_flags) + " #-}\n" if probe_flags else ""
            path.write_text(options + f"module {probe_module} where\nimport {module}\nopen {scope} using ({name})\n", encoding="utf-8")
            checks.append(runner("declaration", [*agda_command(project, registry, declaration=True), "-i", temporary, str(path)], project.project_root, timeout))
        return checks


ADAPTERS: dict[str, VerificationAdapter] = {"lean": LeanAdapter(), "agda": AgdaAdapter()}


