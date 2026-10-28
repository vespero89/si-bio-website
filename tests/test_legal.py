import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)
PAGES = ("note-legali", "privacy", "cookie")
BRACKET = re.compile(
    r"\[(?:DA VERIFICARE|DA COMPLETARE|DA DEFINIRE"
    r"|TO BE VERIFIED|TO BE COMPLETED|TO BE DEFINED)[^\]]*\]"
)

# The open points of the legal pages for the farm and the lawyer: the pre-launch check counts them.
EXPECTED = {
    "note-legali": 3,  # registered office, PEC, REA
    "privacy": 4,  # hosting provider, log basis, log retention, email retention
    "cookie": 0,
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


def main_of(html):
    return re.search(r"<main.*?</main>", html, re.S).group(0)


@pytest.mark.parametrize("prefix", ["", "/en"])
@pytest.mark.parametrize("page", PAGES)
def test_pages_answer_200_with_one_h1(client, prefix, page):
    response = client.get(f"{prefix}/info/{page}")
    assert response.status_code == 200
    assert response.text.count("<h1") == 1
    assert f'<html lang="{prefix[1:] or "it"}">' in response.text


def test_languages_differ(client):
    assert "Note legali" in client.get("/info/note-legali").text
    assert "Legal notice" in client.get("/en/info/note-legali").text
    assert "Informativa sulla privacy" in client.get("/info/privacy").text
    assert "Privacy notice" in client.get("/en/info/privacy").text


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_provisional_notice_on_top_of_every_page(client, prefix):
    for page in PAGES:
        main = main_of(client.get(f"{prefix}/info/{page}").text)
        assert 'class="legal-provisional"' in main
        assert main.index("legal-provisional") < main.index("</h1>") + 400


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_tabs_link_the_three_pages(client, prefix):
    html = client.get(f"{prefix}/info/privacy").text
    tabs = re.search(r'<nav class="legal-tabs".*?</nav>', html, re.S).group(0)
    assert re.findall(r'href="([^"]+)"', tabs) == [f"{prefix}/info/{p}" for p in PAGES]
    assert tabs.count('aria-current="page"') == 1
    assert re.search(r'href="[^"]+" aria-current="page">(Privacy|Informativa)', tabs)


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_footer_links_to_notice_and_privacy(client, prefix):
    html = client.get(f"{prefix}/contatti").text
    footer = re.search(r"<footer.*?</footer>", html, re.S).group(0)
    legal = re.search(r'<nav class="footer-legal".*?</nav>', footer, re.S).group(0)
    assert re.findall(r'href="([^"]+)"', legal) == [
        f"{prefix}/info/note-legali",
        f"{prefix}/info/privacy",
    ]
    assert f'href="{prefix}/info/cookie#scelta"' in footer


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_cookie_page_has_the_choice_and_lists_the_two_cookies(client, prefix):
    html = client.get(f"{prefix}/info/cookie").text
    main = main_of(html)
    assert 'id="scelta"' in main
    assert main.count('name="choice"') == 2
    assert "<code>lang</code>" in main and "<code>cookie_choice</code>" in main
    assert "policies.google.com/privacy" in main


def test_cookie_page_shows_the_current_choice(client):
    client.cookies.set("cookie_choice", "accepted")
    assert "Hai accettato" in client.get("/info/cookie").text
    client.cookies.set("cookie_choice", "rejected")
    assert "You have rejected" in client.get("/en/info/cookie").text


def test_privacy_says_only_what_is_true(client):
    html = main_of(client.get("/info/privacy").text)
    assert "export@si-bio.it" in html
    assert "Fuselli e Filari" in html
    assert "YouTube" in html
    assert "Garante" in html
    assert "<form" not in html


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_notice_has_company_data(client, prefix):
    main = main_of(client.get(f"{prefix}/info/note-legali").text)
    assert "SI - BIO di Premici &amp; Aleandri Società Agricola Semplice" in main
    assert "02274900444" in main


@pytest.mark.parametrize("prefix", ["", "/en"])
def test_placeholders_stay_visible_in_production(client, production, prefix):
    for page, count in EXPECTED.items():
        found = BRACKET.findall(main_of(client.get(f"{prefix}/info/{page}").text))
        assert len(found) == count, (page, found)


def test_placeholders_use_the_marker_of_the_language(client, production):
    it = BRACKET.findall(client.get("/info/note-legali").text)
    en = BRACKET.findall(client.get("/en/info/note-legali").text)
    assert it and all(m.startswith(("[DA COMPLETARE", "[DA DEFINIRE")) for m in it)
    assert en and all(m.startswith(("[TO BE COMPLETED", "[TO BE DEFINED")) for m in en)


def test_no_external_resource_script_or_extra_form(client):
    for prefix in ("", "/en"):
        for page in PAGES:
            html = client.get(f"{prefix}/info/{page}").text
            assert not re.search(r"<(iframe|script|img)\b[^>]+src=\"(https?:)?//", html)
            assert not re.search(
                r"<link rel=\"(stylesheet|preload)\"[^>]+href=\"(https?:)?//", html
            )
            assert "<script" not in re.sub(r'<script src="/static/[^"]+" defer></script>', "", html)
            assert not re.search(r"<[^>]+\son\w+=", html)
            forms = NOTICE.sub("", html).count("<form")
            assert forms == (1 if page == "cookie" else 0)
