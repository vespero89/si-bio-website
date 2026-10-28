# CLAUDE.md

Working notes for this repository.

## What it is
Website of Si Bio (brand always written "Si Bio"; registered name "SI - BIO di Premici & Aleandri
Società Agricola Semplice"): wine and olive oil from Offida (AP). B2B first: credibility towards
buyers, importers and restaurants, in Italian and English. Contacts by `mailto` (no form). The
spec and task list live outside the repo, in the notes folder of the communication project.

## Stack
- Python 3.12+, FastAPI + Uvicorn, Jinja2 + HTMX, no database, no ORM
- Content in TOML files under `content/` (one per wine and per language), site settings in the
  single file `content/site.toml`; interface texts in `locales/<lang>.toml`
- Works without JavaScript; HTMX and a few lines of JS only improve it

## Commands
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --reload-dir app   # http://127.0.0.1:8000
```
Environment variables (names only): `BASE_URL`. Secrets only in `.env`, never in code or commits.

## Checks (run all before every commit)
```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
```
A local git `pre-commit` hook runs ruff check and pytest; never bypass it.

## File map (grows task by task)
```
app/config.py       settings from environment / .env, paths
app/main.py         FastAPI app, static files, routers
app/templating.py   Jinja2 environment
app/templates/      base.html, pages, partials
app/static/         css, js, img, schede (PDF)
content/            site.toml, wines, pages (planned)
locales/            interface texts per language (planned)
scripts/            photos, pre-launch content check (planned)
tests/              pytest
```

## Rules
- No admin panel, no "site that manages the site". Minimal configurability: if something can
  live in a file edited in the code, it lives there.
- Content in files, not in a database. Facts not verified (DOCG, organic, region, awards, Riva dei
  Martin) stay as placeholders, visible in preview and hidden in production.
- Brand: always "Si Bio", in titles, files and emails. Never claim "bio" as an attribute without
  the certification.
- Code, comments, commits and docs in English; text shown on the site in Italian and English.
- No em dashes or en dashes in any text.
- Write code like the code around it: same naming, same comment density.
- Commits are local, never pushed; no remote.
