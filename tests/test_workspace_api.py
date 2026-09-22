from pathlib import Path
import shutil
import time

from fastapi.testclient import TestClient
import pytest

from qprint.paths import WorkspaceError, safe_path
from qprint.server import create_app
from qprint.workspace import Workspace

DEMO = Path(__file__).parents[1] / "examples" / "demo"


@pytest.fixture
def client(tmp_path):
    # Copy the fixed navigation fixture, not arbitrary user-imported repositories.
    for folder in ("blueprint", "tex", "lean", "agda", "coq"):
        for relative in {
            "blueprint": ["Algebra/Functions.md", "Topology/Maps.md", "Topology/Notes26Continuity.md"],
            "tex": ["Topology/Notes26Continuity.tex"],
            "lean": ["Topology/Maps.lean", "Topology/Continuity.lean"],
            "agda": ["Topology/Maps.agda"], "coq": ["Topology/Maps.v"],
        }[folder]:
            target = tmp_path / folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DEMO / folder / relative, target)
    with TestClient(create_app(tmp_path)) as client:
        client.headers["x-qprint-token"] = client.get("/api/project").json()["token"]
        yield client


def test_demo_links_three_languages_and_navigation(client):
    project = client.get("/api/project").json()
    assert project["stats"]["nodes"] == 10
    assert project["diagnostics"] == []
    assert len(project["graph"]["files"]) == 3
    assert {p["id"] for p in project["graph"]["projects"]} == {"Algebra", "Topology"}
    detail = client.get("/api/node", params={"id": "Topology/Notes26Continuity#Identity map"}).json()
    assert len(detail["formal"]) == 3
    assert all(f["code"] and not f["error"] for f in detail["formal"])
    assert detail["previous"] is None
    assert detail["next"] == "Topology/Notes26Continuity#Continuity of the identity"
    assert detail["tex_content"]["html"]
    assert project["papers"][0]["sections"][0]["node_id"] == detail["id"]


def test_document_save_conflict_and_validation(client):
    path = "Topology/Maps.md"
    original = client.get("/api/document", params={"path": path}).json()
    changed = {**original, "text": original["text"] + "\nA new note.\n"}
    assert client.put("/api/document", json=changed).status_code == 200
    assert client.put("/api/document", json=changed).status_code == 409
    fresh = client.get("/api/document", params={"path": path}).json()
    assert client.put("/api/document", json={**fresh, "text": "# Bad\n```qprint\nstatus: invalid\n```"}).status_code == 400
    assert client.get("/api/document", params={"path": path}).json() == fresh


def test_write_token_origin_and_path_guard(client):
    assert client.post("/api/reload", headers={"x-qprint-token": "wrong"}).status_code == 403
    assert client.post("/api/reload", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/document", params={"path": "../../AGENTS.md"}).status_code == 400
    assert client.get("/api/node", params={"id": "missing"}).status_code == 404
    assert client.get("/api/project", headers={"host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "C:/secret", "A/../../x", "A\\x", "A/file:stream", "nul.txt", "a/CON", "a/x.", "a//b"])
def test_portable_path_safety(tmp_path, path):
    with pytest.raises(WorkspaceError):
        safe_path(tmp_path, path)


def test_empty_workspace_and_invalid_tex_do_not_crash(tmp_path):
    workspace = Workspace(tmp_path)
    assert workspace.project()["stats"]["nodes"] == 0
    (tmp_path / "blueprint").mkdir()
    (tmp_path / "blueprint" / "A.md").write_text('# X\n```qprint\ntex: absent#x\nuses: ["[[Missing#X]]"]\n```', encoding="utf-8")
    workspace.reload()
    assert len(workspace.diagnostics) == 2
    assert workspace.detail("A#X")["tex_content"] is None


def test_html_in_notes_escaped_and_wikilinks_work(tmp_path):
    (tmp_path / "blueprint").mkdir()
    (tmp_path / "blueprint" / "A.md").write_text('# X\n<script>alert(1)</script> [[#Y|go]]\n# Y\nHello', encoding="utf-8")
    detail = Workspace(tmp_path).detail("A#X")
    assert "<script>" not in detail["body_html"]
    assert 'href="#node=A%23Y"' in detail["body_html"]


def test_cycles_are_preserved(tmp_path):
    (tmp_path / "blueprint").mkdir()
    (tmp_path / "blueprint" / "A.md").write_text('# X\n```qprint\nuses: ["[[#Y]]"]\n```\n# Y\n```qprint\nuses: ["[[#X]]"]\n```', encoding="utf-8")
    assert len(Workspace(tmp_path).project()["edges"]) == 2


@pytest.mark.parametrize("failure", [False, True])
def test_background_import_lifecycle(client, monkeypatch, failure):
    def run(*args, **kwargs):
        assert kwargs["verify_after_download"] is True
        if failure:
            raise WorkspaceError("test network failure")
        return {"files": 2, "path": "lean/test"}
    monkeypatch.setattr("qprint.server.import_code", run)
    response = client.post("/api/import", json={"kind": "code", "source": "https://github.com/example/repo", "dest": "test", "language": "lean"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    for _ in range(100):
        result = client.get(f"/api/jobs/{job_id}").json()
        if result["status"] in {"failed", "succeeded"}:
            break
        time.sleep(.01)
    assert result["status"] == ("failed" if failure else "succeeded")
    assert (result["error"] == "test network failure") if failure else result["result"]["files"] == 2


def test_static_resources_are_local_and_served(client):
    assert client.get("/").status_code == 200
    for asset in ["app.js", "graph.js", "graph-view.js", "style.css", "vendor/katex/katex.min.js", "vendor/katex/auto-render.min.js", "vendor/katex/fonts/KaTeX_Main-Regular.woff2"]:
        assert client.get(f"/static/{asset}").status_code == 200


def test_import_optout_passed_to_backend(client, monkeypatch):
    def run(*args, **kwargs):
        assert kwargs["verify_after_download"] is False
        return {"verification": {"status": "not_run"}}
    monkeypatch.setattr("qprint.server.import_code", run)
    response = client.post("/api/import", json={"kind": "code", "source": "https://github.com/example/repo",
                                               "dest": "test", "language": "lean", "verify_after_download": False})
    for _ in range(100):
        job = client.get('/api/jobs/' + response.json()["id"]).json()
        if job["status"] in {"failed", "succeeded"}:
            break
        time.sleep(.01)
    assert job["status"] == "succeeded" and job["result"]["verification"]["status"] == "not_run"
