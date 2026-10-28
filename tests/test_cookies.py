import re

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import config, cookies
from app.main import app
from app.templating import templates

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def post(client, path="/cookie-choice", cookie=None, **fields):
    headers = {"Cookie": f"cookie_choice={cookie}"} if cookie else {}
    return client.post(path, data=fields, headers=headers)


def notice(html: str) -> str | None:
    found = re.search(r'<section class="cookie-notice".*?</section>', html, re.S)
    return found.group(0) if found else None


def test_notice_shown_without_a_choice_on_every_page(client):
    for path in ("/", "/vini", "/olio", "/chi-siamo", "/visite", "/contatti", "/en/vini"):
        block = notice(client.get(path).text)
        assert block, path
        assert block.count('name="choice"') == 2
        assert 'value="accept"' in block and 'value="reject"' in block


def test_notice_form_posts_without_javascript_and_keeps_the_page(client):
    block = notice(client.get("/vini").text)
    assert '<form method="post" action="/cookie-choice"' in block
    assert 'name="next" value="/vini"' in block
    en = notice(client.get("/en/vini").text)
    assert 'action="/en/cookie-choice"' in en
    assert 'name="next" value="/vini"' in en


def test_both_buttons_are_equal(client):
    block = notice(client.get("/").text)
    buttons = re.findall(r"<button\b([^>]*)>", block)
    assert len(buttons) == 2
    classes = {re.search(r'class="([^"]*)"', b).group(1) for b in buttons}
    assert len(classes) == 1


def test_notice_texts_in_both_languages(client):
    assert "cookie tecnici" in notice(client.get("/").text)
    assert "technical cookies" in notice(client.get("/en/").text)


@pytest.mark.parametrize(("choice", "value"), [("accept", "accepted"), ("reject", "rejected")])
def test_choice_sets_the_cookie_and_goes_back(client, choice, value):
    r = post(client, choice=choice, next="/olio")
    assert r.status_code == 303
    assert r.headers["location"] == "/olio"
    cookie = r.headers["set-cookie"]
    assert f"cookie_choice={value}" in cookie
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    assert "Path=/" in cookie
    assert f"Max-Age={cookies.MAX_AGE}" in cookie
    assert "Secure" not in cookie
    assert 180 * 86400 <= cookies.MAX_AGE <= 186 * 86400


def test_cookie_is_secure_in_production(client, monkeypatch):
    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    r = post(client, choice="accept", next="/")
    assert "Secure" in r.headers["set-cookie"]


def test_language_prefix_is_kept(client):
    r = post(client, "/en/cookie-choice", choice="reject", next="/vini")
    assert r.status_code == 303
    assert r.headers["location"] == "/en/vini"
    assert "cookie_choice=rejected" in r.headers["set-cookie"]


def test_query_of_the_page_is_kept(client):
    r = post(client, choice="accept", next="/vini?x=1")
    assert r.headers["location"] == "/vini?x=1"


@pytest.mark.parametrize(
    "bad",
    [
        "https://evil.example",
        "//evil.example",
        "http:evil",
        "/\\evil.example",
        "evil",
        "",
        "/a\r\nb",
    ],
)
def test_open_redirect_rejected(client, bad):
    r = post(client, choice="accept", next=bad)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    en = post(client, "/en/cookie-choice", choice="accept", next=bad)
    assert en.headers["location"] == "/en/"


def test_missing_next_goes_home(client):
    assert post(client, choice="reject").headers["location"] == "/"


@pytest.mark.parametrize("fields", [{}, {"choice": "maybe"}, {"choice": "ACCEPT"}, {"next": "/"}])
def test_bad_choice_is_400_and_sets_nothing(client, fields):
    r = post(client, **fields)
    assert r.status_code == 400
    assert "set-cookie" not in r.headers


def test_get_is_405(client):
    assert client.get("/cookie-choice").status_code == 405


def test_notice_hidden_after_a_choice(client):
    for value in ("accepted", "rejected"):
        client.cookies.set("cookie_choice", value)
        assert notice(client.get("/vini").text) is None
        client.cookies.clear()


def test_unknown_cookie_value_is_no_choice(client):
    for value in ("yes", "ACCEPTED", "x" * 500):
        client.cookies.set("cookie_choice", value)
        assert notice(client.get("/").text), value
        client.cookies.clear()


def test_choice_on_english_page_is_valid_everywhere(client):
    r = post(client, "/en/cookie-choice", choice="accept", next="/")
    assert "Path=/" in r.headers["set-cookie"]
    client.cookies.set("cookie_choice", "accepted")
    assert notice(client.get("/").text) is None


def test_reject_after_accept_writes_a_new_rejected_cookie(client):
    r = post(client, cookie="accepted", choice="reject", next="/visite")
    assert "cookie_choice=rejected" in r.headers["set-cookie"]


def test_no_cookie_set_by_pages_and_no_external_resources(client):
    for path in ("/", "/visite", "/en/visite"):
        r = client.get(path)
        assert "cookie_choice" not in r.headers.get("set-cookie", "")
        assert not re.search(r'(src|href|action)="(https?:)?//(?!si-bio)', notice(r.text))
        low = NOTICE.sub("", r.text).lower()
        for bad in ("<iframe", "youtube.com", "youtube-nocookie", "ytimg", "google"):
            assert bad not in low


def test_footer_link_to_manage_cookies(client):
    html = client.get("/").text
    footer = re.search(r"<footer.*?</footer>", html, re.S).group(0)
    assert '<a href="/info/cookie#scelta">Gestisci i cookie</a>' in footer
    en = client.get("/en/").text
    assert '<a href="/en/info/cookie#scelta">Manage cookies</a>' in en


def test_footer_link_stays_after_a_choice(client):
    client.cookies.set("cookie_choice", "accepted")
    assert "Gestisci i cookie" in client.get("/").text


def render_choice_block(lang, cookie=None, path="/info/cookie"):
    headers = [(b"cookie", f"cookie_choice={cookie}".encode())] if cookie else []
    request = Request(
        {"type": "http", "method": "GET", "path": path, "headers": headers, "query_string": b"",
         "state": {"lang": lang, "path": path}}
    )  # fmt: skip
    return templates.get_template("partials/cookie_choice.html").render(request=request)


def test_choice_block_shows_current_choice_and_buttons_for_the_cookie_page():
    html = render_choice_block("it", cookie="accepted")
    assert 'id="scelta"' in html
    assert "Hai accettato" in html
    assert html.count('name="choice"') == 2
    assert "Hai rifiutato" in render_choice_block("it", cookie="rejected")
    assert "Non hai ancora scelto" in render_choice_block("it", cookie="junk")
    assert "You have accepted" in render_choice_block("en", cookie="accepted")


def test_helper(client):
    def req(value):
        headers = [(b"cookie", f"cookie_choice={value}".encode())] if value else []
        return Request({"type": "http", "headers": headers})

    assert cookies.choice(req("accepted")) == "accepted"
    assert cookies.choice(req("rejected")) == "rejected"
    assert cookies.choice(req("zzz")) is None
    assert cookies.choice(req(None)) is None
    assert templates.env.globals["cookie_choice"] is cookies.choice
