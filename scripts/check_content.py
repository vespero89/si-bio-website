"""Check before launch: placeholders left in the content, the public export address, the organic
certificate expiry.

    python scripts/check_content.py

Lists every `[DA COMPLETARE: ...]` style placeholder still in a published language, by language and
file (hidden content does not count: wines with `visible = false`, page keys whose switch is off).
Exits with 1 if any is left, or if the content validator or the export address check finds a
problem. A warning (certificate expiring in 60 days or less) does not change the exit code."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, content  # noqa: E402

EXPORT_EMAIL = "export.sibio@gmail.com"
OLD_EXPORT_EMAIL = "export@si-bio.it"
WARN_DAYS = 60


def certificate_warnings(settings: dict, today: date) -> list[str]:
    if not settings.get("switches", {}).get("organic_certified"):
        return []
    until = date.fromisoformat(str(settings.get("certificate", {}).get("valid_until", "")))
    left = (until - today).days
    if left < 0:
        return [f"the organic certificate expired on {until} ({-left} days ago)"]
    if left <= WARN_DAYS:
        return [f"the organic certificate expires on {until} ({left} days left)"]
    return []


def export_errors(settings: dict) -> list[str]:
    found = settings.get("contact", {}).get("export_email")
    if found != EXPORT_EMAIL:
        return [f"site.toml [contact]: export_email must be {EXPORT_EMAIL}, found {found}"]
    return []


def _found(data: dict, prefix: str = "") -> list[str]:
    """Dotted keys of every value with a placeholder, at any depth."""
    out = []
    for key, value in data.items():
        name = prefix + key
        if isinstance(value, dict):
            out += _found(value, name + ".")
        elif isinstance(value, str) and content.has_marker(value):
            out.append(name)
        elif isinstance(value, list) and any(
            isinstance(v, str) and content.has_marker(v) for v in value
        ):
            out.append(name)
    return out


def markers() -> dict[str, list[tuple[str, str]]]:
    """Placeholders left, as (file, key): under "shared" for the files common to all languages,
    then one list per published language."""
    root = config.CONTENT_DIR
    switches = content.read(root / "site.toml").get("switches", {})
    hidden = [
        slug
        for slug in content._slugs()
        if not content.read(root / "wines" / f"{slug}.toml").get("visible")
    ]
    out: dict[str, list[tuple[str, str]]] = {
        "shared": [],
        **{lang: [] for lang in config.PUBLISHED},
    }

    def scan(group: str, path: Path) -> None:
        if not path.is_file():
            return
        data = content.read(path)
        gated = path.parent.name == "pages"
        data = {
            k: v
            for k, v in data.items()
            if not (gated and k in content.GATED and not switches.get(content.GATED[k]))
        }
        rel = path.relative_to(root).as_posix()
        out[group] += [(rel, key) for key in _found(data)]

    scan("shared", root / "site.toml")
    scan("shared", root / "oil.toml")
    for slug in content._slugs():
        if slug not in hidden:
            scan("shared", root / "wines" / f"{slug}.toml")
    for lang in config.PUBLISHED:
        scan(lang, root / lang / "oil.toml")
        for slug in content._slugs():
            if slug not in hidden:
                scan(lang, root / lang / "wines" / f"{slug}.toml")
        for page in content.PAGES:
            scan(lang, root / lang / "pages" / f"{page}.toml")
    return out


def stale_address_errors() -> list[str]:
    out = []
    for folder in (
        config.CONTENT_DIR,
        config.APP_DIR / "templates",
        config.PROJECT_DIR / "locales",
    ):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and OLD_EXPORT_EMAIL in path.read_text(
                encoding="utf-8", errors="ignore"
            ):
                out.append(f"{path.relative_to(config.PROJECT_DIR)}: still has {OLD_EXPORT_EMAIL}")
    return out


def main(today: date | None = None) -> int:
    today = today or date.today()
    settings = content.read(config.CONTENT_DIR / "site.toml")
    errors = [*content.problems(), *export_errors(settings), *stale_address_errors()]
    left = markers()
    for group, items in left.items():
        label = "shared files" if group == "shared" else group
        print(f"[{label}] {len(items)} placeholders")
        for file, key in items:
            print(f"  {file}: {key}")
    for error in errors:
        print(f"ERROR {error}")
    for warning in certificate_warnings(settings, today):
        print(f"WARNING {warning}")
    return 1 if errors or any(left.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
