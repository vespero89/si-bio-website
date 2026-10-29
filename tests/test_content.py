import shutil

import pytest

from app import config, content

SLUGS = ["offida-pecorino", "offida-passerina", "armide", "passacaille"]


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A writable copy of content/ that the loader reads instead of the real one."""
    root = tmp_path / "content"
    shutil.copytree(config.CONTENT_DIR, root)
    monkeypatch.setattr(config, "CONTENT_DIR", root)
    content.read.cache_clear()
    yield root
    content.read.cache_clear()


@pytest.fixture
def preview(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)


def show_rosso(tree):
    """Offida Rosso (all placeholders) made visible, to test the placeholder rules."""
    path = tree / "wines" / "offida-rosso.toml"
    path.write_text(path.read_text().replace("visible = false", "visible = true"))
    content.read.cache_clear()


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def test_real_content_is_valid():
    assert content.problems() == []


def test_four_wines_in_file_order():
    assert [w["slug"] for w in content.wines("it")] == SLUGS
    assert [w["slug"] for w in content.wines("en")] == SLUGS


def test_wine_merges_neutral_and_language_data():
    wine = content.wine("it", "armide")
    assert wine["slug"] == "armide" and wine["name"] == "Armide"
    assert content.wine("en", "armide")["name"] == "Armide"
    assert "order" in wine and "description" in wine


def test_unknown_wine_is_none():
    assert content.wine("it", "prosecco") is None


def test_hidden_wine_is_left_out(tree):
    path = tree / "wines" / "armide.toml"
    path.write_text(path.read_text().replace("visible = true", "visible = false"))
    content.read.cache_clear()
    assert "armide" not in [w["slug"] for w in content.wines("it")]
    assert content.wine("it", "armide") is None
    assert content.problems() == []


def test_production_hides_every_marker(production):
    for lang in config.PUBLISHED:
        everything = [content.site(), content.oil(lang)]
        everything += content.wines(lang)
        everything += [content.page(lang, name) for name in content.PAGES]
        for data in everything:
            for text in strings(data):
                assert not content.has_marker(text), text


def test_production_wine_card_has_only_filled_fields(tree, production):
    show_rosso(tree)
    wine = content.wine("it", "offida-rosso")
    assert wine["denomination"] == ""
    assert wine["abv"] == "" and wine["formats"] == []


def test_preview_shows_markers(tree, preview):
    show_rosso(tree)
    wine = content.wine("it", "offida-rosso")
    assert wine["denomination"].startswith("[DA VERIFICARE")
    assert content.has_marker(content.site()["contact"]["partner_email"])


def test_marker_anywhere_in_a_text_hides_the_whole_field(tree, production):
    path = tree / "it" / "pages" / "about.toml"
    path.write_text(path.read_text() + '\nextra = "Fondata nel [DA VERIFICARE: anno]."\n')
    content.read.cache_clear()
    assert content.page("it", "about")["extra"] == ""


def test_english_markers_are_recognised():
    assert content.has_marker("[TO BE VERIFIED: grapes]")
    assert content.has_marker("[TO BE COMPLETED: address]")
    assert content.has_marker("[DA DEFINIRE: nome]")
    assert not content.has_marker("Armide [brut] 2020")


def test_site_keeps_real_values_in_production(production):
    site = content.site()
    assert site["contact"]["export_email"] == "export@si-bio.it"
    assert site["contact"]["partner_email"] == ""
    assert site["switches"] == {"riva_dei_martin": False, "organic_certified": False}
    assert site["video"]["youtube_id"] == ""


def test_validator_flags_missing_required_field(tree):
    path = tree / "it" / "wines" / "armide.toml"
    path.write_text(path.read_text().replace('name = "Armide"', ""))
    content.read.cache_clear()
    assert any("it/wines/armide.toml" in p and "name" in p for p in content.problems())


def test_validator_flags_unknown_key(tree):
    path = tree / "it" / "wines" / "armide.toml"
    path.write_text(path.read_text() + '\ngrapez = "x"\n')
    content.read.cache_clear()
    assert any("grapez" in p for p in content.problems())


def test_validator_flags_wine_without_text_in_a_language(tree):
    (tree / "en" / "wines" / "armide.toml").unlink()
    content.read.cache_clear()
    assert any("en/wines/armide.toml" in p for p in content.problems())


def test_validator_flags_text_file_without_neutral_file(tree):
    shutil.copy(tree / "it" / "wines" / "armide.toml", tree / "it" / "wines" / "ghost.toml")
    content.read.cache_clear()
    assert any("ghost" in p for p in content.problems())


def test_validator_flags_missing_pdf_and_duplicate_order(tree):
    path = tree / "wines" / "armide.toml"
    text = path.read_text()
    path.write_text(text + '\n[pdf]\nit = "nope.pdf"\n')
    other = tree / "wines" / "offida-rosso.toml"
    other.write_text(other.read_text().replace("order = 5", "order = 4"))
    content.read.cache_clear()
    found = " ".join(content.problems())
    assert "nope.pdf" in found and "order" in found


def test_validator_flags_wrong_type_and_bad_site(tree):
    path = tree / "site.toml"
    path.write_text(path.read_text().replace("riva_dei_martin = false", 'riva_dei_martin = "no"'))
    content.read.cache_clear()
    assert any("riva_dei_martin" in p for p in content.problems())


def test_validator_flags_broken_toml(tree):
    (tree / "it" / "oil.toml").write_text("name = ")
    content.read.cache_clear()
    assert any("it/oil.toml" in p for p in content.problems())


def test_new_language_is_complete_only_with_every_key(tree, monkeypatch):
    shutil.copytree(tree / "it", tree / "xx")
    monkeypatch.setattr(config, "PUBLISHED", ("it", "en", "xx"))
    content.read.cache_clear()
    assert content.problems() == []
    path = tree / "xx" / "pages" / "home.toml"
    lines = [ln for ln in path.read_text().splitlines() if not ln.startswith("claim")]
    path.write_text("\n".join(lines) + "\n")
    content.read.cache_clear()
    assert any("xx/pages/home.toml" in p and "claim" in p for p in content.problems())


def test_english_lacking_a_key_is_a_problem(tree):
    path = tree / "en" / "oil.toml"
    path.write_text(
        "\n".join(ln for ln in path.read_text().splitlines() if not ln.startswith("cultivar"))
    )
    content.read.cache_clear()
    assert any("en/oil.toml" in p and "cultivar" in p for p in content.problems())


def test_riva_dei_martin_sentence_follows_the_switch(tree, preview):
    assert "Riva dei Martin" not in content.page("it", "about").get("riva_dei_martin", "")
    path = tree / "site.toml"
    path.write_text(path.read_text().replace("riva_dei_martin = false", "riva_dei_martin = true"))
    content.read.cache_clear()
    assert "Riva dei Martin" in content.page("it", "about")["riva_dei_martin"]
    assert "Riva dei Martin" in content.page("en", "about")["riva_dei_martin"]


def test_no_page_mentions_riva_dei_martin_while_switch_is_off(preview):
    for lang in config.PUBLISHED:
        for name in content.PAGES:
            assert "Riva dei Martin" not in " ".join(strings(content.page(lang, name)))
