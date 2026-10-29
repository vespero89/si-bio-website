"""Writes the QR code of the organic certificate as an SVG file, with no library and no service.

    python scripts/qr.py

It encodes `verify_url` of `[certificate]` in content/site.toml (the address of the operator in
the European register, which always shows the current certificate) and writes
`app/static/img/<qr>`. Run it again only when `verify_url` changes; a test fails if the file is
stale. Byte mode, error correction level M, versions 1 to 10 (up to 213 bytes)."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
BORDER = 4
TITLE = "Si Bio organic certificate, EU register"

# level M: version -> (codewords in all, error codewords per block, [(blocks, data codewords)])
BLOCKS = {
    1: (26, 10, [(1, 16)]),
    2: (44, 16, [(1, 28)]),
    3: (70, 26, [(1, 44)]),
    4: (100, 18, [(2, 32)]),
    5: (134, 24, [(2, 43)]),
    6: (172, 16, [(4, 27)]),
    7: (196, 18, [(4, 31)]),
    8: (242, 22, [(2, 38), (2, 39)]),
    9: (292, 22, [(3, 36), (2, 37)]),
    10: (346, 26, [(4, 43), (1, 44)]),
}
ALIGNMENT = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
}
MASKS = [
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
]


def _gf_tables() -> tuple[list[int], list[int]]:
    exp, log, x = [0] * 512, [0] * 256, 1
    for i in range(255):
        exp[i], log[x] = x, i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


EXP, LOG = _gf_tables()


def _reed_solomon(data: list[int], count: int) -> list[int]:
    """The `count` error correction codewords of `data`."""
    generator = [1]
    for i in range(count):
        nxt = [0] * (len(generator) + 1)
        for j, coeff in enumerate(generator):
            nxt[j] ^= coeff
            if coeff:
                nxt[j + 1] ^= EXP[LOG[coeff] + i]
        generator = nxt
    rest = [0] * count
    for byte in data:
        factor = byte ^ rest[0]
        rest = rest[1:] + [0]
        if factor:
            for j in range(count):
                if generator[j + 1]:
                    rest[j] ^= EXP[LOG[generator[j + 1]] + LOG[factor]]
    return rest


def format_bits(mask: int) -> int:
    """The 15 format bits for level M and `mask` (BCH code, then the standard's xor pattern)."""
    rem = mask
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return (mask << 10 | rem) ^ 0x5412


def version_bits(version: int) -> int:
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    return version << 12 | rem


def function_map(version: int) -> list[list[bool]]:
    """True where a module belongs to a pattern (finders, timing, alignment, format, version)."""
    size = 17 + 4 * version
    fixed = [[False] * size for _ in range(size)]

    def block(x0, y0, w, h):
        for y in range(max(y0, 0), min(y0 + h, size)):
            for x in range(max(x0, 0), min(x0 + w, size)):
                fixed[y][x] = True

    block(0, 0, 9, 9)
    block(size - 8, 0, 8, 9)
    block(0, size - 8, 9, 8)
    block(6, 0, 1, size)
    block(0, 6, size, 1)
    last = len(ALIGNMENT[version]) - 1
    for i, cy in enumerate(ALIGNMENT[version]):
        for j, cx in enumerate(ALIGNMENT[version]):
            if (i, j) not in ((0, 0), (0, last), (last, 0)):
                block(cx - 2, cy - 2, 5, 5)
    if version >= 7:
        block(size - 11, 0, 3, 6)
        block(0, size - 11, 6, 3)
    return fixed


def _codewords(data: bytes, version: int) -> list[int]:
    total, ec_len, groups = BLOCKS[version]
    capacity = sum(n * d for n, d in groups)
    width = 16 if version >= 10 else 8
    bits = "0100" + format(len(data), f"0{width}b") + "".join(f"{b:08b}" for b in data)
    bits += "0" * min(4, capacity * 8 - len(bits))
    bits += "0" * (-len(bits) % 8)
    words = [int(bits[i : i + 8], 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    while len(words) < capacity:
        words.append(pad[(len(words) - len(bits) // 8) % 2])
    blocks, pos = [], 0
    for n, d in groups:
        for _ in range(n):
            blocks.append(words[pos : pos + d])
            pos += d
    ecs = [_reed_solomon(b, ec_len) for b in blocks]
    out = [b[i] for i in range(max(map(len, blocks))) for b in blocks if i < len(b)]
    out += [e[i] for i in range(ec_len) for e in ecs]
    assert len(out) == total
    return out


def _penalty(grid: list[list[bool]]) -> int:
    size, score = len(grid), 0
    lines = grid + [list(col) for col in zip(*grid, strict=True)]
    for line in lines:
        run = 1
        for i in range(1, size):
            run = run + 1 if line[i] == line[i - 1] else 1
            if run == 5:
                score += 3
            elif run > 5:
                score += 1
        text = "".join("1" if m else "0" for m in line)
        for pattern in ("10111010000", "00001011101"):
            score += 40 * sum(text.startswith(pattern, i) for i in range(size - 10))
    for y in range(size - 1):
        for x in range(size - 1):
            if grid[y][x] == grid[y][x + 1] == grid[y + 1][x] == grid[y + 1][x + 1]:
                score += 3
    dark = sum(map(sum, grid))
    return score + 10 * (abs(dark * 20 - size * size * 10) // (size * size) if size else 0)


def matrix(text: str, mask: int | None = None) -> list[list[bool]]:
    """The modules of the QR code for `text` (True = dark). `mask` None picks the best one."""
    data = text.encode("utf-8")
    versions = [v for v in BLOCKS if sum(n * d for n, d in BLOCKS[v][2]) >= len(data) + 3]
    if not versions:
        raise ValueError(f"text of {len(data)} bytes is too long for a version 10 QR code")
    version = versions[0]
    size = 17 + 4 * version
    words = _codewords(data, version)
    fixed = function_map(version)
    base = [[False] * size for _ in range(size)]

    def put(x, y, dark):
        base[y][x] = dark

    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):  # finders, with their light ring
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                if 0 <= cx + dx < size and 0 <= cy + dy < size:
                    put(cx + dx, cy + dy, max(abs(dx), abs(dy)) not in (2, 4))
    for i in range(8, size - 8):  # timing
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    last = len(ALIGNMENT[version]) - 1
    for i, cy in enumerate(ALIGNMENT[version]):
        for j, cx in enumerate(ALIGNMENT[version]):
            if (i, j) not in ((0, 0), (0, last), (last, 0)):
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        put(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
    put(8, size - 8, True)  # the always dark module
    if version >= 7:
        bits = version_bits(version)
        for i in range(18):
            dark = bool(bits >> i & 1)
            put(size - 11 + i % 3, i // 3, dark)
            put(i // 3, size - 11 + i % 3, dark)
    k = 0
    for right in [*range(size - 1, 6, -2), *range(5, 0, -2)]:  # column 6 is the timing line
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if ((right + 1) & 2) == 0 else vert
                if not fixed[y][x] and k < len(words) * 8:
                    put(x, y, bool(words[k >> 3] >> (7 - (k & 7)) & 1))
                    k += 1

    def with_mask(m):
        grid = [row[:] for row in base]
        for y in range(size):
            for x in range(size):
                if not fixed[y][x]:
                    grid[y][x] ^= MASKS[m](x, y)
        bits = format_bits(m)
        for i in range(15):
            dark = bool(bits >> i & 1)
            if i < 6:
                ax, ay = 8, i
            elif i < 9:
                ax, ay = [(8, 7), (8, 8), (7, 8)][i - 6]
            else:
                ax, ay = 14 - i, 8
            bx, by = (size - 1 - i, 8) if i < 8 else (8, size - 15 + i)
            grid[ay][ax] = dark
            grid[by][bx] = dark
        return grid

    if mask is not None:
        return with_mask(mask)
    return min((with_mask(m) for m in range(8)), key=_penalty)


def svg(text: str, title: str, mask: int | None = None) -> str:
    """A self-contained SVG of the QR code (no script, no link, no external file)."""
    grid = matrix(text, mask)
    side = len(grid) + 2 * BORDER
    runs = []
    for y, row in enumerate(grid):
        x = 0
        while x < len(row):
            if row[x]:
                start = x
                while x < len(row) and row[x]:
                    x += 1
                runs.append(f"M{start + BORDER} {y + BORDER}h{x - start}v1h-{x - start}z")
            else:
                x += 1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}" '
        f'shape-rendering="crispEdges" role="img">'
        f"<title>{escape(title)}</title><desc>{escape(text)}</desc>"
        f'<rect width="{side}" height="{side}" fill="#fff"/>'
        f'<path d="{"".join(runs)}" fill="#000"/></svg>\n'
    )


def main() -> None:
    site = tomllib.loads((ROOT / "content" / "site.toml").read_text(encoding="utf-8"))
    cert = site["certificate"]
    target = ROOT / "app" / "static" / "img" / cert["qr"]
    target.write_text(svg(cert["verify_url"], TITLE), encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)} for {cert['verify_url']}")


if __name__ == "__main__":
    sys.exit(main())
