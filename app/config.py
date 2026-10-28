"""Settings from environment variables, with an optional .env file in the project root.

Real environment variables win over the .env file. There are no secrets and no database:
site content lives in files under `content/`."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines, # comments, optional quotes."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(PROJECT_DIR / ".env")

CONTENT_DIR = PROJECT_DIR / "content"
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

BASE_URL = (os.environ.get("BASE_URL") or "http://127.0.0.1:8000").rstrip("/")

PREVIEW = os.environ.get("PREVIEW", "").strip().lower() in ("1", "true", "yes", "on")
"""Preview for the family: languages and placeholders that are not published show up."""
COOKIE_SECURE = BASE_URL.startswith("https://")

LANGS = ("it", "en")
"""Languages the code knows. Italian is at the root, every other one under /<code>/."""


def _load_published() -> tuple[str, ...]:
    path = CONTENT_DIR / "site.toml"
    codes = ["it"]
    if path.is_file():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        codes = list(data.get("languages", {}).get("published", codes))
    return tuple(c for c in LANGS if c in codes or c == "it")


PUBLISHED = _load_published()
"""Languages listed in content/site.toml; the others answer 404 unless PREVIEW is on."""
