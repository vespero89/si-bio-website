import shutil

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def german(monkeypatch, tmp_path):
    """A third language known to the code (LANGS) but not published, with a copy of the Italian
    content so that pages that read content files can answer in it."""
    shutil.copytree(config.CONTENT_DIR, tmp_path / "content")
    shutil.copytree(tmp_path / "content" / "it", tmp_path / "content" / "de")
    monkeypatch.setattr(config, "CONTENT_DIR", tmp_path / "content")
    content.read.cache_clear()
    monkeypatch.setattr(config, "LANGS", ("it", "en", "de"))
    yield
    monkeypatch.undo()
    content.read.cache_clear()


def test_site_toml_publishes_it_and_en():
    assert config.PUBLISHED == ("it", "en")
    assert config.LANGS == ("it", "en")


def test_root_is_italian(client):
    response = client.get("/")
    assert response.status_code == 200
    assert '<html lang="it">' in response.text


def test_english_prefix_is_english(client):
    response = client.get("/en/")
    assert response.status_code == 200
    assert '<html lang="en">' in response.text
    assert client.get("/en").status_code == 200


def test_italian_prefix_does_not_exist(client):
    assert client.get("/it/").status_code == 404


def test_unknown_language_prefix_is_404(client):
    assert client.get("/fr/").status_code == 404


def test_static_is_not_prefixed(client):
    assert client.get("/en/static/x.css").status_code == 404


def test_accept_language_italian_stays(client):
    response = client.get("/", headers={"Accept-Language": "it-IT,it;q=0.9"})
    assert response.status_code == 200
    assert "Accept-Language" in response.headers["vary"]
    assert client.get("/", headers={"Accept-Language": "it-CH"}).status_code == 200


def test_no_accept_language_stays_italian(client):
    assert client.get("/").status_code == 200


def test_accept_language_unknown_goes_to_english(client):
    response = client.get("/", headers={"Accept-Language": "fr"})
    assert response.status_code == 302
    assert response.headers["location"] == "/en/"


def test_accept_language_english_goes_to_english(client):
    response = client.get("/", headers={"Accept-Language": "en-GB,en;q=0.8"})
    assert response.headers["location"] == "/en/"


def test_accept_language_picks_published_by_quality(client):
    response = client.get("/", headers={"Accept-Language": "fr,it;q=0.5"})
    assert response.status_code == 200
    response = client.get("/", headers={"Accept-Language": "de,en;q=0.8,it;q=0.5"})
    assert response.headers["location"] == "/en/"


def test_unpublished_language_in_header_goes_to_english(client, german):
    response = client.get("/", headers={"Accept-Language": "de"})
    assert response.headers["location"] == "/en/"


def test_published_language_in_header_goes_to_its_prefix(client, german, monkeypatch):
    monkeypatch.setattr(config, "PUBLISHED", ("it", "en", "de"))
    response = client.get("/", headers={"Accept-Language": "de-AT"})
    assert response.headers["location"] == "/de/"
    assert client.get("/de/").status_code == 200


def test_cookie_wins_over_header(client):
    client.cookies.set("lang", "en")
    response = client.get("/", headers={"Accept-Language": "it"})
    assert response.headers["location"] == "/en/"


def test_cookie_italian_stays_with_foreign_header(client):
    client.cookies.set("lang", "it")
    assert client.get("/", headers={"Accept-Language": "fr"}).status_code == 200


def test_bad_cookie_is_ignored(client):
    client.cookies.set("lang", "xx")
    response = client.get("/", headers={"Accept-Language": "fr"})
    assert response.headers["location"] == "/en/"


def test_unpublished_cookie_is_ignored(client, german):
    client.cookies.set("lang", "de")
    assert client.get("/").status_code == 200


def test_selector_sets_cookie_and_redirects_to_clean_page(client):
    response = client.get("/en/?lang=it&x=1")
    assert response.status_code == 303
    assert response.headers["location"] == "/en/?x=1"
    assert "lang=it" in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"]


def test_selector_ignores_invalid_or_unpublished(client, german):
    assert client.get("/?lang=xx").status_code == 200
    assert client.get("/?lang=de").status_code == 200


def test_unpublished_language_is_404(client, german):
    assert client.get("/de/").status_code == 404
    assert client.get("/de").status_code == 404


def test_unpublished_language_shows_with_preview(client, german, monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    response = client.get("/de/")
    assert response.status_code == 200
    assert '<html lang="de">' in response.text


def test_selector_accepts_unpublished_in_preview(client, german, monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    response = client.get("/?lang=de")
    assert response.status_code == 303
    assert "lang=de" in response.headers["set-cookie"]


def test_redirects_from_routes_keep_the_language():
    from app import lang

    assert lang.localize("/vini", "en") == "/en/vini"
    assert lang.localize("/", "en") == "/en/"
    assert lang.localize("/vini", "it") == "/vini"
    assert lang.localize("/static/a.css", "en") == "/static/a.css"
    assert lang.localize("https://x.example/", "en") == "https://x.example/"
    assert lang.localize("//x.example/", "en") == "//x.example/"


def test_post_is_not_redirected_by_cookie_or_header(client):
    assert client.post("/", headers={"Accept-Language": "fr"}).status_code == 405
