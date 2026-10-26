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


def biblatex_bibliography(source):
    """Read literal Biber records, without loading or executing biblatex.

    Only publication fields are copied into the existing safe bibitem renderer.
    Consume balanced arguments so commands inside a title cannot become records.
    Verbatim URL/DOI fields retain percent escapes and fragment identifiers.
    """
    source = re.sub(r'\\verb\{[^{}]*\}.*?\\endverb|(?<!\\)(?:\\\\)*(%[^\n]*)',
                    lambda m: m[0] if m[1] is None else m[0][:m.start(1) - m.start()],
                    source, flags=re.S)
    command = re.compile(r'\\([A-Za-z]+)\b')
    arities = {'entry': 3, 'field': 2, 'strng': 2, 'name': 4, 'list': 3,
               'range': 2, 'keyw': 1, 'true': 1, 'false': 1, 'set': 1,
               'inset': 1, 'missing': 1}

    def groups(value):
        offset = 0
        while value[offset:].strip():
            group, offset = braced(value, offset)
            yield group

    def names(value):
        result = []
        for record in groups(value):
            _, end = braced(record, 0)  # name hashes/options
            fields, _ = braced(record, end)
            parts, offset = {}, 0
            while match := re.search(r'([A-Za-z]+)\s*=\s*(?=\{)', fields[offset:]):
                part, offset = braced(fields, offset + match.end())
                parts[match[1]] = part
            result.append(parts.get('literal') or ' '.join(parts[k] for k in ('given', 'prefix', 'family', 'suffix') if parts.get(k)))
        return ', '.join(result)

    def text(value):
        replacements = {'bibrangedash': '--', 'bibnamedelima': ' ', 'bibnamedelimb': ' ',
                        'bibnamedelimc': ' ', 'bibnamedelimd': ' ', 'bibnamedelimi': ' ',
                        'bibinitdelim': ' ', 'bibinitperiod': '.', 'bibinithyphendelim': '-'}
        return re.sub(r'\\([A-Za-z]+)\b\s*', lambda m: replacements.get(m[1], m[0]), value)

    def entry(key, fields):
        if not key or re.search(r'[{}\\%\r\n]', key):
            raise ValueError('BibLaTeX 文献键不合法')
        if not fields.get('title'):
            raise ValueError(f'BibLaTeX 条目缺少 title: {key}')
        parts = []
        for name in ('author', 'editor', 'title', 'subtitle', 'journaltitle', 'booktitle',
                     'series', 'volume', 'number', 'publisher', 'location', 'date', 'year', 'pages', 'note'):
            value = text(fields.get(name, ''))
            if value:
                parts.append(r'\emph{' + value + '}' if name in {'journaltitle', 'booktitle'} else value)
        for name in ('doi', 'url', 'eprint'):
            value = fields.get(name, '')
            if value:
                url = ('https://doi.org/' + value if name == 'doi' else
                       'https://arxiv.org/abs/' + value if name == 'eprint' and fields.get('eprinttype') == 'arxiv' else
                       value if name == 'url' else '')
                parts.append(r'\url{' + url + '}' if url else 'eprint: ' + text(value))
        label = fields.get('labelnumber') or fields.get('labelalpha', '')
        extra = fields.get('extraalpha', '')
        if not fields.get('labelnumber') and label and extra.isdigit() and 1 <= int(extra) <= 26:
            label += chr(96 + int(extra))
        # Braces keep TeX math/brackets in an explicit label balanced.
        optional = '[{' + text(label) + '}]' if label else ''
        return r'\bibitem' + optional + '{' + key + '}' + '. '.join(parts) + '.'

    entries, key, fields, offset = [], None, {}, 0
    while match := command.search(source, offset):
        name, offset = match[1], match.end()
        if name == 'verb':
            field, offset = braced(source, offset)
            end = source.find(r'\endverb', offset)
            if end < 0:
                raise ValueError('BibLaTeX verb 字段未闭合')
            if key is not None:
                fields[field] = re.sub(r'^\\verb\s+', '', source[offset:end].strip())
            offset = end + len(r'\endverb')
            continue
        args = []
        for _ in range(arities.get(name, 0)):
            value, offset = braced(source, offset)
            args.append(value)
        if name == 'entry':
            if key is not None:
                raise ValueError('BibLaTeX entry 未闭合')
            key, fields = args[0], {}
        elif name == 'endentry' and key is not None:
            entries.append(entry(key, fields))
            key = None
        elif key is not None:
            if name in {'field', 'strng'}:
                fields[args[0]] = args[1]
            elif name == 'name' and args[0] in {'author', 'editor'}:
                fields[args[0]] = names(args[3])
            elif name == 'list':
                fields[args[0]] = ', '.join(groups(args[2]))
    if key is not None:
        raise ValueError('BibLaTeX entry 未闭合')
    return r'\begin{thebibliography}{999}' + '\n' + '\n'.join(entries) + '\n' + r'\end{thebibliography}'


