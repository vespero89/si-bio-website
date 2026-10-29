"""Organic certificate: the `organic_certified` switch and `[certificate]` of site.toml rule the
block in About, the line in the home, the footer link, the JSON-LD and llms.txt. The word
"organic" only ever describes the farm, never a wine, the oil or the grapes."""

import copy
import json
import re
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NUMBER = "IT-BIO-004.380-0031262.2026.004"
PAGES = ["/", "/chi-siamo", "/visite", "/contatti", "/olio", "/vini/armide", "/vini/passacaille"]
WINES = ["/vini/offida-pecorino", "/vini/offida-passerina", "/vini/armide", "/vini/passacaille"]
ORGANIC = re.compile(r"biologic|organic|\bbio\b", re.I)
# a wine, the oil or the grapes called organic, in either order, in either language
# (words are separated by spaces only: a full stop or a new block is not a phrase)
WRONG = re.compile(
    r"(vin[oi]|olio|uv[ae]|wines?|oil|grapes?)[ -]+(\w+[ -]+){0,2}(biologic\w*|organic)"
    r"|(biologic\w*|organic)[ -]+(\w+[ -]+){0,1}(vin[oi]|olio|uv[ae]|wines?|oil|grapes?)",
    re.I,
)
BRANDS = ("Si Bio", "SI - BIO", "si-bio.it", "Si%20Bio")


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


def patch_site(monkeypatch, switch=None, **certificate):
    """Reads site.toml with the switch and the certificate values changed."""
    real = copy.deepcopy(content.read(config.CONTENT_DIR / "site.toml"))
    if switch is not None:
        real["switches"]["organic_certified"] = switch
    real["certificate"].update(certificate)
    original = content.read

    def read(path):
        return real if path.name == "site.toml" else original(path)

    read.cache_clear = original.cache_clear
    monkeypatch.setattr(content, "read", read)


def text(html):
    for brand in BRANDS:
        html = html.replace(brand, "")
    return re.sub(r"<[^>]+>", " ", html)


