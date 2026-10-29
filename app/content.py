"""Site content from TOML files under `content/`, and the validator that checks them.

Layout: `site.toml` (settings), `wines/<slug>.toml` and `oil.toml` (data that is the same in every
language), `<lang>/wines/<slug>.toml`, `<lang>/oil.toml` and `<lang>/pages/<page>.toml` (texts).
A text that holds a marker like `[DA VERIFICARE: ...]` is a fact not verified yet: it shows in
preview and is hidden (an empty field) in production."""

from __future__ import annotations

import re
import tomllib
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import config

MARKER = re.compile(
    r"\[(DA VERIFICARE|DA COMPLETARE|DA DEFINIRE|TO BE VERIFIED|TO BE COMPLETED|TO BE DEFINED)\b"
)
PAGES = ("home", "about", "visits", "contact")
CARD = (
    "style denomination grapes training vineyard_area harvest vinification aging bottle_aging "
    "total_acidity residual_sugar serving_temperature appearance aroma palate pairings vintage "
    "awards"
).split()
WINE_TEXT = {"name", "description", "claim", *CARD}
OIL_TEXT = {"name", "description", "cultivar", "area", "harvest", "milling", "acidity", "pairings"}
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*$")
GATED = {
    "riva_dei_martin": "riva_dei_martin",
    "buyers_riva_dei_martin": "riva_dei_martin",
    "package_riva_dei_martin": "riva_dei_martin",
    "organic": "organic_certified",
}
"""Page keys shown only when the switch of the same name in site.toml is on."""


def has_marker(text: str) -> bool:
    return bool(MARKER.search(text))