def naming_definitions(preamble):
    """Read complete literal declarations even on shared or multiple lines."""
    source = preamble
    result, end = [], 0
    pattern = r'(?<!\\)\\(newtheorem|newcommand|renewcommand|providecommand|DeclareMathOperator|numberwithin|setcounter|addtocounter)\*?\s*'
    for match in re.finditer(pattern, source):
        if match.start() < end:
            continue
        cursor = match.end()
        try:
            if source[cursor:cursor + 1] == '{':
                _, cursor = braced(source, cursor)
            else:
                macro = re.match(r'\\[A-Za-z]+\s*', source[cursor:])
                if not macro:
                    continue
                cursor += macro.end()
            # Macro argument counts/defaults or a theorem's shared counter.
            while optional := re.match(r'\s*\[[^\]]*\]', source[cursor:]):
                cursor += optional.end()
            _, cursor = braced(source, cursor)
            if match[1] == 'newtheorem':
                parent = re.match(r'\s*\[[^\]]*\]', source[cursor:])
                if parent:
                    cursor += parent.end()
            definition = source[match.start():cursor]
            if not re.search(r'\\(?:bpnode|node|bpdesc|uses|qprint\w*)\b', definition):
                result.append(definition)
            end = cursor
        except ValueError:
            continue
    return result


def compact_label_source(source, preamble):
    """Keep counter-bearing structure for the bounded whole-paper label pass."""
    theorem_names = set(re.findall(r'\\newtheorem\*?\s*\{([^}]+)\}', preamble))
    environments = theorem_names | {'figure', 'figure*', 'table', 'table*', 'abstract', 'enumerate', 'itemize', 'equation', 'equation*', 'align', 'align*', 'gather', 'gather*', 'proof'}
    result, stack, end = [], [], 0
    for match in re.finditer(r'\\([A-Za-z]+\*?|\\)', source):
        if match.start() < end:
            continue
        name = match[1]
        if name in {'begin', 'end', 'section', 'section*', 'subsection', 'subsection*', 'subsubsection', 'subsubsection*', 'chapter', 'chapter*', 'caption', 'label', 'qprintnameprobe', 'setcounter', 'addtocounter', 'numberwithin', 'stepcounter', 'refstepcounter'}:
            try:
                start = match.end()
                optional = re.match(r'\s*\[[^\]]*\]', source[start:])
                if optional:
                    start += optional.end()
                value, end = braced(source, start)
            except ValueError:
                continue
            if name in {'begin', 'end'}:
                if name == 'begin':
                    stack.append(value)
                elif stack and stack[-1] == value:
                    stack.pop()
                if value not in environments:
                    continue
            elif name not in {'label', 'qprintnameprobe', 'setcounter', 'addtocounter', 'numberwithin', 'stepcounter', 'refstepcounter'}:
                value = 'Title'
            result.append('\\' + name + '{' + value + '}')
            if name == 'begin' and value in {'equation', 'equation*', 'align', 'align*', 'gather', 'gather*'}:
                result.append(' x ')
            if name in {'setcounter', 'addtocounter', 'numberwithin'}:
                value, end = braced(source, end)
                result.append('{' + value + '}')
        elif name in {'item', 'appendix', 'nonumber', 'notag'}:
            result.append('\\' + name + ' ')
        elif name == '\\' and stack and stack[-1] in {'align', 'align*', 'gather', 'gather*'}:
            result.append(r'\\ ')
    return '\n'.join(result)
