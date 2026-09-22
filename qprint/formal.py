from pathlib import Path
import re

from .paths import WorkspaceError, read_text, safe_path
from .formal_sources import SOURCE_SUFFIXES

EXTENSIONS = {"lean": ".lean", "agda": ".agda", "coq": ".v"}


def locate_code(root: Path, binding: dict) -> dict:
    result = {**binding, "code": None, "error": None}
    language, declaration = binding["language"], binding["declaration"]
    try:
        base = safe_path(root, language)
        filename = binding.get("file")
        if not filename:
            components = declaration.split(".")
            candidates = ["/".join(components[:i]) + suffix for i in range(len(components), 0, -1)
                          for suffix in SOURCE_SUFFIXES.get(language, (EXTENSIONS[language],))]
            filename = next((p for p in candidates if safe_path(base, p).is_file()), None)
        if not filename:
            result["error"] = "远程绑定，尚未下载" if binding.get("url") else "未找到模块文件，请配置 file 和 lines"
            return result
        path = safe_path(base, filename)
        if not path.is_file():
            result["error"] = "本地代码不存在；可从来源仓库导入"
            return result
        lines = read_text(path).splitlines()
        bounds = binding.get("lines")
        if bounds:
            start, end = bounds
            if end > len(lines):
                raise WorkspaceError("绑定行号超出文件范围")
        else:
            names = {declaration, declaration.rsplit(".", 1)[-1]}
            declarations = []
            namespaces = []
            for i, line in enumerate(lines):
                if language == "lean":
                    if m := re.match(r"^namespace\s+(\S+)", line):
                        namespaces.append(m[1])
                    if re.match(r"^end(?:\s|$)", line) and namespaces:
                        namespaces.pop()
                    m = re.match(r"^(?:@\[[^\]]*\]\s*)?(?:(?:noncomputable|private|protected|unsafe)\s+)*(?:def|theorem|lemma|abbrev|axiom|opaque|structure|inductive|class|instance)\s+([^\s(:{]+)", line)
                    if m:
                        declarations.append((i, ".".join([*namespaces, m[1]])))
                elif language == "coq":
                    m = re.match(r"^(?:Local\s+|Global\s+)?(?:Definition|Theorem|Lemma|Corollary|Proposition|Fixpoint|Inductive|Record|Axiom|Parameter|Example)\s+(\S+?)(?=\s|:|\()", line)
                    if m:
                        declarations.append((i, m[1]))
                elif m := re.match(r"^([^\s:]+)\s*:", line):
                    declarations.append((i, m[1]))
            exact = [x for x in declarations if x[1] == declaration]
            matches = exact or [x for x in declarations if x[1].rsplit(".", 1)[-1] in names]
            if len(matches) != 1:
                raise WorkspaceError("声明不存在或有多个候选，请配置精确 lines")
            first = matches[0][0]
            end = next((i for i, _ in declarations if i > first), len(lines))
            for i in range(first + 1, end):
                if language == "coq" and re.match(r"^\s*(?:Qed|Defined|Admitted)\.", lines[i]):
                    end = i + 1
                    break
                if language == "lean" and re.match(r"^(?:end|namespace|section)(?:\s|$)", lines[i]):
                    end = i
                    break
            start = first + 1
            while end > start and not lines[end - 1].strip():
                end -= 1
        result.update(file=filename, lines=[start, end], code="\n".join(lines[start - 1:end]))
    except (OSError, UnicodeError, WorkspaceError) as exc:
        result["error"] = str(exc)
    return result
