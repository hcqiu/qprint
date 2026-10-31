"""Link imported arXiv papers using explicit citation locators, without guessing."""
from collections import defaultdict
from html import escape
import json
import os
from pathlib import Path
import re
from threading import RLock
import uuid

import yaml

from .bibliography import reference_arxiv_id
from .blueprint import parse_markdown
from .graph_index import project_index_content
from .paths import WorkspaceError, read_text, safe_path
from .tex import mask_comments, render_tex, tex_commands
from .tex_support import braced
from .tex_scope import TexReferenceScope
from .tex_to_blueprint import _environment_names
from .workspace import Workspace


_LOCK = RLock()
_TYPES = {
    'theorem': ('theorem', 'thm', 'th'),
    'proposition': ('proposition', 'prop', 'prp'),
    'lemma': ('lemma', 'lem'),
    'definition': ('definition', 'defn', 'def'),
    'corollary': ('corollary', 'cor'),
    'remark': ('remark', 'rem', 'rmk'),
    'example': ('example', 'ex', 'exmp'),
    'conjecture': ('conjecture', 'conj'),
}
_ALIASES = {alias: kind for kind, aliases in _TYPES.items() for alias in aliases}
_TYPE = r'(?P<kind>' + '|'.join(sorted(_ALIASES, key=len, reverse=True)) + r')s?\.?'
_NUMBER = r'(?:\d+(?:\.\d+)*[a-z]?|[A-Z](?:\.\d+)*|[IVXLCDM]+)'
_LOCATOR = re.compile(r'\b' + _TYPE + r'(?:\s+|(?<=\.))(?P<numbers>' + _NUMBER +
                      r'(?:\s*(?:,|and|&)\s*' + _NUMBER + r')*)(?![\w.]\w)', re.I)
_CITE = re.compile(r'(?<!\\)\\(?:citealp|citealt|citep|citet|cite|parencite|textcite|autocite)\*?(?![A-Za-z])', re.I)


def arxiv_identity(value):
    from .importers import arxiv_id
    return re.sub(r'v[1-9]\d*$', '', arxiv_id(value)).lower()


def _plain(value):
    value = re.sub(r'\\(?:textbf|textit|emph|textrm|textnormal|textup|textsc)\s*', '', value)
    return re.sub(r'\s+', ' ', value.replace('~', ' ').replace('{', '').replace('}', '')).strip()


def citation_locators(before, options, after):
    """Only accept a locator touching the cite, or inside its optional argument."""
    found, suspicious = [], False
    for value, side in [(before, 'before'), *[(o, 'option') for o in options], (after, 'after')]:
        value = _plain(value)
        for match in _LOCATOR.finditer(value):
            left, right = value[:match.start()], value[match.end():]
            if side == 'before' and not re.fullmatch(r'\s*(?:(?:of|in|from)\s*)?[\[(]*', right, re.I):
                continue
            if side == 'after' and not re.fullmatch(r'[\s,;:\[\]()]*', left):
                continue
            # Ranges must not silently turn into just the first numbered result.
            if re.match(r'\s*(?:[-–—]|to\b)', right):
                suspicious = True
                continue
            kind = _ALIASES[match['kind'].lower()]
            found.extend((kind, n.lower()) for n in re.split(r'\s*(?:,|and|&)\s*', match['numbers'], flags=re.I))
        # A named result without a supported number is not a bare paper citation.
        if not found and re.search(r'\b(?:' + '|'.join(_ALIASES) + r')s?\.?\s+[\w(]', value, re.I):
            if side == 'option' or side == 'after' and re.match(r'^[\s,;:\[\]()]*(?:' + '|'.join(_ALIASES) + r')\b', value, re.I):
                suspicious = True
        if not found and side == 'before' and re.search(
                r'\b(?:' + '|'.join(_ALIASES) + r')s?[.\s]+\S+(?:\s+(?:in|of|from))?\s*[\[(]*$', value, re.I):
            suspicious = True
    return list(dict.fromkeys(found)), suspicious


