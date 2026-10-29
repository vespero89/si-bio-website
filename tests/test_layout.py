import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def links(html: str, tag: str) -> list[dict]:
    """Attributes of every <tag ...> in the html, as dicts."""
    out = []
    for raw in re.findall(rf"<{tag}\b([^>]*)>", html):
        out.append(dict(re.findall(r'([\w-]+)="([^"]*)"', raw)))
    return out


def test_menu_links_in_italian(client):
    html = client.get("/").text
    nav = re.search(r'<nav class="menu".*?</nav>', html, re.S).group(0)
    hrefs = [a["href"] for a in links(nav, "a")]
    assert hrefs == ["/vini", "/olio", "/chi-siamo", "/visite", "/contatti"]
    for label in ("Vini", "Olio", "Chi siamo", "Visite e pacchetti", "Contatti"):
        assert f">{label}<" in nav


def test_menu_links_in_english_carry_the_prefix(client):
    html = client.get("/en/").text
    nav = re.search(r'<nav class="menu".*?</nav>', html, re.S).group(0)
    hrefs = [a["href"] for a in links(nav, "a")]
    assert hrefs == ["/en/vini", "/en/olio", "/en/chi-siamo", "/en/visite", "/en/contatti"]
    assert ">Visits and packages<" in nav


def test_header_has_wordmark_linking_home(client):
    assert '<a class="brand" href="/">' in client.get("/").text
    assert '<a class="brand" href="/en/">' in client.get("/en/").text


def test_language_selector_links_to_same_page_in_each_language(client):
    html = client.get("/").text
    sel = re.search(r'<nav class="lang".*?</nav>', html, re.S).group(0)
    anchors = links(sel, "a")
    assert [(a["lang"], a["hreflang"], a["href"]) for a in anchors] == [
        ("it", "it", "/?lang=it"),
        ("en", "en", "/en/?lang=en"),
    ]
    assert ">Italiano<" in sel and ">English<" in sel
    assert 'aria-current="true"' in sel


def test_language_selector_from_english_page(client):
    sel = re.search(r'<nav class="lang".*?</nav>', client.get("/en/").text, re.S).group(0)
    hrefs = [a["href"] for a in links(sel, "a")]
    assert hrefs == ["/?lang=it", "/en/?lang=en"]


def test_selector_lists_only_published_languages(client, monkeypatch):
    monkeypatch.setattr(config, "PUBLISHED", ("it",))
    sel = re.search(r'<nav class="lang".*?</nav>', client.get("/").text, re.S).group(0)
    assert "English" not in sel


def test_canonical_and_hreflang_italian(client):
    html = client.get("/").text
    canonical = [a for a in links(html, "link") if a.get("rel") == "canonical"]
    assert [c["href"] for c in canonical] == [config.BASE_URL + "/"]
    alt = {a["hreflang"]: a["href"] for a in links(html, "link") if a.get("rel") == "alternate"}
    assert alt == {
        "it": config.BASE_URL + "/",
        "en": config.BASE_URL + "/en/",
        "x-default": config.BASE_URL + "/en/",
    }


def test_canonical_of_english_page_is_its_own_url(client):
    html = client.get("/en/").text
    canonical = [a["href"] for a in links(html, "link") if a.get("rel") == "canonical"]
    assert canonical == [config.BASE_URL + "/en/"]


def test_hreflang_follows_published_languages(client, monkeypatch):
    monkeypatch.setattr(config, "PUBLISHED", ("it",))
    html = client.get("/").text
    alt = {a["hreflang"]: a["href"] for a in links(html, "link") if a.get("rel") == "alternate"}
    assert alt == {"it": config.BASE_URL + "/", "x-default": config.BASE_URL + "/"}


def test_footer_company_data(client):
    html = client.get("/").text
    footer = re.search(r"<footer.*?</footer>", html, re.S).group(0)
    assert "Si Bio di Premici Silvia e Aleandri Vincenzo, società semplice agricola" in footer
    assert "02274900444" in footer
    assert 'href="mailto:export.sibio@gmail.com"' in footer
    assert "Fattoria nel Ciafone" in footer


def test_footer_farm_link_only_when_the_address_is_known(client, monkeypatch):
    html = client.get("/").text
    assert "Fattoria nel Ciafone" in html and "<a" in html
    assert 'rel="noopener"' not in html  # marker address: the name is plain text
    real = content.site()
    real["farm"] = {"url": "https://farm.example/"}
    monkeypatch.setattr(content, "site", lambda: real)
    it = client.get("/").text
    en = client.get("/en/").text
    assert 'href="https://farm.example/"' in it
    assert 'href="https://farm.example/en/"' in en


def test_pages_have_landmarks_and_one_h1(client):
    for path in ("/", "/en/"):
        html = client.get(path).text
        for tag in ("<header", "<main", "<footer"):
            assert html.count(tag) == 1
        assert len(re.findall(r"<h1\b", html)) == 1


def test_no_external_resource_in_the_html(client):
    for path in ("/", "/en/"):
        html = client.get(path).text
        for tag, attr in (("link", "href"), ("script", "src"), ("img", "src")):
            for a in links(html, tag):
                if a.get("rel") in ("canonical", "alternate"):
                    continue
                assert not re.match(r"(https?:)?//", a.get(attr, "")), (path, tag, a)
        assert "fonts.googleapis" not in html


def test_stylesheet_is_one_file_with_palette_in_root_and_local_fonts(client):
    html = client.get("/").text
    sheets = [a["href"] for a in links(html, "link") if a.get("rel") == "stylesheet"]
    assert len(sheets) == 1 and sheets[0].startswith("/static/css/")
    css = client.get(sheets[0]).text
    assert ":root" in css
    urls = re.findall(r"url\(([^)]+)\)", css)
    assert urls and all(u.strip("'\"").startswith("/static/fonts/") for u in urls)
    for u in urls:
        assert client.get(u.strip("'\"")).status_code == 200


def test_font_licenses_ship_with_the_fonts():
    fonts = config.STATIC_DIR / "fonts"
    assert list(fonts.glob("*OFL*.txt"))
    assert all(f.stat().st_size > 0 for f in fonts.glob("*.woff2"))
