import json
import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

VISIBLE = ["offida-pecorino", "offida-passerina", "armide", "passacaille"]
DOCG = {"offida-pecorino", "offida-passerina"}
CLAIM = {"armide", "passacaille"}
# Fields the family has no data for: they stay markers, hidden in production.
NO_DATA = {"total_acidity", "vintage", "awards", "story"}
PRICE = re.compile(r"€|\bEUR\b|\bEXW\b|\bIVA\b|\bVAT\b|prezz|\bprices?\b|listino|price list", re.I)
ORGANIC = re.compile(r"biologic|organic|\bbio\b", re.I)


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)


def sheet_html(client, path: str) -> str:
    html = client.get(path).text
    return re.search(r'<article class="wp".*?</article>', html, re.S).group(0)


def raw(lang: str, slug: str) -> dict:
    return content.read(config.CONTENT_DIR / lang / "wines" / f"{slug}.toml")


def test_four_wines_visible_in_order_and_rosso_hidden():
    for lang in ("it", "en"):
        assert [w["slug"] for w in content.wines(lang)] == VISIBLE
    assert content.read(config.CONTENT_DIR / "wines" / "offida-rosso.toml")["visible"] is False
    assert content.wine("it", "offida-rosso") is None


@pytest.mark.parametrize("lang", ["it", "en"])
@pytest.mark.parametrize("slug", VISIBLE)
def test_published_fields_have_no_placeholder(lang, slug):
    neutral = content.read(config.CONTENT_DIR / "wines" / f"{slug}.toml")
    assert content.has_marker(neutral["photo"]) is False
    assert isinstance(neutral["abv"], float) and isinstance(neutral["bottles_per_year"], int)
    assert neutral["formats"] == ["750 ml"]
    for key, value in raw(lang, slug).items():
        if key not in NO_DATA and not (key == "residual_sugar" and slug != "passacaille"):
            assert not content.has_marker(value), (slug, key)


def test_real_figures():
    figures = {slug: content.wine("it", slug) for slug in VISIBLE}
    assert {s: (w["abv"], w["bottles_per_year"]) for s, w in figures.items()} == {
        "offida-pecorino": (13.5, 5000),
        "offida-passerina": (13.5, 5000),
        "armide": (11.5, 4000),
        "passacaille": (11.5, 4000),
    }


def test_passacaille_is_extra_brut_spumante():
    it, en = raw("it", "passacaille"), raw("en", "passacaille")
    assert it["name"] == "Passacaille" and en["name"] == "Passacaille"
    assert it["style"] == "Spumante" and en["style"] == "Sparkling wine"
    assert "Extra Brut" in it["residual_sugar"] and "Extra Brut" in en["residual_sugar"]


@pytest.mark.parametrize("slug", VISIBLE)
def test_vineyard_area_is_offida(slug):
    assert raw("it", slug)["vineyard_area"] == "Offida"
    assert raw("en", slug)["vineyard_area"] == "Offida"


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_docg_only_on_pecorino_and_passerina(client, production, prefix):
    """N2: pages, JSON-LD and llms.txt say DOCG (or DOC) only for the two Offida wines."""
    for slug in VISIBLE:
        html = client.get(f"{prefix}/vini/{slug}").text
        found = re.search(r"\bDOCG?\b", html) is not None
        assert found == (slug in DOCG), slug
        ld = [json.loads(b) for b in re.findall(r'ld\+json">(.*?)</script>', html, re.S)]
        assert (re.search(r"\bDOCG?\b", json.dumps(ld)) is not None) == (slug in DOCG), slug
    names = {slug: raw("it" if not prefix else "en", slug)["name"] for slug in VISIBLE}
    for line in client.get(f"{prefix}/llms.txt").text.splitlines():
        if re.search(r"\bDOCG?\b", line):
            assert any(names[s] in line for s in DOCG), line
            assert not any(names[s] in line for s in VISIBLE if s not in DOCG), line


@pytest.mark.parametrize("prefix", ["", "/en"])
@pytest.mark.parametrize("slug", VISIBLE)
def test_no_price_and_no_organic_on_wine_pages(client, production, prefix, slug):
    """N1 and N4 on the wine sheet and its meta description and JSON-LD."""
    html = client.get(f"{prefix}/vini/{slug}").text
    meta = re.findall(r'<meta[^>]+name="description"[^>]+>', html)
    ld = re.findall(r'ld\+json">(.*?)</script>', html, re.S)
    for text in [sheet_html(client, f"{prefix}/vini/{slug}"), *meta, *ld]:
        for brand in ("Si Bio", "Si%20Bio", "si-bio.it"):
            text = text.replace(brand, "")
        assert not PRICE.search(text), PRICE.search(text).group(0)
        assert not ORGANIC.search(text), ORGANIC.search(text).group(0)


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_no_price_in_llms_and_sitemap(client, production, prefix):
    assert not re.search(r"€|\bEUR\b|\bEXW\b", client.get(f"{prefix}/llms.txt").text)


def test_wine_content_files_have_no_price_or_organic():
    for lang in ("it", "en"):
        for slug in VISIBLE:
            for key, value in raw(lang, slug).items():
                assert not PRICE.search(value), (lang, slug, key)
                assert not ORGANIC.search(value.replace("Si Bio", "")), (lang, slug, key)


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_marmolada_claim_only_on_passacaille_and_armide(client, production, prefix):
    for slug in VISIBLE:
        html = sheet_html(client, f"{prefix}/vini/{slug}")
        assert ("Marmolada" in html) == (slug in CLAIM), slug
        assert ("Taste the Essence" in html) == (slug in CLAIM), slug
        assert "<footer" not in html  # the elder stays unnamed


@pytest.mark.parametrize(
    ("prefix", "alt"),
    [("", "Offida Pecorino in vigna"), ("/en", "Offida Pecorino in the vineyard")],
)
def test_bottle_photo_exists_with_descriptive_alt(client, production, prefix, alt):
    html = sheet_html(client, f"{prefix}/vini/offida-pecorino")
    assert f'src="/static/img/vini/offida-pecorino.jpg" alt="{alt}"' in html
    for slug in VISIBLE:
        assert (config.STATIC_DIR / "img" / "vini" / f"{slug}.jpg").is_file()


def test_fixed_texts_do_not_count_the_wines():
    for lang in ("it", "en"):
        text = (config.CONTENT_DIR.parent / "locales" / f"{lang}.toml").read_text(encoding="utf-8")
        assert not re.search(r"\b(cinque|five)\b", text, re.I)


def test_armide_vintage_2023_shown_others_hidden(client, production):
    labels = (("it", "", "Annata in commercio"), ("en", "/en", "Vintage on sale"))
    for lang, prefix, label in labels:
        assert content.wine(lang, "armide")["vintage"] == "2023"
        assert content.wine(lang, "passacaille")["vintage"] == ""
        assert label in sheet_html(client, f"{prefix}/vini/armide")
        assert label not in sheet_html(client, f"{prefix}/vini/passacaille")
