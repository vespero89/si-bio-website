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
app/contact.py      route `/contatti` (mailto block, company data, sales manager role)
app/pages.py        routes `/`, `/olio`, `/chi-siamo` (helper `oil_sheet`)
app/wines.py        routes `/vini` and `/vini/<slug>` (fragment for HTMX, `Vary`), helpers `sheet`, `photo`, `pdf` for the wine page
app/templating.py   Jinja2 environment, globals `t(key, **values)` and `num(value, decimals)` (language of the request), `canonical()`, `alternates()` (selector and hreflang), `farm_url()`, `menu`, `localize`, `site()`, `mailto(address, subject)`, `has_marker`
app/cookies.py      cookie choice (POST /cookie-choice, `choice(request)`)
app/legal.py        legal pages `/info/note-legali|privacy|cookie` (templates in `templates/legal/<lang>/`, `company(lang)`)
app/pages.py        also `video()` (id and cover from site.toml for the visits page)
app/templates/      base.html (header, menu, selector, canonical/hreflang, footer), home.html, oil.html, about.html, wines.html (page), wine_fragment.html (HTMX), partials/wine_row|wine_stage|wine_intro|contact_block.html
app/static/         css/sibio.css (the only stylesheet), fonts/ (woff2 + OFL files), js/htmx.min.js (2.0.4, same file as ecommerce-fattoria), js/wines.js (focus), js/contact.js (Copy button, loaded by base.html), img/vini (bottle photos), schede (PDF)
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
facts stay markers until the family confirms them. Legal pages are exempt from hiding (see "Legal pages").

## Layout
`app/templates/base.html`: header (text wordmark "Si Bio" until the logo arrives), menu (`templating.MENU`, links
localized by `localize`, `aria-current` on the current page), language selector (`alternates()`: one link per
language that can be shown, `/path?lang=xx` so the cookie follows the choice, name of each language from
`language.name` of its own file), footer (company data from `site.toml`; the farm link needs `farm.url`, without
it the name is plain text; `legal_links` in the footer: legal notice and privacy; "Gestisci i cookie" link to `/info/cookie#scelta`, always shown, the page comes with the legal pages task). Head: `canonical` and `hreflang` (every language that can be shown plus `x-default` on English) from
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

## Wine carousel (HTMX)
`/vini` and `/vini/<slug>` render `wines.html`: `#wine-intro` (h1 + lead, only on `/vini`), `nav#wine-row` (links
with `hx-get`, `hx-target="#wine-stage"`, `hx-push-url="true"` on the nav) and `#wine-stage` (the
`.wine-front` article). With `HX-Request: true` the route returns `wine_fragment.html` instead: `<title>`
(htmx updates the tab title), the intro and the row as out of band swaps (`hx-swap-oob="innerHTML"`, so the new
`aria-current` and an h1 that is only on `/vini` follow, and the row keeps its scroll position) and the
stage. A history restore (`HX-History-Restore-Request`) gets the full page. Every wine response has
`Vary: HX-Request, HX-History-Restore-Request`. After the swap `js/wines.js` focuses the wine title
(`tabindex="-1"`) and `contact.js` runs again to add the Copy button. HTMX and the scripts are local (no CDN).
The fade in uses `.htmx-added`; the global `prefers-reduced-motion` rule disables it. Arrow keys are not
implemented (links are enough). Without JS the plain links of the page keep working.

## Contact page
`/contatti` (`app/contact.py`, `contact.html`): h1 and intro from `content/<lang>/pages/contact.toml`, the
`partials/contact_block.html` with subject `contact.subject_info` ("Si Bio: informazioni" / "Si Bio: information", no wine),
then company data from `site.toml` (name, VAT, registered office, PEC, phone) and the role of the commercial manager read
from `sales_contact` of the `about` page file. Every value that is still a marker is empty in production, so its line is
left out (shown in preview). No form, no database. The menu entry `nav.contact` already points here.

## Home, oil, about
`app/pages.py`. Home: h1, `home.lead`, the claim as `blockquote.claim` (`claim`, optional `claim_by` as its source; both
markers until the DOCG and Veneto check, so no quotation in production), `who` when verified, the family line with the farm
link (`footer.family_*` keys), the five wines as plain links in a `.wine-row` (no HTMX), links to `/olio` and `/visite`,
the buyers sentence (`buyers` of the file, else `home.buyers`) and the "Contattaci" button; `certification` only when filled.
In production the home is therefore h1, lead, family line, wines and links. Oil: h1 `oil.name`, `oil.intro`, description,
a `dl.sheet` from `pages.OIL_SHEET` (harvest uses the label `sheet.oil_harvest`), optional PDF (`[pdf]` of `oil.toml`, same
`wines.pdf` rule), contact block with subject `contact.subject_olio` ("Si Bio: olio" / "Si Bio: oil"). About: h1, `family`
(who), `about.what` (fixed text: five wines from Piceno grapes and an oil, no "organic"), `why_veneto`, the family line, the
Riva dei Martin sentence only with `riva_dei_martin = true` in `site.toml` (`content.GATED`; never "our winery"), the commercial
manager role (`sales_contact`) and the contact button. Tests: `tests/test_pages.py`.

