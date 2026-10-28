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
app/content.py      content loader (`site`, `wines`, `wine`, `oil`, `page`), markers, validator `problems()`
app/lang.py         language middleware: Italian at the root, others under /<code>/, root redirect
app/main.py         FastAPI app, static files, routers
app/wines.py        routes `/vini` and `/vini/<slug>`, helpers `sheet`, `photo`, `pdf` for the wine page
app/templating.py   Jinja2 environment, globals `t(key, **values)` and `num(value, decimals)` (language of the request), `canonical()`, `alternates()` (selector and hreflang), `farm_url()`, `menu`, `localize`, `site()`, `mailto(address, subject)`, `has_marker`
app/templates/      base.html (header, menu, selector, canonical/hreflang, footer), wines.html, partials/contact_block.html
app/static/         css/sibio.css (the only stylesheet), fonts/ (woff2 + OFL files), js/contact.js (Copy button), img/vini (bottle photos), schede (PDF)
content/            site.toml (settings), wines/<slug>.toml and oil.toml (neutral), <lang>/wines, <lang>/oil.toml, <lang>/pages (texts)
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

## Content
`app/content.py` reads `content/` (see its docstring for the layout). `wines(lang)` gives the visible
wines by `order`, `wine(lang, slug)` one or None, `oil(lang)`, `page(lang, name)`, `site()`.
Markers (`[DA VERIFICARE: ...]`, `[DA COMPLETARE: ...]`, `[DA DEFINIRE: ...]`, English `[TO BE VERIFIED: ...]`
and the like): a text holding one is shown in preview and becomes empty in production (a list becomes
`[]`), so templates just test for an empty value. Page keys listed in `content.GATED` (the Riva dei
Martin sentence) also need their switch in `site.toml`. `content.problems()` validates the raw files
(required fields, types, unknown keys, same keys as Italian in each published language, pdf files,
unique `order`); `tests/test_content.py` fails if it returns anything. `content.read` is cached: tests that
change `CONTENT_DIR` call `content.read.cache_clear()`. Texts are written, not invented: wine and oil
facts stay markers until the family confirms them. Legal pages (task 13) are exempt from hiding.

## Layout
`app/templates/base.html`: header (text wordmark "Si Bio" until the logo arrives), menu (`templating.MENU`, links
localized by `localize`, `aria-current` on the current page), language selector (`alternates()`: one link per
language that can be shown, `/path?lang=xx` so the cookie follows the choice, name of each language from
`language.name` of its own file), footer (company data from `site.toml`; the farm link needs `farm.url`, without
it the name is plain text; legal links area reserved: `legal_links` in the footer, wired in the legal pages
task). Head: `canonical` and `hreflang` (every language that can be shown plus `x-default` on English) from
`request.state.path`, absolute from `BASE_URL`. One stylesheet, mobile first, palette only in `:root`. Fonts
self hosted in `app/static/fonts/` with their OFL files (Cormorant Garamond 500 for headings, Source Sans 3
400 and 600 for text, latin subset only); never Google Fonts. Pages put their text in `{% block content %}`
with one `h1`.

## Wine pages
`/vini` shows the first wine in front with its own h1 ("I nostri vini") and intro; `/vini/<slug>` has the wine name as h1.
Unknown or hidden slugs answer 404. The row of wines (`nav.wine-row`) is plain links, full page loads (the HTMX
carousel is a later task); `aria-current="page"` on the wine of the page, `"true"` on `/vini`. The technical sheet
(`wines.sheet`) is a `dl` built only from filled fields, in the order of `wines.SHEET`, labels `sheet.<field>`;
a marker value is empty in production, so a field never shows empty. Photo: `photo` in the neutral file is a file in
`static/img/vini/`; while it is a marker a CSS placeholder shows. PDF: `[pdf]` table of the neutral file
(`it = "x.pdf"`, files in `static/schede/`); page language first, else the Italian one with "(in italiano)".
`partials/contact_block.html` (needs `subject`): address as text, `mailto` built by `mailto()` (percent-encoded UTF-8,
`%20`, never `+`), subject `contact.subject_wine`. The "Copy" button is created by `static/js/contact.js` (labels in
`data-copy` / `data-copied`), so without JS only address and link exist.
