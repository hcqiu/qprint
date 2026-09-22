import json
from pathlib import Path
import time

import pytest

from qprint.formal_git import package_name
from qprint.formal_legacy_lake import needs_native_git, prepare_native_git, prepare_native_tag, git_command
from qprint.formal_environment import FormalExecutionContext
from qprint.formal_runner import Check


@pytest.mark.parametrize('name,expected', [('«doc-gen4»','doc-gen4'), ('mathlib','mathlib'), ('../x',None), ('«../x»',None), ('«»',None)])
def test_legacy_escaped_package_names_preserve_path_validation(name, expected):
    if expected is None:
        with pytest.raises(ValueError):
            package_name(name)
    else:
        assert package_name(name) == expected


@pytest.mark.parametrize('supported', [True, False])
def test_native_git_uses_actual_lake_capability(tmp_path, supported):
    source = tmp_path / 'src/lean/lake/Lake/Load/Config.lean'
    source.parent.mkdir(parents=True)
    source.write_text('packageOverrides : Array PackageEntry' if supported else 'old config')
    context = FormalExecutionContext('lean','4.7.0-rc2',tmp_path/'bin/lean.exe',tmp_path/'bin/lake.exe',tmp_path,tmp_path,(),{})
    assert needs_native_git(context) == (not supported)


def test_git_metadata_fetch_checks_exact_commit_without_checkout(tmp_path, monkeypatch):
    revision = 'a' * 40
    entry = {'name':'mathlib','url':'https://github.com/leanprover-community/mathlib4','rev':revision}
    (tmp_path / '.qprint-package.json').write_text(json.dumps({'repository':'leanprover-community/mathlib4','revision':revision}))
    proof = tmp_path / 'A.lean'
    proof.write_text('def a := 1')
    monkeypatch.setattr('qprint.formal_legacy_lake.shutil.which', lambda *args, **kw: 'git')
    commands = []
    def run(stage, command, cwd, timeout, **kwargs):
        commands.append(command)
        if 'init' in command:
            Path(command[-1]).mkdir()
        return Check(stage,'passed',output=revision if 'rev-parse' in command else '')
    prepare_native_git(tmp_path, entry, env={}, deadline=time.monotonic()+30, runner=run)
    assert proof.read_text() == 'def a := 1'
    assert not any('checkout' in c or 'reset' in c for c in commands)
    fetch = next(c for c in commands if 'fetch' in c)
    assert fetch[-1] == revision and '--depth=1' in fetch
    assert (tmp_path / '.git/qprint-native.json').is_file()


@pytest.mark.parametrize('matches', [True, False])
def test_release_tag_is_published_only_after_lock_match(tmp_path, monkeypatch, matches):
    monkeypatch.setattr('qprint.formal_legacy_lake.shutil.which', lambda *args, **kw: 'git')
    commands = []
    entry = {'name':'proofwidgets', 'inputRev':'v0.0.30', 'rev':'a'*40,
             'url':'https://github.com/leanprover-community/ProofWidgets4'}
    def run(stage, command, *args, **kwargs):
        commands.append(command)
        if '--verify' in command:
            return Check(stage,'failed')
        return Check(stage,'passed',output=('a' if matches else 'b')*40)
    if matches:
        prepare_native_tag(tmp_path, entry, env={}, deadline=time.monotonic()+30, runner=run,
                           query=lambda _: {'object':{'type':'tag'}})
        assert any('update-ref' in c for c in commands)
    else:
        with pytest.raises(ValueError, match='does not match'):
            prepare_native_tag(tmp_path, entry, env={}, deadline=time.monotonic()+30, runner=run,
                               query=lambda _: {'object':{'type':'tag'}})
        assert not any('update-ref' in c for c in commands)


@pytest.mark.parametrize('output,count', [('Could not connect to server',3), ('repository not found',1)])
def test_git_fetch_retries_only_transient_errors_within_original_budget(tmp_path, output, count):
    calls = []
    def run(stage, command, cwd, timeout, **kwargs):
        calls.append(timeout)
        return Check(stage, 'failed', output=output)
    result = git_command('git-prepare',['git','fetch','url','sha'],tmp_path,time.monotonic()+30,{},run)
    assert result.status == 'failed' and len(calls) == count
    assert all(0 < t <= 30 for t in calls)


@pytest.mark.parametrize('matches', [True, False])
def test_official_lightweight_tag_reuses_only_matching_existing_commit(tmp_path, monkeypatch, matches):
    monkeypatch.setattr('qprint.formal_legacy_lake.shutil.which', lambda *args, **kw: 'git')
    entry = {'inputRev':'v0.0.30', 'rev':'a'*40, 'url':'https://github.com/leanprover-community/ProofWidgets4'}
    commands = []
    def run(stage, command, *args, **kwargs):
        commands.append(command)
        return Check(stage,'failed' if '--verify' in command else 'passed')
    def query(url):
        assert url.endswith('/git/ref/tags/v0.0.30')
        return {'object':{'type':'commit','sha':('a' if matches else 'b')*40}}
    if matches:
        prepare_native_tag(tmp_path, entry, env={}, deadline=time.monotonic()+30, runner=run, query=query)
        assert commands[-1][-1] == entry['rev'] and 'update-ref' in commands[-1]
    else:
        with pytest.raises(ValueError, match='does not match'):
            prepare_native_tag(tmp_path, entry, env={}, deadline=time.monotonic()+30, runner=run, query=query)
        assert not any('update-ref' in c for c in commands)
    assert not any('fetch' in c for c in commands)
