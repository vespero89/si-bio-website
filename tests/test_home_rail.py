"""Home, task 3 of the design: the rail of wines in two movements, one dialog template per visible
wine, the neutral `group`, the new wine text fields, the script loaded on the home only."""

import re
import shutil
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

ORDER = ["offida-pecorino", "offida-passerina", "armide", "passacaille"]
CLAIM = {
    "": "L'uva deve essere raccolta vicino al mare e vinificata in Marmolada.",
    "/en": "Grapes should be picked by the sea and made into wine in the Marmolada.",
}


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


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "content"
    shutil.copytree(config.CONTENT_DIR, root)
    monkeypatch.setattr(config, "CONTENT_DIR", root)
    content.read.cache_clear()
    yield root
    content.read.cache_clear()


def rail(html):
    return re.search(r"<ul class=\"rail\" data-rail>.*?</ul>", html, re.S).group(0)


def template(html, slug):
    return re.search(rf'<template id="wine-{slug}">(.*?)</template>', html, re.S).group(1)


def outside_templates(html):
    return re.sub(r"<template.*?</template>", "", html, flags=re.S)


def flat(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_rail_has_two_movements_and_the_cards_in_order(client, production, prefix):
    html = client.get(prefix + "/").text
    block = rail(html)
    slugs = re.findall(r'<a href="[^"]*/vini/([a-z-]+)" data-wine="([a-z-]+)"', block)
    assert [a for a, _ in slugs] == ORDER and [b for _, b in slugs] == ORDER
    first, second = block.index("movement-1"), block.index("movement-2")
    assert (
        first
        < block.index('data-wine="offida-pecorino"')
        < block.index('data-wine="offida-passerina"')
    )
    assert block.index('data-wine="offida-passerina"') < second < block.index('data-wine="armide"')
    assert block.index('data-wine="armide"') < block.index('data-wine="passacaille"')
    assert 'data-wine="offida-rosso"' not in block


def test_cards_link_to_the_localized_wine_page(client, production):
    assert 'href="/en/vini/armide"' in rail(client.get("/en/").text)
    assert 'href="/vini/armide"' in rail(client.get("/").text)


def test_arrows_are_hidden_until_the_script_runs(client, production):
    html = client.get("/").text
    assert re.search(r"<div class=\"arrows\" data-rail-arrows hidden>", html)
    assert html.count("data-rail-step") == 2


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_claim_is_only_in_movement_two(client, production, prefix):
    outside = outside_templates(client.get(prefix + "/").text)
    block = rail(outside)
    one, two = block.index("movement-1"), block.index("movement-2")
    assert CLAIM[prefix] not in unescape(block[one:two])
    assert CLAIM[prefix] in unescape(block[two:])
    assert flat(outside).count(CLAIM[prefix]) == 1
    assert CLAIM[prefix] not in unescape(re.search(r"<figure.*?</figure>", outside, re.S).group(0))


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_tagline_comes_after_the_long_stave(client, production, prefix):
    outside = outside_templates(client.get(prefix + "/").text)
    figure = re.search(r'<figure class="claim.*?</figure>', outside, re.S).group(0)
    assert figure.index("<svg") < figure.index("Taste the Essence")
    assert "<blockquote" in figure and CLAIM[prefix] not in unescape(figure)


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_one_visually_hidden_h1(client, production, prefix):
    html = outside_templates(client.get(prefix + "/").text)
    assert re.findall(r"<h1[^>]*>.*?</h1>", html, re.S) == ['<h1 class="sr-only">Si Bio</h1>']


def test_dialog_script_is_loaded_on_the_home_only(client, production):
    tag = '<script src="/static/js/wine-dialog.js" defer></script>'
    assert tag in client.get("/").text and tag in client.get("/en/").text
    for path in ("/vini", "/vini/armide", "/olio", "/chi-siamo", "/visite", "/contatti"):
        assert "wine-dialog.js" not in client.get(path).text, path


def test_one_template_per_visible_wine(client, production):
    html = client.get("/").text
    assert re.findall(r'<template id="(wine-[a-z-]+)">', html) == [f"wine-{s}" for s in ORDER]


def test_armide_presentation_it(client, production):
    body = template(client.get("/").text, "armide")
    text = flat(body)
    assert '<h2 id="dlg-armide" tabindex="-1">Armide</h2>' in body
    assert "Opera di Lully" in text and "Bianco fermo" in text
    for label, value in (("Vitigni", "100% Pecorino"), ("Gradazione alcolica", "11,5 % vol")):
        assert re.search(rf"<dt[^>]*>{label}</dt>\s*<dd>{re.escape(value)}</dd>", body), label
    assert re.search(r"<dt[^>]*>Temperatura di servizio</dt>\s*<dd>10-12 °C</dd>", body)
    for label in ("Aspetto", "Profumo", "Gusto", "Abbinamenti"):
        assert f">{label}</dt>" in body
    assert "<h3>Il nome</h3>" in body and "Jean-Baptiste Lully" in text
    assert CLAIM[""] in text and "Taste the Essence" in text
    assert 'href="/vini/armide"' in body and "Scheda tecnica completa" in body
    assert "mailto:export.sibio@gmail.com?subject=Si%20Bio%3A%20Armide" in body
    assert ">Scrivici</a>" in body and 'aria-label="Chiudi"' in body and "data-close" in body


def test_armide_presentation_en(client, production):
    body = template(client.get("/en/").text, "armide")
    text = flat(body)
    assert "Lully" in text and "<h3>The name</h3>" in body
    assert CLAIM["/en"] in text
    assert 'href="/en/vini/armide"' in body and "Full technical sheet" in body
    assert ">Write to us</a>" in body and 'aria-label="Close"' in body


def test_wines_without_claim_have_no_claim_in_the_dialog(client, production):
    for slug in ("offida-pecorino", "offida-passerina"):
        assert CLAIM[""] not in template(client.get("/").text, slug)


def test_marker_story_is_hidden_in_production_and_shown_in_preview(client, production, monkeypatch):
    body = template(client.get("/").text, "offida-pecorino")
    assert "story" not in body and "DA COMPLETARE" not in body
    monkeypatch.setattr(config, "PREVIEW", True)
    assert "DA COMPLETARE" in template(client.get("/").text, "offida-pecorino")


def test_marker_fact_is_left_out_never_invented(client, production, tree):
    path = tree / "it" / "wines" / "offida-pecorino.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        re.sub(r'serving_temperature = ".*"', 'serving_temperature = "[DA VERIFICARE: x]"', text),
        encoding="utf-8",
    )
    content.read.cache_clear()
    body = template(client.get("/").text, "offida-pecorino")
    assert "Temperatura di servizio" not in body and "VERIFICARE" not in body
    assert "Vitigni" in body and "Gradazione alcolica" in body


