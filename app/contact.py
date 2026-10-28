"""Contact page `/contatti`: mailto block, company data, commercial manager role. No form."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import content
from app.lang import of
from app.templating import templates

router = APIRouter()


@router.get("/contatti", response_class=HTMLResponse)
def contact_page(request: Request):
    lang = of(request)
    return templates.TemplateResponse(
        request,
        "contact.html",
        {
            "page": content.page(lang, "contact"),
            # The role lives with the "About" texts; empty in production while it is a marker.
            "sales_contact": content.page(lang, "about").get("sales_contact", ""),
        },
    )
