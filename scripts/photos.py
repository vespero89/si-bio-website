"""Makes the served sizes of a photo: `<name>.jpg` and, if the original is bigger, `<name>-600.jpg`.

    python scripts/photos.py <source.jpg> <name> [folder]

Writes into `app/static/img/<folder>/` (default `vini`). Sizes are 600 and 1200 wide and only the
ones smaller than the source are made: a photo is never enlarged, so a 687 px wide source gets just
the 600 variant. The served `<name>.jpg` is the source itself, or the 1200 version if it is wider.
Originals stay out of git. Resizing uses `sips` (macOS)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import photos  # noqa: E402

SIZES = (600, 1200)
QUALITY = "60"


def variant_widths(width: int) -> list[int]:
    """The widths to make for a source of this width: only the smaller ones."""
    return [size for size in SIZES if size < width]


def _resample(source: Path, width: int, target: Path) -> None:
    subprocess.run(
        ["sips", "--resampleWidth", str(width), "-s", "formatOptions", QUALITY, str(source),
         "--out", str(target)],
        check=True,
        capture_output=True,
    )  # fmt: skip


def build(source: Path, name: str, folder: Path) -> list[Path]:
    size = photos.jpeg_size(source)
    if size is None:
        raise ValueError(f"{source} is not a JPEG")
    folder.mkdir(parents=True, exist_ok=True)
    widths = variant_widths(size[0])
    written = []
    main = folder / f"{name}.jpg"
    if 1200 in widths:
        _resample(source, 1200, main)
    else:
        shutil.copyfile(source, main)
    written.append(main)
    if 600 in widths:
        small = folder / f"{name}-600.jpg"
        _resample(source, 600, small)
        written.append(small)
    return written


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print("usage: python scripts/photos.py <source.jpg> <name> [folder]", file=sys.stderr)
        return 2
    folder = ROOT / "app" / "static" / "img" / (argv[2] if len(argv) == 3 else "vini")
    try:
        written = build(Path(argv[0]), argv[1], folder)
    except ValueError as error:
        print(f"error: {error}, expected a JPEG", file=sys.stderr)
        return 1
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for path in written:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
