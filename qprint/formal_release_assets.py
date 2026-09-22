"""Pinned official auxiliary assets, including pre-digest GitHub releases."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from .formal_downloads import download_file, event, github_json
from .formal_archives import extract
from .paths import WorkspaceError, safe_path
from .toolchains import host_platform


def acquire_asset(asset, expected_url, destination, receipt, *, downloader=download_file, cached=None):
    if asset.get('browser_download_url') != expected_url:
        raise WorkspaceError('Unexpected official release asset URL')
    digest = asset.get('digest')
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest)):
        raise WorkspaceError('Invalid official release digest')
    identity = {'url': expected_url, 'asset_id': asset.get('id'), 'asset_size': asset.get('size')}
    if digest is None and any(type(identity[key]) is not int or identity[key] <= 0 for key in ('asset_id','asset_size')):
        raise WorkspaceError('Legacy release asset lacks exact identity and size')
    expected_hash = digest[7:] if digest else None
    if receipt.is_file():
        prior = json.loads(receipt.read_text(encoding='utf-8'))
        if any(prior.get(k) != v for k, v in identity.items()) or not re.fullmatch(r'[0-9a-f]{64}', prior.get('sha256', '')):
            raise WorkspaceError('Official asset identity differs from recorded receipt')
        if expected_hash and expected_hash != prior['sha256']:
            raise WorkspaceError('Official asset digest differs from recorded receipt')
        expected_hash = prior['sha256']
    cached_hash = None
    if cached is not None and cached.is_file() and expected_hash:
        with cached.open('rb') as stream:
            cached_hash = hashlib.file_digest(stream,'sha256').hexdigest()
    if cached_hash == expected_hash and expected_hash:
        shutil.copyfile(cached,destination)
    else:
        downloader(expected_url, destination, expected_sha256=expected_hash)
    if type(asset.get('size')) is int and destination.stat().st_size != asset['size']:
        raise WorkspaceError('Official asset size mismatch')
    with destination.open('rb') as stream:
        actual = hashlib.file_digest(stream,'sha256').hexdigest()
    if expected_hash and actual != expected_hash:
        raise WorkspaceError('Official asset SHA-256 mismatch')
    result = {**identity, 'sha256': actual,
              'integrity': 'github-release-digest' if digest else 'official-release-https-first-use-sha256'}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result,indent=2),encoding='utf-8')
    event('artifact_integrity', **result)
    return actual


def prepare_legacy_leantar(source, cache, context, timeout, runner, *, query=github_json, downloader=download_file):
    if host_platform() != 'windows-x64':
        return
    match = re.search(r'\bdef LEANTARVERSION\s*:=\s*"(\d+\.\d+\.\d+)"', source.read_text(encoding='utf-8'))
    if not match:
        return  # Unknown upstream conventions stay with the native program.
    version = match[1]
    target = safe_path(cache, f'leantar-{version}.exe')
    if target.is_file():
        return
    name = f'leantar-v{version}-x86_64-pc-windows-msvc.zip'
    url = f'https://github.com/digama0/leangz/releases/download/v{version}/{name}'
    assets = [a for a in query(f'repos/digama0/leangz/releases/tags/v{version}').get('assets',[]) if a.get('name') == name]
    if len(assets) != 1:
        raise WorkspaceError('No exact official leantar asset for the upstream version')
    with tempfile.TemporaryDirectory(prefix='.qprint-leantar-', dir=cache) as temporary:
        directory = Path(temporary)
        archive = directory/'tool.zip'
        acquire_asset(assets[0], url, archive, safe_path(cache,f'.qprint-leantar-{version}.json'), downloader=downloader)
        payload = directory/'payload'
        payload.mkdir()
        extract(archive,payload)
        executables = list(payload.rglob('leantar.exe'))
        if len(executables) != 1 or not executables[0].is_file():
            raise WorkspaceError('Official leantar archive is missing leantar.exe')
        executable = executables[0]
        check = runner('cache-tool-version',[str(executable),'--version'],context.project_root,timeout,env=context.environment)
        if check.status != 'passed' or not re.search(rf'(?<![\w.]){re.escape(version)}(?![\w.])',check.output):
            raise WorkspaceError('leantar version does not match upstream requirement')
        shutil.copyfile(executable,target)
