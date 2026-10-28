from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_home_answers_200_with_html():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Si Bio" in response.text


def test_unknown_path_answers_404():
    assert client.get("/does-not-exist").status_code == 404
