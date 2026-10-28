import tomllib

import pytest
from fastapi.testclient import TestClient

from app import config, i18n
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def locales(tmp_path, monkeypatch):
    """A locales folder with a fake language 'xx' (a copy of the Italian file) published
    and known to the code, without touching any code or real file."""
    (tmp_path / "it.toml").write_text(
        (config.LOCALES_DIR / "it.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "xx.toml").write_text(
        (config.LOCALES_DIR / "it.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(config, "LOCALES_DIR", tmp_path)
    monkeypatch.setattr(config, "LANGS", ("it", "en", "xx"))
    monkeypatch.setattr(config, "PUBLISHED", ("it", "en", "xx"))
    i18n.load.cache_clear()
    yield tmp_path
    i18n.load.cache_clear()


def test_every_published_language_has_every_italian_key():
    for lang in config.PUBLISHED:
        assert i18n.missing(lang) == [], f"locales/{lang}.toml misses keys of it.toml"


def test_files_are_valid_toml_and_keys_are_flattened():
    data = tomllib.loads((config.LOCALES_DIR / "it.toml").read_text(encoding="utf-8"))
    assert data["nav"]["wines"] == i18n.load("it")["nav.wines"]


def test_fake_language_is_complete_without_code_changes(locales):
    assert i18n.missing("xx") == []


def test_removing_a_key_makes_the_check_fail_with_a_clear_message(locales):
    path = locales / "xx.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('contact = "Contatti"\n', ""))
    i18n.load.cache_clear()
    assert i18n.missing("xx") == ["nav.contact"]
    with pytest.raises(AssertionError, match=r"locales/xx.toml misses.*nav\.contact"):
        i18n.assert_complete("xx")


def test_t_uses_the_language_of_the_request(client):
    assert "Vai al contenuto" in client.get("/").text
    assert "Skip to content" in client.get("/en/").text


def test_t_formats_placeholders():
    assert i18n.t("it", "wine.abv", value="13,5") == "13,5 % vol"
    assert i18n.t("en", "wine.abv", value="13.5") == "13.5% vol"


def test_numbers_use_the_decimal_separator_of_the_language():
    assert i18n.num("it", 13.5) == "13,5"
    assert i18n.num("en", 13.5) == "13.5"
    assert i18n.num("it", 13.5, 2) == "13,50"
    assert i18n.num("en", 14, 1) == "14.0"
    assert i18n.num("it", 14) == "14"


def test_missing_key_in_a_language_shows_the_key_outside_preview(locales, monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)
    path = locales / "xx.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('contact = "Contatti"\n', ""))
    i18n.load.cache_clear()
    assert i18n.t("xx", "nav.contact") == "nav.contact"


def test_missing_key_falls_back_to_italian_in_preview(locales, monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    path = locales / "xx.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('contact = "Contatti"\n', ""))
    i18n.load.cache_clear()
    assert i18n.t("xx", "nav.contact") == "Contatti"


def test_root_falls_back_to_italian_when_english_is_not_published(client, monkeypatch):
    monkeypatch.setattr(config, "PUBLISHED", ("it",))
    response = client.get("/", headers={"Accept-Language": "fr"})
    assert response.status_code == 200
    assert '<html lang="it">' in response.text
