"""Jinja2 environment shared by the routes."""

from __future__ import annotations

import re
from urllib.parse import quote

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from app import certificate, config, content, cookies, i18n, lang, photos
from app.lang import of

templates = Jinja2Templates(directory=str(config.TEMPLATE_DIR))


@pass_context
def _t(context, key: str, **values) -> str:
    return i18n.t(of(context["request"]), key, **values)


@pass_context
def _num(context, value: float, decimals: int | None = None, group: bool = False) -> str:
    return i18n.num(of(context["request"]), value, decimals, group)


templates.env.globals.update(
    t=_t, num=_num, t_in=i18n.t, is_preview=lambda: config.PREVIEW, origin=lambda: config.BASE_URL
)


def _language_name(code: str) -> str:
    return i18n.load(code).get("language.name", code)


@pass_context
def _alternates(context) -> list[dict]:
    """The same page in every language that can be shown, for the selector and hreflang."""
    request = context["request"]
    path = request.state.path
    return [
        {"code": code, "name": _language_name(code), "url": lang.localize(path, code)}
        for code in lang.available()
    ]


@pass_context
def _canonical(context) -> str:
    request = context["request"]
    return config.BASE_URL + lang.localize(request.state.path, of(request))


@pass_context
def _farm_url(context) -> str:
    """Home of the family farm in the language of the page; empty until the address is known."""
    url = content.site().get("farm", {}).get("url", "").rstrip("/")
    return url + lang.localize("/", of(context["request"])) if url else ""


@pass_context
def _certificate(context) -> dict | None:
    """The organic certificate in the language of the page, or None (see app/certificate.py)."""
    return certificate.get(of(context["request"]))


@pass_context
def _is_current(context, path: str) -> bool:
    return context["request"].state.path.rstrip("/") == path


def _mailto(address: str, subject: str) -> str:
    """A mailto link with the subject percent-encoded in UTF-8 (spaces as %20, never +)."""
    return f"mailto:{address}?subject={quote(subject, safe='')}"


def _meta_text(text: str, limit: int = 155) -> str:
    """First sentence of a text for a meta description, cut at a word near `limit`; empty for
    an empty text or a placeholder."""
    text = " ".join((text or "").split())
    if not text or content.has_marker(text):
        return ""
    first = re.match(r".+?[.!?](?=\s|$)", text)
    text = first.group(0) if first else text
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "..."


templates.env.filters["meta_text"] = _meta_text

MENU = (
    ("nav.wines", "/vini"),
    ("nav.oil", "/olio"),
    ("nav.about", "/chi-siamo"),
    ("nav.visits", "/visite"),
    ("nav.contact", "/contatti"),
)

templates.env.globals.update(
    alternates=_alternates,
    canonical=_canonical,
    certificate=_certificate,
    farm_url=_farm_url,
    is_current=_is_current,
    menu=MENU,
    mailto=_mailto,
    cookie_choice=cookies.choice,
    has_marker=content.has_marker,
    srcset=photos.srcset,
    base_url=config.BASE_URL,
    localize=lang.localize,
    site=content.site,
    x_default_lang=lambda: lang.FALLBACK if lang.FALLBACK in lang.available() else lang.DEFAULT,
)
