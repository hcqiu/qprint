import hashlib

import httpx
import pytest

from qprint.formal_artifacts import ArtifactProvider, release_asset
from qprint.toolchains import ToolchainManager


@pytest.mark.parametrize('digest', [None, 'sha256:' + 'a' * 64, 'sha512:bad'])
def test_legacy_release_requires_identity_and_distinguishes_integrity(monkeypatch, digest):
    real_client = httpx.Client
    def response(request):
        return httpx.Response(200, json={'assets': [{'name': 'lean-4.7.0-rc2-windows.zip', 'digest': digest,
            'id': 155141827, 'size': 249401814,
            'browser_download_url': 'https://github.com/leanprover/lean4/releases/download/v4.7.0-rc2/lean-4.7.0-rc2-windows.zip'}]})
    monkeypatch.setattr('qprint.formal_artifacts.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(response), **kw))
    monkeypatch.setattr('qprint.formal_artifacts.host_platform', lambda: 'windows-x64')
    if digest == 'sha512:bad':
        with pytest.raises(ValueError, match='digest'):
            release_asset('lean', '4.7.0-rc2')
        return
    key, artifact = release_asset('lean', '4.7.0-rc2')
    if digest is None:
        assert 'sha256' not in artifact
        assert artifact['integrity'] == 'official-release-https-first-use-sha256'
        assert artifact['asset_id'] == 155141827
    else:
        assert artifact['sha256'] == 'a' * 64
        assert artifact['integrity'] == 'github-release-digest'


@pytest.mark.parametrize('size', [4, 5])
def test_first_acquisition_pins_bytes_before_install_and_rejects_wrong_size(tmp_path, size):
    manager = ToolchainManager(tmp_path, catalog={'schema_version': 1, 'artifacts': {}})
    item = {'kind': 'toolchain', 'language': 'lean', 'version': '4.7.0-rc2', 'path': 'lean/4.7.0-rc2',
            'url': 'https://github.com/leanprover/lean4/releases/download/v4.7.0-rc2/lean-4.7.0-rc2-windows.zip',
            'asset_size': size, 'asset_id': 123, 'integrity': 'official-release-https-first-use-sha256'}
    installs = []
    def install(key, archive=None):
        assert manager.catalog['artifacts'][key]['sha256'] == hashlib.sha256(archive.read_bytes()).hexdigest()
        installs.append(key)
    manager.install = install
    provider = ArtifactProvider(manager, downloader=lambda url, path: path.write_bytes(b'data'),
                                release_lookup=lambda *args: ('old-lean', dict(item)))
    if size == 5:
        with pytest.raises(ValueError, match='size mismatch'):
            provider.discover(kind='toolchain', language='lean', version='4.7.0-rc2')
        assert not installs and not (tmp_path / 'toolchains/.qprint-catalog.json').exists()
    else:
        provider.discover(kind='toolchain', language='lean', version='4.7.0-rc2')
        assert installs == ['old-lean']
        assert ToolchainManager(tmp_path).catalog['artifacts']['old-lean']['sha256'] == hashlib.sha256(b'data').hexdigest()
