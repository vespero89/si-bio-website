"""scripts/check_content.py: lists the placeholders left per language and file, checks the public
export address and warns when the organic certificate is about to expire. Dates are passed in, the
tests never read today's date."""

import shutil
from datetime import date

import pytest

from app import config, content
from scripts import check_content as check

SITE = content.read(config.CONTENT_DIR / "site.toml")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "content"
    shutil.copytree(config.CONTENT_DIR, root)
    monkeypatch.setattr(config, "CONTENT_DIR", root)
    content.read.cache_clear()
    yield root
    content.read.cache_clear()


def settings(**certificate):
    return {
        "switches": {"organic_certified": True},
        "certificate": {"valid_until": "2029-08-24", **certificate},
    }


def test_certificate_valid_until_is_the_real_one():
    assert SITE["certificate"]["valid_until"] == "2029-08-24"


@pytest.mark.parametrize(
    ("today", "warns"),
    [
        (date(2029, 6, 25), True),  # 60 days left: warns
        (date(2029, 6, 24), False),  # 61 days left
        (date(2029, 8, 24), True),  # last day
        (date(2029, 8, 25), True),  # expired
        (date(2026, 10, 29), False),
    ],
)
def test_expiry_warning_at_60_days(today, warns):
    assert bool(check.certificate_warnings(settings(), today)) is warns


def test_expiry_warning_says_how_many_days():
    (text,) = check.certificate_warnings(settings(), date(2029, 7, 25))
    assert "30 days" in text and "2029-08-24" in text
    (text,) = check.certificate_warnings(settings(), date(2029, 9, 3))
    assert "expired" in text


def test_no_warning_when_the_certificate_is_switched_off():
    off = settings()
    off["switches"]["organic_certified"] = False
    assert check.certificate_warnings(off, date(2029, 8, 1)) == []


def test_expected_export_address_is_the_public_one():
    assert check.EXPORT_EMAIL == "export.sibio@gmail.com" == SITE["contact"]["export_email"]
    assert check.export_errors(SITE) == []


def test_other_export_address_is_an_error():
    wrong = {"contact": {"export_email": "export@si-bio.it"}}
    (error,) = check.export_errors(wrong)
    assert "export.sibio@gmail.com" in error


def test_markers_are_listed_by_language_and_file(tree):
    found = check.markers()
    assert any(file == "site.toml" for file, _ in found["shared"])
    assert all(isinstance(found[lang], list) for lang in ("it", "en"))
    assert any("pages/home.toml" in file for file, _ in found["it"]) or found["it"]


def test_hidden_content_does_not_count(tree):
    found = check.markers()
    files = [file for lang in found.values() for file, _ in lang]
    assert not any("offida-rosso" in file for file in files)  # visible = false
    assert not any(key == "buyers_riva_dei_martin" for lang in found.values() for _, key in lang)


def test_a_marker_in_visible_text_is_found(tree):
    path = tree / "it" / "pages" / "contact.toml"
    path.write_text(path.read_text() + '\nextra = "[DA COMPLETARE: prova]"\n')
    content.read.cache_clear()
    assert ("it/pages/contact.toml", "extra") in check.markers()["it"]


def test_exit_code_is_1_while_markers_remain(tree, capsys):
    assert check.main(today=date(2026, 10, 29)) == 1
    out = capsys.readouterr().out
    assert "site.toml" in out and "[it]" in out


def test_exit_code_is_0_when_everything_is_filled(tree, capsys, monkeypatch):
    monkeypatch.setattr(check, "markers", lambda: {"shared": [], "it": [], "en": []})
    assert check.main(today=date(2026, 10, 29)) == 0


def test_warning_alone_does_not_fail(tree, capsys, monkeypatch):
    monkeypatch.setattr(check, "markers", lambda: {"shared": [], "it": [], "en": []})
    assert check.main(today=date(2029, 8, 1)) == 0
    assert "WARNING" in capsys.readouterr().out
