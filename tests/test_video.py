import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

from .test_visits import patch

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)
SLOT = re.compile(r'<div class="video-slot".*?</div>', re.S)
VID = "dQw4w9WgXcQ"
READY = {"video": {"youtube_id": VID, "cover": "video-cover.jpg"}}
EXTERNAL = ("<iframe", "youtube-nocookie", "youtube.com/embed", "ytimg")
LOADED = re.compile(r'<(?:img|script|source|iframe)\b[^>]*(?:src|srcset|href)="https?://')


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


def page(client, prefix="", choice=None):
    cookies = {"cookie_choice": choice} if choice else {}
    return client.get(prefix + "/visite", cookies=cookies).text


def body(html: str) -> str:
    return NOTICE.sub("", html)


@pytest.mark.parametrize("choice", [None, "rejected", "nonsense"])
@pytest.mark.parametrize("prefix", ["", "/en"])
def test_no_external_resource_without_acceptance(client, production, monkeypatch, choice, prefix):
    patch(monkeypatch, site=READY)
    html = page(client, prefix, choice)
    for needle in EXTERNAL:
        assert needle not in body(html).lower()
    assert not LOADED.search(html)  # no absolute resource; the plain link is an anchor
    assert 'class="video-slot"' in html
    assert 'src="/static/img/video-cover.jpg"' in html
    assert re.search(r'<img[^>]+alt="[^"]+"[^>]+width="\d+"[^>]+height="\d+"', html)


def test_fallback_link_is_a_plain_anchor(client, production, monkeypatch):
    patch(monkeypatch, site=READY)
    for prefix, label in (("", "Guarda su YouTube"), ("/en", "Watch on YouTube")):
        html = page(client, prefix)
        link = re.search(rf'<a [^>]*href="https://www\.youtube\.com/watch\?v={VID}"[^>]*>', html)
        assert link and 'target="_blank"' in link.group(0)
        assert 'rel="noopener noreferrer"' in link.group(0)
        assert label in html


def test_no_choice_offers_both_buttons_and_returns_to_the_video(client, production, monkeypatch):
    patch(monkeypatch, site=READY)
    slot = SLOT.search(page(client)).group(0)
    assert 'value="accept"' in slot and 'value="reject"' in slot
    assert "Accetto e guardo" in slot and "Non ora" in slot
    assert 'name="next" value="/visite#video"' in slot
    en = SLOT.search(page(client, "/en")).group(0)
    assert "I accept and watch" in en and "Not now" in en


def test_rejected_offers_only_a_way_to_accept(client, production, monkeypatch):
    patch(monkeypatch, site=READY)
    slot = SLOT.search(page(client, choice="rejected")).group(0)
    assert 'value="accept"' in slot and 'value="reject"' not in slot


@pytest.mark.parametrize("prefix,lang", [("", "it"), ("/en", "en")])
def test_accepted_renders_the_nocookie_iframe(client, production, monkeypatch, prefix, lang):
    patch(monkeypatch, site=READY)
    html = page(client, prefix, "accepted")
    tag = re.search(r"<iframe[^>]*>", html).group(0)
    assert f'src="https://www.youtube-nocookie.com/embed/{VID}?' in tag
    assert 'loading="lazy"' in tag
    assert re.search(r'title="[^"]+"', tag)
    assert 'referrerpolicy="strict-origin-when-cross-origin"' in tag
    assert re.search(r'allow="encrypted-media; picture-in-picture; fullscreen"', tag)
    assert "allow-same-origin" not in tag and "autoplay" not in tag
    assert f"hl={lang}" in tag
    slot = SLOT.search(html).group(0)
    assert "<form" not in slot  # no consent form once accepted
    assert "ytimg" not in html and "youtube.com/embed" not in html
    assert "youtube.com/watch?v=" in html  # the plain link stays


def test_iframe_only_on_the_visits_page(client, production, monkeypatch):
    patch(monkeypatch, site=READY)
    for path in ("/", "/olio", "/chi-siamo", "/contatti", "/vini"):
        html = client.get(path, cookies={"cookie_choice": "accepted"}).text
        assert "<iframe" not in html and "youtube-nocookie" not in html


def test_placeholders_hide_the_block_in_production(client, production):
    for choice in (None, "accepted"):
        html = page(client, choice=choice)
        assert 'class="video-slot"' not in html
        assert "<iframe" not in html and "youtube" not in body(html).lower()
        assert "[DA COMPLETARE" not in html


def test_one_placeholder_is_enough_to_hide_it(client, production, monkeypatch):
    patch(monkeypatch, site={"video": {"youtube_id": VID}})  # cover still a marker
    assert 'class="video-slot"' not in page(client, choice="accepted")
    patch(monkeypatch, site={"video": {"youtube_id": VID + "x", "cover": "video-cover.jpg"}})
    assert 'class="video-slot"' not in page(client, choice="accepted")  # not an id


def test_preview_shows_a_placeholder_never_an_iframe(client, preview):
    html = page(client, choice="accepted")
    assert 'class="video-slot"' in html and "DA COMPLETARE" in SLOT.search(html).group(0)
    assert "<iframe" not in html and "youtube-nocookie" not in html
    assert "youtube.com/watch" not in html


def test_preview_with_real_values_behaves_like_production(client, preview, monkeypatch):
    patch(monkeypatch, site=READY)
    assert "<iframe" not in page(client)
    assert "<iframe" in page(client, choice="accepted")
