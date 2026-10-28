"""Cookie choice: the only POST of the site. `cookie_choice` holds `accepted` or `rejected`
(6 months, no identifier). Nothing is loaded from a third party unless it is `accepted`; read it
on the server with `choice(request)`, never from JavaScript."""

from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from app import config

router = APIRouter()

COOKIE = "cookie_choice"
MAX_AGE = 183 * 24 * 3600
VALUES = {"accept": "accepted", "reject": "rejected"}


def choice(request: Request) -> str | None:
    """'accepted', 'rejected' or None (no choice, or an unknown value)."""
    value = request.cookies.get(COOKIE)
    return value if value in VALUES.values() else None


def safe_next(value: str) -> str:
    """A local path (one leading '/', no '//', no backslash or control character); else the home."""
    local = value.startswith("/") and not value.startswith("//") and "\\" not in value
    if not local or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return "/"
    return value


@router.post("/cookie-choice")
async def cookie_choice(request: Request):
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    value = VALUES.get((form.get("choice") or [""])[0])
    if value is None:
        return PlainTextResponse("Bad request", status_code=400)
    # The language middleware puts the /<code> prefix back on this local path
    response = RedirectResponse(safe_next((form.get("next") or [""])[0]), status_code=303)
    response.set_cookie(
        COOKIE, value, max_age=MAX_AGE, path="/", samesite="lax", httponly=True,
        secure=config.COOKIE_SECURE,
    )  # fmt: skip
    return response
