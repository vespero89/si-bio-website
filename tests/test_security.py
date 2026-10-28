"""Task 15: error pages in the language of the page, no redirects from the old WordPress,
security headers on every response, cache rules for HTML and static files."""

import re

import pytest
from fastapi.testclient import TestClient

from app import config, content, wines
from app.main import app

PAGES = ["/", "/vini", "/vini/armide", "/olio", "/chi-siamo", "/visite", "/contatti"]
PAGES += ["/info/note-legali", "/info/privacy", "/info/cookie"]
HEADERS = [
    "content-security-policy",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "x-frame-options",
]


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", False)
    monkeypatch.setattr(config, "BASE_URL", "https://www.si-bio.it")
    content.read.cache_clear()
    yield
    content.read.cache_clear()


def csp(response) -> dict[str, str]:
    out = {}
    for part in response.headers["content-security-policy"].split(";"):
        name, _, value = part.strip().partition(" ")
        if name:
            out[name] = value
    return out


# error pages


@pytest.mark.parametrize(
    ("path", "code", "vini", "contatti"),
    [
        ("/nonexistent", "it", 'href="/vini"', 'href="/contatti"'),
        ("/vini/prosecco", "it", 'href="/vini"', 'href="/contatti"'),
        ("/en/nonexistent", "en", 'href="/en/vini"', 'href="/en/contatti"'),
        ("/en/vini/prosecco", "en", 'href="/en/vini"', 'href="/en/contatti"'),
        ("/en/a/b/c", "en", 'href="/en/vini"', 'href="/en/contatti"'),
    ],
)
def test_404_in_the_language_of_the_page(production, client, path, code, vini, contatti):
    r = client.get(path)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    assert f'<html lang="{code}">' in r.text
    assert vini in r.text
    assert contatti in r.text
    assert "Traceback" not in r.text
    assert not r.text.lstrip().startswith("{")


def test_error_pages_are_noindex_and_not_canonical(production, client):
    for path in ["/nonexistent", "/en/nonexistent", "/feed/", "/cookie-choice"]:
        r = client.get(path)
        assert "noindex" in r.headers["x-robots-tag"]
        assert re.search(r'<meta name="robots" content="noindex', r.text)
        assert 'rel="canonical"' not in r.text
        assert 'rel="alternate"' not in r.text


def test_unpublished_language_prefix_is_404_in_production(production, client):
    r = client.get("/de/vini")
    assert r.status_code == 404
    assert '<html lang="it">' in r.text


