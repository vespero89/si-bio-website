"""Language of a request. Italian lives at the root, every other language of `config.LANGS`
under /<code>/...: the middleware strips the prefix, so the same routes answer all languages, and
leaves the language in `request.state.lang`. A language that is not published answers 404 (the
prefix is left in place and no route matches) unless `config.PREVIEW` is on."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import RedirectResponse

from . import config

DEFAULT = "it"
FALLBACK = "en"
COOKIE = "lang"
COOKIE_MAX_AGE = 365 * 24 * 3600
# Parts of the site that are not translated and have no /<code>/ twin
UNPREFIXED = ("/static",)


def _in(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def available() -> tuple[str, ...]:
    """Languages that can be shown now: the published ones, all of LANGS in preview."""
    return config.LANGS if config.PREVIEW else config.PUBLISHED


def localize(path: str, lang: str) -> str:
    """Local link of the same page in `lang`: '/vini' -> '/en/vini' ('/' -> '/en/',
    '/#wines' -> '/en/#wines'). Static files and external links are never prefixed."""
    if lang == DEFAULT or not path.startswith("/") or path.startswith("//"):
        return path
    if _in(path.split("?")[0].split("#")[0], UNPREFIXED):
        return path
    return f"/{lang}" + path


def of(request) -> str:
    return getattr(request.state, "lang", DEFAULT)


def preferred(header: str) -> str:
    """Language for the root from an Accept-Language header: the published language with the
    highest q, 'it' when the header is empty, and English when it names only languages the site
    does not publish. 'de,en;q=0.8' -> 'en'; 'it-CH' -> 'it'; 'fr' -> 'en'."""
    ranked = []
    for n, part in enumerate(header.split(",")):
        tag, _, params = part.strip().partition(";")
        q = 1.0
        if params.strip().startswith("q="):
            try:
                q = float(params.strip()[2:])
            except ValueError:
                q = 0.0
        code = tag.strip().lower().split("-")[0]
        if q > 0 and code and code != "*":
            ranked.append((-q, n, code))
    if not ranked:
        return DEFAULT
    for _, _, code in sorted(ranked):
        if code in config.PUBLISHED:
            return code
    return FALLBACK


class LanguageMiddleware:
    """Pure ASGI middleware, outermost: the path seen by the routes has no language prefix."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        lang, rest = DEFAULT, path
        code, _, tail = path[1:].partition("/")
        if code in config.LANGS and code != DEFAULT and code in available():
            tail = "/" + tail
            if not _in(tail, UNPREFIXED):
                lang, rest = code, tail
        readonly = scope["method"] in ("GET", "HEAD")
        request = Request(scope)

        query = parse_qsl(scope["query_string"].decode("latin-1"), keep_blank_values=True)
        chosen = next((v for k, v in query if k == "lang" and v in available()), None)
        if readonly and chosen:
            # The selector: remember the choice, then show the page without the parameter
            clean = [(k, v) for k, v in query if k != "lang"]
            target = path + ("?" + urlencode(clean) if clean else "")
            response = RedirectResponse(target, status_code=303)
            response.set_cookie(
                COOKIE, chosen, max_age=COOKIE_MAX_AGE, path="/", samesite="lax",
                secure=config.COOKIE_SECURE,
            )  # fmt: skip
            await response(scope, receive, send)
            return
        if readonly and path == "/":
            pick = request.cookies.get(COOKIE)
            if pick not in available():
                pick = preferred(request.headers.get("accept-language", ""))
            if pick != DEFAULT:
                response = RedirectResponse(localize("/", pick), status_code=302)
                response.headers["Vary"] = "Accept-Language, Cookie"
                await response(scope, receive, send)
                return

        if lang != DEFAULT:
            scope["path"] = rest
            scope["raw_path"] = rest.encode("latin-1")
        state = scope.setdefault("state", {})
        state["lang"] = lang
        state["path"] = rest

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = Headers(raw=message["headers"])
                extra = []
                if rest == "/":
                    extra.append((b"vary", b"Accept-Language, Cookie"))
                location = headers.get("location")
                if lang != DEFAULT and location:
                    message["headers"] = [
                        (k, v) for k, v in message["headers"] if k.lower() != b"location"
                    ]
                    extra.append((b"location", localize(location, lang).encode("latin-1")))
                message["headers"] = [*message["headers"], *extra]
            await send(message)

        await self.app(scope, receive, send_wrapper)
