"""Drift of the home rail: markup, locale keys, script, styles (motion is checked in a browser)."""

import re

import pytest
from fastapi.testclient import TestClient

from app import config, i18n
from app.main import app

JS = (config.STATIC_DIR / "js" / "rail-drift.js").read_text()
CSS = (config.STATIC_DIR / "css" / "sibio.css").read_text()


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def rail(html):
    return re.search(r"<ul class=\"rail\" data-rail>.*?</ul>", html, re.S).group(0)


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_toggle_button_is_hidden_until_the_script_runs(client, prefix):
    html = client.get(prefix + "/").text
    button = re.search(r"<button[^>]*data-rail-toggle[^>]*>", html).group(0)
    assert " hidden" in button and 'aria-pressed="false"' in button
    assert 'type="button"' in button and "aria-label=" in button
    assert html.count("data-rail-toggle") == 1


@pytest.mark.parametrize("lang", ["it", "en"])
def test_pause_label_exists_in_both_languages(lang):
    assert i18n.load(lang)["wines.pause"].strip()


def test_server_markup_has_no_clones(client):
    block = rail(client.get("/").text)
    assert '<li class="wine" aria-hidden' not in block and "tabindex" not in block
    assert block.count('class="wine"') == block.count("data-wine=")


def test_home_loads_the_drift_script_after_the_dialog_script(client):
    html = client.get("/").text
    dialog = html.index("/static/js/wine-dialog.js")
    drift = html.index('<script src="/static/js/rail-drift.js" defer></script>')
    assert dialog < drift
    assert "/static/js/rail-drift.js" not in client.get("/vini").text


def test_script_animates_with_css_and_respects_reduced_motion():
    assert "prefers-reduced-motion" in JS and "reduce.matches" in JS
    assert "requestAnimationFrame" not in JS and "setInterval" not in JS
    assert "--drift-distance" in JS and "--drift-duration" in JS and "--drift-delay" in JS
    assert 'aria-hidden", "true"' in JS and '"tabindex", "-1"' in JS
    assert "aria-pressed" in JS and "SECONDS_PER_CARD = 7" in JS


def test_script_keeps_the_panels_in_the_row():
    # The movement panels are items of the row: they are cloned and move with the cards
    assert "li.movement" not in JS and "movements" not in JS
    assert "rail.children" in JS


def test_script_adds_nothing_inline_and_no_dashes():
    for forbidden in ("innerHTML", "cssText", 'setAttribute("style"', "<style", "eval("):
        assert forbidden not in JS
    assert "—" not in JS and "–" not in JS


def test_drift_styles_exist():
    for name in ("is-drifting", "is-enhanced", "rail-clip", "head-tools"):
        assert re.search(r"\." + name + r"\b", CSS), name
    assert "rail-stage" not in CSS and ".movements" not in CSS
    assert re.search(r"@keyframes rail-drift\s*\{[^}]*translateX", CSS)
    assert "animation: rail-drift" in CSS and "animation-play-state: paused" in CSS
    assert "has-dialog .rail.is-drifting" in CSS
    # the animation sits under no-preference, so reduced motion never gets it
    block = CSS[
        CSS.index("@media (prefers-reduced-motion: no-preference) {\n  .rail.is-drifting") :
    ]
    assert "animation: rail-drift" in block.split("\n}\n")[0]
    assert re.search(r"\.rail\.is-enhanced\s*\{[^}]*scroll-snap-type: none", CSS)
