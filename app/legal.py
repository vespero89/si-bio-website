"""Legal pages under `/info/`: legal notice, privacy, cookies. The texts are templates, one folder
per language (`templates/legal/<lang>/`). Open points stay as visible markers in production too."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import content, i18n
from app.lang import of
from app.templating import templates

router = APIRouter()

PAGES = (
    ("note-legali", "legal.tab_notice", "legal.title_notice"),
    ("privacy", "legal.tab_privacy", "legal.title_privacy"),
    ("cookie", "legal.tab_cookie", "legal.title_cookie"),
)
COMPANY = (("address", "legal.what_address"), ("pec", "legal.what_pec"), ("rea", "legal.what_rea"))


def company(lang: str) -> dict:
    """Company data from site.toml; a marker value gets the marker of the language."""
    data = dict(content.site_raw().get("company", {}))
    for key, what in COMPANY:
        if not data.get(key) or content.has_marker(data[key]):
            data[key] = i18n.t(lang, "legal.todo", what=i18n.t(lang, what))
    return data


def _page(request: Request, name: str) -> HTMLResponse:
    lang = of(request)
    title = next(title for slug, _, title in PAGES if slug == name)
    return templates.TemplateResponse(
        request,
        f"legal/{lang}/{name.replace('-', '_')}.html",
        {"pages": PAGES, "current": name, "title": i18n.t(lang, title), "company": company(lang)},
    )


@router.get("/info/note-legali", response_class=HTMLResponse)
def notice(request: Request):
    return _page(request, "note-legali")


@router.get("/info/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return _page(request, "privacy")


@router.get("/info/cookie", response_class=HTMLResponse)
def cookie(request: Request):
    return _page(request, "cookie")
