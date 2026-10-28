"""Pages written from the content files: home `/`, oil `/olio`, about `/chi-siamo`."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import content
from app.lang import of
from app.templating import templates
from app.wines import pdf, photo

router = APIRouter()

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
        request, "home.html", {"page": content.page(lang, "home"), "wines": content.wines(lang)}
    )


@router.get("/olio", response_class=HTMLResponse)
def oil_page(request: Request):
    lang = of(request)
    oil = content.oil(lang)
    return templates.TemplateResponse(
        request,
        "oil.html",
        {"oil": oil, "sheet": oil_sheet(oil), "photo": photo(oil), "pdf": pdf(oil, lang)},
    )


@router.get("/chi-siamo", response_class=HTMLResponse)
def about_page(request: Request):
    return templates.TemplateResponse(
        request, "about.html", {"page": content.page(of(request), "about")}
    )
