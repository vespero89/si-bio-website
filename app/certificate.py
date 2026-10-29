"""The organic certificate for the pages: `get(lang)` gives what the block, the home line, the
footer link, the JSON-LD and llms.txt show, or None when the switch `organic_certified` is off or
the certificate settings are not sound (a marker or an empty number, body or address, an address
that is not the European register). Nothing about "organic" is printed without it."""

from __future__ import annotations

from datetime import date

from app import config, content, i18n

REGISTER = "https://webgate.ec.europa.eu/"
"""Where `verify_url` must point: the European register of organic operators."""


def _date(value: str, lang: str) -> str:
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return ""
    month = i18n.t(lang, f"certificate.month_{day.month}")
    return i18n.t(lang, "certificate.date", day=day.day, month=month, year=day.year)


def get(lang: str) -> dict | None:
    site = content.site()
    if not site.get("switches", {}).get("organic_certified"):
        return None
    cert = site.get("certificate", {})
    if not all(cert.get(k) and not content.has_marker(cert[k]) for k in ("number", "body")):
        return None
    if not cert.get("verify_url", "").startswith(REGISTER) or content.has_marker(
        cert["verify_url"]
    ):
        return None
    qr = cert.get("qr", "")
    return {
        "number": cert["number"],
        "body": cert["body"],
        "regulation": cert.get("regulation", ""),
        "valid_from": _date(cert.get("valid_from", ""), lang),
        "valid_until": _date(cert.get("valid_until", ""), lang),
        "valid_from_iso": cert.get("valid_from", ""),
        "valid_until_iso": cert.get("valid_until", ""),
        "holder": cert.get("holder", ""),
        "holder_address": cert.get("holder_address", ""),
        "verify_url": cert["verify_url"],
        "qr": f"/static/img/{qr}" if qr and (config.STATIC_DIR / "img" / qr).is_file() else "",
    }