def plain(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def main_text(html):
    """The page without its header and footer."""
    return text(re.search(r"<main.*?</main>", html, re.S).group(0))


def blocks(html):
    return [json.loads(b) for b in re.findall(r'ld\+json">(.*?)</script>', html, re.S)]


def test_real_settings_have_the_certificate(production):
    site = content.site()
    assert site["switches"]["organic_certified"] is True
    cert = site["certificate"]
    assert cert["number"] == NUMBER
    assert cert["body"] == "Suolo e Salute Srl (IT-BIO-004)"
    assert cert["regulation"] == "Reg. (UE) 2018/848"
    assert (cert["valid_from"], cert["valid_until"]) == ("2026-08-25", "2029-08-24")
    assert cert["verify_url"].startswith("https://webgate.ec.europa.eu/")
    assert cert["verify_url"].endswith(NUMBER + ".pdf")
    assert (
        cert["holder"] == "Si Bio di Premici Silvia e Aleandri Vincenzo, società semplice agricola"
    )
    assert cert["holder_address"] == "Contrada San Lazzaro 118, 63073 Offida"
    assert cert["qr"] == "certificate-qr.svg"


def test_about_block_in_italian(client, production):
    html = client.get("/chi-siamo").text
    assert html.count('id="certificato"') == 1
    block = re.search(r'<section[^>]*id="certificato".*?</section>', html, re.S).group(0)
    flat = plain(block)
    assert "Azienda biologica certificata" in flat
    assert "Il certificato riguarda la coltivazione di uva, olive e cereali." in flat
    assert f"Certificato n. {NUMBER}" in flat
    assert "organismo di controllo Suolo e Salute Srl (IT-BIO-004)" in flat
    assert "Reg. (UE) 2018/848" in flat
    assert "Valido dal 25 agosto 2026 al 24 agosto 2029" in flat
    assert "Intestato a Si Bio di Premici Silvia e Aleandri Vincenzo, società semplice" in flat
    assert "Contrada San Lazzaro 118, 63073 Offida" in flat
    assert "Inquadra per verificare il certificato aggiornato" in flat
    assert re.search(r'<a [^>]*href="https://webgate\.ec\.europa\.eu/[^"]+\.pdf"', block)
    assert "Verifica nel registro UE" in flat
    assert re.search(r'<img [^>]*src="/static/img/certificate-qr\.svg"[^>]*alt="[^"]+"', block)
    assert re.search(r'<img [^>]*width="\d+"[^>]*height="\d+"', block)


def test_about_block_in_english(client, production):
    html = client.get("/en/chi-siamo").text
    block = re.search(r'<section[^>]*id="certificato".*?</section>', html, re.S).group(0)
    flat = plain(block)
    assert "Certified organic farm" in flat
    sentence = "Si Bio is a certified organic farm. The certificate covers the cultivation of "
    assert sentence + "grapes, olives and cereals." in flat
    assert f"Certificate no. {NUMBER}" in flat
    assert "control body Suolo e Salute Srl (IT-BIO-004)" in flat
    assert "Valid from 25 August 2026 to 24 August 2029" in flat
    assert "Scan to check the current certificate" in flat
    assert "Check in the EU register" in flat


def test_home_line_and_footer_link(client, production):
    for prefix, label, footer in (
        ("", "Azienda biologica certificata", "Certificato biologico"),
        ("/en", "Certified organic farm", "Organic certificate"),
    ):
        href = f'href="{prefix}/chi-siamo#certificato"'
        home = client.get(prefix + "/").text
        assert re.search(rf"<a [^>]*{re.escape(href)}[^>]*>\s*{label}\s*</a>", main_text_raw(home))
        for path in ("/", "/olio", "/vini/armide", "/chi-siamo"):
            page = client.get(prefix + path).text
            foot = re.search(r"<footer.*?</footer>", page, re.S).group(0)
            assert re.search(rf"<a [^>]*{re.escape(href)}[^>]*>\s*{footer}\s*</a>", foot), path


def main_text_raw(html):
    return re.search(r"<main.*?</main>", html, re.S).group(0)


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_block_and_home_line_not_on_wines_nor_oil(client, production, prefix):
    for path in ["/olio", *WINES]:
        html = client.get(prefix + path).text
        assert 'id="certificato"' not in html
        assert "certificate-qr" not in html
        assert "webgate.ec.europa.eu" not in html
        assert not ORGANIC.search(main_text(html)), path


def test_switch_off_means_no_trace(client, production, monkeypatch):
    patch_site(monkeypatch, switch=False)
    for prefix in ("", "/en"):
        for path in PAGES:
            html = client.get(prefix + path).text
            assert not ORGANIC.search(text(html)), (prefix, path)
            assert "certificato" not in html and "certificate" not in html.lower(), (prefix, path)
            assert "webgate.ec.europa.eu" not in html
        assert "hasCertification" not in client.get(prefix + "/").text
        llms = client.get(prefix + "/llms.txt").text
        assert not ORGANIC.search(text(llms)) and "webgate" not in llms


@pytest.mark.parametrize(
    "change",
    [
        {"number": "[DA COMPLETARE: numero]"},
        {"number": ""},
        {"verify_url": ""},
        {"verify_url": "http://webgate.ec.europa.eu/x.pdf"},
        {"verify_url": "https://example.org/x.pdf"},
        {"body": ""},
    ],
)
def test_switch_on_but_certificate_unsound_shows_nothing(client, production, monkeypatch, change):
    patch_site(monkeypatch, **change)
    for path in ("/", "/chi-siamo", "/olio"):
        html = client.get(path).text
        assert 'id="certificato"' not in html and "chi-siamo#certificato" not in html
        assert not ORGANIC.search(text(html)), path
    assert "hasCertification" not in client.get("/").text


def test_block_without_qr_file_keeps_the_link(client, production, monkeypatch):
    patch_site(monkeypatch, qr="missing.svg")
    html = client.get("/chi-siamo").text
    assert 'id="certificato"' in html and "webgate.ec.europa.eu" in html
    assert "<img" not in re.search(r'<section[^>]*id="certificato".*?</section>', html, re.S).group(
        0
    )


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_organization_has_certification(client, production, prefix):
    org = blocks(client.get(prefix + "/").text)[0]
    cert = org["hasCertification"]
    assert cert["@type"] == "Certification"
    assert cert["certificationIdentification"] == NUMBER
    assert cert["issuedBy"] == {"@type": "Organization", "name": "Suolo e Salute Srl (IT-BIO-004)"}
    assert cert["url"].startswith("https://webgate.ec.europa.eu/")
    assert (cert["validFrom"], cert["expires"]) == ("2026-08-25", "2029-08-24")
    assert "name" in cert


def test_certification_not_on_wine_or_oil_json_ld(client, production):
    for path in ("/olio", "/vini/armide"):
        assert "Certification" not in client.get(path).text


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_llms_txt_has_one_line(client, production, prefix):
    lines = [line for line in client.get(prefix + "/llms.txt").text.splitlines() if NUMBER in line]
    assert len(lines) == 1
    assert "2029" in lines[0] and "webgate.ec.europa.eu" in lines[0]
    assert "organic farm" in lines[0] or "Azienda biologica" in lines[0]


@pytest.mark.parametrize("switch", [True, False])
@pytest.mark.parametrize("prefix", ["", "/en"])
def test_never_a_wine_oil_or_grapes_called_organic(client, production, monkeypatch, switch, prefix):
    patch_site(monkeypatch, switch=switch)
    for path in [*PAGES, "/llms.txt", "/sitemap.xml"]:
        html = client.get(prefix + path).text
        found = WRONG.search(text(html))
        assert not found, (prefix, path, found.group(0))
    for lang in ("it", "en"):
        for name in ("home", "about", "visits", "contact"):
            for value in content.page(lang, name).values():
                assert not WRONG.search(value), (lang, name, value)


def test_organic_detector_catches_the_forbidden_phrases():
    for phrase in (
        "vino biologico",
        "vini biologici",
        "olio biologico",
        "uve biologiche",
        "organic wine",
        "organic wines",
        "organic oil",
        "organic grapes",
        "biologico olio",
    ):
        assert WRONG.search(phrase), phrase
    for phrase in (
        "azienda agricola biologica certificata. Il certificato riguarda la coltivazione di uva",
        "certified organic farm. The certificate covers the cultivation of grapes",
    ):
        assert not WRONG.search(phrase), phrase


def test_preview_shows_no_marker_in_the_block(client, monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    content.read.cache_clear()
    html = client.get("/chi-siamo").text
    assert not content.MARKER.search(
        re.search(r"<section[^>]*id=.certificato.*?</section>", html, re.S).group(0)
    )
