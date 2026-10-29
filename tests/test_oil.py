"""Oil page: brochure texts, the olive tree photo, never called organic; linked from the home."""

import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def preview(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    content.read.cache_clear()
    yield
    content.read.cache_clear()


def main_of(html):
    return re.search(r"<main.*?</main>", html, flags=re.S).group(0)


def text_of(html):
    html = main_of(html)
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def test_oil_page_has_the_brochure_texts(client, preview):
    it = text_of(client.get("/olio").text)
    assert "raccolte a mano" in it
    assert "estratto a freddo entro poche ore" in it
    assert "Fattoria nel Ciafone" in it
    en = text_of(client.get("/en/olio").text)
    assert "handpicked" in en
    assert "cold-extracted within hours" in en
    assert "Fattoria nel Ciafone" in en


def test_oil_placeholders_stay_in_preview(client, preview):
    html = client.get("/olio").text
    for field in ("cultivar", "acidità"):
        assert f"[DA VERIFICARE: {field}]" in html
    assert "[DA VERIFICARE: descrizione dell'olio]" not in html


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_oil_page_shows_the_olive_tree_photo(client, prefix):
    html = client.get(prefix + "/olio").text
    match = re.search(r'<img [^>]*src="(/static/img/olio/olivo\.jpg)"([^>]*)>', html)
    assert match, html
    assert 'width="1112"' in match.group(2) and 'height="616"' in match.group(2)
    assert re.search(r'alt="[^"]{10,}"', match.group(2))
    assert (config.STATIC_DIR / "img" / "olio" / "olivo.jpg").is_file()


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_oil_page_never_says_organic(client, preview, prefix):
    text = text_of(client.get(prefix + "/olio").text)
    for brand in ("Si Bio", "SI - BIO", "si-bio.it"):
        text = text.replace(brand, "")
    assert not re.search(r"biologic|organic|\bbio\b", text, re.I)
    assert "certificate" not in text.lower() and "certificato" not in text.lower()


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_oil_page_has_no_price(client, preview, prefix):
    assert "€" not in client.get(prefix + "/olio").text


@pytest.mark.parametrize(
    "prefix, href, link",
    [("", "/olio", "Scopri l'olio"), ("/en", "/en/olio", "Discover the oil")],
)
def test_home_links_to_the_oil_page(client, prefix, href, link):
    html = main_of(client.get(prefix + "/").text)
    assert f'href="{href}"' in html
    assert link.replace("'", "&#39;") in html or link in html
    tile = html[html.index(f'href="{href}"') - 400 : html.index(f'href="{href}"') + 100]
    assert not re.search(r"organic|biologic", tile, re.I)
