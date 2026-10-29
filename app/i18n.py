"""Interface texts: one file per language, `locales/<code>.toml`, keys like `nav.wines`.
The Italian file is the reference: a published language must have all its keys."""

from __future__ import annotations

import tomllib
from functools import lru_cache

from . import config

REFERENCE = "it"


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    flat = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


@lru_cache
def load(lang: str) -> dict[str, str]:
    path = config.LOCALES_DIR / f"{lang}.toml"
    if not path.is_file():
        return {}
    return _flatten(tomllib.loads(path.read_text(encoding="utf-8")))


def missing(lang: str) -> list[str]:
    """Keys of the reference language that `lang` does not have."""
    return sorted(set(load(REFERENCE)) - set(load(lang)))


def assert_complete(lang: str) -> None:
    gone = missing(lang)
    assert not gone, f"locales/{lang}.toml misses keys of {REFERENCE}.toml: {', '.join(gone)}"


def t(lang: str, key: str, **values) -> str:
    """Text of `key` in `lang`. A key the language lacks falls back to Italian in preview only
    (a published language is complete); otherwise the key itself shows."""
    text = load(lang).get(key)
    if text is None and config.PREVIEW:
        text = load(REFERENCE).get(key)
    if text is None:
        return key
    return text.format(**values) if values else text


def num(lang: str, value: float, decimals: int | None = None, group: bool = False) -> str:
    """Number with the decimal separator of the language: 13.5 -> '13,5' (it), '13.5' (en).
    With `group` the thousands are separated too: 5000 -> '5.000' (it), '5,000' (en)."""
    text = f"{value:,}" if group and decimals is None else str(value)
    if decimals is not None:
        text = f"{value:,.{decimals}f}" if group else f"{value:.{decimals}f}"
    marks = load(lang)
    return text.translate(
        str.maketrans(
            {".": marks.get("number.decimal", "."), ",": marks.get("number.thousands", ",")}
        )
    )
