import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)

PARTNER = "info@example-partner.it"


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)
    content.read.cache_clear()
    yield
    content.read.cache_clear()


@pytest.fixture
def preview(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    content.read.cache_clear()
    yield
    content.read.cache_clear()


def patch(monkeypatch, site=None, visits=None):
    """Overrides site.toml sections and/or visits.toml keys (all languages)."""
    real = content.read

    def read(path):
        data = real(path)
        if path.name == "site.toml" and site:
            data = {**data, **{k: {**data.get(k, {}), **v} for k, v in site.items()}}
        if path.name == "visits.toml" and visits:
            data = {**data, **visits}
        return data

    read.cache_clear = real.cache_clear
    monkeypatch.setattr(content, "read", read)


def ready(monkeypatch, **extra):
    patch(
        monkeypatch,
        site={"contact": {"partner_email": PARTNER}, **extra.pop("site", {})},
        visits={
            "package_name": "Vendemmia a Offida",
            "package_lead": "Tre giorni nel Piceno",
            "package_text": "Testo di prova.",
            "package_hotel": "Hotel Casale",
            **extra,
        },
    )


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_visits_one_h1_and_buyers_block(client, production, prefix):
    response = client.get(prefix + "/visite")
    assert response.status_code == 200
    assert response.text.count("<h1") == 1
    assert "mailto:export@si-bio.it?subject=Si%20Bio%3A%20" in response.text
    assert not re.search(
        r"DA (VERIFICARE|COMPLETARE|DEFINIRE)|TO BE (VERIFIED|COMPLETED|DEFINED)", response.text
    )


def test_buyers_texts_and_subject(client, production):
    html = client.get("/visite").text
    assert "Vieni a trovarci" in html
    assert "Ospitiamo buyer e importatori" in html
    assert "subject=Si%20Bio%3A%20programma%20buyer" in html
    assert "subject=Si%20Bio%3A%20buyer%20programme" in client.get("/en/visite").text


def test_no_price_no_form_no_external(client, preview):
    for prefix in ("", "/en"):
        html = client.get(prefix + "/visite").text
        assert "<form" not in NOTICE.sub("", html)  # only the cookie choice posts
        assert "€" not in html
        assert "youtube" not in NOTICE.sub("", html).lower()
        assert not re.search(r"<(iframe|script)[^>]+src=\"https?://", html)
    assert 'class="video-slot"' in client.get("/visite").text


def test_package_hidden_in_production_while_contact_is_placeholder(client, production):
    html = client.get("/visite").text
    assert "Fuselli e Filari" not in html
    assert "Chiedi il programma" not in html


def test_package_block_with_partner_contact(client, production, monkeypatch):
    ready(monkeypatch)
    html = client.get("/visite").text
    assert "Vendemmia a Offida" in html
    assert "Organizzato e venduto da Fuselli e Filari, agenzia di Offida." in html
    assert "Hotel Casale" in html
    assert "Chiedi il programma" in html
    assert f"mailto:{PARTNER}?subject=Richiesta%20programma%3A%20Vendemmia%20a%20Offida" in html
    assert html.count("<h1") == 1
    en = client.get("/en/visite").text
    assert "Organised and sold by Fuselli e Filari, a travel agency in Offida." in en
    assert f"mailto:{PARTNER}?subject=Programme%20request%3A%20Vendemmia%20a%20Offida" in en


def test_package_hidden_without_name_even_with_contact(client, production, monkeypatch):
    patch(monkeypatch, site={"contact": {"partner_email": PARTNER}})
    assert PARTNER not in client.get("/visite").text


def test_package_has_no_price(client, production, monkeypatch):
    ready(monkeypatch)
    assert "€" not in client.get("/visite").text


def test_package_subject_with_special_characters(client, production, monkeypatch):
    ready(monkeypatch, package_name="Brut & Rosé d'autunno")
    html = client.get("/visite").text
    assert "subject=Richiesta%20programma%3A%20Brut%20%26%20Ros%C3%A9%20d%27autunno" in html


def test_riva_off_by_default(client, preview):
    for prefix in ("", "/en"):
        assert "Riva dei Martin" not in client.get(prefix + "/visite").text


def test_riva_on_shown_in_preview_hidden_in_production(client, monkeypatch):
    patch(monkeypatch, site={"switches": {"riva_dei_martin": True}})
    monkeypatch.setattr(config, "PREVIEW", True)
    assert "Riva dei Martin" in client.get("/visite").text
    monkeypatch.setattr(config, "PREVIEW", False)
    assert "Riva dei Martin" not in client.get("/visite").text


def test_preview_shows_placeholders(client, preview):
    assert "DA DEFINIRE" in client.get("/visite").text
    assert "TO BE DEFINED" in client.get("/en/visite").text


def test_menu_marks_visits_current(client, production):
    assert 'aria-current="page"' in client.get("/visite").text
