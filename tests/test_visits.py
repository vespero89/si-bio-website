import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)
SLOT = re.compile(r'<div class="video-slot".*?</div>', re.S)

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
    assert "mailto:export.sibio@gmail.com?subject=Si%20Bio%3A%20" in response.text
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
        assert "youtube" not in SLOT.sub("", NOTICE.sub("", html)).lower()
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


INCLUDES = {
    "it": [
        "Incontri con importatori e partner",
        "Ospitalità all'Hotel Il Casale, con pasti e pernottamento",
        "Transfer da e per l'aeroporto",
        "Degustazioni ed esperienze sul territorio",
    ],
    "en": [
        "Meetings with importers and partners",
        "Hospitality at Hotel Il Casale, with meals and overnight stay",
        "Transfers to and from the airport",
        "Tastings and experiences in the territory",
    ],
}
HOTEL_URL = "https://www.hotelcasale.it/"
MONEY = re.compile(r"€|\bEUR\b|\bEXW\b|\bIVA\b|\bVAT\b|prezz|\bprices?\b|anticip|prepay", re.I)


@pytest.mark.parametrize(("lang", "prefix"), [("it", ""), ("en", "/en")])
def test_buyers_includes_list_of_four(client, production, lang, prefix):
    html = client.get(prefix + "/visite").text
    block = re.search(r'<div class="includes">.*?<ol>(.*?)</ol>', html, re.S).group(1)
    assert re.findall(r"<li>(.*?)</li>", block, re.S) == [
        s.replace("'", "&#39;") for s in INCLUDES[lang]
    ]
    assert content.page(lang, "visits")["buyers_includes"] == INCLUDES[lang]


def test_hotel_description_and_link(client, production):
    for prefix, name in (("", "Hotel Il Casale"), ("/en", "Hotel Il Casale")):
        html = client.get(prefix + "/visite").text
        para = re.search(r'<p class="hotel">(.*?)</p>', html, re.S).group(1)
        assert name in para
        assert "Colli del Tronto" in para
        assert f'href="{HOTEL_URL}"' in para
        assert 'rel="noopener"' in para
        assert "[" not in para


def test_price_list_row_mailto(client, production):
    it = client.get("/visite").text
    row = re.search(r'<p class="price">(.*?)</p>', it, re.S).group(1)
    assert "Listino su richiesta" in row
    assert "mailto:export.sibio@gmail.com?subject=Si%20Bio%3A%20listino" in row
    en = client.get("/en/visite").text
    row = re.search(r'<p class="price">(.*?)</p>', en, re.S).group(1)
    assert "Price list on request" in row
    assert "mailto:export.sibio@gmail.com?subject=Si%20Bio%3A%20price%20list" in row


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_buyers_block_has_no_price_or_terms(client, production, prefix):
    html = client.get(prefix + "/visite").text
    block = re.search(r'<section class="buyers".*?</section>', html, re.S).group(0)
    text = re.sub(r"<[^>]+>", " ", block)
    assert not MONEY.search(text.replace("Listino su richiesta", "").replace("Price list on", ""))
    assert not re.search(r"biologic|organic|\bbio\b|conto terzi|contract", text, re.I)


def test_package_hotel_name_unlocked(client, production):
    page = content.page("it", "visits")
    assert "Hotel Il Casale" in page["package_hotel"]
    assert "Hotel Il Casale" in content.page("en", "visits")["package_hotel"]


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_llms_txt_lists_the_four_programme_items(client, production, prefix):
    items = content.page("en" if prefix else "it", "visits")["buyers_includes"]
    assert len(items) == 4
    text = client.get(f"{prefix}/llms.txt").text
    for item in items:
        assert f"  - {item}" in text
    assert text.index(items[0]) > text.index("/visite")


@pytest.mark.parametrize("mode", ["production", "preview"])
def test_llms_txt_never_prints_a_programme_marker(client, request, monkeypatch, mode):
    request.getfixturevalue(mode)
    patch(monkeypatch, visits={"buyers_includes": ["Transfer", "[DA COMPLETARE: voce]"]})
    text = client.get("/llms.txt").text
    assert "DA COMPLETARE" not in text
    assert ("  - Transfer" in text) == (mode == "preview")


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_visits_page_uses_the_new_layout(client, production, prefix):
    html = client.get(prefix + "/visite").text
    assert re.search(r'<div class="wrap page-head">\s*<p class="eyebrow">[^<]+</p>\s*<h1>', html)
    assert html.count("<h1") == 1
    assert '<section class="buyers"' in html
    assert '<div class="includes">' in html
    assert "visits-" not in html
    assert 'class="eyebrow">' + ("Su invito" if not prefix else "By invitation") in html
