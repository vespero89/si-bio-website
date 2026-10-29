"""Technical pass: walks the public pages in every published language."""

import re

import pytest
from fastapi.testclient import TestClient

from app import config, content
from app.main import app

NOTICE = re.compile(r'<section class="cookie-notice".*?</section>', re.S)
PATHS = ["/", "/vini", "/olio", "/chi-siamo", "/visite", "/contatti"]
PATHS += ["/info/note-legali", "/info/privacy", "/info/cookie"]
PATHS += [f"/vini/{w['slug']}" for w in content.wines("it")]


def urls():
    return [
        (lang, path if lang == "it" else f"/{lang}{path}")
        for lang in config.PUBLISHED
        for path in PATHS
    ]


@pytest.fixture(scope="module")
def client():
    return TestClient(app, follow_redirects=False)


def attrs(html, tag):
    return [
        dict(re.findall(r'([\w-]+)="([^"]*)"', raw))
        for raw in re.findall(rf"<{tag}\b([^>]*)>", html)
    ]


@pytest.mark.parametrize("lang,url", urls())
def test_page_structure(client, lang, url):
    response = client.get(url)
    assert response.status_code == 200
    html = response.text
    assert f'<html lang="{lang}">' in html
    assert len(re.findall(r"<h1\b", html)) == 1
    levels = [int(n) for n in re.findall(r"<h([1-6])\b", html)]
    for before, after in zip(levels, levels[1:], strict=False):
        assert after <= before + 1, f"{url}: h{before} then h{after}"
    # Photos inside the wine row sit in a link with the wine name: alt="" is right for them.
    row = "".join(re.findall(r'<nav class="wine-row".*?</nav>', html, re.S))
    for img in attrs(html.replace(row, ""), "img"):
        assert img.get("alt") and img.get("width") and img.get("height"), (url, img)
    for img in attrs(row, "img"):
        assert img.get("width") and img.get("height"), (url, img)
    body = re.sub(r"<script.*?</script>", "", NOTICE.sub("", html), flags=re.S)
    for match in re.finditer(r"<(a|button)\b([^>]*)>(.*?)</\1>", body, re.S):
        text = re.sub(r"<[^>]+>", "", match.group(3)).strip()
        assert text or "aria-label=" in match.group(2), (url, match.group(0)[:80])
    head = html.split("</head>")[0]
    canonical = re.findall(r'<link rel="canonical" href="([^"]+)"', head)
    assert len(canonical) == 1 and canonical[0].startswith(config.BASE_URL)
    hreflangs = re.findall(r'<link rel="alternate" hreflang="([^"]+)"', head)
    assert sorted(hreflangs) == sorted([*config.PUBLISHED, "x-default"])
    assert len(re.findall(r"<title>[^<]+</title>", head)) == 1
    assert 'name="description"' in head
