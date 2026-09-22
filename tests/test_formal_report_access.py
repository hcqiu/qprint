import io
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
import pytest

from qprint.formal_reports import failure_report
from qprint.formal_import import verify_download
from qprint.importers import import_code
from qprint.server import create_app


def test_existing_reports_survive_new_server_and_have_readable_links(tmp_path):
    project = tmp_path / 'lean/FLT3'
    project.mkdir(parents=True)
    original = failure_report(project, 'lean', ValueError('No official digest'))
    with TestClient(create_app(tmp_path)) as client:
        reports = client.get('/api/formal-reports').json()['reports']
        assert len(reports) == 1 and reports[0]['report_path'] == original['report_path']
        viewed = client.get(reports[0]['report_url'])
        assert viewed.status_code == 200 and 'No official digest' in viewed.text
        downloaded = client.get(reports[0]['download_url'])
        assert downloaded.json()['report_id'] == original['report_id']
        assert 'attachment' in downloaded.headers['content-disposition']


def test_corrupt_history_entry_does_not_hide_valid_report(tmp_path):
    project = tmp_path / 'lean/FLT3'
    project.mkdir(parents=True)
    report = failure_report(project, 'lean', ValueError('real error'))
    Path(report['report_path']).with_name('20990101T000000.000000Z-aaaaaaaa.json').write_text('[]')
    with TestClient(create_app(tmp_path)) as client:
        assert len(client.get('/api/formal-reports').json()['reports']) == 1


@pytest.mark.parametrize('path', ['../secret.json', 'lean/FLT3/lean-toolchain', 'C:/secret.json', '.qprint/reports/random.json'])
def test_report_endpoint_does_not_expose_arbitrary_files(tmp_path, path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/formal-report', params={'path': path}).status_code == 400


def test_one_project_exception_preserves_other_reports(tmp_path, monkeypatch):
    first, second = tmp_path / 'first', tmp_path / 'second'
    for root in (first, second):
        root.mkdir()
        (root / 'lean-toolchain').write_text('leanprover/lean4:v4.7.0-rc2')
    def verify(root, *args, **kwargs):
        if root == first:
            raise RuntimeError('unexpected installer exception')
        return {'project': str(root), 'status': 'passed'}
    monkeypatch.setattr('qprint.formal_import.formal_project', verify)
    result = verify_download(tmp_path, 'lean')
    assert len(result['reports']) == 2
    assert Path(result['reports'][0]['report_path']).is_file()
    assert result['reports'][1]['status'] == 'passed'


def test_one_unwritable_report_does_not_discard_other_projects(tmp_path, monkeypatch):
    roots = [tmp_path/'first',tmp_path/'second']
    for root in roots:
        root.mkdir()
        (root/'lean-toolchain').write_text('leanprover/lean4:v4.7.0-rc2')
    def verify(root, *args, **kwargs):
        if root == roots[0]:
            raise RuntimeError('check failed')
        return {'status':'passed'}
    def store(*args, **kwargs):
        raise PermissionError('read-only')
    monkeypatch.setattr('qprint.formal_import.formal_project', verify)
    monkeypatch.setattr('qprint.formal_import.failure_report', store)
    result = verify_download(tmp_path,'lean')
    assert 'read-only' in result['reports'][0]['report_error']
    assert result['reports'][1]['status'] == 'passed'


def broken_import(tmp_path):
    def fetch(url):
        if 'api.github.com' in url:
            return json.dumps({'sha': 'a' * 40}).encode()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('repo/A.lean', 'def a := 1')
        return stream.getvalue()
    def broken(*args, **kwargs):
        raise RuntimeError('discovery failed')
    return import_code(tmp_path, 'https://github.com/example/repo', 'lean', 'repo', ref='main',
                       downloader=fetch, verifier=broken)


def test_import_orchestration_exception_has_report(tmp_path):
    result = broken_import(tmp_path)
    verification = result['verification']
    assert verification['status'] == 'error'
    assert json.loads(Path(verification['reports'][0]['report_path']).read_text())['message'] == 'discovery failed'


def test_report_write_failure_is_explicit(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise PermissionError('read-only report directory')
    monkeypatch.setattr('qprint.formal_reports.save_report', broken)
    verification = broken_import(tmp_path)['verification']
    assert verification['reports'] == []
    assert 'read-only report directory' in verification['report_error']
