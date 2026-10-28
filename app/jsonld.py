"""Structured data (schema.org JSON-LD) for the public pages.

Builders return plain dicts made from the content files; `dumps` writes them for a
`<script type="application/ld+json">` tag. Empty values are dropped, and so is anything that is
still a placeholder marker, so an unverified fact never reaches the page. Products carry no Offer
(no prices). Wording comes from the content files and the locale keys, not from this module."""

from __future__ import annotations

import json

from app import config, content, i18n
from app.lang import localize

BRAND = "Si Bio"
CONTEXT = "https://schema.org"


def clean(node):
    """Copy without empty values ('', None, empty list or dict) or markers, at any depth."""
    if isinstance(node, dict):
        out = {k: clean(v) for k, v in node.items()}
        return {k: v for k, v in out.items() if v not in ("", None, [], {})}
    if isinstance(node, list):
        out = [clean(v) for v in node]
        return [v for v in out if v not in ("", None, [], {})]
    if isinstance(node, str) and content.has_marker(node):
        return ""
    return node


def dumps(data: dict) -> str:
    """JSON for a script tag: every '<' is escaped, so no value can close the tag or open a
    comment ('</script>', '<!--')."""
    return json.dumps(clean(data), ensure_ascii=False).replace("<", "\\u003c")


def url(path: str, lang: str) -> str:
    return config.BASE_URL + localize(path, lang)


def organization(lang: str) -> dict:
    site = content.site_raw()
    company, contact, social = (site.get(k, {}) for k in ("company", "contact", "social"))
    vat = company.get("vat", "")
    street = company.get("address", "")
    street = "" if content.has_marker(street) else street
    return {
        "@context": CONTEXT,
        "@type": "Organization",
        "name": BRAND,
        "legalName": company.get("name"),
        "vatID": f"IT{vat}" if vat and not content.has_marker(vat) else "",
        "url": url("/", lang),
        "email": contact.get("export_email"),
        "address": {"@type": "PostalAddress", "streetAddress": street} if street else "",
        "sameAs": [social.get("instagram"), social.get("facebook")],
    }


def website(lang: str) -> dict:
    return {
        "@context": CONTEXT,
        "@type": "WebSite",
        "name": BRAND,
        "url": url("/", lang),
        "inLanguage": lang,
    }


def product(item: dict, path: str, lang: str, category_key: str, image: str = "") -> dict:
    return {
        "@context": CONTEXT,
        "@type": "Product",
        "name": item.get("name"),
        "description": item.get("description"),
        "url": url(path, lang),
        "image": f"{config.BASE_URL}/static/img/vini/{image}" if image else "",
        "brand": {"@type": "Brand", "name": BRAND},
        "category": i18n.t(lang, category_key),
    }


def breadcrumbs(trail: list[tuple[str, str]], lang: str) -> dict:
    """`trail` is [(name, path), ...] from the home down to the page."""
    return {
        "@context": CONTEXT,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": n, "name": name, "item": url(path, lang)}
            for n, (name, path) in enumerate(trail, 1)
        ],
    }
