import re
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)
    content.read.cache_clear()
    yield
    content.read.cache_clear()


def mailto_subject(html):
    href = re.search(r'href="(mailto:[^"]+)"', html.split('class="contact-block"')[1]).group(1)
    return href, unquote(parse_qs(urlsplit(href).query)["subject"][0])


def test_contact_page_it(client):
    response = client.get("/contatti")
    assert response.status_code == 200
    assert response.text.count("<h1") == 1
    assert "export@si-bio.it" in response.text
    href, subject = mailto_subject(response.text)
    assert href == "mailto:export@si-bio.it?subject=Si%20Bio%3A%20informazioni"
    assert "+" not in href
    assert 'aria-current="page"' in response.text
    assert "<form" not in NOTICE.sub("", response.text)  # only the cookie choice posts


def test_contact_page_en_subject(client):
    response = client.get("/en/contatti")
    assert response.status_code == 200
    assert "Contact" in response.text
    href, subject = mailto_subject(response.text)
    assert subject == "Si Bio: information"
    assert "+" not in href


def test_company_data_in_page(client):
    html = client.get("/contatti").text
    assert "02274900444" in html
    assert "Si Bio di Premici Silvia e Aleandri Vincenzo" in html
    assert "Contrada San Lazzaro 118, 63073 Offida" in html


def test_placeholders_in_preview_hidden_in_production(client, production, monkeypatch):
    html = client.get("/contatti").text
    assert "DA COMPLETARE" not in html
    assert "DA DEFINIRE" not in html
    assert "export@si-bio.it" in html
    monkeypatch.setattr(config, "PREVIEW", True)
    content.read.cache_clear()
    html = client.get("/contatti").text
    assert "DA COMPLETARE: PEC" in html
    assert "DA DEFINIRE: ruolo della responsabile commerciale" in html


def test_menu_links_contact(client):
    assert 'href="/contatti"' in client.get("/").text
    assert 'href="/en/contatti"' in client.get("/en/").text
