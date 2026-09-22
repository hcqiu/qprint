"""Project requirements -> exact installed tools/packages -> execution context."""
from dataclasses import dataclass, field, asdict
import os
from pathlib import Path
import re
import shutil

from .paths import WorkspaceError, read_text, safe_path
from .toolchains import EnvironmentUnavailable, ToolchainManager, host_platform

from .formal_projects import FormalProjectResolver
from .formal_artifacts import ArtifactProvider
from .formal_policy import safe_policy
from .formal_downloads import event


@dataclass(frozen=True)
class FormalExecutionContext:
    language: str
    version: str
    compiler: Path
    driver: Path
    project_root: Path
    source_root: Path
    include_paths: tuple[Path, ...]
    environment: dict[str, str]
    artifacts: tuple[str, ...] = ()
    origin: str = "managed"
    safe: str | bool = "inherit"
    mode: str = "standard"
    flags: tuple[str, ...] = ()
    library_files: tuple[Path, ...] = ()
    requirements: dict = field(default_factory=dict)

    def public(self):
        return {"language": self.language, "version": self.version, "compiler": str(self.compiler),
                "driver": str(self.driver), "origin": self.origin, "artifacts": list(self.artifacts),
                "include_paths": [str(p) for p in self.include_paths], "flags": list(self.flags),
                "library_files": [str(p) for p in self.library_files], "requirements": self.requirements}


class ToolchainResolver:
    def __init__(self, home: Path | None = None, *, allow_system: bool = False, manager=None,
                 auto_install: bool = False, project_resolver=None, provider=None):
        self.manager = manager or ToolchainManager(home)
        self.allow_system = allow_system
        self.auto_install = auto_install
        self.project_resolver = project_resolver or FormalProjectResolver()
        self.provider = provider or ArtifactProvider(self.manager)

    def _artifact(self, *, kind, language, version=None, name=None, revision=None):
        matches = [(key, item) for key, item in self.manager.catalog["artifacts"].items()
                   if item["kind"] == kind and item["language"] == language
                   and item.get("platform", "any") in {"any", host_platform()}
                   and (version is None or item["version"] == version)
                   and (name is None or item.get("name") == name)
                   and (revision is None or item.get("revision") == revision)]
        if not matches and self.auto_install:
            matches = [self.provider.discover(kind=kind, language=language, version=version, name=name, revision=revision)]
        if len(matches) != 1:
            raise EnvironmentUnavailable(f"No unique catalog entry for {language} {version or revision or name}")
        key, item = matches[0]
        if self.manager.installed(key) is None:
            if not self.auto_install:
                raise EnvironmentUnavailable(f"Missing {key}; run qprint toolchain install {key}")
            self.manager.install(key)
        event("artifact_integrity", artifact=key, **{field: item[field] for field in
              ("integrity", "sha256", "url", "release_api", "asset_id", "asset_size") if field in item})
        return key, item, self.manager.target(item)

    def resolve(self, project) -> FormalExecutionContext:
        resolved = self.project_resolver.resolve(project)
        requirements = resolved.legacy()
        version = resolved.version
        env = dict(os.environ)
        # Never inherit another toolchain's Lean paths or executable overrides.
        for key in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "LEAN", "LAKE", "ELAN_TOOLCHAIN", "LEAN_CC"):
            env.pop(key, None)
        artifacts = []
        origin = "managed"
        try:
            key, item, target = self._artifact(kind="toolchain", language=project.language, version=version)
            compiler = safe_path(target, item["executables"][project.language])
            driver = safe_path(target, item["executables"].get("lake", item["executables"][project.language]))
            artifacts.append(key)
        except EnvironmentUnavailable:
            if not self.allow_system:
                raise
            compiler_path = shutil.which(project.language)
            driver_path = shutil.which("lake" if project.language == "lean" else project.language)
            if not compiler_path or not driver_path:
                raise EnvironmentUnavailable("Explicit system fallback requested, but tools are not on PATH")
            compiler, driver = Path(compiler_path).resolve(), Path(driver_path).resolve()
            origin, target = "system", compiler.parent.parent
            # Fallback must satisfy the project pin; never silently switch versions.
            from .verification import run_command
            result = run_command("version", [str(compiler), "--version"], project.root, 15, env=env)
            if result.status != "passed" or not re.search(rf"(?<![\w.-]){re.escape(version)}(?![\w.-])", result.output):
                raise EnvironmentUnavailable(f"PATH compiler does not satisfy project version {version}")
            if project.language == "lean":
                result = run_command("version", [str(driver), "--version"], project.root, 15, env=env)
                if result.status != "passed" or not re.search(rf"Lean version {re.escape(version)}(?![\w.-])", result.output):
                    raise EnvironmentUnavailable("PATH Lake does not match the required Lean version")
        env["PATH"] = str(driver.parent) + os.pathsep + env.get("PATH", "")
        libraries = list(project.include_paths)
        flags = []
        library_files = []
        source_root = project.source_root
        if project.language == "agda":
            native_flags = resolved.native.get("flags", [])
            flags.extend(f for f in native_flags if f in {"--guardedness", "--no-import-sorts"})
            # Native include directories inside the project define module roots.
            # External native includes remain Agda's own scoped configuration.
            local_includes = []
            for relative in resolved.native.get("include", []):
                candidate = (project.root / relative).resolve()
                if candidate.is_relative_to(project.root) and candidate.is_dir():
                    local_includes.append(candidate)
            if source_root == project.root and local_includes:
                source_root = local_includes[0]
            libraries.extend(p for p in local_includes if p != source_root)
            # Compiler data and app config stay under Qprint, never in the user's profile.
            env["AGDA_DIR"] = str(target / "data" if origin == "managed" else self.manager.home)
            if origin == "managed":
                env["Agda_datadir"] = str(target / "data")
            requested = requirements.get("libraries", [])
            if not isinstance(requested, list):
                raise WorkspaceError("Agda libraries must be an array")
            for library in requested:
                if (not isinstance(library, dict) or set(library) not in ({"name", "version"}, {"name", "revision"})
                        or not all(isinstance(v, str) and v for v in library.values())):
                    raise WorkspaceError("Each library needs name and exactly one pinned version/revision")
                key, item, package = self._artifact(kind="package", language="agda", **library)
                artifacts.append(key)
                flags.extend(item.get("flags", []))
                if library_file := item.get("library_file"):
                    definition = safe_path(package, library_file)
                    if not definition.is_file():
                        raise EnvironmentUnavailable(f"Missing library definition for {key}")
                    library_files.append(definition)
                for path in item.get("include_paths", ["."]):
                    include = package if path == "." else safe_path(package, path)
                    if not include.is_dir():
                        raise EnvironmentUnavailable(f"Missing include directory for {key}")
                    libraries.append(include)
        safe, mode = safe_policy(requirements.get("safe", project.safe)), requirements.get("mode", project.mode)
        if mode not in ("standard", "cubical", "erased-cubical"):
            raise WorkspaceError("Invalid Agda safe/mode requirement")
        return FormalExecutionContext(project.language, version, compiler, driver, project.root,
                                      source_root, tuple(libraries), env, tuple(artifacts), origin, safe, mode,
                                      tuple(dict.fromkeys(flags)), tuple(library_files), asdict(resolved))