@lru_cache
def read(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _resolve(value):
    """Production: a text with a marker becomes empty, a list with one becomes []."""
    if config.PREVIEW:
        return value
    if isinstance(value, str):
        return "" if has_marker(value) else value
    if isinstance(value, list):
        return [] if any(isinstance(v, str) and has_marker(v) for v in value) else value
    if isinstance(value, dict):
        return {k: _resolve(v) for k, v in value.items()}
    return value


def site() -> dict:
    return _resolve(read(config.CONTENT_DIR / "site.toml"))


def site_raw() -> dict:
    """The settings as written, markers included: the legal pages show them in production too."""
    return read(config.CONTENT_DIR / "site.toml")


def _slugs() -> list[str]:
    return sorted(p.stem for p in (config.CONTENT_DIR / "wines").glob("*.toml"))


def _wine(lang: str, slug: str) -> dict | None:
    neutral = read(config.CONTENT_DIR / "wines" / f"{slug}.toml")
    if not neutral.get("visible"):
        return None
    text = read(config.CONTENT_DIR / lang / "wines" / f"{slug}.toml")
    return _resolve({"slug": slug, **neutral, **text})


def wines(lang: str) -> list[dict]:
    """Visible wines in file order (`order`)."""
    found = [w for w in (_wine(lang, s) for s in _slugs()) if w]
    return sorted(found, key=lambda w: w["order"])


def wine(lang: str, slug: str) -> dict | None:
    """The wine, or None when the slug is unknown or the wine is hidden."""
    return _wine(lang, slug) if slug in _slugs() else None


def oil(lang: str) -> dict:
    return _resolve(
        {**read(config.CONTENT_DIR / "oil.toml"), **read(config.CONTENT_DIR / lang / "oil.toml")}
    )


def page(lang: str, name: str) -> dict:
    data = read(config.CONTENT_DIR / lang / "pages" / f"{name}.toml")
    switches = read(config.CONTENT_DIR / "site.toml").get("switches", {})
    data = {k: v for k, v in data.items() if not (k in GATED and not switches.get(GATED[k]))}
    return _resolve(data)


# Validator: runs on the raw files, so a marker is not a problem here (scripts/check_content.py,
# planned, lists them). Returns one line per problem; empty means the content is sound.

SITE_FIELDS = {
    "company": {"name": str, "vat": str, "address": str, "pec": str, "rea": str},
    "contact": {"export_email": str, "partner_email": str, "phone": str},
    "farm": {"url": str},
    "social": {"instagram": str, "facebook": str},
    "video": {"youtube_id": str, "cover": str},
    "switches": {"riva_dei_martin": bool, "organic_certified": bool},
}
CERTIFICATE_FIELDS = (
    "number body regulation valid_from valid_until holder holder_address verify_url qr"
).split()


def _load(path: Path, out: list[str]) -> dict | None:
    name = path.relative_to(config.CONTENT_DIR).as_posix()
    if not path.is_file():
        out.append(f"{name}: file missing")
        return None
    try:
        return read(path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        out.append(f"{name}: not valid TOML ({error})")
        return None


def _typed(name: str, data: dict, fields: dict, out: list[str]) -> None:
    for key, kind in fields.items():
        if key not in data:
            out.append(f"{name}: missing '{key}'")
        elif not isinstance(data[key], kind) or (kind is int and isinstance(data[key], bool)):
            out.append(f"{name}: '{key}' must be {kind.__name__}")


def _texts(path: Path, allowed: set[str] | None, reference: set[str], out: list[str]) -> None:
    """Checks a text file: known keys, text values, the keys Italian has."""
    data = _load(path, out)
    if data is None:
        return
    name = path.relative_to(config.CONTENT_DIR).as_posix()
    for key, value in data.items():
        if not isinstance(value, str):
            out.append(f"{name}: '{key}' must be text")
        elif allowed is not None and key not in allowed:
            out.append(f"{name}: unknown key '{key}'")
    for key in sorted(reference - set(data)):
        out.append(f"{name}: misses '{key}' (present in Italian)")


def _required(path: Path, keys: tuple[str, ...], out: list[str]) -> set[str]:
    data = _load(path, out) or {}
    name = path.relative_to(config.CONTENT_DIR).as_posix()
    for key in keys:
        if not data.get(key):
            out.append(f"{name}: missing '{key}'")
    return set(data)


def _check_files(files: dict, out: list[str]) -> None:
    for lang, filename in files.items():
        if not (config.STATIC_DIR / "schede" / filename).is_file():
            out.append(f"pdf '{filename}' ({lang}) not found in app/static/schede/")


def _certificate_problems(settings: dict, out: list[str]) -> None:
    """`[certificate]` must be sound while the switch `organic_certified` is on."""
    cert = settings.get("certificate", {})
    _typed("site.toml [certificate]", cert, dict.fromkeys(CERTIFICATE_FIELDS, str), out)
    if not settings.get("switches", {}).get("organic_certified"):
        return
    name = "site.toml [certificate]"
    for key in ("number", "body", "verify_url"):
        if not cert.get(key) or has_marker(str(cert.get(key))):
            out.append(f"{name}: '{key}' must be filled while organic_certified is on")
    if not str(cert.get("verify_url", "")).startswith("https://webgate.ec.europa.eu/"):
        out.append(f"{name}: 'verify_url' must be an https address of webgate.ec.europa.eu")
    dates = {}
    for key in ("valid_from", "valid_until"):
        try:
            dates[key] = date.fromisoformat(str(cert.get(key, "")))
        except ValueError:
            out.append(f"{name}: '{key}' must be a date like 2029-08-24")
    if len(dates) == 2 and dates["valid_from"] >= dates["valid_until"]:
        out.append(f"{name}: 'valid_from' must be before 'valid_until'")
    qr = cert.get("qr", "")
    if not qr or not (config.STATIC_DIR / "img" / str(qr)).is_file():
        out.append(f"{name}: 'qr' file not found in app/static/img/ (run scripts/qr.py)")


def problems() -> list[str]:
    out: list[str] = []
    root = config.CONTENT_DIR
    settings = _load(root / "site.toml", out) or {}
    for section, fields in SITE_FIELDS.items():
        _typed(f"site.toml [{section}]", settings.get(section, {}), fields, out)
    if "it" not in settings.get("languages", {}).get("published", []):
        out.append("site.toml: Italian must be published")

    _certificate_problems(settings, out)

    slugs = _slugs()
    orders: dict[int, str] = {}
    for slug in slugs:
        if not SLUG.match(slug):
            out.append(f"wines/{slug}.toml: slug must be lowercase letters, digits and hyphens")
        data = _load(root / "wines" / f"{slug}.toml", out) or {}
        name = f"wines/{slug}.toml"
        _typed(name, data, {"order": int, "visible": bool, "photo": str}, out)
        for key in ("abv", "formats"):
            if key not in data:
                out.append(f"{name}: missing '{key}'")
        if not isinstance(data.get("abv", 0), (int, float, str)):
            out.append(f"{name}: 'abv' must be a number or text")
        if not isinstance(data.get("bottles_per_year", 0), (int, float, str)):
            out.append(f"{name}: 'bottles_per_year' must be a number or text")
        if not isinstance(data.get("formats", []), list):
            out.append(f"{name}: 'formats' must be a list")
        if isinstance(data.get("order"), int):
            if data["order"] in orders:
                out.append(f"{name}: 'order' repeated (also {orders[data['order']]})")
            orders[data["order"]] = slug
        _check_files(data.get("pdf", {}), out)
    oil_data = _load(root / "oil.toml", out) or {}
    _typed("oil.toml", oil_data, {"photo": str, "formats": list}, out)
    _check_files(oil_data.get("pdf", {}), out)

    # Italian is the reference; every published language must have the same keys and files.
    langs = [lang for lang in config.PUBLISHED if lang != "it"]
    for lang in ("it", *langs):
        folder = root / lang
        for stray in sorted((folder / "wines").glob("*.toml")):
            if stray.stem not in slugs:
                out.append(f"{lang}/wines/{stray.name}: no wines/{stray.stem}.toml")
        checks = [(f"wines/{s}.toml", WINE_TEXT) for s in slugs]
        checks += [("oil.toml", OIL_TEXT)] + [(f"pages/{p}.toml", None) for p in PAGES]
        for rel, allowed in checks:
            keys = ("title",) if rel.startswith("pages") else ("name", "description")
            if lang == "it":
                _required(folder / rel, keys, out)
                _texts(folder / rel, allowed, set(), out)
            else:
                reference = set(_load(root / "it" / rel, []) or {})
                _texts(folder / rel, allowed, reference, out)
                _required(folder / rel, keys, out)
    return out
