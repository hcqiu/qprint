"""Literal adapters for paper syntax; these never execute TeX definitions."""
import re


def braced(source, start):
    while start < len(source) and source[start].isspace():
        start += 1
    if start >= len(source) or source[start] != "{":
        raise ValueError("需要完整的 TeX 花括号参数")
    depth, end = 1, start + 1
    while end < len(source) and depth:
        if source[end] == "\\":
            end += 2
            continue
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    if depth:
        raise ValueError("未闭合的 TeX 花括号参数")
    return source[start + 1:end - 1], end


def simple_definitions(preamble):
    """Translate only ordinary braced def macros, not TeX programs or I/O."""
    result = []
    for match in re.finditer(r"\\def\s*(\\[A-Za-z]+)\s*((?:#[1-9])*)\s*(?=\{)", preamble):
        try:
            body, _ = braced(preamble, match.end())
        except ValueError:
            continue
        count = len(match[2]) // 2
        if match[2] != ''.join(f'#{i}' for i in range(1, count + 1)):
            continue
        if re.search(r"\\(?:def|let|input|include\w*|open\w*|read\w*|write\w*|special|catcode|csname|loop|repeat|usepackage|documentclass|setbox|ooalign|newcommand|renewcommand|providecommand)\b|\^\^", body):
            continue
        result.append(r"\newcommand{" + match[1] + "}" + (f"[{count}]" if count else "") + "{" + body + "}")
    return result


def normalize_math(source, definitions):
    macros = {}
    for definition in definitions:
        match = re.match(r'\\newcommand\{(\\[A-Za-z]+)\}(?=\{)', definition)
        if match:
            macros[match[1]] = braced(definition, match.end())[0]
    # plasTeX preserves a few built-in accent names (e.g. H) in math source
    # even after a paper redefines them. Expand these literal aliases here.
    for _ in range(12):
        expanded = re.sub(r'\\[A-Za-z]+', lambda m: macros.get(m[0], m[0]), source)
        if expanded == source or len(expanded) > 100_000:
            break
        source = expanded
    for match in reversed(list(re.finditer(r'\\begin\{array\}\s*', source))):
        spec, end = braced(source, match.end())
        # Empty intercolumn inserts are spacing only; nonempty inserts stay
        # visible to KaTeX instead of silently dropping mathematical content.
        source = source[:match.end()] + '{' + re.sub(r'@\s*\{\s*\}', '', spec) + '}' + source[end:]
    for match in reversed(list(re.finditer(r'\\makebox(?:\s*\[[^]]*\]){0,2}\s*(?=\{)', source))):
        body, end = braced(source, match.end())
        body = re.sub(r'\\(?:tiny|scriptsize|small)\b', '', body).strip()
        if body.startswith('$') and body.endswith('$'):
            body = body[1:-1]
        else:
            body = r'\text{' + body + '}'
        source = source[:match.start()] + '{' + body + '}' + source[end:]
    return source


def amsrefs_bibliography(source):
    """Convert AMSRefs records into the same bibitem DOM used by BibTeX.

    Without precomputed labels, web citations use stable BBL-order numbering.
    All field values remain TeX and go through the bounded, escaping renderer.
    """
    entries = []
    for match in re.finditer(r"\\bib\s*(?=\{)", source):
        key, end = braced(source, match.end())
        _, end = braced(source, end)
        fields, _ = braced(source, end)
        values, offset = {}, 0
        pattern = re.compile(r"([A-Za-z][\w-]*)\s*=\s*(?=\{)")
        while m := pattern.search(fields, offset):
            value, offset = braced(fields, m.end())
            values.setdefault(m[1].lower(), []).append(value)
        if not values.get('title'):
            raise ValueError(f"AMSRefs 条目缺少 title: {key}")
        parts = []
        for name in ('author', 'editor', 'title', 'journal', 'booktitle', 'series', 'volume', 'number', 'publisher', 'address', 'date', 'pages', 'note'):
            if name in values:
                value = ', '.join(values[name])
                parts.append(r'\emph{' + value + '}' if name in {'journal', 'booktitle'} else value)
        for url in values.get('url', []):
            parts.append(r'\url{' + url + '}')
        for eprint in values.get('eprint', []):
            parts.append('arXiv: ' + eprint)
        label = values.get('label', [''])[0]
        label = '[' + label + ']' if label and not re.search(r'[\[\]]', label) else ''
        entries.append(r'\bibitem' + label + '{' + key + '}' + '. '.join(parts) + '.')
    return r'\begin{thebibliography}{999}' + '\n' + '\n'.join(entries) + '\n' + r'\end{thebibliography}' if entries else source


def compact_label_source(source, preamble):
    """Keep counter-bearing structure for the bounded whole-paper label pass."""
    theorem_names = set(re.findall(r'\\newtheorem\*?\s*\{([^}]+)\}', preamble))
    environments = theorem_names | {'figure', 'figure*', 'table', 'table*', 'enumerate', 'itemize', 'equation', 'equation*', 'align', 'align*', 'gather', 'gather*', 'proof'}
    result, stack, end = [], [], 0
    for match in re.finditer(r'\\([A-Za-z]+\*?|\\)', source):
        if match.start() < end:
            continue
        name = match[1]
        if name in {'begin', 'end', 'section', 'section*', 'subsection', 'subsection*', 'subsubsection', 'chapter', 'caption', 'label', 'setcounter', 'addtocounter'}:
            try:
                value, end = braced(source, match.end())
            except ValueError:
                continue
            if name in {'begin', 'end'}:
                if name == 'begin':
                    stack.append(value)
                elif stack and stack[-1] == value:
                    stack.pop()
                if value not in environments:
                    continue
            elif name not in {'label', 'setcounter', 'addtocounter'}:
                value = 'Title'
            result.append('\\' + name + '{' + value + '}')
            if name == 'begin' and value in {'equation', 'equation*', 'align', 'align*', 'gather', 'gather*'}:
                result.append(' x ')
            if name in {'setcounter', 'addtocounter'}:
                value, end = braced(source, end)
                result.append('{' + value + '}')
        elif name in {'item', 'appendix', 'nonumber', 'notag'}:
            result.append('\\' + name + ' ')
        elif name == '\\' and stack and stack[-1] in {'align', 'align*', 'gather', 'gather*'}:
            result.append(r'\\ ')
    return '\n'.join(result)
