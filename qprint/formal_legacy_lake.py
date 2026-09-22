"""Native Git metadata for Lake versions without package overrides."""
import json
import re
from pathlib import Path
import shutil
import tempfile
import time

from .formal_downloads import event, github_json
from .formal_git import github_repo, PACKAGE_RECEIPT
from .formal_runner import run_command
from .paths import WorkspaceError, safe_path


def git_command(stage, command, target, deadline, env, runner):
    attempts = 3 if 'fetch' in command else 1
    for attempt in range(1, attempts + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WorkspaceError('Native Git preparation deadline exhausted')
        result = runner(stage, command, target, remaining, env=env)
        transient = any(term in result.output.lower() for term in
                        ('could not connect', 'connection', 'timed out', 'curl 28', 'http 502', 'http 503', 'http 504', 'could not resolve host'))
        if result.status == 'passed' or not transient or attempt == attempts:
            return result
        event('download_retry', transport='git', attempt=attempt, reason='transient network failure')


def needs_native_git(context):
    source = context.compiler.parent.parent / 'src/lean/lake/Lake/Load/Config.lean'
    if source.is_file():
        return 'packageOverrides' not in source.read_text(encoding='utf-8')
    # Official legacy manifests used integer schema versions. Unknown systems
    # conservatively use real Git repositories, which both old and new Lake accept.
    return isinstance(context.requirements.get('native', {}).get('lake-manifest.json', {}).get('version'), int)


def prepare_native_git(target, entry, *, env, deadline, offline=False, runner=run_command):
    receipt = json.loads(safe_path(target, PACKAGE_RECEIPT).read_text(encoding='utf-8'))
    revision = entry['rev']
    if receipt.get('revision') != revision or receipt.get('repository') != github_repo(entry['url']):
        raise WorkspaceError('Native Git preparation requires a matching managed source receipt')
    git = shutil.which('git', path=env.get('PATH'))
    if not git:
        raise WorkspaceError('Legacy Lake dependency preparation requires Git')
    destination = safe_path(target, '.git')
    if destination.exists():
        result = runner('git-revision', [git, '-c', f'safe.directory={target.as_posix()}', '-C', str(target),
                                        'rev-parse', 'HEAD'], target, max(.1, deadline-time.monotonic()), env=env)
        if result.status != 'passed' or result.output.strip() != revision:
            raise WorkspaceError('Existing dependency Git revision differs from native lock')
        return
    if offline:
        raise WorkspaceError('Offline: missing native Git metadata for ' + entry['name'])
    with tempfile.TemporaryDirectory(prefix='.qprint-native-git-', dir=target) as temporary:
        stage = Path(temporary) / 'repository'
        commands = [
            [git, 'init', '--bare', str(stage)],
            [git, '--git-dir', str(stage), 'fetch', '--depth=1', '--no-tags', '--no-recurse-submodules', entry['url'], revision],
            [git, '--git-dir', str(stage), 'rev-parse', 'FETCH_HEAD'],
            [git, '--git-dir', str(stage), 'update-ref', 'HEAD', revision],
            [git, '--git-dir', str(stage), 'read-tree', revision],
            [git, '--git-dir', str(stage), 'config', 'core.bare', 'false'],
            [git, '--git-dir', str(stage), 'config', 'remote.origin.url', entry['url']],
        ]
        for index, command in enumerate(commands):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkspaceError('Native Git preparation deadline exhausted')
            result = git_command('git-prepare', command, target, deadline, env, runner)
            if result.status != 'passed':
                raise WorkspaceError('Native Git dependency preparation failed: ' + result.output[-2000:])
            if index == 2 and result.output.strip() != revision:
                raise WorkspaceError('Fetched Git commit does not match native lock')
        (stage / 'qprint-native.json').write_text(json.dumps({'revision': revision, 'repository': receipt['repository']}))
        stage.rename(destination)
    event('native_git_prepared', package=entry['name'], revision=revision)


def prepare_native_tag(target, entry, *, env, deadline, offline=False, runner=run_command, query=github_json):
    """Publish a real release tag only after checking its peeled commit against the lock."""
    tag = entry.get('inputRev')
    if not isinstance(tag, str) or not re.fullmatch(r'v\d+(?:\.\d+)+(?:-[\w.]+)?', tag):
        raise WorkspaceError('Native cloud release requires an exact upstream tag')
    git = shutil.which('git', path=env.get('PATH'))
    base = [git, '-c', f'safe.directory={target.as_posix()}', '-C', str(target)]
    def run(arguments):
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise WorkspaceError('Native tag preparation deadline exhausted')
        return git_command('git-release-tag', base + arguments, target, deadline, env, runner)
    current = run(['rev-parse', '--verify', f'refs/tags/{tag}^{{}}'])
    if current.status == 'passed':
        if current.output.strip() != entry['rev']:
            raise WorkspaceError('Existing release tag differs from locked commit')
        return
    if offline:
        raise WorkspaceError('Offline: missing native release tag')
    reference = query(f"repos/{github_repo(entry['url'])}/git/ref/tags/{tag}").get('object', {})
    if reference.get('type') == 'commit':
        if reference.get('sha') != entry['rev']:
            raise WorkspaceError('Official release tag does not match locked commit')
        published = run(['update-ref', f'refs/tags/{tag}', entry['rev']])
        if published.status != 'passed':
            raise WorkspaceError('Could not record verified native release tag')
        event('release_metadata_restored', repository=github_repo(entry['url']), revision=entry['rev'], tag=tag,
              transport='official-api-existing-commit')
        return
    if reference.get('type') != 'tag':
        raise WorkspaceError('Unsupported official release tag reference')
    fetched = run(['fetch', '--depth=1', '--no-tags', '--no-recurse-submodules', entry['url'], f'refs/tags/{tag}'])
    if fetched.status != 'passed':
        raise WorkspaceError('Native release tag download failed: ' + fetched.output[-1500:])
    peeled = run(['rev-parse', 'FETCH_HEAD^{}'])
    if peeled.status != 'passed' or peeled.output.strip() != entry['rev']:
        raise WorkspaceError('Official release tag does not match locked commit')
    published = run(['update-ref', f'refs/tags/{tag}', 'FETCH_HEAD'])
    if published.status != 'passed':
        raise WorkspaceError('Could not record verified native release tag')
    event('release_metadata_restored', repository=github_repo(entry['url']), revision=entry['rev'], tag=tag)
