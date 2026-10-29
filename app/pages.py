"""Pages written from the content files: home `/`, oil `/olio`, about `/chi-siamo`."""

from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import config, content, jsonld
from app.lang import of
from app.templating import templates
from app.wines import pdf, photo

router = APIRouter()

YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def video() -> dict | None:
    """The promo video from `[video]` of site.toml: {id, cover}, or None while a value is a marker
    or not a YouTube id (production). In preview with a marker: {placeholder: text}, never a URL."""
    data = content.site().get("video", {})
    vid, cover = data.get("youtube_id", ""), data.get("cover", "")
    if config.PREVIEW and (content.has_marker(vid) or content.has_marker(cover)):
        return {"placeholder": " ".join(v for v in (vid, cover) if content.has_marker(v))}
    if YOUTUBE_ID.fullmatch(vid) and cover and not content.has_marker(cover):
        return {"id": vid, "cover": cover}
    return None


OIL_SHEET = "cultivar area harvest milling acidity formats pairings".split()
"""Fields of the oil sheet, in the order shown; the labels are the keys `sheet.<field>`."""


def oil_sheet(oil: dict) -> list[tuple[str, str]]:
    """(field, text) for every field that has a value."""
    rows = []
    for field in OIL_SHEET:
        value = oil.get(field)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        if value:
            # The label of "harvest" for oil is "Raccolta", not the grape "Vendemmia".
            rows.append(("oil_harvest" if field == "harvest" else field, value))
    return rows


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    lang = of(request)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "page": content.page(lang, "home"),
            "about": content.page(lang, "about"),
            "wines": content.wines(lang),
            "jsonld": [jsonld.dumps(jsonld.organization(lang)), jsonld.dumps(jsonld.website(lang))],
        },
    )


@router.get("/olio", response_class=HTMLResponse)
def oil_page(request: Request):
    lang = of(request)
    oil = content.oil(lang)
    trail = [(jsonld.BRAND, "/"), (oil["name"], "/olio")]
    return templates.TemplateResponse(
        request,
        "oil.html",
        {
            "oil": oil,
            "sheet": oil_sheet(oil),
            "photo": photo(oil),
            "scene": oil.get("scene", ""),
            "pdf": pdf(oil, lang),
            "jsonld": [
                jsonld.dumps(jsonld.product(oil, "/olio", lang, "jsonld.category_oil", photo(oil))),
                jsonld.dumps(jsonld.breadcrumbs(trail, lang)),
            ],
        },
    )


@router.get("/chi-siamo", response_class=HTMLResponse)
def about_page(request: Request):
    return templates.TemplateResponse(
        request, "about.html", {"page": content.page(of(request), "about")}
    )


@router.get("/visite", response_class=HTMLResponse)
def visits_page(request: Request):
    return templates.TemplateResponse(
        request, "visits.html", {"page": content.page(of(request), "visits"), "video": video()}
    )
