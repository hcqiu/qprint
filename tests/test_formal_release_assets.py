import hashlib
import io
import zipfile

import pytest

from qprint.formal_release_assets import acquire_asset, prepare_legacy_leantar
from qprint.formal_environment import FormalExecutionContext
from qprint.formal_runner import Check


def test_first_use_receipt_reuses_checked_archive_and_rejects_changes(tmp_path):
    url = 'https://github.com/example/repo/releases/download/v1/tool.zip'
    asset = {'browser_download_url':url,'id':1,'size':4,'digest':None}
    receipt, archive = tmp_path/'receipt.json', tmp_path/'archive'
    def download(url, target, **kwargs):
        target.write_bytes(b'data')
    digest = acquire_asset(asset,url,archive,receipt,downloader=download)
    assert digest == hashlib.sha256(b'data').hexdigest()
    acquire_asset(asset,url,tmp_path/'second',receipt,cached=archive,
                  downloader=lambda *a, **kw: pytest.fail('must reuse validated archive'))
    with pytest.raises(ValueError, match='identity differs'):
        acquire_asset({**asset,'id':2},url,tmp_path/'third',receipt,downloader=download)
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        acquire_asset(asset,url,tmp_path/'third',receipt,downloader=lambda u,p,**kw:p.write_bytes(b'evil'))


@pytest.mark.parametrize('prefix', ['', 'leantar-v0.1.11-x86_64-pc-windows-msvc/'])
def test_exact_upstream_leantar_version_with_flat_or_nested_zip(tmp_path, monkeypatch, prefix):
    source = tmp_path/'IO.lean'
    source.write_text('def LEANTARVERSION :=\n  "0.1.11"')
    cache = tmp_path/'cache'
    cache.mkdir()
    context = FormalExecutionContext('lean','4.7.0-rc2',tmp_path/'lean',tmp_path/'lake',tmp_path,tmp_path,(),{})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as archive:
        archive.writestr(prefix+'leantar.exe',b'fake executable')
    data = buffer.getvalue()
    url = 'https://github.com/digama0/leangz/releases/download/v0.1.11/leantar-v0.1.11-x86_64-pc-windows-msvc.zip'
    asset = {'id':1,'size':len(data),'name':url.split('/')[-1],'browser_download_url':url,'digest':None}
    monkeypatch.setattr('qprint.formal_release_assets.host_platform',lambda:'windows-x64')
    def runner(stage,command,*args,**kwargs):
        assert command[-1] == '--version' and command[0].endswith('leantar.exe')
        return Check(stage,'passed',output='leantar 0.1.11')
    prepare_legacy_leantar(source,cache,context,30,runner,query=lambda _: {'assets':[asset]},
                          downloader=lambda u,p,**kw:p.write_bytes(data))
    assert (cache/'leantar-0.1.11.exe').read_bytes() == b'fake executable'
