"""Indexed reference resolution for one immutable Workspace snapshot."""
from collections import defaultdict


def _binding(node):
    if not node.tex:
        return None, None
    path, anchor = node.tex.rsplit("#", 1) if "#" in node.tex else (node.path.removesuffix(".md"), node.tex)
    return path.removesuffix(".tex"), anchor


class NodeLookup:
    """Preserve blueprint.resolve_* precedence without scanning all nodes per link.

    Rebuild after changing nodes, bindings or dependencies; caches are never shared
    across workspaces or reloads.
    """

    def __init__(self, nodes):
        self.nodes = nodes
        self.basenames = defaultdict(list)
        self.aliases = defaultdict(list)
        self.papers = {}
        self.declared = {}
        for node in nodes.values():
            self.basenames[node.id.rsplit("/", 1)[-1]].append(node.id)
            paper, anchor = _binding(node)
            self.papers[node.id] = paper
            self.aliases[node.title].append(node.id)
            if anchor is not None and anchor != node.title:
                self.aliases[anchor].append(node.id)

    def link(self, link, current):
        target = link.removeprefix("[[").removesuffix("]]").split("|", 1)[0]
        if "#" not in target:
            return None
        path, title = target.split("#", 1)
        path = path.removesuffix(".md") or current.split("#", 1)[0]
        exact = f"{path}#{title}"
        if exact in self.nodes:
            return exact
        if "/" not in path:
            matches = self.basenames.get(exact, ())
            if len(matches) == 1:
                return matches[0]
        return None

    def tex_use(self, label, current):
        if "#" in label:
            return self.link(label, current.id)
        matches = self.aliases.get(label, ())
        paper = self.papers[current.id]
        local = [key for key in matches if paper is not None and self.papers[key] == paper]
        if current.id not in self.declared:
            self.declared[current.id] = {self.link(link, current.id) for link in current.uses}
        candidates = local or [key for key in matches if key in self.declared[current.id]] or matches
        return candidates[0] if len(candidates) == 1 else None
