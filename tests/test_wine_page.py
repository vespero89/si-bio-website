import re

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

HX = {"HX-Request": "true"}


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)


def stage(html: str) -> str:
    return re.search(r'<article class="wp">.*?</article>', html, re.S).group(0)


def test_wine_page_has_the_score_header_with_stave_and_subtitle(client, production):
    html = stage(client.get("/vini/armide").text)
    header = re.search(r'<header class="score">.*?</header>', html, re.S).group(0)
    assert '<svg class="stave"' in header
    assert '<h1 tabindex="-1">Armide</h1>' in header
    assert '<p class="score-sub">Opera di Lully</p>' in header
    assert 'class="wp-body"' in html and 'class="wp-photo"' in html


def test_story_comes_before_the_sheet_and_holds_the_claim(client, production):
    html = stage(client.get("/vini/armide").text)
    story = re.search(r'<section class="story".*?</section>', html, re.S).group(0)
    assert "<h2" in story and "Il nome" in story
    assert 'class="story-claim"' in story and "Marmolada" in story
    assert "Taste the Essence" in story
    assert html.index('class="story"') < html.index('<dl class="sheet">')


def test_wine_without_a_story_has_no_story_section_in_production(client, production):
    html = stage(client.get("/vini/offida-pecorino").text)
    assert 'class="story' not in html
    assert "DA COMPLETARE" not in html and "Marmolada" not in html


def test_english_story_and_subtitle(client, production):
    html = stage(client.get("/en/vini/passacaille").text)
    assert 'class="score-sub"' in html and 'class="story"' in html
    assert "Taste the Essence" in html


def test_index_stage_uses_h2_and_keeps_the_page_h1(client, production):
    html = client.get("/vini").text
    assert len(re.findall(r"<h1\b", html)) == 1
    assert '<h2 tabindex="-1">' in stage(html)


def test_fragment_still_has_the_wp_stage_and_oob_row(client, production):
    html = client.get("/vini/armide", headers=HX).text
    assert '<article class="wp">' in html
    assert 'id="wine-row" hx-swap-oob="innerHTML"' in html
    assert "wine-front" not in html
