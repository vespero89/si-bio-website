import re
import shutil
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)

SLUGS = ["offida-pecorino", "offida-passerina", "armide", "passacaille"]


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A writable copy of content/ and static/ that the app reads instead of the real ones."""
    root = tmp_path / "content"
    shutil.copytree(config.CONTENT_DIR, root)
    static = tmp_path / "static"
    (static / "schede").mkdir(parents=True)
    (static / "img").mkdir()
    shutil.copy(config.STATIC_DIR / "img" / "certificate-qr.svg", static / "img")
    monkeypatch.setattr(config, "CONTENT_DIR", root)
    monkeypatch.setattr(config, "STATIC_DIR", static)
    content.read.cache_clear()
    yield root
    content.read.cache_clear()


@pytest.fixture
def rosso(tree):
    """Offida Rosso (still all placeholders) made visible, to test the placeholder rules."""
    path = tree / "wines" / "offida-rosso.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("visible = false", "visible = true"))
    content.read.cache_clear()
    return tree


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)


@pytest.fixture
def preview(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)


def attrs(html: str, tag: str) -> list[dict]:
    return [
        dict(re.findall(r'([\w-]+)="([^"]*)"', raw))
        for raw in re.findall(rf"<{tag}\b([^>]*)>", html)
    ]


def row(html: str) -> str:
    return re.search(r'<nav class="wine-row".*?</nav>', html, re.S).group(0)


def edit(path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    content.read.cache_clear()


def test_every_wine_page_answers_200_in_both_languages(client):
    for prefix in ("", "/en"):
        assert client.get(f"{prefix}/vini").status_code == 200
        for slug in SLUGS:
            assert client.get(f"{prefix}/vini/{slug}").status_code == 200


def test_row_lists_the_four_wines_in_order_with_aria_current_on_the_selected(client):
    html = client.get("/vini/armide").text
    anchors = attrs(row(html), "a")
    assert [a["href"] for a in anchors] == [f"/vini/{s}" for s in SLUGS]
    assert [a["href"] for a in anchors if a.get("aria-current") == "page"] == ["/vini/armide"]
    assert 'aria-label="I nostri vini"' in row(html)


def test_row_links_carry_the_language_prefix(client):
    anchors = attrs(row(client.get("/en/vini/armide").text), "a")
    assert [a["href"] for a in anchors] == [f"/en/vini/{s}" for s in SLUGS]
    assert 'aria-label="Our wines"' in row(client.get("/en/vini/armide").text)


def test_vini_shows_first_wine_in_front_with_its_own_h1(client):
    html = client.get("/vini").text
    assert re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.S) == ["I nostri vini"]
    anchors = attrs(row(html), "a")
    assert anchors[0]["href"] == "/vini/offida-pecorino"
    assert anchors[0].get("aria-current") == "true"
    assert "Offida Pecorino" in html
    canonical = [a["href"] for a in attrs(html, "link") if a.get("rel") == "canonical"]
    assert canonical == [config.BASE_URL + "/vini"]


def test_wine_page_has_one_h1_with_the_wine_name(client):
    html = client.get("/vini/armide").text
    assert re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.S) == ["Armide"]
    assert 'class="wine-front"' in html


def test_unknown_slug_is_404(client):
    assert client.get("/vini/nope").status_code == 404
    assert client.get("/en/vini/nope").status_code == 404


def test_hidden_wine_is_404_and_not_in_the_row(client, tree):
    edit(tree / "wines" / "armide.toml", "visible = true", "visible = false")
    assert client.get("/vini/armide").status_code == 404
    html = client.get("/vini/offida-passerina").text
    assert [a["href"] for a in attrs(row(html), "a")] == [
        f"/vini/{s}" for s in SLUGS if s != "armide"
    ]


def test_production_shows_no_placeholder_and_no_empty_labelled_row(client, rosso, production):
    html = client.get("/vini/offida-rosso").text
    assert "[DA " not in html and "[TO BE" not in html
    assert "<dt" not in html
    assert "Denominazione" not in html


def test_preview_shows_placeholders(client, rosso, preview):
    html = client.get("/vini/offida-rosso").text
    assert "[DA VERIFICARE: denominazione]" in html
    assert "<dt>Denominazione</dt>" in html


def test_sheet_shows_only_filled_fields(client, rosso, production):
    edit(
        rosso / "it" / "wines" / "offida-rosso.toml",
        'grapes = "[DA VERIFICARE: vitigni]"',
        'grapes = "Pecorino 100%"',
    )
    html = client.get("/vini/offida-rosso").text
    assert re.findall(r"<dt>(.*?)</dt>", html) == ["Vitigni"]
    assert "<dd>Pecorino 100%</dd>" in html


def test_sheet_in_english_uses_english_labels(client, rosso, production):
    edit(
        rosso / "en" / "wines" / "offida-rosso.toml",
        'grapes = "[TO BE VERIFIED: grapes]"',
        'grapes = "Pecorino"',
    )
    assert re.findall(r"<dt>(.*?)</dt>", client.get("/en/vini/offida-rosso").text) == ["Grapes"]


def test_abv_and_formats_are_in_the_sheet_when_filled(client, rosso, production):
    edit(
        rosso / "wines" / "offida-rosso.toml",
        'abv = "[DA VERIFICARE: gradazione alcolica]"',
        "abv = 13.5",
    )
    edit(
        rosso / "wines" / "offida-rosso.toml",
        'formats = ["[DA VERIFICARE: formati in ml]"]',
        'formats = ["750 ml", "1500 ml"]',
    )
    html = client.get("/vini/offida-rosso").text
    assert "<dd>13,5 % vol</dd>" in html
    assert "<dd>750 ml, 1500 ml</dd>" in html
    assert "13.5% vol" in client.get("/en/vini/offida-rosso").text


NEW_FIELDS = ["style", "training", "bottle_aging", "appearance", "aroma", "palate"]
NEW_TEXT = {
    "it": [
        "Bianco fermo",
        "Guyot",
        "Minimo 6 mesi",
        "Giallo paglierino",
        "Frutta gialla",
        "Morbido",
    ],
    "en": ["Still white", "Guyot", "Minimum 6 months", "Straw yellow", "Yellow fruit", "Smooth"],
}


def fill_new_fields(rosso, lang: str, values: list[str]) -> None:
    path = rosso / lang / "wines" / "offida-rosso.toml"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "".join(f'{k} = "{v}"\n' for k, v in zip(NEW_FIELDS, values, strict=True)),
        encoding="utf-8",
    )
    content.read.cache_clear()


def test_new_sheet_fields_show_in_order_with_italian_labels(client, rosso, production):
    fill_new_fields(rosso, "it", NEW_TEXT["it"])
    edit(
        rosso / "wines" / "offida-rosso.toml",
        'abv = "[DA VERIFICARE: gradazione alcolica]"',
        "abv = 11.5",
    )
    html = client.get("/vini/offida-rosso").text
    assert re.findall(r"<dt>(.*?)</dt>", html) == [
        "Stile",
        "Allevamento",
        "Affinamento in bottiglia",
        "Gradazione alcolica",
        "Aspetto",
        "Profumo",
        "Gusto",
    ]
    assert "<dd>Bianco fermo</dd>" in html


def test_new_sheet_fields_in_english(client, rosso, production):
    fill_new_fields(rosso, "en", NEW_TEXT["en"])
    labels = re.findall(r"<dt>(.*?)</dt>", client.get("/en/vini/offida-rosso").text)
    assert labels == ["Style", "Training", "Bottle ageing", "Appearance", "Aroma", "Palate"]


def test_bottles_per_year_is_grouped_by_language(client, rosso, production):
    edit(rosso / "wines" / "offida-rosso.toml", 'photo = "', 'bottles_per_year = 5000\nphoto = "')
    html = client.get("/vini/offida-rosso").text
    assert re.findall(r"<dt>(.*?)</dt>", html) == ["Bottiglie all&#39;anno"]
    assert "<dd>5.000</dd>" in client.get("/vini/offida-rosso").text
    assert "<dd>5,000</dd>" in client.get("/en/vini/offida-rosso").text


def test_new_fields_with_a_marker_are_hidden_in_production_and_shown_in_preview(
    client, rosso, production, monkeypatch
):
    edit(
        rosso / "wines" / "offida-rosso.toml",
        'photo = "',
        'bottles_per_year = "[DA VERIFICARE: bottiglie]"\nphoto = "',
    )
    fill_new_fields(rosso, "it", ["[DA VERIFICARE: x]"] * 6)
    html = client.get("/vini/offida-rosso").text
    assert "<dt>" not in html and "DA VERIFICARE: x" not in html
    monkeypatch.setattr(config, "PREVIEW", True)
    html = client.get("/vini/offida-rosso").text
    assert "Stile" in html and "DA VERIFICARE: bottiglie" in html


def test_new_fields_are_valid_in_the_validator(rosso):
    fill_new_fields(rosso, "it", NEW_TEXT["it"])
    fill_new_fields(rosso, "en", NEW_TEXT["en"])
    edit(rosso / "wines" / "offida-rosso.toml", 'photo = "', 'bottles_per_year = 4000\nphoto = "')
    assert content.problems() == []


def test_bottles_per_year_must_be_a_number_or_text(rosso):
    edit(rosso / "wines" / "offida-rosso.toml", 'photo = "', 'bottles_per_year = [1]\nphoto = "')
    assert any("bottles_per_year" in p for p in content.problems())


def pdf_setup(tree, langs):
    edit(
        tree / "wines" / "armide.toml",
        "# [pdf]",
        "[pdf]",
    )
    edit(
        tree / "wines" / "armide.toml",
        '# it = "armide-it.pdf"   # file in app/static/schede/',
        "\n".join(f'{lang} = "armide-{lang}.pdf"' for lang in langs),
    )
    for lang in langs:
        (config.STATIC_DIR / "schede" / f"armide-{lang}.pdf").write_bytes(b"%PDF" + b"x" * 2400)


def test_no_pdf_no_link(client):
    assert ".pdf" not in client.get("/vini/armide").text


def test_pdf_in_the_page_language(client, tree):
    pdf_setup(tree, ["it", "en"])
    html = client.get("/en/vini/armide").text
    link = [a for a in attrs(html, "a") if a.get("href", "").endswith(".pdf")]
    assert [a["href"] for a in link] == ["/static/schede/armide-en.pdf"]
    assert "Download the sheet (PDF, 2 KB)" in html


def test_italian_pdf_is_the_fallback_for_other_languages(client, tree):
    pdf_setup(tree, ["it"])
    html = client.get("/en/vini/armide").text
    link = [a for a in attrs(html, "a") if a.get("href", "").endswith(".pdf")]
    assert [a["href"] for a in link] == ["/static/schede/armide-it.pdf"]
    assert "Sheet in PDF (in Italian)" in html
    assert "Scarica la scheda (PDF, 2 KB)" in client.get("/vini/armide").text


def mailto(html: str) -> str:
    """The mailto link of the contact block (the footer has its own, without subject)."""
    block = re.search(r'<div class="contact-block".*?</div>', html, re.S).group(0)
    return [a["href"] for a in attrs(block, "a") if a.get("href", "").startswith("mailto:")][0]


def test_contact_block_has_address_text_and_mailto_with_subject(client):
    html = client.get("/vini/armide").text
    block = re.search(r'<div class="contact-block".*?</div>', html, re.S).group(0)
    assert "export@si-bio.it" in re.sub(r"<[^>]+>", "", block)
    assert mailto(block) == "mailto:export@si-bio.it?subject=Si%20Bio%3A%20Armide"
    assert "Scrivici" in block


def test_mailto_subject_follows_the_wine(client):
    assert mailto(client.get("/vini/passacaille").text).endswith(
        "?subject=Si%20Bio%3A%20Passacaille"
    )
    assert mailto(client.get("/en/vini/armide").text).endswith("?subject=Si%20Bio%3A%20Armide")


def test_mailto_encodes_accents_apostrophes_and_ampersands(client, tree):
    for text in ("it", "en"):
        edit(tree / text / "wines" / "armide.toml", 'name = "Armide"', 'name = "L\'Ârmide & Co"')
    href = mailto(client.get("/vini/armide").text)
    assert "+" not in href and " " not in href and "&" not in href and "'" not in href
    subject = parse_qs(urlsplit(href).query, keep_blank_values=True)["subject"][0]
    assert subject == "Si Bio: L'Ârmide & Co"
    assert unquote(href.split("subject=")[1]) == "Si Bio: L'Ârmide & Co"
    assert "%C3%82" in href


def test_no_copy_button_in_the_html_but_script_and_labels_are_there(client):
    html = client.get("/vini/armide").text
    assert "<button" not in NOTICE.sub("", html)
    assert "/static/js/contact.js" in html
    assert 'data-copy="Copia"' in html and 'data-copied="Copiato"' in html


def test_no_inline_script_and_no_form(client):
    html = client.get("/vini/armide").text
    # JSON-LD blocks are data, not code
    scripts = re.findall(r"<script\b([^>]*)>", html)
    assert not [s for s in scripts if "src=" not in s and "application/ld+json" not in s]
    assert "<form" not in NOTICE.sub("", html)  # only the cookie choice posts


def test_wine_without_photo_shows_a_graphic_placeholder(client, rosso, production):
    html = client.get("/vini/offida-rosso").text
    stage = re.search(r'<div class="wine-photo">.*?</div>', html, re.S).group(0)
    assert 'class="bottle-placeholder"' in stage
    assert "<img" not in stage


def test_wine_photo_is_an_img_with_alt_and_size(client, rosso, production):
    edit(
        rosso / "wines" / "offida-rosso.toml",
        'photo = "[DA COMPLETARE: foto della bottiglia]"',
        'photo = "offida-rosso.jpg"',
    )
    img = [a for a in attrs(client.get("/vini/offida-rosso").text, "img") if a.get("alt")]
    assert img and img[0]["src"] == "/static/img/vini/offida-rosso.jpg"
    assert img[0]["alt"] == "Offida Rosso in vigna" and img[0]["width"] and img[0]["height"]
