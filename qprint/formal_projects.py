"""Read ecosystem configuration first; fill only missing version information.

No downloads, compiler invocation or AI calls belong in this module.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re

import yaml

from .paths import WorkspaceError, read_text, safe_path
from .toolchains import EnvironmentUnavailable
from .formal_policy import safe_policy

METADATA = ".qprint-formal.yaml"
RECIPES = (".qprint-formal.lock.yaml", ".qprint-formal.recipe.yaml")
VERSION = r"\d+\.\d+\.\d+(?:\.\d+)?"
REVISION = r"[0-9a-fA-F]{40}"


class ResolutionError(EnvironmentUnavailable):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass
class Requirements:
    language: str
    version: str
    libraries: list[dict] = field(default_factory=list)
    native: dict = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)
    safe: str | bool = "inherit"
    mode: str = "standard"

    def legacy(self):
        return {"version": self.version, "libraries": self.libraries, "safe": self.safe, "mode": self.mode}


def read_mapping(path):
    try:
        data = yaml.safe_load(read_text(path))
    except yaml.YAMLError as exc:
        raise ResolutionError("invalid_metadata", f"Invalid {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ResolutionError("invalid_metadata", f"{path.name} must contain a mapping")
    return data


def legacy_requirements(project):
    path = safe_path(project.root, "project.yaml")
    if not path.exists():
        return {}
    data = read_mapping(path)
    if (set(data) != {"schema_version", "formal"} or type(data["schema_version"]) is not int
            or data["schema_version"] != 1 or not isinstance(data["formal"], dict)
            or set(data["formal"]) - {"lean", "agda"}):
        raise ResolutionError("invalid_metadata", "project.yaml requires schema_version: 1 and formal: {lean/agda: ...}")
    config = data["formal"].get(project.language, {})
    allowed = {"libraries", "version", "safe", "mode"} if project.language == "agda" else set()
    if not isinstance(config, dict) or set(config) - allowed:
        raise ResolutionError("invalid_metadata", "Unsupported project requirement; Lean versions belong only in lean-toolchain")
    return config


def agda_library(root):
    definitions = sorted(root.glob("*.agda-lib"))
    if len(definitions) > 1:
        raise ResolutionError("ambiguous_native_config", "Multiple .agda-lib files; select a single native project")
    if not definitions:
        return {}
    definition = safe_path(root, definitions[0].name)
    fields, current = {}, None
    for raw in read_text(definition).splitlines():
        line = re.sub(r"(?:^|\s)--(?:\s|$).*", "", raw)
        match = re.match(r"^([a-z-]+):\s*(.*)$", line)
        if match:
            current = match[1]
            fields.setdefault(current, []).extend(match[2].split())
        elif line.strip() and current and raw[:1].isspace():
            fields[current].extend(line.split())
        elif line.strip():
            raise ResolutionError("invalid_native_config", f"Invalid .agda-lib line: {line}")
    return {"file": definition.name, **fields}


def metadata_requirements(path):
    data = read_mapping(path)
    if set(data) - {"toolchain", "dependencies", "policy", "provenance"}:
        raise ResolutionError("invalid_metadata", f"Unsupported fields in {path.name}")
    tools, deps, policy = data.get("toolchain", {}), data.get("dependencies", {}), data.get("policy", {})
    if (not isinstance(tools, dict) or set(tools) - {"agda"} or not isinstance(deps, dict)
            or not isinstance(policy, dict) or set(policy) - {"safe", "mode"}):
        raise ResolutionError("invalid_metadata", f"Invalid toolchain/dependencies/policy in {path.name}")
    config = dict(policy)
    if "agda" in tools:
        config["version"] = tools["agda"]
    config["libraries"] = []
    for name, pin in deps.items():
        if not isinstance(name, str) or not isinstance(pin, dict) or set(pin) not in ({"revision"}, {"version"}):
            raise ResolutionError("invalid_metadata", "Dependencies require name: {revision: full-commit} or {version: exact-version}")
        config["libraries"].append({"name": name, **pin})
    return config


def readme_requirements(root):
    evidence, versions, revisions = [], set(), set()
    for name in ("README.md", "README", "README.rst"):
        path = safe_path(root, name)
        if not path.is_file():
            continue
        for number, line in enumerate(read_text(path).splitlines(), 1):
            found = re.findall(rf"\bAgda\s+v?({VERSION})(?![\w.-])", line, re.I)
            commits = re.findall(rf"\b({REVISION})\b", line) if "cubical" in line.lower() else []
            if found or commits:
                evidence.append({"file": name, "line": number, "text": line})
            versions.update(found)
            revisions.update(c.lower() for c in commits)
    return versions, revisions, evidence


class FormalProjectResolver:
    def resolve(self, project, *, persist=True):
        if project.language == "lean":
            legacy_requirements(project)  # reject duplicate version authorities
            path = safe_path(project.root, "lean-toolchain")
            if not path.is_file():
                raise ResolutionError("missing_version", "Missing lean-toolchain; pin leanprover/lean4:vX.Y.Z in the project")
            pin = read_text(path).strip()
            match = re.fullmatch(r"leanprover/lean4:v(\d+\.\d+\.\d+(?:-rc\d+)?)", pin)
            if not match:
                raise ResolutionError("invalid_version", "lean-toolchain must pin an exact Lean 4 release (not stable/nightly)")
            native = {"lean-toolchain": pin}
            lock = safe_path(project.root, "lake-manifest.json")
            if lock.exists():
                try:
                    manifest = json.loads(read_text(lock))
                    if not isinstance(manifest, dict) or not isinstance(manifest.get("packages", []), list):
                        raise ValueError("expected object with packages array")
                    native["lake-manifest.json"] = manifest
                except ValueError as exc:
                    raise ResolutionError("invalid_native_config", f"Invalid lake-manifest.json: {exc}") from exc
            return Requirements("lean", match[1], native=native, evidence=[{"file": path.name, "text": pin}])
        if project.language != "agda":
            raise ResolutionError("unsupported_language", f"No verification adapter for {project.language}")
        native = agda_library(project.root)
        config, evidence, libraries = {}, [], {}
        # Higher priority values are never silently replaced by weaker evidence.
        sources = [(METADATA, metadata_requirements), ("project.yaml", lambda p: legacy_requirements(project)),
                   *((name, metadata_requirements) for name in RECIPES)]
        for name, reader in sources:
            path = safe_path(project.root, name)
            if not path.exists():
                continue
            values = reader(path)
            evidence.append({"file": name, "role": "requirements"})
            for key in ("version", "safe", "mode"):
                if key in values:
                    config.setdefault(key, values[key])
            items = values.get("libraries", [])
            if not isinstance(items, list):
                raise ResolutionError("invalid_metadata", "Agda libraries must be an array")
            for item in items:
                if (not isinstance(item, dict) or set(item) not in ({"name", "version"}, {"name", "revision"})
                        or not all(isinstance(v, str) and v for v in item.values())):
                    raise ResolutionError("invalid_metadata", "Each library needs name and one pinned version/revision")
                if "revision" in item and not re.fullmatch(REVISION, item["revision"]):
                    raise ResolutionError("invalid_version", "Library revision must be a full 40-character commit")
                if "revision" in item:
                    item = {**item, "revision": item["revision"].lower()}
                libraries.setdefault(item["name"], item)
        versions, revisions, hints = readme_requirements(project.root)
        if "version" not in config:
            if len(versions) != 1:
                raise ResolutionError("missing_version" if not versions else "ambiguous_version",
                                      "Missing or ambiguous Agda version; supply .qprint-formal.yaml (legacy project.yaml also supported)")
            config["version"] = versions.pop()
            evidence.extend(hints)
        value = config["version"]
        if not isinstance(value, str) or not re.fullmatch(VERSION, value):
            raise ResolutionError("invalid_version", "Agda version must be an exact quoted version")
        for dependency in native.get("depend", []):
            name = re.sub(r"-\d+(?:\.\d+)*$", "", dependency)
            if name in libraries:
                continue
            if name == "cubical" and len(revisions) == 1:
                libraries[name] = {"name": name, "revision": next(iter(revisions))}
                evidence.extend(hint for hint in hints if hint not in evidence)
            else:
                raise ResolutionError("missing_dependency_pin", f"Native dependency {dependency} has no exact metadata/recipe/README pin")
        flags = native.get("flags", [])
        mode = "erased-cubical" if "--erased-cubical" in flags else "cubical" if "--cubical" in flags else config.get("mode", project.mode)
        safe = safe_policy(config.get("safe", project.safe))
        if mode not in {"standard", "cubical", "erased-cubical"}:
            raise ResolutionError("invalid_metadata", "Invalid Agda safe/mode requirement")
        result = Requirements("agda", value, list(libraries.values()), native, evidence, safe, mode)
        output = safe_path(project.root, METADATA)
        if persist and not output.exists():
            document = {"toolchain": {"agda": value}, "dependencies": {
                p["name"]: {k: v for k, v in p.items() if k != "name"} for p in result.libraries},
                "policy": {"safe": safe, "mode": mode}, "provenance": evidence}
            try:
                with output.open("x", encoding="utf-8") as stream:
                    yaml.safe_dump(document, stream, allow_unicode=True, sort_keys=False)
            except FileExistsError:
                pass
        return result
