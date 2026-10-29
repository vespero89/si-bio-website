import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

PAGES = ["/", "/olio", "/chi-siamo"]
RIVA = "Riva dei Martin"


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


def visible_text(html):
    return re.sub(r"<[^>]+>", " ", html)


@pytest.mark.parametrize("prefix", ["", "/en"])
@pytest.mark.parametrize("path", PAGES)
def test_pages_answer_with_one_h1(client, path, prefix):
    response = client.get(prefix + (path if path != "/" else "/"))
    assert response.status_code == 200
    assert response.text.count("<h1") == 1


@pytest.mark.parametrize("path", PAGES)
def test_no_placeholder_in_production(client, production, path):
    for prefix in ("", "/en"):
        html = client.get(prefix + path).text
        assert not re.search(
            r"DA (VERIFICARE|COMPLETARE|DEFINIRE)|TO BE (VERIFIED|COMPLETED|DEFINED)", html
        )


def test_preview_shows_placeholders(client, preview):
    assert "DA VERIFICARE" in client.get("/chi-siamo").text
    assert "DA VERIFICARE" in client.get("/olio").text
    assert "DA DEFINIRE" in client.get("/").text
    assert "TO BE DEFINED" in client.get("/en/").text


@pytest.mark.parametrize("path", PAGES)
def test_riva_off_by_default(client, path):
    assert content.site()["switches"]["riva_dei_martin"] is False
    for prefix in ("", "/en"):
        assert RIVA not in client.get(prefix + path).text


def test_riva_on_shows_sentence(client, monkeypatch):
    real = content.site()
    switched = {**real, "switches": {**real["switches"], "riva_dei_martin": True}}
    monkeypatch.setattr(
        content,
        "read",
        lambda path, _r=content.read: switched if path.name == "site.toml" else _r(path),
    )
    assert "Vincenzo Aleandri guida anche Riva dei Martin" in client.get("/chi-siamo").text
    assert "Vincenzo Aleandri also runs Riva dei Martin" in client.get("/en/chi-siamo").text


ORGANIC_FARM = re.compile(
    r"azienda (agricola )?biologica|organic farm|certificat|organic cert", re.I
)


def test_organic_only_as_the_certified_farm(client, production):
    """With the switch on the farm and its certificate may be called organic; a wine, the oil or
    the grapes never (tests/test_certificate.py checks the exact phrases)."""
    for path in PAGES:
        for prefix in ("", "/en"):
            text = visible_text(
                re.sub(r"<script.*?</script>", "", client.get(prefix + path).text, flags=re.S)
            )
            for brand in ("Si Bio", "SI - BIO", "si-bio.it"):
                text = text.replace(brand, "")
            text = re.sub(r"IT-BIO-[\w.-]+", "", text)  # the certificate number
            for found in re.findall(
                r"[\w ]{0,30}(?:biologic|organic|\bbio\b)[\w ]{0,30}", text, re.I
            ):
                assert ORGANIC_FARM.search(found), (prefix + path, found)


def test_switch_off_keeps_the_total_ban_on_organic(client, production, monkeypatch):
    real = content.site()
    off = {**real, "switches": {**real["switches"], "organic_certified": False}}
    original = content.read

    def read(path):
        return off if path.name == "site.toml" else original(path)

    read.cache_clear = original.cache_clear
    monkeypatch.setattr(content, "read", read)
    for path in PAGES:
        for prefix in ("", "/en"):
            text = (
                visible_text(client.get(prefix + path).text)
                .replace("Si Bio", "")
                .replace("SI - BIO", "")
                .replace("si-bio.it", "")
            )
            assert not re.search(r"biologic|organic|\bbio\b", text, re.I)


def test_home_production_content(client, production):
    html = client.get("/").text
    assert "Le radici di Si Bio sono alla" in html
    for slug in (
        "armide",
        "offida-pecorino",
        "offida-passerina",
        "passacaille",
    ):
        assert f'href="/vini/{slug}"' in html
    assert 'href="/vini/offida-rosso"' not in html  # hidden until sheet and photo arrive
    assert 'href="/olio"' in html and 'href="/visite"' in html and 'href="/contatti"' in html
    assert "<blockquote" in html and "<footer>" not in html  # the claim, with no attribution


def test_home_claim_quotation_in_preview(client, preview):
    assert "<blockquote" in client.get("/").text


def test_olio_mailto_subject(client):
    html = client.get("/olio").text
    assert "mailto:export.sibio@gmail.com?subject=Si%20Bio%3A%20olio" in html
    assert "mailto:export.sibio@gmail.com?subject=Si%20Bio%3A%20oil" not in html
    assert "subject=Si%20Bio%3A%20oil" in client.get("/en/olio").text


def test_about_production_has_family_and_company(client, production):
    html = client.get("/chi-siamo").text
    assert "<h1>Chi siamo</h1>" in html
    assert "Le radici di Si Bio sono alla" in html
    assert "Si Bio di Premici Silvia e Aleandri Vincenzo, società semplice agricola" in html
    assert 'aria-current="page"' in html


def test_oil_and_contact_pages_use_the_page_head(client):
    for path, eyebrow in (
        ("/olio", "Extravergine di oliva"),
        ("/en/olio", "Extra virgin olive oil"),
    ):
        html = client.get(path).text
        assert 'class="wrap page-head oil-page"' in html
        assert f'<p class="eyebrow">{eyebrow}</p>' in html
        assert html.count("<h1") == 1
        assert "data-inline" in html
    contact = client.get("/contatti").text
    assert 'class="wrap page-head contact-page"' in contact
    assert "data-inline" in contact


def test_dialog_focus_does_not_scroll_the_sheet():
    script = (config.STATIC_DIR / "js" / "wine-dialog.js").read_text()
    assert "preventScroll: true" in script