def citations(doc):
    source = mask_comments(doc.source)
    start, stop = len(doc.preamble), min([doc.body_end, *doc.bibliography_offsets])
    end = start
    for match in _CITE.finditer(source, start, stop):
        if match.start() < end:
            continue
        cursor, options = match.end(), []
        while True:
            while cursor < stop and source[cursor].isspace():
                cursor += 1
            if cursor >= stop or source[cursor] != '[':
                break
            opening, depth, braces = cursor, 1, 0
            cursor += 1
            while cursor < stop and depth:
                if source[cursor] == '\\':
                    cursor += 2
                    continue
                braces += (source[cursor] == '{') - (source[cursor] == '}')
                if not braces:
                    depth += (source[cursor] == '[') - (source[cursor] == ']')
                cursor += 1
            if depth:
                raise ValueError('cite 可选参数未闭合')
            options.append(source[opening + 1:cursor - 1])
        keys, end = braced(source, cursor)
        if end > stop:
            raise ValueError('cite 超出正文边界')
        tail, existing = end, []
        while use := re.match(r'\s*\\uses\s*(?=\{)', source[tail:]):
            value, tail = braced(source, tail + use.end())
            existing.extend(v.strip() for v in value.split(',') if v.strip())
        before = source[max(start, match.start() - 180):match.start()]
        after = source[tail:min(stop, tail + 180)]
        # Never borrow a locator from the following citation's optional argument.
        next_cite = _CITE.search(after)
        if next_cite:
            after = after[:next_cite.start()]
        locators, uncertain = citation_locators(before, options, after)
        yield {'start': match.start(), 'end': end, 'keys': [k.strip() for k in keys.split(',')],
               'locators': locators, 'uncertain': uncertain, 'existing': existing}


def _bib_identifiers(source):
    """Read ordinary literal BibTeX fields, including eprint in .bib-only sources."""
    source = mask_comments(source)
    offset = 0
    for match in re.finditer(r'@([A-Za-z]+)\s*(?=\{)', source):
        if match.start() < offset:
            continue
        body, offset = braced(source, match.end())
        if match[1].lower() in {'comment', 'preamble', 'string'} or ',' not in body:
            continue
        key, fields_text = body.split(',', 1)
        fields, cursor = {}, 0
        while field := re.search(r'([A-Za-z][\w-]*)\s*=\s*', fields_text[cursor:]):
            cursor += field.end()
            if fields_text[cursor:cursor + 1] == '{':
                value, cursor = braced(fields_text, cursor)
            elif fields_text[cursor:cursor + 1] == '"':
                quoted = re.match(r'"((?:\\.|[^"\\])*)"', fields_text[cursor:], re.S)
                if not quoted:
                    break
                value, cursor = quoted[1], cursor + quoted.end()
            else:
                literal = re.match(r'[^,]*', fields_text[cursor:])
                value, cursor = literal[0], cursor + literal.end()
            fields[field[1].lower()] = value
        values = ' '.join(fields.get(k, '') for k in ('url', 'doi', 'journal', 'note', 'howpublished'))
        values = values.replace('10.48550/arXiv.', 'https://doi.org/10.48550/arXiv.')
        if fields.get('archiveprefix', fields.get('eprinttype', '')).strip().lower() == 'arxiv':
            values += ' arXiv:' + fields.get('eprint', '')
        identifier = reference_arxiv_id(escape(values))
        if identifier:
            yield key.strip(), arxiv_identity(identifier)


def _owner(workspace, path, position):
    doc = workspace.tex[path]
    anchors = [a for a in doc.anchors if a['content_start'] <= position]
    if not anchors:
        return None
    anchor = anchors[-1]
    if any(anchor['content_start'] <= s['offset'] <= position for s in doc.sections):
        return None
    owners = [node_id for node_id, binding in workspace.locations.items() if binding == (path, anchor['label'])]
    return owners[0] if len(owners) == 1 else None


