"""Task D: mission and territory in Home and About, the claim and the tagline in Home, no
`why_veneto`, the registered name and office, the regulation in the page language."""

import re
from html import unescape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NAME = "Si Bio di Premici Silvia e Aleandri Vincenzo, società semplice agricola"
OFFICE = "Contrada San Lazzaro 118, 63073 Offida"
MISSION = {
    "": "La nostra missione è produrre vini che esprimano l'identità autentica del Piceno",
    "/en": "Our mission is to produce wines that express the authentic identity of the Piceno",
}
TERRITORY = {
    "": "Il Piceno è una terra di colline, vigneti e antiche tradizioni agricole",
    "/en": "The Piceno is a land of hills, vineyards and old farming traditions",
}
CLAIM = {
    "": "L'uva deve essere raccolta vicino al mare e vinificata in Marmolada.",
    "/en": "Grapes should be picked by the sea and made into wine in the Marmolada.",
}
# a wine, the oil or the grapes called organic (same rule as tests/test_certificate.py)
WRONG = re.compile(
    r"(vin[oi]|olio|uv[ae]|wines?|oil|grapes?)[ -]+(\w+[ -]+){0,2}(biologic\w*|organic)"
    r"|(biologic\w*|organic)[ -]+(\w+[ -]+){0,1}(vin[oi]|olio|uv[ae]|wines?|oil|grapes?)",
    re.I,
)


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)
    monkeypatch.setattr(config, "BASE_URL", "https://www.si-bio.it")
    content.read.cache_clear()
    yield
    content.read.cache_clear()


def main_text(html):
    main = re.search(r"<main.*?</main>", html, re.S).group(0)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", main)))


@pytest.mark.parametrize("prefix", ["", "/en"])
@pytest.mark.parametrize("path", ["/", "/chi-siamo"])
def test_mission_and_territory_in_production(client, production, prefix, path):
    flat = main_text(client.get(f"{prefix}{path}".replace("//", "/")).text)
    assert MISSION[prefix] in flat
    assert TERRITORY[prefix] in flat


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_mission_does_not_say_organic(production, prefix):
    lang = prefix.strip("/") or "it"
    about = content.page(lang, "about")
    for key in ("mission", "territory"):
        assert not re.search(r"biologic|organic|\bbio\b", about[key], re.I), key


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_no_wine_oil_or_grapes_called_organic(client, production, prefix):
    for path in ("/", "/chi-siamo"):
        flat = main_text(client.get(f"{prefix}{path}".replace("//", "/")).text)
        assert not WRONG.search(flat), (prefix + path, WRONG.search(flat).group(0))


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_about_what_ends_before_the_certified_block(client, production, prefix):
    html = client.get(f"{prefix}/chi-siamo").text
    what = re.search(
        r'<p class="lead">(Our wines from Piceno grapes and an olive oil\.'
        r"|I nostri vini[^<]*olio\.)</p>",
        html,
    )
    assert what, "about.what must end with a full stop in its own paragraph"
    assert html.index('id="certificato"') > what.end()


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_home_tagline_without_attribution_and_claim_in_movement_two(client, production, prefix):
    html = re.sub(r"<template.*?</template>", "", client.get(f"{prefix}/").text, flags=re.S)
    quote = re.search(r"<blockquote.*?</blockquote>", html, re.S).group(0)
    assert "Taste the Essence" in quote and CLAIM[prefix] not in unescape(quote)
    assert "<footer" not in quote
    movement = re.search(r'<li class="movement movement-2">.*?</li>', html, re.S).group(0)
    assert CLAIM[prefix] in unescape(movement)


def test_why_veneto_is_gone():
    for lang in ("it", "en"):
        assert "why_veneto" not in content.read(config.CONTENT_DIR / lang / "pages" / "about.toml")
        assert "who" not in content.read(config.CONTENT_DIR / lang / "pages" / "home.toml")
    assert "Veneto" not in (Path(config.APP_DIR) / "templates/about.html").read_text()


def test_wine_pages_still_carry_the_claim_only_on_two_wines(client, production):
    for slug, has in (("armide", True), ("passacaille", True), ("offida-pecorino", False)):
        assert ("Marmolada" in client.get(f"/vini/{slug}").text) == has, slug


def test_registered_name_and_office():
    company = content.site_raw()["company"]
    assert company["name"] == NAME
    assert company["address"] == OFFICE
    assert company["vat"] == "02274900444"


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_name_in_footer_and_legal_pages(client, production, prefix):
    assert NAME in unescape(client.get(f"{prefix}/").text)
    assert NAME in unescape(client.get(f"{prefix}/info/note-legali").text)


@pytest.mark.parametrize(
    ("prefix", "expected"), [("", "Reg. (UE) 2018/848"), ("/en", "Reg. (EU) 2018/848")]
)
def test_regulation_follows_the_page_language(client, production, prefix, expected):
    flat = main_text(client.get(f"{prefix}/chi-siamo").text)
    assert expected in flat
    other = "Reg. (EU)" if prefix == "" else "Reg. (UE)"
    assert other not in flat
    assert expected in client.get(f"{prefix}/llms.txt").text