@pytest.mark.parametrize("path", ["/info/", "/info2/", "/blog/", "/2023/11/24/hello-world/"])
def test_old_wordpress_paths_do_not_redirect(production, client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert "location" not in r.headers
    assert "/vini/armide" not in r.text.replace('href="/vini"', "")
    r = client.get("/en" + path)
    assert r.status_code == 404
    assert '<html lang="en">' in r.text


@pytest.mark.parametrize(
    "path", ["/feed/", "/comments/feed/", "/wp-json/wp/v2/posts", "/xmlrpc.php"]
)
def test_gone_paths_answer_410_in_the_language_of_the_page(production, client, path):
    r = client.get(path)
    assert r.status_code == 410
    assert '<html lang="it">' in r.text
    assert 'href="/vini"' in r.text
    r = client.get("/en" + path)
    assert r.status_code == 410
    assert '<html lang="en">' in r.text
    assert 'href="/en/contatti"' in r.text


@pytest.mark.parametrize("path", ["/wp-login.php", "/wp-admin/index.php", "/wp-content/x.css"])
def test_wordpress_internals_get_a_plain_404(production, client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/plain")
    assert len(r.content) < 100
    assert "noindex" in r.headers["x-robots-tag"]


def test_htmx_request_to_a_missing_page_is_404_with_the_page(production, client):
    r = client.get("/vini/prosecco", headers={"HX-Request": "true"})
    assert r.status_code == 404
    assert "<html" in r.text
    r = client.get("/en/vini/prosecco", headers={"HX-Request": "true"})
    assert r.status_code == 404
    assert '<html lang="en">' in r.text


def test_method_not_allowed_is_a_page_with_allow(production, client):
    r = client.get("/cookie-choice")
    assert r.status_code == 405
    assert r.headers["allow"] == "POST"
    assert '<html lang="it">' in r.text
    assert 'href="/vini"' in r.text
    r = client.post("/vini", data={})
    assert r.status_code == 405
    assert "noindex" in r.headers["x-robots-tag"]


def test_unexpected_error_is_a_500_page_without_details(production, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(wines.content, "wines", boom)
    r = TestClient(app, raise_server_exceptions=False).get("/vini")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("text/html")
    assert "secret detail" not in r.text
    assert "Traceback" not in r.text
    assert "noindex" in r.headers["x-robots-tag"]
    assert "content-security-policy" in r.headers


# security headers


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/en/vini",
        "/static/css/sibio.css",
        "/static/js/wines.js",
        "/robots.txt",
        "/nonexistent",
        "/feed/",
        "/wp-login.php",
        "/cookie-choice",
        "/?lang=en",
    ],
)
def test_security_headers_on_every_response(production, client, path):
    r = client.get(path)
    for name in HEADERS:
        assert name in r.headers, f"{name} missing on {path} ({r.status_code})"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert r.headers["x-frame-options"] == "DENY"


def test_security_headers_on_the_cookie_choice_redirect(production, client):
    r = client.post("/cookie-choice", data={"choice": "accept", "next": "/vini"})
    assert r.status_code == 303
    assert "content-security-policy" in r.headers


def test_csp_is_strict(production, client):
    r = client.get("/")
    policy = csp(r)
    full = r.headers["content-security-policy"]
    assert "unsafe-inline" not in full
    assert "unsafe-eval" not in full
    assert policy["default-src"] == "'self'"
    assert policy["script-src"] == "'self'"
    assert policy["style-src"] == "'self'"
    assert policy["img-src"] == "'self' data:"
    assert policy["font-src"] == "'self'"
    assert policy["frame-src"] == "https://www.youtube-nocookie.com"
    assert policy["frame-ancestors"] == "'none'"
    assert policy["object-src"] == "'none'"
    assert policy["base-uri"] == "'self'"
    assert "*" not in full


def test_csp_is_the_same_everywhere(production, client):
    assert (
        client.get("/").headers["content-security-policy"]
        == client.get("/visite").headers["content-security-policy"]
        == client.get("/static/css/sibio.css").headers["content-security-policy"]
    )


@pytest.mark.parametrize("path", PAGES + ["/en/vini/armide", "/en/visite", "/nonexistent"])
def test_pages_work_under_the_csp(production, client, path):
    """No inline script, style tag, style attribute or event handler: the CSP would block them.
    The application/ld+json blocks are data, not executed, so the policy does not apply."""
    html = client.get(path).text
    scripts = re.findall(r"<script\b([^>]*)>", html)
    assert all("src=" in s or "application/ld+json" in s for s in scripts)
    assert "<style" not in html
    assert not re.search(r"<[^>]+\sstyle=", html)
    assert not re.search(r"<[^>]+\son[a-z]+=", html)
    assert "javascript:" not in html


def test_htmx_does_not_inject_its_inline_style(production, client):
    html = client.get("/vini").text
    assert 'name="htmx-config"' in html
    assert "includeIndicatorStyles" in html


def test_hsts_only_when_base_url_is_https(production, client, monkeypatch):
    assert "max-age=" in client.get("/").headers["strict-transport-security"]
    monkeypatch.setattr(config, "BASE_URL", "http://127.0.0.1:8000")
    assert "strict-transport-security" not in client.get("/").headers


def test_html_varies_by_cookie_and_is_not_stored_by_shared_caches(production, client):
    for path in ["/", "/vini", "/vini/armide", "/nonexistent", "/info/cookie"]:
        r = client.get(path)
        vary = [v.strip().lower() for v in r.headers["vary"].split(",")]
        assert "cookie" in vary, path
        assert "no-cache" in r.headers["cache-control"] or "private" in r.headers["cache-control"]
    vary = client.get("/vini/armide", headers={"HX-Request": "true"}).headers["vary"].lower()
    assert "hx-request" in vary
    assert "cookie" in vary


def test_static_files_revalidate(production, client):
    r = client.get("/static/css/sibio.css")
    assert r.headers["cache-control"] == "no-cache"
    assert "etag" in r.headers
    assert "cookie" not in r.headers.get("vary", "").lower()
