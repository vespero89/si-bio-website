"""FastAPI app: routes and static files."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import config, contact, wines
from app.lang import LanguageMiddleware
from app.templating import templates

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.add_middleware(LanguageMiddleware)
app.include_router(wines.router)
app.include_router(contact.router)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html")
