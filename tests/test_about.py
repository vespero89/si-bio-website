"""About page on the new design: page head, split blocks, the Silvia music section, the certificate
as a sheet and the family line on the dark band."""

import re
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import config, content, i18n
from app.main import app

SILVIA = {
    "": ("Silvia Premici, socia di Si Bio", "Lully", "1686", "colonna sonora"),
    "/en": ("Silvia Premici is a partner of Si Bio", "Lully", "1686", "soundtrack"),
}


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


def flat(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_page_head_and_split(client, production, prefix):
    html = client.get(f"{prefix}/chi-siamo").text
    assert re.search(r'<div class="wrap page-head">\s*<p class="eyebrow">', html)
    assert html.count("<h1") == 1
    assert '<p class="lead">' in html
    assert re.search(r'<div class="wrap split split-bordered">\s*<div class="prose">', html)
    assert 'class="ph ph-portrait"' in html


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_silvia_section_before_the_certificate(client, production, prefix):
    html = client.get(f"{prefix}/chi-siamo").text
    section = re.search(r'<section class="silvia".*?</section>', html, re.S).group(0)
    assert html.index('class="silvia"') < html.index('id="certificato"')
    assert 'class="watermark"' in section
    assert re.search(r'<span class="ph ph-portrait">', section)
    assert "<h2" in section and 'class="eyebrow"' in section
    link = re.search(r'<a class="text-link" href="([^"]+)"', section).group(1)
    assert link == f"{prefix}/visite#video"
    text = flat(section)
    for fragment in SILVIA[prefix]:
        assert fragment in text
    assert not re.search(r"biologic|organic|Veneto", text, re.I)


@pytest.mark.parametrize("lang", ["it", "en"])
def test_music_texts_are_plain_facts(lang):
    about = content.page(lang, "about")
    assert about["music_title"] and about["music"]
    assert about["music"].count("\n\n") == 2
    assert not content.has_marker(about["music"])
    assert "Passacaille" in about["music"] and "Armide" in about["music"]


def test_music_locale_keys_in_both_languages():
    for lang in ("it", "en"):
        for key in ("about.music_label", "about.music_link"):
            assert i18n.t(lang, key) != key
    assert i18n.missing("en") == []


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_certificate_is_a_sheet_with_the_qr(client, production, prefix):
    html = client.get(f"{prefix}/chi-siamo").text
    block = re.search(r'<section[^>]*id="certificato".*?</section>', html, re.S).group(0)
    assert block.count("<dt>") == 5 and block.count("<dd>") == 5
    assert '<dl class="sheet">' in block
    assert 'class="certificate-qr"' in block
    assert 'class="sentence"' in block and 'class="eyebrow"' in block
    assert 'class="text-link"' in block


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_family_line_is_on_the_dark_band(client, production, prefix):
    html = client.get(f"{prefix}/chi-siamo").text
    band = re.search(r'<section class="band band-dark".*?</section>', html, re.S).group(0)
    assert '<p class="family">' in band
    assert ("since 1915" if prefix else "dal 1915") in band
    assert 'class="button"' in band and "/contatti" in band
    assert html.index('class="certificate"') < html.index("band-dark")


def test_silvia_stays_when_the_certificate_switch_is_off(client, production, monkeypatch):
    original = content.site()
    switches = {**original["switches"], "organic_certified": False}
    monkeypatch.setattr(content, "site", lambda: {**original, "switches": switches})
    html = client.get("/chi-siamo").text
    assert 'id="certificato"' not in html
    assert 'class="silvia"' in html