## Visits and package
`/visite` (`pages.visits_page`, `visits.html`, page file `visits.toml`). h1 `title`, then two sections. Buyers (on invitation,
`visits.invitation`): `buyers_title` ("Vieni a trovarci" / "Visit us"), `buyers_text`, the video block `partials/video.html` (see "Video"), contact block to `export_email` with subject `contact.subject_buyers` and button
`visits.buyers_button`. Package (sold by Fuselli e Filari, no price, no programme invented): `package_name` as h2, `package_lead`,
`package_text`, `package_hotel` (Hotel Casale), the fixed line `visits.organizer`, contact block with `contact_address` =
`partner_email` of `site.toml`, subject `contact.subject_package` ("Richiesta programma: {name}") and button `visits.package_button`.
The whole package section is left out in production unless `partner_email` AND `package_name` are verified (markers). The partial
`contact_block.html` takes optional `contact_address` and `contact_button`. Riva dei Martin lines (`buyers_riva_dei_martin`,
`package_riva_dei_martin`) are in `content.GATED`: only with the switch on (and still markers until agreed). Tests: `tests/test_visits.py`.

## Cookie choice
`app/cookies.py`. The site sets only technical cookies (`lang`, `cookie_choice`); the choice exists for the YouTube video (task 12),
which loads only when `cookie_choice(request)` is `"accepted"` (template global, same function as `cookies.choice`: `accepted`,
`rejected` or None; any other value counts as no choice). Cookie `cookie_choice`: 183 days (`cookies.MAX_AGE`), Path=/, HttpOnly,
SameSite=Lax, Secure when `BASE_URL` is https (`config.COOKIE_SECURE`); no identifier; nothing in JavaScript reads or writes it.
`POST /cookie-choice` (also `/en/cookie-choice`): urlencoded `choice` = `accept`|`reject` (else 400, no cookie) and `next`, a local
path (`safe_next`: one leading `/`, no `//`, backslash or control character; else the home). Answers 303; the language middleware
puts the prefix back on the Location. `GET` is 405. The body is read by hand (no python-multipart). `partials/cookie_notice.html`
(band before `</body>`, only while there is no choice, on every full page, not in HTMX fragments) holds `partials/cookie_form.html`
(two `.button`s, same style). `partials/cookie_choice.html` (`#scelta`: current choice sentence + the form) is included by the `/info/cookie` page. No `Vary: Cookie` from the app: the proxy must vary on `Cookie` or not cache HTML. Tests: `tests/test_cookies.py`;
other tests that forbid forms or buttons strip the notice with `NOTICE`.

## Video
`/visite` only. `pages.video()` reads `[video]` of `site.toml`: `youtube_id` (11 characters `[A-Za-z0-9_-]`) and `cover` (file name in
`static/img/`, 16:9, rendered 1280x720). While one is a marker or the id is not valid, the whole block is gone in production; in preview
a `p.video-placeholder` shows the marker text (no URL, no iframe). `partials/video.html` renders `div.video-slot#video` (no nested div):
a `figure.video-frame` (16:9 box) holding either the iframe or the cover plus a CSS play mark, then, unless accepted, the consent text and a
form to `/cookie-choice` (`next` = page + `#video`): no choice gives "Accetto e guardo" / "Non ora", `rejected` gives only the accept
button. Always the plain anchor "Guarda su YouTube" (`youtube.com/watch?v=<id>`, `target="_blank"`, `noopener noreferrer`). Only with
`cookie_choice(request) == "accepted"` the server renders `https://www.youtube-nocookie.com/embed/<id>?rel=0&hl=<lang>` (`loading="lazy"`,
title, `referrerpolicy="strict-origin-when-cross-origin"`, `allow="encrypted-media; picture-in-picture; fullscreen"`). No JavaScript.
Subtitles are YouTube's. Tests: `tests/test_video.py`.
**CSP (task 15, not set yet):** needs `frame-src https://www.youtube-nocookie.com` (kept even without consent, it is only a permission)
and `img-src 'self' data:`; no `media-src`, no inline script.

## Legal pages
`app/legal.py`: `/info/note-legali`, `/info/privacy`, `/info/cookie` (and `/en/info/...`). Texts are templates, one per page and
language (`templates/legal/it|en/{note_legali,privacy,cookie}.html`, extending `legal/base.html`: tabs `nav.legal-tabs`, h1, and
`p.legal-provisional` "provisional text, awaiting review by a lawyer"; the English one says it is a literal translation to be
reviewed). Only what is true for the site: no forms, no analytics, mailto to `export@si-bio.it` (and to Fuselli e Filari for the
package), server logs, cookies `lang` (1 year) and `cookie_choice` (6 months), YouTube only after consent. The cookie page lists the
two cookies and includes `partials/cookie_choice.html` (`#scelta`). Footer: `legal_links` (notice, privacy) plus "Gestisci i cookie".
**Placeholders are never hidden here**: company values come from `content.site_raw()` (markers kept; `legal.company(lang)` turns a
marker into the marker of the page language via `legal.todo`/`legal.define`, keys `legal.what_*`), text placeholders are written in the
templates with `t('legal.todo'|'legal.define', what=...)`. Open points today: notice 3 (registered office, PEC, REA = `[company]` of
`site.toml`, new key `rea`), privacy 4 (hosting provider, legal basis of logs, retention of logs, retention of emails), cookie 0.
`tests/test_legal.py` (`EXPECTED`) counts them per page and fails if the number changes: update it when a point is filled in.
When a legal text changes, change its twin in the other language too. Not invented: legal basis of the logs, any retention period.
