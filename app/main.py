"""FastAPI app: routes and static files."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app import config, contact, cookies, errors, legal, pages, seo, wines
from app.errors import SecurityHeadersMiddleware
from app.lang import LanguageMiddleware
from app.seo import NoindexMiddleware

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.add_middleware(LanguageMiddleware)
app.add_middleware(NoindexMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_exception_handler(HTTPException, errors.http_error)
app.include_router(wines.router)
app.include_router(contact.router)
app.include_router(cookies.router)
app.include_router(legal.router)
app.include_router(pages.router)
app.include_router(seo.router)
