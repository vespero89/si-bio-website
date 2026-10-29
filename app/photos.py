"""Photo sizes: the `srcset` of a photo from the files that exist (`<name>.jpg` and
`<name>-600.jpg`, made by scripts/photos.py). No variant on disk, no srcset."""

from __future__ import annotations

import re
from pathlib import Path

from . import config, content

VARIANT_WIDTH = 600
SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def jpeg_size(path: Path) -> tuple[int, int] | None:
    """(width, height) read from the JPEG header, or None if the file is missing or not a JPEG."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker in SOF:
            return int.from_bytes(data[i + 7 : i + 9], "big"), int.from_bytes(
                data[i + 5 : i + 7], "big"
            )
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    return None


def variant(name: str) -> str:
    return re.sub(r"(\.\w+)$", rf"-{VARIANT_WIDTH}\1", name)


def srcset(name: str) -> str:
    """`srcset` of a photo given as a path under static/img (e.g. `vini/armide.jpg`); empty when
    the name is a placeholder or the 600 wide variant is not there."""
    if not name or content.has_marker(name):
        return ""
    img = config.STATIC_DIR / "img"
    original, small = jpeg_size(img / name), jpeg_size(img / variant(name))
    if not original or not small:
        return ""
    return f"/static/img/{variant(name)} {small[0]}w, /static/img/{name} {original[0]}w"
