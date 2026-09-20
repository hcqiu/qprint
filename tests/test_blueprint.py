from qprint.blueprint import parse_markdown, resolve_link


def test_multiple_nodes_frontmatter_fences_and_subheadings():
    text = '''---
title: Library
---
# First
```qprint
kind: theorem
status: complete
uses: ["[[#Second]]"]
lean: Module.first
```
A description.
## A subsection
```lean
# not a heading
```
# Second
Second node.
'''
    nodes, errors = parse_markdown("Algebra/Test.md", text)
    assert not errors
    assert [n.title for n in nodes] == ["First", "Second"]
    assert nodes[0].kind == "theorem"
    assert "## A subsection" in nodes[0].body
    assert nodes[0].bindings[0]["declaration"] == "Module.first"
    assert resolve_link(nodes[0].uses[0], nodes[0].id, {n.id: n for n in nodes}) == nodes[1].id


def test_duplicate_and_malformed_metadata_are_reported_without_losing_valid_nodes():
    nodes, errors = parse_markdown("A.md", '# Good\nText\n# Good\nDuplicate\n# Bad\n```qprint\nuses: [42]\n```\n# Last\nOK')
    assert [n.title for n in nodes] == ["Good", "Last"]
    assert len(errors) == 2


def test_basename_ambiguity_and_alias():
    a, _ = parse_markdown("A/Foo.md", "# X\nA")
    b, _ = parse_markdown("B/Foo.md", "# X\nB")
    nodes = {n.id: n for n in a + b}
    assert resolve_link("[[Foo#X]]", a[0].id, nodes) is None
    assert resolve_link("[[A/Foo.md#X|Display name]]", b[0].id, nodes) == a[0].id


def test_invalid_status_yaml_lines_and_unsafe_url():
    for metadata in ['status: done', 'kind: [theorem]', 'lean: {declaration: test, lines: [0, 2]}', 'coq: {declaration: test, url: "javascript:alert(1)"}', 'uses: [[oops]]', 'status: [']:
        nodes, errors = parse_markdown("A.md", f"# X\n```qprint\n{metadata}\n```\n")
        assert not nodes and errors