def _numbered_nodes(workspace, project, diagnostics):
    sources = {p: d.source for p, d in workspace.tex.items() if p.startswith(project + '/')}
    aliases = dict(re.findall(r'\\newtheorem\*?\s*\{([^{}]+)\}(?:\s*\[[^]]*\])?\s*\{([^{}]+)\}',
                              mask_comments('\n'.join(sources.values()))))
    candidates = {}
    for path, source in sources.items():
        doc = workspace.tex[path]
        stop = min([doc.body_end, *doc.bibliography_offsets])
        candidates[path] = []
        for cmd in tex_commands(source[:stop], {'begin'}):
            title = aliases.get(cmd['value'], cmd['value'])
            if _plain(title).lower().rstrip('.') in _ALIASES and _owner(workspace, path, cmd['start']):
                candidates[path].append({'start': cmd['start'], 'begin_end': cmd['end']})
    names, warnings = _environment_names(sources, candidates)
    diagnostics.extend({'project': project, 'reason': warning} for warning in warnings)
    result = defaultdict(set)
    numbered_owners = set()
    for (path, offset), name in names.items():
        match = _LOCATOR.fullmatch(_plain(name))
        if match:
            owner = _owner(workspace, path, offset)
            numbered_owners.add(owner)
            result[(_ALIASES[match['kind'].lower()], match['numbers'].lower())].add(owner)
    # Hand-reviewed Blueprint nodes can have an explicit numbered title without
    # a theorem environment. A successfully computed TeX number takes priority.
    for node in workspace.nodes.values():
        if node.path.startswith(project + '/') and node.id not in numbered_owners:
            match = _LOCATOR.fullmatch(_plain(node.title))
            if match:
                result[(_ALIASES[match['kind'].lower()], match['numbers'].lower())].add(node.id)
    return result


def _merge_uses(text, path, additions):
    nodes, errors = parse_markdown(path, text)
    if any(d['severity'] == 'error' for d in errors):
        raise WorkspaceError(f'Blueprint 无法解析: {path}')
    lines = text.splitlines(keepends=True)
    for node in reversed(nodes):
        targets = sorted(additions.get(node.id, set()) - set(node.uses))
        if not targets:
            continue
        start = node.line
        while start < len(lines) and not lines[start].strip():
            start += 1
        if start < len(lines) and lines[start].strip() == '```qprint':
            end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == '```')
            metadata = yaml.safe_load(''.join(lines[start + 1:end])) or {}
            metadata['uses'] = [*node.uses, *targets]
            lines[start + 1:end] = [yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)]
        else:
            lines[node.line:node.line] = ['\n```qprint\n', yaml.safe_dump({'uses': targets}, allow_unicode=True), '```\n\n']
    return ''.join(lines)


def link_workspace(root: Path, *, imported: str | None = None, dry_run: bool = False):
    """Plan and atomically apply individual files, keeping backups and a report.

    With imported set, only pairs involving that arXiv paper are considered.
    Existing uses are preserved; missing/ambiguous numbered nodes are diagnosed.
    """
    with _LOCK:
        return _link_workspace(root, imported=imported, dry_run=dry_run)


