"""Wine pages: `/vini` and `/vini/<slug>`, the technical sheet, the PDF link .

Without JavaScript the row of wines is a list of plain links and every click loads a page."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app import config, content, i18n, jsonld
from app.lang import of
from app.templating import templates

router = APIRouter()

SHEET = (
    "style denomination grapes training vineyard_area harvest vinification aging bottle_aging abv "
    "total_acidity residual_sugar serving_temperature appearance aroma palate pairings "
    "bottles_per_year formats vintage awards"
).split()
"""Fields of the technical sheet, in the order shown; the labels are the keys `sheet.<field>`."""


def sheet(wine: dict) -> list[tuple[str, str]]:
    """(field, text) for every field that has a value; the template looks the label up."""
    rows = []
    for field in SHEET:
        value = wine.get(field)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        if value is None or value == "":
            continue
        rows.append((field, value))
    return rows


def photo(wine: dict) -> str:
    """File name of the bottle photo, or empty while it is a placeholder."""
    value = wine.get("photo", "")
    return "" if not value or content.has_marker(value) else value


def pdf(wine: dict, lang: str) -> dict | None:
    """The PDF in the page language, else the Italian one (`fallback`); None if there is none."""
    files = wine.get("pdf", {})
    for code in (lang, "it"):
        name = files.get(code)
        if name and (config.STATIC_DIR / "schede" / name).is_file():
            size = (config.STATIC_DIR / "schede" / name).stat().st_size
            return {
                "url": f"/static/schede/{name}",
                "size_kb": max(1, round(size / 1024)),
                "fallback": code != lang,
            }
    return None


def _structured(current: dict, lang: str) -> list[str]:
    """JSON-LD of a wine page: the product and its breadcrumb."""
    path = f"/vini/{current['slug']}"
    trail = [
        (jsonld.BRAND, "/"),
        (i18n.t(lang, "nav.wines"), "/vini"),
        (current["name"], path),
    ]
    return [
        jsonld.dumps(jsonld.product(current, path, lang, "jsonld.category_wine", photo(current))),
        jsonld.dumps(jsonld.breadcrumbs(trail, lang)),
    ]


def _page(request: Request, current: dict, heading: bool):
    lang = of(request)
    wines = content.wines(lang)
    # HTMX asks for the fragment; a history restore after a cache miss also sends HX-Request but
    # needs the whole page.
    fragment = (
        request.headers.get("hx-request") == "true"
        and request.headers.get("hx-history-restore-request") != "true"
    )
    response = templates.TemplateResponse(
        request,
        "wine_fragment.html" if fragment else "wines.html",
        {
            "wines": wines,
            "wine": current,
            "heading": heading,
            "sheet": sheet(current),
            "photo": photo(current),
            "pdf": pdf(current, lang),
            "jsonld": [] if heading else _structured(current, lang),
        },
    )
    response.headers["Vary"] = "HX-Request, HX-History-Restore-Request"
    return response


@router.get("/vini", response_class=HTMLResponse)
def wines_index(request: Request):
    wines = content.wines(of(request))
    if not wines:
        raise HTTPException(404)
    return _page(request, wines[0], heading=True)


@router.get("/vini/{slug}", response_class=HTMLResponse)
def wine_page(request: Request, slug: str):
    current = content.wine(of(request), slug)
    if current is None:
        raise HTTPException(404)
    return _page(request, current, heading=False)
