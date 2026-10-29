"""scripts/qr.py: a QR code written as SVG with no library. The decoder here is a check, not a
scanner: it reads the modules back, checks the Reed-Solomon codewords and returns the text."""

import re

import pytest

from app import config, content
from scripts import qr

URL = content.read(config.CONTENT_DIR / "site.toml")["certificate"]["verify_url"]
SHIPPED = config.STATIC_DIR / "img" / "certificate-qr.svg"


def modules(svg):
    """The square of dark/light modules (border removed) read from the SVG path."""
    size = int(re.search(r'viewBox="0 0 (\d+) \d+"', svg).group(1))
    grid = [[False] * size for _ in range(size)]
    for x, y, run in re.findall(r"M(\d+) (\d+)h(\d+)v1", svg):
        for dx in range(int(run)):
            grid[int(y)][int(x) + dx] = True
    cut = qr.BORDER
    return [row[cut : size - cut] for row in grid[cut : size - cut]]


def bits_of(value, count):
    return [(value >> i) & 1 for i in range(count - 1, -1, -1)]


def gf_pow_table():
    exp, x = [0] * 512, 1
    for i in range(255):
        exp[i] = x
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp


def gf_mul(a, b, exp, log):
    return 0 if a == 0 or b == 0 else exp[log[a] + log[b]]


def decode(svg):
    grid = modules(svg)
    size = len(grid)
    version = (size - 17) // 4
    # format information: read the copy next to the top-left finder
    positions = (
        [(8, i) for i in range(6)] + [(8, 7), (8, 8), (7, 8)] + [(14 - i, 8) for i in range(9, 15)]
    )
    raw = sum(int(grid[y][x]) << i for i, (x, y) in enumerate(positions)) ^ 0x5412
    assert (raw >> 13) == 0, "error correction level must be M"
    mask = (raw >> 10) & 7
    rem = raw >> 10
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    assert rem & 0x3FF == raw & 0x3FF, "format information fails its BCH check"
    function = qr.function_map(version)
    bits = []
    for right in [*range(size - 1, 6, -2), *range(5, 0, -2)]:
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if ((right + 1) & 2) == 0 else vert
                if not function[y][x]:
                    bits.append(grid[y][x] ^ qr.MASKS[mask](x, y))
    words = [
        sum(int(b) << (7 - k) for k, b in enumerate(bits[i : i + 8]))
        for i in range(0, len(bits) - 7, 8)
    ]
    total, ec_len, groups = qr.BLOCKS[version]
    words = words[:total]
    lengths = [d for n, d in groups for _ in range(n)]
    blocks = [[] for _ in lengths]
    pos = 0
    for i in range(max(lengths)):
        for b, length in enumerate(lengths):
            if i < length:
                blocks[b].append(words[pos])
                pos += 1
    ecs = [[] for _ in lengths]
    for _ in range(ec_len):
        for b in range(len(lengths)):
            ecs[b].append(words[pos])
            pos += 1
    exp = gf_pow_table()
    log = {exp[i]: i for i in range(255)}
    data = []
    for block, ec in zip(blocks, ecs, strict=True):
        poly = block + ec
        for i in range(ec_len):  # every syndrome must be zero
            acc = 0
            for coeff in poly:
                acc = gf_mul(acc, exp[i], exp, log) ^ coeff
            assert acc == 0, "Reed-Solomon check fails"
        data += block
    stream = "".join(f"{w:08b}" for w in data)
    assert stream[:4] == "0100", "byte mode expected"
    width = 16 if version >= 10 else 8
    count = int(stream[4 : 4 + width], 2)
    body = stream[4 + width :]
    return bytes(int(body[i * 8 : i * 8 + 8], 2) for i in range(count)).decode("utf-8")


def test_format_and_version_codes_match_the_standard():
    assert qr.format_bits(0) == 0b101010000010010  # level M, mask 0
    assert qr.version_bits(7) == 0x07C94


@pytest.mark.parametrize(
    "text",
    ["a", "https://www.si-bio.it/", "Offida 63073 è qui", "x" * 60, "y" * 118, URL],
)
def test_svg_decodes_back_to_the_text(text):
    assert decode(qr.svg(text, "title")) == text


def test_every_mask_gives_a_sound_symbol():
    for mask in range(8):
        assert decode(qr.svg(URL, "t", mask=mask)) == URL


def test_text_too_long_for_the_largest_version_is_refused():
    with pytest.raises(ValueError):
        qr.svg("z" * 400, "t")


def test_svg_is_self_contained_and_describes_its_target():
    svg = qr.svg("https://example.org/?a=1&b=<2>", "Code & <title>")
    assert "<desc>https://example.org/?a=1&amp;b=&lt;2&gt;</desc>" in svg
    assert "<title>Code &amp; &lt;title&gt;</title>" in svg
    assert not re.search(r"<(script|image|style|a)\b|href=|url\(", svg)
    assert svg.count("http") == 2  # the xmlns and the text above, nothing fetched


def test_shipped_qr_is_the_one_for_the_current_verify_url():
    svg = SHIPPED.read_text(encoding="utf-8")
    assert f"<desc>{URL}</desc>" in svg
    assert decode(svg) == URL
    assert svg == qr.svg(URL, qr.TITLE)