def _link_workspace(root, *, imported, dry_run):
    root = Path(root).resolve()
    if not root.is_dir():
        raise WorkspaceError('工作区不存在')
    selected = arxiv_identity(imported) if imported else None
    workspace = Workspace(root)
    report = {'status': 'dry_run' if dry_run else 'completed', 'imported': selected,
              'links_added': 0, 'citations_changed': 0, 'files': [], 'matches': [], 'diagnostics': []}
    diagnostics, projects = report['diagnostics'], {}
    for path in sorted((root / 'tex').rglob('.qprint-source.json')):
        relative = path.relative_to(root).as_posix()
        try:
            data = json.loads(read_text(safe_path(root, relative)))
            if data.get('type') == 'arxiv':
                projects[path.parent.relative_to(root / 'tex').as_posix()] = arxiv_identity(data['id'])
        except (ValueError, KeyError, OSError) as exc:
            diagnostics.append({'path': relative, 'reason': str(exc)})
    by_id = defaultdict(list)
    for project, identifier in projects.items():
        by_id[identifier].append(project)
    changes, md_additions, number_cache, bib_cache, index_cache = {}, defaultdict(set), {}, {}, {}
    changed_tex = set()

    def stage(relative, text):
        path = safe_path(root, relative)
        original = path.read_bytes() if path.exists() else None
        previous = original.decode('utf-8-sig').replace('\r\n', '\n') if original is not None else ''
        expected = workspace.documents.get(relative.removeprefix('blueprint/')) if relative.startswith('blueprint/') else (
            workspace.tex[relative.removeprefix('tex/')].source if relative.removeprefix('tex/') in workspace.tex else previous)
        if expected is not None and previous != expected:
            raise WorkspaceError(f'文件在分析期间已修改: {relative}')
        if text == previous:
            return
        newline = '\r\n' if original and b'\r\n' in original else '\n'
        content = text.replace('\n', newline).encode('utf-8')
        if original and original.startswith(b'\xef\xbb\xbf'):
            content = b'\xef\xbb\xbf' + content
        changes[relative] = (original, content)

    def index_node(project):
        if project in index_cache:
            return index_cache[project]
        path = project + '/index.md'
        text = workspace.documents.get(path, '')
        nodes, errors = parse_markdown(path, text)
        if errors:
            raise WorkspaceError(f'文献索引无法解析: {path}')
        target = path.removesuffix('.md') + '#index'
        if not any(node.id == target for node in nodes):
            front = re.match(r'\A---\s*\n.*?\n---\s*\n', text, re.S)
            offset = front.end() if front else 0
            files = {file['path']: [workspace.nodes[key] for key in file['node_ids']]
                     for file in workspace.graph_index['files']
                     if file['project_id'] == project and file['path'] != path}
            text = text[:offset] + '\n' + project_index_content(files) + '\n\n' + text[offset:]
            stage('blueprint/' + path, text)
        index_cache[project] = target
        return target

    def references(project, path):
        if project not in bib_cache:
            ids = defaultdict(set)
            folder = safe_path(root, 'tex' if project == '.' else 'tex/' + project)

            def owned_files(pattern):
                files = folder.rglob(pattern) if project in projects else folder.glob(pattern)
                return sorted(p for p in files if not any(
                    other != project and p.relative_to(root / 'tex').as_posix().startswith(other + '/')
                    for other in projects))

            for bib in owned_files('*.bib'):
                try:
                    for key, identifier in _bib_identifiers(read_text(safe_path(root, bib.relative_to(root).as_posix()))):
                        ids[key].add(identifier)
                except (ValueError, OSError) as exc:
                    diagnostics.append({'path': bib.relative_to(root).as_posix(), 'reason': str(exc)})
            for bbl in owned_files('*.bbl'):
                parsed, warnings = render_tex(read_text(safe_path(root, bbl.relative_to(root).as_posix())), bibliography_only=True)
                if isinstance(parsed, dict):
                    for entry in parsed['entries']:
                        identifier = reference_arxiv_id(entry['html'])
                        if identifier:
                            ids[entry['key']].add(arxiv_identity(identifier))
                else:
                    diagnostics.append({'path': bbl.relative_to(root).as_posix(), 'reason': '; '.join(warnings)})
            bib_cache[project] = ids
        ids = {key: set(values) for key, values in bib_cache[project].items()}
        data = workspace.bibliography(path)
        for entry in data['entries']:
            if entry.get('arxiv_id'):
                ids.setdefault(entry['key'], set()).add(arxiv_identity(entry['arxiv_id']))
        return ids

    for path, doc in workspace.tex.items():
        owners = [p for p in projects if path.startswith(p + '/')]
        hint = workspace.bibliography_project(path)
        project = max(owners, key=len) if owners else hint if hint != '.' and path.startswith(hint + '/') else Path(path).parent.as_posix()
        try:
            calls = list(citations(doc))
        except ValueError as exc:
            diagnostics.append({'path': path, 'reason': str(exc)})
            continue
        if not calls:
            continue
        refs = references(project, path)
        edits = []
        for call in calls:
            targets = []
            for key in call['keys']:
                identities = refs.get(key, set())
                if not identities:
                    continue
                if len(identities) != 1:
                    diagnostics.append({'path': path, 'cite': key, 'reason': '同一引用键对应多个 arXiv 编号'})
                    continue
                identifier = next(iter(identities))
                if selected and selected not in {projects.get(project), identifier}:
                    continue
                candidates = [p for p in by_id[identifier] if p != project]
                if not candidates:
                    continue
                context = {'path': path, 'line': doc.source.count('\n', 0, call['start']) + 1, 'cite': key}
                if len(candidates) != 1:
                    diagnostics.append({**context, 'reason': '工作区内有多个相同 arXiv 项目'})
                    continue
                target_project = candidates[0]
                if call['uncertain'] or call['locators'] and len(call['keys']) > 1:
                    diagnostics.append({**context, 'reason': '文献定位语义不明确，已链接到 index'})
                    matches = [index_node(target_project)]
                elif not call['locators']:
                    matches = [index_node(target_project)]
                else:
                    if target_project not in number_cache:
                        number_cache[target_project] = _numbered_nodes(workspace, target_project, diagnostics)
                    choices = [number_cache[target_project].get(locator, set()) for locator in call['locators']]
                    if any(len(choice) != 1 for choice in choices):
                        diagnostics.append({**context, 'locators': call['locators'], 'reason': '编号节点不存在或不唯一，已链接到 index'})
                    matches = list(dict.fromkeys(next(iter(choice)) if len(choice) == 1 else index_node(target_project)
                                                 for choice in choices))
                if any(re.search(r'[{},%\\\r\n]', target) for target in matches):
                    diagnostics.append({**context, 'reason': '节点 ID 不能安全写入 uses'})
                    continue
                targets.extend(matches)
                report['matches'].append({**context, 'target_project': target_project, 'targets': matches})
            owner = _owner(workspace, path, call['start'])
            existing = set(call['existing'])
            if owner:
                existing.update(workspace.lookup.tex_use(value, workspace.nodes[owner]) for value in call['existing'])
                declared = {workspace.lookup.link(value, owner) for value in workspace.nodes[owner].uses}
                md_additions[owner].update('[[' + target + ']]' for target in targets if target not in declared)
            elif targets:
                diagnostics.append({'path': path, 'line': doc.source.count('\n', 0, call['start']) + 1,
                                    'reason': '引用尚未绑定 Blueprint 节点；仅添加 TeX uses，未新增节点依赖'})
            added = list(dict.fromkeys(target for target in targets if target not in existing))
            if added:
                edits.append((call['end'], ''.join(r'\uses{' + target + '}' for target in added)))
                report['links_added'] += len(added)
                report['citations_changed'] += 1
        if edits:
            source = doc.source
            for offset, insertion in reversed(edits):
                source = source[:offset] + insertion + source[offset:]
            stage('tex/' + path, source)
            changed_tex.add(path)
    if changed_tex:
        scope = workspace.tex_reference_scope or TexReferenceScope(workspace.tex)
        for path in set.union(*(scope.files(path) for path in changed_tex)):
            relative = 'tex/' + path
            source = changes[relative][1].decode('utf-8-sig').replace('\r\n', '\n') if relative in changes else workspace.tex[path].source
            begin = re.search(r'\\begin\{document\}', mask_comments(source))
            if begin and not re.search(r'\\(?:providecommand|newcommand|renewcommand)\*?\s*\{?\\uses\b', mask_comments(source[:begin.start()])):
                stage(relative, source[:begin.start()] + '\\providecommand{\\uses}[1]{}\n' + source[begin.start():])
    for path in {workspace.nodes[node_id].path for node_id in md_additions}:
        stage('blueprint/' + path, _merge_uses(workspace.documents[path], path, md_additions))
    report['files'] = sorted(changes)
    if not dry_run and (changes or diagnostics):
        _publish(root, changes, report)
    return report


def _publish(root, changes, report):
    folder = safe_path(root, '.qprint/cross-links/' + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    report['report_path'] = (folder / 'report.json').relative_to(root).as_posix()
    for relative, (original, _) in changes.items():
        path = safe_path(root, relative)
        if (path.read_bytes() if path.exists() else None) != original:
            raise WorkspaceError(f'文件在分析期间已修改: {relative}')
        if original is not None:
            backup = folder / 'before' / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(original)
    written = []
    try:
        for relative, (original, content) in changes.items():
            path = safe_path(root, relative)
            if (path.read_bytes() if path.exists() else None) != original:
                raise WorkspaceError(f'文件在发布期间已修改: {relative}')
            path.parent.mkdir(parents=True, exist_ok=True)
            staged = folder / 'next'
            staged.write_bytes(content)
            os.replace(staged, path)
            written.append(relative)
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        for relative in reversed(written):
            original, content = changes[relative]
            path = safe_path(root, relative)
            if path.read_bytes() == content:
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)
        raise
