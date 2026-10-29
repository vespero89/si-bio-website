"""Photo sizes: scripts/photos.py makes the 600 wide variant only where the original is bigger (no
enlargements), app/photos.py builds the srcset from the files that exist, and the templates keep
width, height and alt next to it."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, photos
from app.main import app
from scripts import photos as script

IMG = config.STATIC_DIR / "img"
WINES = ["offida-pecorino", "offida-passerina", "armide", "passacaille"]


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_variant_widths_never_enlarge():
    assert script.variant_widths(687) == [600]
    assert script.variant_widths(1112) == [600]
    assert script.variant_widths(1500) == [600, 1200]
    assert script.variant_widths(600) == []
    assert script.variant_widths(400) == []


def test_jpeg_size_reads_the_header():
    assert photos.jpeg_size(IMG / "olio" / "olivo.jpg") == (1112, 616)
    assert photos.jpeg_size(IMG / "certificate-qr.svg") is None
    assert photos.jpeg_size(IMG / "olio" / "missing.jpg") is None


@pytest.mark.skipif(shutil.which("sips") is None, reason="sips (macOS) not installed")
def test_script_writes_original_and_600(tmp_path):
    out = tmp_path / "img" / "vini"
    written = script.build(IMG / "vini" / "armide.jpg", "armide", out)
    assert sorted(p.name for p in written) == ["armide-600.jpg", "armide.jpg"]
    assert photos.jpeg_size(out / "armide.jpg") == (687, 515)
    width, height = photos.jpeg_size(out / "armide-600.jpg")
    assert width == 600 and height in (449, 450)


@pytest.mark.skipif(shutil.which("sips") is None, reason="sips (macOS) not installed")
def test_script_makes_no_variant_for_a_small_photo(tmp_path):
    small = tmp_path / "small.jpg"
    subprocess.run(
        ["sips", "--resampleWidth", "400", str(IMG / "vini" / "armide.jpg"), "--out", str(small)],
        check=True,
        capture_output=True,
    )
    written = script.build(small, "small", tmp_path / "out")
    assert [p.name for p in written] == ["small.jpg"]


def test_script_refuses_a_file_that_is_not_a_jpeg(tmp_path, capsys):
    (tmp_path / "x.jpg").write_text("not a photo")
    assert script.main([str(tmp_path / "x.jpg"), "x"]) == 1
    assert "JPEG" in capsys.readouterr().err


def test_shipped_photos_have_their_600_variant():
    for slug in WINES:
        width, height = photos.jpeg_size(IMG / "vini" / f"{slug}-600.jpg")
        assert width == 600 and height in (449, 450), slug
    assert photos.jpeg_size(IMG / "olio" / "olivo-600.jpg")[0] == 600


def test_srcset_lists_the_existing_sizes():
    assert photos.srcset("vini/armide.jpg") == (
        "/static/img/vini/armide-600.jpg 600w, /static/img/vini/armide.jpg 687w"
    )


def test_srcset_is_empty_without_variant_or_for_a_placeholder():
    assert photos.srcset("certificate-qr.svg") == ""
    assert photos.srcset("vini/missing.jpg") == ""
    assert photos.srcset("[DA COMPLETARE: foto della bottiglia]") == ""
    assert photos.srcset("") == ""


def test_srcset_skips_a_variant_that_does_not_exist(tmp_path, monkeypatch):
    (tmp_path / "img" / "vini").mkdir(parents=True)
    shutil.copy(IMG / "vini" / "armide.jpg", tmp_path / "img" / "vini")
    monkeypatch.setattr(config, "STATIC_DIR", tmp_path)
    assert photos.srcset("vini/armide.jpg") == ""


@pytest.mark.parametrize("prefix", ["", "/en"])
@pytest.mark.parametrize("path", ["/", "/vini", "/vini/armide", "/olio"])
def test_images_with_srcset_keep_size_and_alt(client, prefix, path):
    html = client.get(prefix + path).text
    found = 0
    for tag in re.findall(r"<img [^>]*>", html):
        if "srcset=" not in tag:
            continue
        found += 1
        assert re.search(r' width="\d+"', tag) and re.search(r' height="\d+"', tag), tag
        assert " alt=" in tag and "sizes=" in tag, tag
        for url in re.findall(r"(/static/img/\S+?) \d+w", tag):
            assert (config.STATIC_DIR / url.removeprefix("/static/")).is_file(), url
    assert found, path


def test_the_scripts_run_as_files():
    run = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "photos.py")],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "usage" in run.stderr.lower()
