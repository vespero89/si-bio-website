import re

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

HX = {"HX-Request": "true"}


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_htmx_request_gets_the_fragment_only(client):
    html = client.get("/vini/armide", headers=HX).text
    assert "<html" not in html and "site-header" not in html and "<footer" not in html
    assert 'class="wp"' in html
    assert "<h1" in html and "Armide" in html
    assert "<title>" in html and "| Si Bio" in html
    assert "subject=Si%20Bio%3A" in html


def test_plain_request_gets_the_full_page(client):
    html = client.get("/vini/armide").text
    assert "<html" in html and "<footer" in html and 'class="wp"' in html


def test_fragment_requested_without_hx_header_is_the_full_page(client):
    assert "<html" in client.get("/vini/armide", headers={"HX-Request": "false"}).text


def test_history_restore_gets_the_full_page(client):
    headers = {**HX, "HX-History-Restore-Request": "true"}
    assert "<html" in client.get("/vini/armide", headers=headers).text


@pytest.mark.parametrize("path", ["/vini", "/vini/armide", "/en/vini/armide"])
@pytest.mark.parametrize("headers", [{}, HX])
def test_vary_hx_request(client, path, headers, monkeypatch):
    monkeypatch.setattr(config, "PREVIEW", True)
    response = client.get(path, headers=headers)
    assert response.status_code == 200
    assert "HX-Request" in response.headers["vary"]


def test_unknown_wine_is_404_with_and_without_htmx(client):
    assert client.get("/vini/nope").status_code == 404
    assert client.get("/vini/nope", headers=HX).status_code == 404


def test_row_links_carry_htmx_attributes(client):
    html = client.get("/vini/armide").text
    nav = re.search(r'<nav class="wine-row".*?</nav>', html, re.S).group(0)
    assert 'hx-target="#wine-stage"' in nav and 'hx-push-url="true"' in nav
    links = re.findall(r'<a href="([^"]+)"[^>]*hx-get="([^"]+)"', nav)
    assert len(links) == 4 and all(href == get for href, get in links)
    assert 'id="wine-stage"' in html


def test_fragment_updates_the_row_out_of_band(client):
    html = client.get("/vini/armide", headers=HX).text
    assert 'id="wine-row"' in html and 'hx-swap-oob="innerHTML"' in html
    current = re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', html)
    assert current == ["/vini/armide"]


def test_focus_target_in_page_and_fragment(client):
    for html in (client.get("/vini/armide").text, client.get("/vini/armide", headers=HX).text):
        assert re.search(r'<h1 tabindex="-1">Armide', html)


def test_index_keeps_one_h1(client):
    html = client.get("/vini").text
    assert html.count("<h1") == 1 and 'aria-current="true"' in html


def test_scripts_are_local(client):
    html = client.get("/vini/armide").text
    srcs = re.findall(r'<script\b[^>]*src="([^"]+)"', html)
    assert "/static/js/htmx.min.js" in srcs and "/static/js/wines.js" in srcs
    assert "/static/js/contact.js" in srcs
    assert all(s.startswith("/static/") for s in srcs)
    assert not re.findall(r'<(?:script|img)\b[^>]*src="(?!/)', html)
    assert not re.findall(r'<link\b[^>]*rel="(?:stylesheet|preload)"[^>]*href="(?!/)', html)
    assert client.get("/static/js/htmx.min.js").status_code == 200
    assert client.get("/static/js/wines.js").status_code == 200


def test_contact_script_comes_from_the_base_layout(client):
    assert "/static/js/contact.js" in client.get("/").text
