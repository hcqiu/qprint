"""Prebuilt, level-zero reading context; no Navigator queries or rendering."""
from .blueprint import resolve_link, resolve_tex_use


MAX_DEPENDENCIES = 20
MAX_SUMMARY_CHARS = 600
MAX_DEPENDENCY_CHARS = 8000


def build_contexts(nodes, locations, tex):
    """Build once per workspace snapshot, preserving the complete node TeX."""
    sources, annotations, summaries = {}, {}, {}
    for node in nodes.values():
        source, metadata = None, {"descriptions": [], "uses": []}
        if node.id in locations:
            path, label = locations[node.id]
            source = tex[path].fragment(label)
            try:
                metadata = tex[path].annotations(label)
            except ValueError:
                pass  # Malformed annotations must not prevent ordinary copying.
        sources[node.id] = source
        annotations[node.id] = metadata
        description = "\n".join(metadata["descriptions"]) or node.body
        summaries[node.id] = (description[:MAX_SUMMARY_CHARS - 1] + "…"
                              if len(description) > MAX_SUMMARY_CHARS else description)

    bundles = {}
    for node in nodes.values():
        targets, unresolved = [], []
        refs = [(ref, resolve_link(ref, node.id, nodes)) for ref in node.uses]
        refs.extend((ref, resolve_tex_use(ref, node, nodes))
                    for ref in annotations[node.id]["uses"])
        for ref, target in refs:
            if target is None:
                if ref not in unresolved:
                    unresolved.append(ref)
            elif target != node.id and target not in targets:
                targets.append(target)
        dependencies, used = [], 0
        for target in targets:
            dependency = nodes[target]
            entry = {"node": target, "title": dependency.title, "description": summaries[target]}
            size = sum(len(value) for value in entry.values())
            if len(dependencies) >= MAX_DEPENDENCIES or used + size > MAX_DEPENDENCY_CHARS:
                break
            dependencies.append(entry)
            used += size
        location = locations.get(node.id)
        bundles[node.id] = {
            "version": 1, "level": 0, "node": node.id, "title": node.title,
            "tex": sources[node.id],
            "source": "tex/" + location[0] if location else "blueprint/" + node.path,
            "description": summaries[node.id],
            "dependencies": dependencies,
            "dependencies_omitted": len(targets) - len(dependencies),
            "unresolved_dependencies": unresolved[:MAX_DEPENDENCIES],
            "unresolved_omitted": max(0, len(unresolved) - MAX_DEPENDENCIES),
        }
    return bundles
