import json
import re
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app import config, content, i18n, jsonld
from app.main import app

SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
XH = "{http://www.w3.org/1999/xhtml}"
MARKER = re.compile(r"\[(?:DA |TO BE )[A-Z ]+\b")
SLUGS = ["armide", "offida-passerina", "offida-pecorino", "passacaille"]
STATIC_PAGES = ["/", "/vini", "/olio", "/chi-siamo", "/visite", "/contatti"]
LEGAL = ["/info/note-legali", "/info/privacy", "/info/cookie"]


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


@pytest.fixture
def preview(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    content.read.cache_clear()
    yield
    content.read.cache_clear()


def entries(client):
    root = ET.fromstring(client.get("/sitemap.xml").text)
    out = {}
    for url in root.findall(f"{SM}url"):
        alts = {a.get("hreflang"): a.get("href") for a in url.findall(f"{XH}link")}
        out[url.find(f"{SM}loc").text] = (url, alts)
    return out


def test_sitemap_lists_every_page_in_every_published_language(client, production):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    found = entries(client)
    paths = STATIC_PAGES + [f"/vini/{s}" for s in SLUGS] + LEGAL
    base = "https://www.si-bio.it"
    for path in paths:
        it = base + path
        en = base + ("/en" + path if path != "/" else "/en/")
        assert it in found and en in found
        for loc in (it, en):
            alts = found[loc][1]
            assert alts == {"it": it, "en": en, "x-default": en}


def test_sitemap_has_no_lastmod_and_no_unpublished_language(client, production, monkeypatch):
    monkeypatch.setattr(config, "PUBLISHED", ("it",))
    text = client.get("/sitemap.xml").text
    assert "lastmod" not in text
    assert "/en" not in text
    found = entries(client)
    assert all(alts == {"it": loc, "x-default": loc} for loc, (_, alts) in found.items())


def test_sitemap_leaves_out_hidden_wines(client, production, monkeypatch):
    real = content.wines
    monkeypatch.setattr(
        content, "wines", lambda lang: [w for w in real(lang) if w["slug"] != "armide"]
    )
    assert "/vini/armide" not in client.get("/sitemap.xml").text
    assert "/vini/offida-pecorino" in client.get("/sitemap.xml").text
    assert "/vini/offida-rosso" not in client.get("/sitemap.xml").text


def test_sitemap_only_in_italian_root(client, production):
    assert client.get("/en/sitemap.xml").status_code == 404
    assert client.get("/en/robots.txt").status_code == 404


def test_robots_production_is_open_with_sitemap(client, production):
    response = client.get("/robots.txt")
    assert response.headers["content-type"].startswith("text/plain")
    assert "Disallow: /\n" not in response.text + "\n"
    assert "Sitemap: https://www.si-bio.it/sitemap.xml" in response.text
    assert "x-robots-tag" not in response.headers
    assert "noindex" not in client.get("/").text


def test_preview_blocks_indexing_everywhere(client, preview):
    assert re.search(r"^Disallow: /$", client.get("/robots.txt").text, re.M)
    assert "Sitemap:" not in client.get("/robots.txt").text
    for path in ("/", "/en/vini", "/robots.txt", "/sitemap.xml", "/llms.txt", "/nope"):
        assert client.get(path).headers["x-robots-tag"] == "noindex"
    assert re.search(r'<meta name="robots" content="noindex', client.get("/olio").text)


@pytest.mark.parametrize("lang,prefix", [("it", ""), ("en", "/en")])
def test_head_has_title_description_open_graph(client, production, lang, prefix):
    html = client.get(f"{prefix}/vini/armide").text
    head = html.split("</head>")[0]
    desc = re.search(r'<meta name="description" content="([^"]+)"', head)
    assert desc and desc.group(1).strip()
    og = dict(re.findall(r'<meta property="(og:[a-z:_]+)" content="([^"]*)"', head))
    assert og["og:site_name"] == "Si Bio"
    assert og["og:url"] == f"https://www.si-bio.it{prefix}/vini/armide"
    assert og["og:title"] == re.search(r"<title>(.*?)</title>", head).group(1)
    assert og["og:description"] == desc.group(1)
    assert og["og:locale"] == i18n.t(lang, "meta.locale")
    assert 'name="twitter:card"' in head


def test_description_comes_from_the_content_with_fallback(client, production, monkeypatch):
    monkeypatch.setattr(config, "BASE_URL", "http://x")
    real = content.wine
    # A description still a marker is empty in production: the locale fallback is used.
    monkeypatch.setattr(content, "wine", lambda lang, s: {**real(lang, s), "description": ""})
    html = client.get("/vini/armide").text
    fallback = i18n.t("it", "meta.default")
    assert f'<meta name="description" content="{fallback}">' in html

    def with_text(lang, slug):
        w = real(lang, slug)
        return {**w, "description": "Prima frase vera. Seconda frase."} if w else w

    monkeypatch.setattr(content, "wine", with_text)
    html = client.get("/vini/armide").text
    assert '<meta name="description" content="Prima frase vera.">' in html


def test_wine_image_in_open_graph_only_when_there_is_a_photo(client, production, monkeypatch):
    real = content.wine
    monkeypatch.setattr(content, "wine", lambda lang, s: {**real(lang, s), "photo": ""})
    assert 'property="og:image"' not in client.get("/vini/armide").text
    monkeypatch.setattr(content, "wine", lambda lang, s: {**real(lang, s), "photo": "a.png"})
    html = client.get("/vini/armide").text
    assert 'property="og:image" content="https://www.si-bio.it/static/img/vini/a.png"' in html


def blocks(html):
    out = []
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        assert "<" not in raw
        out.append(json.loads(raw))
    return out


def test_home_has_organization_and_website(client, production):
    data = blocks(client.get("/").text)
    types = [d["@type"] for d in data]
    assert types == ["Organization", "WebSite"]
    org = data[0]
    assert org["@context"] == "https://schema.org"
    assert org["name"] == "Si Bio"
    assert (
        org["legalName"]
        == "Si Bio di Premici Silvia e Aleandri Vincenzo, società semplice agricola"
    )
    assert org["vatID"] == "IT02274900444"
    assert org["email"] == "export.sibio@gmail.com"
    assert "sameAs" not in org
    assert org["address"]["streetAddress"] == "Contrada San Lazzaro 118, 63073 Offida"
    assert data[1]["url"] == "https://www.si-bio.it/"
    assert blocks(client.get("/en/").text)[1]["url"] == "https://www.si-bio.it/en/"


def test_json_ld_never_holds_a_placeholder(client, preview):
    for path in ("/", "/vini/armide", "/olio", "/en/vini/armide"):
        for raw in re.findall(r"ld\+json\">(.*?)</script>", client.get(path).text, re.S):
            assert not MARKER.search(raw), path


def test_same_as_only_when_set(client, production, monkeypatch):
    site = {**content.site_raw()}
    site["social"] = {"instagram": "https://instagram.com/sibio", "facebook": ""}
    monkeypatch.setattr(content, "site_raw", lambda: site)
    assert blocks(client.get("/").text)[0]["sameAs"] == ["https://instagram.com/sibio"]


def test_wine_has_product_without_offer_and_breadcrumb(client, production):
    data = blocks(client.get("/vini/armide").text)
    product, crumbs = data
    assert product["@type"] == "Product"
    assert product["name"] == "Armide"
    assert product["brand"] == {"@type": "Brand", "name": "Si Bio"}
    assert "offers" not in json.dumps(data)
    assert product["url"] == "https://www.si-bio.it/vini/armide"
    assert crumbs["@type"] == "BreadcrumbList"
    items = crumbs["itemListElement"]
    assert [i["position"] for i in items] == [1, 2, 3]
    assert items[-1]["item"] == "https://www.si-bio.it/vini/armide"
    assert items[1]["item"] == "https://www.si-bio.it/vini"
    en = blocks(client.get("/en/vini/armide").text)[1]["itemListElement"]
    assert en[-1]["item"] == "https://www.si-bio.it/en/vini/armide"


def test_oil_and_index_structured_data(client, production):
    oil = blocks(client.get("/olio").text)
    assert [d["@type"] for d in oil] == ["Product", "BreadcrumbList"]
    assert "offers" not in json.dumps(oil)
    assert blocks(client.get("/vini").text) == []
    for path in ("/contatti", "/chi-siamo", "/visite", "/info/privacy"):
        assert blocks(client.get(path).text) == []


def test_jsonld_helpers():
    assert jsonld.clean({"a": "", "b": [None, {"c": []}], "d": {"e": "x"}}) == {"d": {"e": "x"}}
    assert "<" not in jsonld.dumps({"a": "</script><!--"})
    assert "\\u003c/script>" in jsonld.dumps({"a": "</script>"})


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_llms_txt_per_language(client, production, prefix):
    response = client.get(f"{prefix}/llms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert text.startswith("# Si Bio")
    assert "export.sibio@gmail.com" in text
    for slug in SLUGS:
        assert f"https://www.si-bio.it{prefix}/vini/{slug}" in text
    assert f"https://www.si-bio.it{prefix}/olio" in text
    assert not MARKER.search(text)
    assert "Riva dei Martin" not in text


def test_llms_txt_in_preview_still_has_no_placeholder(client, preview):
    assert not MARKER.search(client.get("/llms.txt").text)
    assert not MARKER.search(client.get("/en/llms.txt").text)


def test_llms_unpublished_language_is_404(client, production, monkeypatch):
    monkeypatch.setattr(config, "PUBLISHED", ("it",))
    assert client.get("/en/llms.txt").status_code == 404


def test_meta_keys_exist_in_every_language():
    for lang in config.LANGS:
        for key in ("meta.default", "meta.locale", "llms.summary"):
            assert i18n.load(lang).get(key), (lang, key)