def test_images_in_templates_have_alt_width_height(client, production):
    html = client.get("/").text
    for img in re.findall(r"<img\b[^>]*>", html):
        assert re.search(r'alt="', img) and 'width="' in img and 'height="' in img, img


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_home_never_says_organic_wine_or_veneto(client, production, prefix):
    text = flat(client.get(prefix + "/").text)
    assert not re.search(r"veneto", text, re.I)
    main = re.search(r"<main.*?</main>", client.get(prefix + "/").text, re.S).group(0)
    main = flat(re.sub(r'<p class="certified">.*?</p>', "", main, flags=re.S))  # the home line
    assert not re.search(r"biologic|organic", main, re.I)


def test_group_is_set_on_every_wine():
    groups = {
        slug: content.read(config.CONTENT_DIR / "wines" / f"{slug}.toml")["group"]
        for slug in ORDER + ["offida-rosso"]
    }
    assert groups == {
        "offida-pecorino": "piceno",
        "offida-passerina": "piceno",
        "armide": "opera",
        "passacaille": "opera",
        "offida-rosso": "piceno",
    }


def test_validator_requires_a_known_group_on_visible_wines(tree):
    path = tree / "wines" / "armide.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace('group = "opera"', ""), encoding="utf-8"
    )
    content.read.cache_clear()
    assert any("armide.toml: missing 'group'" in p for p in content.problems())
    path.write_text(path.read_text(encoding="utf-8") + 'group = "other"\n', encoding="utf-8")
    content.read.cache_clear()
    assert any("'group' must be" in p for p in content.problems())


def test_validator_knows_the_new_text_fields(tree):
    path = tree / "it" / "wines" / "armide.toml"
    assert content.problems() == []
    for key in ("subtitle", "story_title", "story"):
        assert key in path.read_text(encoding="utf-8")
    assert content.wine("it", "armide")["subtitle"] == "Opera di Lully"
    assert content.wine("en", "passacaille")["subtitle"] == "Finale of the same opera"
    assert content.wine("it", "offida-pecorino")["subtitle"] == ""


def test_story_texts_are_in_both_languages_without_markers():
    for lang in ("it", "en"):
        for slug in ("armide", "passacaille"):
            data = content.read(config.CONTENT_DIR / lang / "wines" / f"{slug}.toml")
            assert data["story_title"] and data["story"] and not content.has_marker(data["story"])
        for slug in ("offida-pecorino", "offida-passerina"):
            data = content.read(config.CONTENT_DIR / lang / "wines" / f"{slug}.toml")
            assert content.has_marker(data["story"]) and data["story_title"]


def test_new_locale_keys_in_both_languages():
    from app import i18n

    for key in (
        "home.movement_1_label",
        "home.movement_1_title",
        "home.movement_1_text",
        "home.movement_2_text",
        "wines.full_sheet",
        "wines.write",
        "wines.close",
        "wines.prev",
        "wines.next",
    ):
        for lang in ("it", "en"):
            assert i18n.load(lang).get(key), (lang, key)
