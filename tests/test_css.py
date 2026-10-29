"""The stylesheet of the new design: assets are in place and every class the pages use is styled."""

import re

from app import config

TEMPLATES = config.APP_DIR / "templates"

CSS = (config.STATIC_DIR / "css" / "sibio.css").read_text()

# Classes the current templates carry as page or hook names only; nothing to style.
HOOKS = {
    "contact-page",
    "cookie-choice",
    "oil-page",
    "pdf-link",
    "visits-buyers",
    "visits-hotel",
    "visits-package",
    "visits-price",
    "wines-page",
    "movement-1",  # first movement of the home row, only a hook
    "visits-page",
    "header-row",
    "cls",  # variable of the stave partials
}


def css_classes(text):
    return set(
        re.findall(r"\.([a-zA-Z_][a-zA-Z0-9_-]*)", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
    )


def template_classes():
    found = set()
    for path in TEMPLATES.rglob("*.html"):
        for value in re.findall(r'class="([^"]*)"', path.read_text()):
            found.update(c for c in value.split() if not re.search(r"[{%}]", c))
    return found


def test_every_class_in_the_templates_is_styled_or_a_known_hook():
    missing = template_classes() - css_classes(CSS) - HOOKS
    assert not missing, sorted(missing)


def test_parts_the_redesign_did_not_cover_keep_their_styles():
    wanted = {
        "cookie-notice",
        "cookie-form",
        "wp",
        "wp-photo",
        "visits-tag",
        "visits-includes",
        "oil-scene",
        "lead",
        "legal-tabs",
        "legal-provisional",
        "legal-table",
        "video-slot",
        "video-play",
        "video-placeholder",
        "wine-row",
        "wine-row-name",
        "bottle-placeholder",
        "htmx-added",
        "copy-live",
        "claim",
        "certified",
    }
    assert wanted <= css_classes(CSS), sorted(wanted - css_classes(CSS))


def test_error_page_and_legal_text_are_styled():
    assert "error-page" in css_classes(CSS)
    assert re.search(r"\.legal-page|\.legal-tabs", CSS)


def test_css_has_no_external_url_and_fonts_exist():
    urls = [u.strip("'\"") for u in re.findall(r"url\(([^)]+)\)", CSS)]
    assert urls and all(u.startswith("/static/fonts/") for u in urls)
    for u in urls:
        assert (config.STATIC_DIR / u.removeprefix("/static/")).is_file(), u
    assert "@import" not in CSS and "http" not in CSS


def test_dialog_script_and_stave_partials_are_in_place():
    assert (config.STATIC_DIR / "js" / "wine-dialog.js").is_file()
    for name in ("stave_long.html", "stave_short.html"):
        text = (TEMPLATES / "partials" / name).read_text()
        assert "<svg" in text and "aria-hidden" in text and "cls" in text


def test_no_dashes_in_new_assets():
    for path in (
        config.STATIC_DIR / "css" / "sibio.css",
        config.STATIC_DIR / "js" / "wine-dialog.js",
        TEMPLATES / "partials" / "stave_long.html",
        TEMPLATES / "partials" / "stave_short.html",
    ):
        text = path.read_text() if path.exists() else ""
        assert "—" not in text and "–" not in text, path
