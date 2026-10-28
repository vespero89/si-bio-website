"""FastAPI app: routes and static files."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, contact, cookies, pages, wines
from app.lang import LanguageMiddleware

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.add_middleware(LanguageMiddleware)
app.include_router(wines.router)
app.include_router(contact.router)
app.include_router(cookies.router)
app.include_router(pages.router)
