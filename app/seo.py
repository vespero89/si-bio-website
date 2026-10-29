"""Search engine and assistant files: `/robots.txt`, `/sitemap.xml`, `/llms.txt`, and the noindex
header of preview. Pages come from the content files; wording comes from the locale keys.

Only the published languages are listed. The files exist at the root only: the other languages
get their own `/<code>/llms.txt` and 404 for the rest."""

from __future__ import annotations

from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from app import certificate, config, content, i18n, lang
from app.lang import of
from app.wines import sheet

router = APIRouter()

PAGES = ("/", "/vini", "/olio", "/chi-siamo", "/visite", "/contatti")
LEGAL = ("/info/note-legali", "/info/privacy", "/info/cookie")


def absolute(path: str, code: str) -> str:
    return config.BASE_URL + lang.localize(path, code)


def paths() -> list[str]:
    """Every page of the sitemap, as a path without language prefix."""
    return [*PAGES[:2], *(f"/vini/{w['slug']}" for w in content.wines("it")), *PAGES[2:], *LEGAL]


def x_default() -> str:
    return lang.FALLBACK if lang.FALLBACK in config.PUBLISHED else lang.DEFAULT


def robots_txt() -> str:
    if config.PREVIEW:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nAllow: /\n\nSitemap: {config.BASE_URL}/sitemap.xml\n"


def sitemap_xml() -> str:
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for path in paths():
        alternates = [
            f'<xhtml:link rel="alternate" hreflang="{code}" href="{escape(absolute(path, code))}"/>'
            for code in config.PUBLISHED
        ]
        alternates.append(
            '<xhtml:link rel="alternate" hreflang="x-default" '
            f'href="{escape(absolute(path, x_default()))}"/>'
        )
        for code in config.PUBLISHED:
            out.append(f"<url><loc>{escape(absolute(path, code))}</loc>{''.join(alternates)}</url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"


def _fact(value) -> str:
    return "" if not isinstance(value, str) or content.has_marker(value) else value.strip()


def _item(title: str, link: str, facts: list[tuple[str, str]], code: str) -> list[str]:
    out = [f"- [{title}]({link})"]
    for field, value in facts:
        text = _fact(str(value))
        if text:
            out.append(f"  - {i18n.t(code, 'sheet.' + field)}: {text}")
    return out


def llms_txt(code: str) -> str:
    """Markdown summary for language models, from verified content only."""
    t = lambda key, **kw: i18n.t(code, key, **kw)  # noqa: E731
    site = content.site_raw()
    lines = ["# Si Bio", "", f"> {t('llms.summary')}", "", f"## {t('llms.wines')}", ""]
    for wine in content.wines(code):
        lines += _item(wine["name"], absolute(f"/vini/{wine['slug']}", code), sheet(wine), code)
        if _fact(wine.get("description")):
            lines.append(f"  - {wine['description'].strip()}")
    oil = content.oil(code)
    lines += ["", f"## {t('llms.oil')}", ""]
    lines += _item(oil["name"], absolute("/olio", code), [], code)
    visits = content.page(code, "visits")
    contact = site.get("contact", {})
    lines += ["", f"## {t('llms.visits')}", ""]
    lines.append(
        f"- [{_fact(visits.get('title')) or t('llms.visits')}]({absolute('/visite', code)})"
    )
    lines += [f"  - {_fact(item)}" for item in visits.get("buyers_includes", []) if _fact(item)]
    if _fact(visits.get("package_name")) and _fact(contact.get("partner_email")):
        lines.append(f"  - {visits['package_name']}. {t('visits.organizer')}")
    cert = certificate.get(code)
    if cert:
        lines += ["", f"## {t('llms.company')}", ""]
        lines.append(
            "- "
            + t(
                "llms.organic",
                regulation=cert["regulation"],
                number=cert["number"],
                body=cert["body"],
                end=cert["valid_until"],
                url=cert["verify_url"],
            )
        )
    lines += ["", f"## {t('llms.contact')}", ""]
    if _fact(contact.get("export_email")):
        lines.append(f"- {contact['export_email']}")
    lines.append(f"- [{t('nav.contact')}]({absolute('/contatti', code)})")
    farm = _fact(site.get("farm", {}).get("url"))
    if farm:
        lines += ["", f"## {t('llms.farm')}", "", f"- {farm.rstrip('/')}{lang.localize('/', code)}"]
    return "\n".join(lines) + "\n"


def _root_only(request: Request) -> None:
    if of(request) != lang.DEFAULT:
        raise HTTPException(404)


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request):
    _root_only(request)
    return PlainTextResponse(robots_txt())


@router.get("/sitemap.xml")
def sitemap(request: Request):
    _root_only(request)
    return Response(sitemap_xml(), media_type="application/xml")


@router.get("/llms.txt", response_class=PlainTextResponse)
def llms(request: Request):
    return PlainTextResponse(llms_txt(of(request)), media_type="text/plain; charset=utf-8")


class NoindexMiddleware:
    """Preview: every response says noindex, so a test copy online is never indexed."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not config.PREVIEW:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                if not any(k.lower() == b"x-robots-tag" for k, _ in message["headers"]):
                    message["headers"] = [*message["headers"], (b"x-robots-tag", b"noindex")]
            await send(message)

        await self.app(scope, receive, send_wrapper)
