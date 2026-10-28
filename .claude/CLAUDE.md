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
Environment variables (names only): `BASE_URL`, `PREVIEW`. Secrets only in `.env`, never in code or commits.

## Checks (run all before every commit)
```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
```
A local git `pre-commit` hook runs ruff check and pytest; never bypass it.

## File map (grows task by task)
```
app/config.py       settings from environment / .env, paths, `LANGS`, `PUBLISHED`, `PREVIEW`
app/i18n.py         interface texts: `load`, `t(lang, key)`, `num`, completeness check
app/lang.py         language middleware: Italian at the root, others under /<code>/, root redirect
app/main.py         FastAPI app, static files, routers
app/templating.py   Jinja2 environment, globals `t(key, **values)` and `num(value, decimals)` (language of the request)
app/templates/      base.html, pages, partials
app/static/         css, js, img, schede (PDF)
content/            site.toml (published languages for now), wines, pages (planned)
locales/            interface texts per language (it is the reference), flat keys like `nav.wines`
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

## Languages
`config.LANGS` lists the languages the code knows; `content/site.toml` (`[languages] published`) the
published ones (Italian always). Italian is at the root, the others under `/<code>/`; the middleware
strips the prefix and sets `request.state.lang`. An unpublished language answers 404, unless
`PREVIEW=1`. `/` goes by cookie `lang`, then `Accept-Language`: a published language goes to its
prefix, any other language to `/en/` (Italian if English is not published), empty header stays Italian. `?lang=xx` (the selector) sets the
cookie (1 year, Path=/) and redirects to the same page without the parameter.

## Interface texts
`locales/<code>.toml`, nested tables read as flat keys (`nav.wines`). `{{ t('nav.wines') }}` in
templates, `{{ num(13.5) }}` for numbers (decimal separator is the key `number.decimal` of the
language); sentences with a number use a placeholder: `t('wine.abv', value=num(13.5))`. Italian is
the reference: `i18n.missing(lang)` lists the keys a language lacks and `tests/test_i18n.py` fails if
a published language lacks any. Falling back to Italian happens in preview only; otherwise the key
shows. Adding a language: translate its file, add the code to `LANGS` and `site.toml`.
If English is not published, the root falls back to Italian instead of `/en/`.
