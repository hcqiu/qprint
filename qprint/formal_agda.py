"""Agda command construction and OPTIONS for declaration probes."""
from pathlib import Path
import re

from .formal_policy import safe_policy


def code_text(path):
    text = path.read_text(encoding="utf-8-sig")
    name = path.name
    if name.endswith((".lagda", ".lagda.tex")):
        chunks, active = [], False
        for line in text.splitlines():
            if active:
                if re.match(r"^[ \t]*\\end\{code\}", line):
                    active = False
                else:
                    chunks.append(line)
            elif re.match(r"^(?:[^%\\]|\\.)*?\\begin\{code\}", line):
                active = True
        return "\n".join(chunks)
    if name.endswith((".lagda.md", ".lagda.typ")):
        return "\n".join(re.findall(r"(?m)^```(?:agda)?[^\S\n]*\n(.*?)^```[^\S\n]*$", text, re.S))
    if name.endswith(".lagda.org"):
        return "\n".join(re.findall(r"(?im)^#\+begin_src agda2[ \t]*\n(.*?)^#\+end_src[ \t]*$", text, re.S))
    if name.endswith(".lagda.rst"):
        chunks, indent = [], None
        for line in text.splitlines():
            depth = len(line) - len(line.lstrip())
            if indent is not None and (not line.strip() or depth > indent):
                chunks.append(line)
                continue
            indent = None
            if line.rstrip().endswith("::") and not line.lstrip().startswith(".."):
                indent = depth
        return "\n".join(chunks)
    return text


def source_options(path):
    """Skip nested ordinary comments; preserve actual module pragma options."""
    text = code_text(path)
    options, position, depth = [], 0, 0
    while position < len(text):
        if text.startswith("{-#", position) and not depth:
            end = text.find("#-}", position + 3)
            if end == -1:
                break
            pragma = text[position + 3:end].strip()
            if pragma.startswith("OPTIONS ") or pragma.startswith("OPTIONS\n"):
                options.extend(pragma[len("OPTIONS"):].split())
            position = end + 3
        elif text.startswith("{-", position):
            depth += 1
            position += 2
        elif depth and text.startswith("-}", position):
            depth -= 1
            position += 2
        elif not depth and text.startswith("--", position):
            end = text.find("\n", position)
            position = len(text) if end == -1 else end + 1
        elif not depth and text[position] == '"':
            position += 1
            while position < len(text):
                if text[position] == "\\":
                    position += 2
                elif text[position] == '"':
                    position += 1
                    break
                else:
                    position += 1
        else:
            position += 1
    # The probe must turn an unknown name in `using` into an error even when
    # the source customizes warning levels. Other native OPTIONS stay intact.
    return [option for option in options if not option.startswith("--warning")]


def command(context, registry, *, declaration=False):
    result = [str(context.compiler), "--no-default-libraries", "--library-file", str(registry)]
    if safe_policy(context.safe) == "require":
        result += ["--safe", "--ignore-all-interfaces"]
    if declaration:
        result.append("--warning=error")
    for include in (context.source_root, *context.include_paths):
        result += ["-i", str(include)]
    return result


def write_registry(context, directory):
    registry = Path(directory) / "libraries"
    registry.write_text("".join(str(p) + "\n" for p in context.library_files), encoding="utf-8")
    return registry
