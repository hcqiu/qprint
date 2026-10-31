from qprint.workspace import Workspace
from qprint.tex import render_tex
import pytest
import yaml
from urllib.parse import quote


def test_reader_links_use_names_preserve_aliases_and_ignore_code(tmp_path):
    folder = tmp_path / 'blueprint/Paper'
    folder.mkdir(parents=True)
    (folder / 'nodes.md').write_text('# Lemma_a_b <1>\nResult.\n', encoding='utf-8')
    (folder / 'empty.md').write_text('<!-- no nodes -->', encoding='utf-8')
    (folder / 'index.md').write_text(
        '# index\n\n### [[Paper/nodes.md|Results]]\n\n'
        '- [[Paper/nodes#Lemma_a_b <1>]]\n'
        '- [[Paper/nodes#Lemma_a_b <1>|A custom name]]\n'
        '- [[Paper/empty.md|Empty]]\n\n'
        '`[[Paper/nodes#Lemma_a_b <1>]]`\n', encoding='utf-8')
    workspace = Workspace(tmp_path)
    assert not workspace.diagnostics
    detail = workspace.detail('Paper/index#index')
    assert detail['is_index']
    assert '>↗ Lemma_a_b &lt;1&gt;</a>' in detail['body_html']
    assert '>↗ A custom name</a>' in detail['body_html']
    assert 'data-milestone="Paper/empty.md"' in detail['body_html']
    assert '<code>[[Paper/nodes#Lemma_a_b &lt;1&gt;]]</code>' in detail['body_html']
    assert workspace.project()['nodes'][0]['title'] == 'index'


def test_tex_explicit_uses_hide_project_and_filename():
    target = 'Topic/Paper/index#index'
    html, warnings = render_tex(r'\uses{' + target + '}', references={target: target})
    assert not warnings
    assert '>↗ index</a>' in html
    assert '>↗ Topic/' not in html


@pytest.mark.parametrize('target_project,prefix,back_prefix', [
    ('Topology/A', '', ''),
    ('Topology/B', 'B/', 'A/'),
    ('Geometry/B', 'Geometry/B/', 'Topology/A/'),
    ('Research/Topology/A', 'Research/Topology/A/', 'Topology/A/'),
])
def test_links_qualify_only_other_projects(tmp_path, target_project, prefix, back_prefix):
    current_project = 'Topology/A'
    for project in {current_project, target_project}:
        folder = tmp_path / 'blueprint' / project
        folder.mkdir(parents=True)
        (folder / 'index.md').write_text('# index\n', encoding='utf-8')
    target_path = target_project + '/sections/result.md'
    target = target_path.removesuffix('.md') + '#Result'
    result_file = tmp_path / 'blueprint' / target_path
    result_file.parent.mkdir()
    result_file.write_text('# Result\nText.\n', encoding='utf-8')
    metadata = yaml.safe_dump({'tex': 'a.tex#current', 'uses': [f'[[{target}]]']})
    (tmp_path / 'blueprint/Topology/A/main.md').write_text(
        '# Current\n\n```qprint\n' + metadata + '```\n\n'
        f'[[{target}]] [[{target}|Alias]] [[{target_project}/index.md]]', encoding='utf-8')
    (tmp_path / 'tex').mkdir()
    (tmp_path / 'tex/a.tex').write_text(
        r'\bpnode{current}\uses{' + target + r'}\uses{Result}', encoding='utf-8')
    workspace = Workspace(tmp_path)
    assert not workspace.diagnostics
    detail = workspace.detail('Topology/A/main#Current')
    assert f'>↗ {prefix}Result</a>' in detail['body_html']
    assert f'>↗ {prefix}Alias</a>' in detail['body_html']
    assert f'>↗ {prefix}index</a>' in detail['body_html']
    assert not detail['tex_content']['warnings']
    assert detail['tex_content']['html'].count(f'>↗ {prefix}Result</a>') == 2
    assert f'href="#node={quote(target, safe="")}"' in detail['tex_content']['html']
    assert detail['relations'][0]['label'] == prefix + 'Result'
    assert detail['relations'][0]['title'] == 'Result'
    assert workspace.detail(target)['backlinks'][0]['label'] == back_prefix + 'Current'
