"""Static reference scopes over TeX files already loaded by the workspace."""
import posixpath
from pathlib import PurePosixPath

from .tex import tex_commands


class TexReferenceScope:
    def __init__(self, documents):
        self.children = {path: set() for path in documents}
        self.parents = {path: set() for path in documents}
        self.labels = {}
        self.cache = {}
        for path, doc in documents.items():
            label_end = min([doc.body_end, *doc.bibliography_offsets])
            try:
                for command in tex_commands(doc.source[:doc.body_end], {'input', 'include', 'label'}):
                    if command['name'] == 'label':
                        if len(doc.preamble) <= command['start'] < label_end:
                            self.labels.setdefault(command['value'], set()).add(path)
                        continue
                    value = command['value']
                    # Never read or execute includes; only match loaded TeX paths.
                    if not value or any(c in value for c in '\\{}:#') or value.startswith('/'):
                        continue
                    if not value.endswith('.tex'):
                        value += '.tex'
                    folder = PurePosixPath(path).parent
                    # Chapter-local paths first, then enclosing document folders.
                    for base in (folder, *folder.parents):
                        target = posixpath.normpath(str(base / value))
                        if target in documents:
                            self.children[path].add(target)
                            self.parents[target].add(path)
                            break
            except ValueError:
                # Retain earlier literal declarations from a malformed file.
                continue

    @staticmethod
    def reachable(start, edges):
        seen, pending = set(), [start]
        while pending:
            path = pending.pop()
            if path not in seen:
                seen.add(path)
                pending.extend(edges[path] - seen)
        return seen

    def files(self, path):
        if path not in self.cache:
            ancestors = self.reachable(path, self.parents)
            roots = {p for p in ancestors if not self.parents[p]}
            # Rootless include cycles remain bounded. Shared files do not join
            # independent books: retain only files common to all possible roots.
            scopes = [self.reachable(root, self.children) for root in (roots or ancestors)]
            self.cache[path] = set.intersection(*scopes)
        return self.cache[path]

    def candidates(self, label, path):
        return self.labels.get(label, set()) & self.files(path)
