from fastapi.testclient import TestClient

from qprint.server import create_app


def test_frontend_assets_revalidate_and_startup_uses_error_boundary(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        for path in ("/", "/static/bootstrap.js", "/static/app.js", "/static/graph-view.js"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-cache"
            cached = client.get(path, headers={"If-None-Match": response.headers["etag"]})
            assert cached.headers["cache-control"] == "no-cache"
        assert '/static/bootstrap.js' in client.get('/').text
        assert client.get('/api/project').headers['cache-control'] == 'no-store'
