"""Error pages and security headers. Errors are pages in the language of the request (the language
middleware has already stripped the prefix), `noindex`, with links to the wines and the contacts.
No stack trace ever reaches the browser. The old WordPress addresses are not redirected: the
ones with no page here answer 404 (or 410 for feeds and the API), `/info/` included."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException

from app import config
from app.templating import templates

log = logging.getLogger("app.errors")

KNOWN = (404, 405, 410, 500)
GONE = ("/feed", "/comments/feed", "/wp-json", "/xmlrpc.php")
"""Old WordPress addresses that will never come back: 410."""
PLAIN = ("/wp-login.php", "/wp-admin", "/wp-content", "/wp-includes")
"""Bot targets: a short 404 without the page."""

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "frame-src https://www.youtube-nocookie.com",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)
PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()"
HSTS = "max-age=31536000"


def _under(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def page(request: Request, status: int, headers: dict | None = None):
    """The error page for `status`; any status not listed gets the generic text."""
    headers = {**(headers or {}), "X-Robots-Tag": "noindex"}
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status": status, "kind": status if status in KNOWN else 500, "noindex": True},
        status_code=status,
        headers=headers,
    )


async def http_error(request: Request, exc: HTTPException):
    path = request.url.path
    if exc.status_code == 404:
        if _under(path, PLAIN):
            return PlainTextResponse("Not found", 404, headers={"X-Robots-Tag": "noindex"})
        if _under(path, GONE):
            return page(request, 410)
    return page(request, exc.status_code, dict(exc.headers or {}))


class SecurityHeadersMiddleware:
    """Outermost middleware: security headers on every response (static files, redirects and
    errors included), cache rules, and the 500 page for an unexpected error."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                self.decorate(scope, message)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("Unhandled error on %s", scope.get("path"))
            if started:
                raise
            response = page(Request(scope), 500)
            await response(scope, receive, send_wrapper)

    @staticmethod
    def decorate(scope, message) -> None:
        headers = MutableHeaders(raw=message["headers"])
        headers["Content-Security-Policy"] = CSP
        headers["X-Content-Type-Options"] = "nosniff"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = PERMISSIONS
        headers["X-Frame-Options"] = "DENY"
        if config.BASE_URL.startswith("https://"):
            headers["Strict-Transport-Security"] = HSTS
        kind = headers.get("content-type", "")
        if kind.startswith("text/html"):
            # The cookie notice and the video depend on the cookie_choice cookie
            vary = [v.strip() for v in headers.get("vary", "").split(",") if v.strip()]
            if "cookie" not in (v.lower() for v in vary):
                headers["Vary"] = ", ".join([*vary, "Cookie"])
            if "cache-control" not in headers:
                headers["Cache-Control"] = "no-cache"
        elif scope["path"].startswith("/static/") and "cache-control" not in headers:
            headers["Cache-Control"] = "no-cache"
