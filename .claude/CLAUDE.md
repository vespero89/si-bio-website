# CLAUDE.md

Working notes for this repository.

## What it is
Website of Si Bio (brand always written "Si Bio"; registered name "Si Bio di Premici Silvia e
Aleandri Vincenzo, società semplice agricola"): wine and olive oil from Offida (AP). B2B first: credibility towards
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
app/templating.py   Jinja2 environment, globals `t(key, **values)` and `num(value, decimals, group)` (language of the request), `canonical()`, `alternates()` (selector and hreflang), `farm_url()`, `menu`, `localize`, `site()`, `mailto(address, subject)`, `has_marker`
app/cookies.py      cookie choice (POST /cookie-choice, `choice(request)`)
app/errors.py       error pages (404, 405, 410, 500), `SecurityHeadersMiddleware` (headers, CSP, cache)
app/seo.py          `/robots.txt`, `/sitemap.xml`, `/llms.txt` (per language), `NoindexMiddleware` (preview)
app/jsonld.py       JSON-LD builders: `clean`, `dumps`, `organization`, `website`, `product`, `breadcrumbs`
app/legal.py        legal pages `/info/note-legali|privacy|cookie` (templates in `templates/legal/<lang>/`, `company(lang)`)
app/pages.py        also `video()` (id and cover from site.toml for the visits page)
app/templates/      base.html (header, menu, selector, canonical/hreflang, footer), home.html, oil.html, about.html, wines.html (page), wine_fragment.html (HTMX), partials/stave_long|stave_short (inline SVG staves)|wine_row|wine_stage|wine_intro|contact_block.html
app/static/         css/sibio.css (the only stylesheet), fonts/ (woff2 + OFL files), js/htmx.min.js (2.0.4, same file as ecommerce-fattoria), js/wines.js (focus), js/wine-dialog.js (home dialog and arrows, home only), js/contact.js (Copy button, loaded by base.html), img/vini (bottle photos), schede (PDF)
content/            (wines: Pecorino, Passerina, Armide, Passacaille visible; Offida Rosso `visible = false` until sheet and photo; optional text `claim` on Armide and Passacaille only, shown with "Taste the Essence"; DOCG only on the two Offida wines)
content/            site.toml (settings), wines/<slug>.toml and oil.toml (neutral), <lang>/wines, <lang>/oil.toml, <lang>/pages (texts)
locales/            interface texts per language (it is the reference), flat keys like `nav.wines`
scripts/            qr.py, photos.py (photo sizes), check_content.py (pre-launch check)
tests/              pytest (`test_css.py`: every template class is styled or a hook; `test_about`, `test_wine_page`, `test_home_rail`, `test_visits`, `test_video`: markup of the redesigned pages)
```

## Rules
- No admin panel, no "site that manages the site". Minimal configurability: if something can
  live in a file edited in the code, it lives there.
- Content in files, not in a database. Facts not verified (DOCG, region, awards, Riva dei
  Martin) stay as placeholders, visible in preview and hidden in production.
- Brand: always "Si Bio", in titles, files and emails. "Organic" only as "azienda biologica" /
  "organic farm", in the certificate block, the home line, the footer link, JSON-LD and llms.txt, and
  only with `organic_certified = true`. Never "vino biologico", "olio biologico", "uve biologiche"
  or the English twins (the certificate covers unprocessed crops, not wine or oil).
- Code, comments, commits and docs in English; text shown on the site in Italian and English.
- No em dashes or en dashes in any text.
- Write code like the code around it: same naming, same comment density.
- One local branch per stream of work, merged into `main` by Fabio; the private GitHub remote `origin` is pushed only when Fabio says so.

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
(required fields, `group` of visible wines in `content.GROUPS`, types, unknown keys, same keys as Italian in each published language, pdf files,
unique `order`); `tests/test_content.py` fails if it returns anything. `content.read` is cached: tests that
change `CONTENT_DIR` call `content.read.cache_clear()`. Texts are written, not invented: wine and oil
facts stay markers until the family confirms them. Legal pages are exempt from hiding (see "Legal pages").

## Layout
`app/templates/base.html`: header (text wordmark "Si Bio" until the logo arrives), menu (`templating.MENU`, links
localized by `localize`, `aria-current` on the current page), language selector (`nav.lang`, plain links without a list; `alternates()`: one link per
language that can be shown, `/path?lang=xx` so the cookie follows the choice, name of each language from
`language.name` of its own file), footer (`.footer-grid` in three columns: "Si Bio" with company name, registered office, VAT and the farm line; "Esplora" with the menu; "Contatti" with `export_email` and, only with the certificate, the link to `/chi-siamo#certificato`; then the `nav.legal` row: `footer.copyright` with `this_year()`, legal notice, privacy and "Gestisci i cookie" to `/info/cookie#scelta`, always shown; the farm link needs `farm.url`, without it the name is plain text). Head: `canonical` and `hreflang` (every language that can be shown plus `x-default` on English) from
`request.state.path`, absolute from `BASE_URL`. One stylesheet, mobile first, palette only in `:root`. Page blocks to reuse: `.wrap` (width and gutter), `.page-head` (eyebrow, h1, `.lead`), `.split` (+ `.split-bordered`, `.prose`), `.band` / `.band-dark`; a script-focused title (`tabindex="-1"`) shows no outline. Fonts
self hosted in `app/static/fonts/` with their OFL files (Cormorant Garamond 500 for headings, Source Sans 3
400 and 600 for text, latin subset only); never Google Fonts. Pages put their text in `{% block content %}`
with one `h1`.

## Wine pages
`/vini` shows the first wine in front with its own h1 ("I nostri vini") and intro; `/vini/<slug>` has the wine name as h1.
Unknown or hidden slugs answer 404. The row of wines (`nav.wine-row`) is plain links, full page loads (the HTMX
carousel is a later task); `aria-current="page"` on the wine of the page, `"true"` on `/vini`. The stage (`partials/wine_stage.html`) is `article.wp`: `.wp-photo` (photo with `srcset`, `alt`, size, or the CSS placeholder), then
`.wp-body`: `header.score` (short stave partial with `cls="stave"`, the name as h1 on `/vini/<slug>` and h2 on `/vini`, `p.score-sub` =
`subtitle`, `p.kicker` = `style`), `p.desc`, `section.story` (h2 `story_title`, `story`, and the `blockquote.story-claim` with "Taste the Essence"
inside it when the wine has a `claim`; no section while `story` is empty or a marker, so Pecorino and Passerina have none in production),
h2 `wines.sheet_title`, the sheet, PDF link and contact block. The other wines are the `nav.wine-row`. The technical sheet
(`wines.sheet`) is a `dl` built only from filled fields, in the order of `wines.SHEET`, labels `sheet.<field>`;
a marker value is empty in production, so a field never shows empty. New wine fields: neutral `group` ("piceno" | "opera", required for visible wines; Offida Rosso is piceno); texts `subtitle` (Armide "Opera di Lully", Passacaille "Finale della stessa opera", empty elsewhere), `story_title` and `story` (Armide and Passacaille: the name; Pecorino and Passerina: markers until the family writes them; listed in `content.WINE_TEXT`). Earlier fields: `style`, `training`, `bottle_aging`, `appearance`, `aroma`, `palate` (texts per language, in `content.CARD`) and `bottles_per_year` (number in the neutral file, shown grouped by `num(value, 0, true)`: 5.000 / 5,000; published on purpose). No price field; keep the sheet free of prices, of the contract winemaking and of "organic" for wines (the certificate block and the home line never appear on wine or oil pages; the footer link is on every page). Photo: `photo` in the neutral file is a file in
`static/img/vini/`; while it is a marker a CSS placeholder shows. PDF: `[pdf]` table of the neutral file
(`it = "x.pdf"`, files in `static/schede/`); page language first, else the Italian one with "(in italiano)".
`partials/contact_block.html` (needs `subject`; optional `inline`): address as text, `mailto` built by `mailto()` (percent-encoded UTF-8,
`%20`, never `+`), subject `contact.subject_wine`. The "Copy" button is created by `static/js/contact.js` (labels in
`data-copy` / `data-copied`), so without JS only address and link exist.

## Wine carousel (HTMX)
`/vini` and `/vini/<slug>` render `wines.html`: `#wine-intro` (h1 + lead, only on `/vini`), `nav#wine-row` (links
with `hx-get`, `hx-target="#wine-stage"`, `hx-push-url="true"` on the nav) and `#wine-stage` (the
`article.wp`). With `HX-Request: true` the route returns `wine_fragment.html` instead: `<title>`
(htmx updates the tab title), the intro and the row as out of band swaps (`hx-swap-oob="innerHTML"`, so the new
`aria-current` and an h1 that is only on `/vini` follow, and the row keeps its scroll position) and the
stage. A history restore (`HX-History-Restore-Request`) gets the full page. Every wine response has
`Vary: HX-Request, HX-History-Restore-Request`. After the swap `js/wines.js` focuses the wine title
(`tabindex="-1"`) and `contact.js` runs again to add the Copy button. HTMX and the scripts are local (no CDN).
The fade in uses `.htmx-added`; the global `prefers-reduced-motion` rule disables it. Arrow keys are not
implemented (links are enough). Without JS the plain links of the page keep working.

## Contact page
`/contatti` (`app/contact.py`, `contact.html`): `.page-head` with h1 and intro from `content/<lang>/pages/contact.toml` (and the sales role), the
`partials/contact_block.html` (`inline`: `data-inline`, address and button side by side on wide screens; also used by the oil page) with subject `contact.subject_info` ("Si Bio: informazioni" / "Si Bio: information", no wine),
then company data from `site.toml` (name, VAT, registered office, PEC, phone) and the role of the commercial manager read
from `sales_contact` of the `about` page file. Every value that is still a marker is empty in production, so its line is
left out (shown in preview). No form, no database. The menu entry `nav.contact` already points here.

## Home, oil, about
`app/pages.py`. Home (`home.html`): visually hidden `h1.sr-only` "Si Bio" (page `title`), then `section.wines`: `ul.rail[data-rail]` in two
movements by the neutral field `group` (`piceno` then `opera`, wines by `order`): movement I (`home.movement_1_*`), the cards, movement II
(eyebrow `tagline`, the `claim` of the home file as its title, `home.movement_2_text`), the cards. A card is
`<a href="/vini/<slug>" data-wine="<slug>">` with the bottle photo (`alt=""`, the caption names the wine; `subtitle`, else `style`, under it).
The arrows `div[data-rail-arrows][hidden]` are shown by `js/wine-dialog.js` (loaded with `defer` by the home only, through `{% block scripts %}`
of `base.html`). After the main blocks come one `<template id="wine-<slug>">` per visible wine, the presentation the script puts in a native
`<dialog>`: close button, photo, `header.score` (short stave, name, `subtitle`, kicker = style + denomination), description, `dl.facts`
(grapes, abv, serving temperature), `dl.senses` (appearance, aroma, palate, pairings), `section.story` (`story_title`, `story`, and the
claim with "Taste the Essence" on the wines that have one), buttons "Scheda tecnica completa" (wine page) and "Scrivici" (`mailto()`,
subject `contact.subject_wine`). A field that is empty (a marker in production) leaves its row out; a wine without `story` has no story
section. Without JS the cards are plain links. Then `section.intro` (`home.lead`, `mission`, `territory`), `figure.claim` (long stave,
"Taste the Essence" as the only quote, the family line with the farm link: "The roots of Si Bio are at Fattoria nel Ciafone...", the muted line `home.people` under `home.lead`), the tiles for the oil (`/olio`, keys `home.oil_*`, no "organic") and visits (`/visite`), and `section.band` (the
buyers sentence, "Contattaci", the certificate line `p.certified` only with the switch on). The claim appears only in movement II (and in the
Armide and Passacaille dialogs). Tests: `tests/test_home_rail.py`, `tests/test_home_about.py`.
Oil (`oil.html`): `.page-head` (eyebrow `oil.eyebrow`, h1 `oil.name`, `p.lead` = `oil.intro`), the scene photo, `.split` with the description (`.prose`) and the
`dl.sheet` from `pages.OIL_SHEET` (harvest uses the label `sheet.oil_harvest`), optional PDF (`[pdf]` of `oil.toml`, same
`wines.pdf` rule), contact block (`inline`) with subject `contact.subject_olio` ("Si Bio: olio" / "Si Bio: oil"). About (`about.html`): `div.page-head` (eyebrow `about.eyebrow`, h1, `p.lead` = `about.what`), `div.split.split-bordered` with `.prose` (`family`: two plain-fact paragraphs split on a blank line, also the meta description; `mission`, `territory`, the Riva dei Martin sentence only with `riva_dei_martin = true` in `site.toml` (`content.GATED`; never "our winery"), the commercial manager role `sales_contact`) and a 4:5 family photo placeholder; then `section.silvia#musica` (long stave watermark, 4:5 portrait placeholder, `about.music_label`, h2 `music_title`, `music` split on blank lines into paragraphs, link `about.music_link` to `/visite#video`; facts stated by Fabio, no markers, no "organic", no Veneto; left out only if `music` is empty); then the certificate block (below, `dl.sheet` + QR, only with `certificate()`); last the family line and the contact button on `section.band.band-dark`. Tests: `tests/test_pages.py`.

## Visits and package
`/visite` (`pages.visits_page`, `visits.html`, page file `visits.toml`). `.page-head` (eyebrow `visits.eyebrow`, h1 `title`), then `section.buyers`: left column eyebrow
`visits.invitation`, h2 `buyers_title`, `p.first` = `buyers_text`, `p.hotel` (`buyers_hotel` + `buyers_hotel_url`, Hotel Il Casale, facts from hotelcasale.it, link
`visits.hotel_link`), Riva dei Martin line; right column `div.includes` (h3 `visits.includes_title`, `ol` of `buyers_includes`, listed in `content.LIST_KEYS`) and
`p.price` "Listino su richiesta" (`visits.price_list`, mailto to `export_email` with subject `contact.subject_price`; no price or terms anywhere). Then the video
block (`partials/video.html`, see "Video"), then `div.buyers-contact` with the contact block to `export_email`, subject `contact.subject_buyers`, button
`visits.buyers_button`. Package (`section.wrap.package`, sold by Fuselli e Filari, no price, no programme invented): `package_name` as h2, `package_lead`,
`package_text`, `package_hotel` (Hotel Il Casale), the fixed line `visits.organizer`, contact block with `contact_address` =
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
(two `.button`s, same style). `partials/cookie_choice.html` (`#scelta`: current choice sentence + the form) is included by the `/info/cookie` page. HTML carries `Vary: Cookie` and `Cache-Control: no-cache` (see "Errors and security"). Tests: `tests/test_cookies.py`;
other tests that forbid forms or buttons strip the notice with `NOTICE`.

## Video
`/visite` only. The partial is `section.video` (`.wrap`, `div.video-head` with eyebrow `video.eyebrow`, h2 `video.title` and `p.music-credit` = `video.music_credit`, "Musica originale di Silvia Premici" / "Original music by Silvia Premici"), then the slot; the credit lives in this block only and goes with it when the block is left out. `pages.video()` reads `[video]` of `site.toml`: `youtube_id` (11 characters `[A-Za-z0-9_-]`) and `cover` (file name in
`static/img/`, 16:9, rendered 1280x720). While one is a marker or the id is not valid, the whole block is gone in production; in preview
a `p.video-placeholder` shows the marker text (no URL, no iframe). `partials/video.html` renders `div.video-slot#video` (no nested div):
a `figure.video-frame` (16:9 box) holding either the iframe or the cover plus a CSS play mark, then, unless accepted, a
`form.consent` (text + buttons) to `/cookie-choice` (`next` = page + `#video`): no choice gives "Accetto e guardo" / "Non ora", `rejected` gives only the accept
button. Always the plain anchor "Guarda su YouTube" (`p.yt`) (`youtube.com/watch?v=<id>`, `target="_blank"`, `noopener noreferrer`). Only with
`cookie_choice(request) == "accepted"` the server renders `https://www.youtube-nocookie.com/embed/<id>?rel=0&hl=<lang>` (`loading="lazy"`,
title, `referrerpolicy="strict-origin-when-cross-origin"`, `allow="encrypted-media; picture-in-picture; fullscreen"`). No JavaScript.
Subtitles are YouTube's. Tests: `tests/test_video.py`.
**CSP (task 15, not set yet):** needs `frame-src https://www.youtube-nocookie.com` (kept even without consent, it is only a permission)
and `img-src 'self' data:`; no `media-src`, no inline script.

## Legal pages
`app/legal.py`: `/info/note-legali`, `/info/privacy`, `/info/cookie` (and `/en/info/...`). Texts are templates, one per page and
language (`templates/legal/it|en/{note_legali,privacy,cookie}.html`, extending `legal/base.html`: tabs `nav.legal-tabs`, h1, and
`p.legal-provisional` "provisional text, awaiting review by a lawyer"; the English one says it is a literal translation to be
reviewed). Only what is true for the site: no forms, no analytics, mailto to `export_email` (the brochure's Gmail, decided by Fabio 29/10) (and to Fuselli e Filari for the
package), server logs, cookies `lang` (1 year) and `cookie_choice` (6 months), YouTube only after consent. The cookie page lists the
two cookies and includes `partials/cookie_choice.html` (`#scelta`). Footer: `legal_links` (notice, privacy) plus "Gestisci i cookie".
**Placeholders are never hidden here**: company values come from `content.site_raw()` (markers kept; `legal.company(lang)` turns a
marker into the marker of the page language via `legal.todo`/`legal.define`, keys `legal.what_*`), text placeholders are written in the
templates with `t('legal.todo'|'legal.define', what=...)`. Open points today: notice 3 (registered office, PEC, REA = `[company]` of
`site.toml`, new key `rea`), privacy 4 (hosting provider, legal basis of logs, retention of logs, retention of emails), cookie 0.
`tests/test_legal.py` (`EXPECTED`) counts them per page and fails if the number changes: update it when a point is filled in.
When a legal text changes, change its twin in the other language too. Not invented: legal basis of the logs, any retention period.

## SEO and GEO
Mechanics only; the wording is provisional (see "Texts to review before deploy").
`app/seo.py`: `/robots.txt` and `/sitemap.xml` exist at the root only (`/en/...` answers 404), `/llms.txt` and `/en/llms.txt` one per
published language. Production: robots allows everything and ends with `Sitemap: <BASE_URL>/sitemap.xml`. `PREVIEW=1`: robots is
`Disallow: /` without sitemap line, `NoindexMiddleware` (outermost) adds `X-Robots-Tag: noindex` to every response, and `base.html`
adds `<meta name="robots" content="noindex, nofollow">`; production has neither. Sitemap: home, `/vini`, each visible wine, `/olio`,
`/chi-siamo`, `/visite`, `/contatti`, the three legal pages, each in every PUBLISHED language (never in preview-only ones), every entry with
`xhtml:link` alternates for the published languages plus `x-default` (English if published, else Italian). No `lastmod`: the files carry no
reliable date. Absolute URLs from `config.BASE_URL`.
Head (`base.html`): `description` = `meta_description` set by the page (`{% set meta_description = ... %}` at the top of the child
template, filter `meta_text` = first sentence cut near 155 characters, empty for a marker) or the key `meta.default`; Open Graph
(`og:site_name`, `type`, `title` = the `<title>`, `description`, `url` = canonical, `locale` from the key `meta.locale`, `locale:alternate`,
`og:image` only when the page sets `og_image`, today the bottle photo of wines and oil), Twitter card (`summary_large_image` with an image,
else `summary`). Page sources: home `home.lead`, wine and oil their description, about `family`, visits `buyers_text`.
JSON-LD (`app/jsonld.py`, routes pass `jsonld` = list of `dumps` strings, `base.html` prints one `application/ld+json` script each):
home `Organization` (name "Si Bio", legalName, `vatID` = IT + VAT, url, email, address only when verified, `sameAs` only for set social
profiles) and `WebSite`; each wine page and the oil page `Product` (name, description, url, bottle photo, brand, `category` from
`jsonld.category_*`) with NO `Offer`, plus `BreadcrumbList`. `clean` drops empty values and markers at any depth, so a placeholder never
appears even in preview. No JSON-LD on `/vini`, contact, about, visits, legal. Inline scripts of this type are data, the "no inline
script" tests allow them.
`/llms.txt` (`seo.llms_txt`): headings from `llms.*` keys, summary `llms.summary`, wines with their link and the filled sheet facts
(markers skipped), oil, visits (package line only when `package_name` and `partner_email` are verified), contact email, farm link when
known. Riva dei Martin never appears. When the content flow changes, check it still tells the truth.
Tests: `tests/test_seo.py` (files, head, JSON-LD, llms), `tests/test_seo_structure.py` walks every public page in every published
language (one h1, heading order, img alt/width/height, links with text, one canonical, hreflang for each language plus x-default, title,
description).

## Errors and security
`app/errors.py`. No redirects from the old WordPress (Fabio, 29/10): `/info/`, `/info2/`, `/blog/` answer a normal 404. Errors are
`templates/error.html` (title and text from `error.title_<status>` / `error.text_<status>`, links to Vini and Contatti), in the language of
the request (the language middleware has stripped the prefix, so `/en/anything` is English; an unpublished prefix is Italian 404), always
`noindex` (header `X-Robots-Tag` plus meta robots, no canonical or hreflang). Same page for HTMX requests (htmx does not swap 4xx, so the
carousel stays as it is). 404 on feeds and the old API (`errors.GONE`: `/feed`, `/comments/feed`, `/wp-json`, `/xmlrpc.php`) becomes 410;
`errors.PLAIN` (`/wp-login.php`, `/wp-admin`, `/wp-content`, `/wp-includes`) gets a 7 byte plain text 404. 405 keeps its `Allow`.
An unexpected error is logged and answers the 500 page (caught in `SecurityHeadersMiddleware`, since Starlette's own 500 handler sits
outside the middleware and would skip the headers); no detail is shown.
`SecurityHeadersMiddleware` is the outermost middleware, so every response has: `Content-Security-Policy` (`default-src 'self'`; script,
style, font `'self'`; `img-src 'self' data:`; `frame-src https://www.youtube-nocookie.com` always, it is only a permission and the iframe
is rendered only after the choice; `frame-ancestors 'none'`; `object-src 'none'`; `base-uri` and `form-action` `'self'`), `X-Frame-Options:
DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (camera, microphone,
geolocation, payment, usb, topics off; fullscreen and encrypted-media are not listed, so the video iframe `allow` still works),
`Strict-Transport-Security: max-age=31536000` only when `BASE_URL` is https. Nothing inline is allowed: no `<style>`, `style=""`, `on*=`
or inline script (`test_pages_work_under_the_csp` checks every page); the `application/ld+json` blocks are data, not executed, so the
CSP does not apply to them; htmx would inject a `<style>` for indicators, so `base.html` sets `htmx-config` `includeIndicatorStyles:
false`. When adding JS or CSS, put it in `app/static/`. Cache: HTML gets `Vary: Cookie` (merged with `HX-Request` on the wine pages;
the cookie notice and the video depend on `cookie_choice`) and `Cache-Control: no-cache`; `/static/` gets `Cache-Control: no-cache`
(ETag revalidation) because file names are not versioned yet: if names get a hash or `?v=`, a year of cache can be set for them.
Tests: `tests/test_security.py`.

## Texts to review before deploy
Provisional, to be read by Fabio and the family before launch:
- locale keys `meta.default` (fallback description of every page), `llms.*` (summary and headings), `jsonld.category_wine|oil`, in `locales/it.toml` and `en.toml`;
- titles: `<name> | Si Bio` built in each template (`page.title`, wine or oil name);
- descriptions: `home.lead`, first sentence of wine/oil description, `about.family`, `visits.buyers_text` (content files);
- JSON-LD values: legalName, VAT, email, address, `sameAs` come from `site.toml`; name "Si Bio" and brand in `jsonld.BRAND`;
- `llms.txt` structure and the line `visits.organizer`.

## Organic certificate
`organic_certified` (`[switches]`) and `[certificate]` in `content/site.toml` rule everything: `app/certificate.py`
`get(lang)` returns the data (dates written per language with the `certificate.month_N` keys) or None when the switch is
off or the settings are not sound (empty or marker number, body or address; `verify_url` not on
`https://webgate.ec.europa.eu/`). None means no trace of "organic" anywhere. With it: the block `partials/certificate_block.html`
(`id="certificato"`, in About after `about.what`, with the sentence `organic` of `pages/about.toml`, gated in `content.GATED`),
one line in the home and a footer link (both to `/chi-siamo#certificato`), `hasCertification` on the Organization JSON-LD
(`jsonld._certification`) and one line in `llms.txt`. Not on wine sheets or the oil page. The QR code is a file we generate:
`python scripts/qr.py` writes `app/static/img/<qr>` from `verify_url` (own encoder, no library, no service; byte mode, level M);
it encodes the operator's page in the European register, which stays valid at renewal, so the QR does not change when the
numbers do. At renewal Fabio edits the dates and number in `[certificate]`. Run `scripts/qr.py` again only if `verify_url` `regulation` is the bare number ("2018/848"); the locale key `certificate.regulation` writes "Reg. (UE)" or "Reg. (EU)".
changes (`tests/test_qr.py` fails on a stale file). Legal name of the holder: `holder` / `holder_address`. Tests:
`tests/test_certificate.py`, `tests/test_qr.py`, `tests/test_pages.py`.

## Photos and pre-launch check
`python scripts/photos.py <source.jpg> <name> [folder]` writes `app/static/img/<folder>/<name>.jpg` and, only if the source is wider than 600 px, `<name>-600.jpg` (1200 only for sources wider than 1200: never an enlargement; resizing with `sips`, macOS). Originals stay out of git. `photos.srcset(name)` (template global `srcset`) builds the `srcset` from the files on disk, empty without the variant; the `<img>` keeps `alt`, `width` and `height`. `python scripts/check_content.py` lists the placeholders left per language and file (hidden wines and switched-off page keys do not count), exits 1 if any is left or the validator fails, checks that `export_email` is `export.sibio@gmail.com` (the old `export@si-bio.it` must not appear) and prints a WARNING when the organic certificate expires in 60 days or less (no effect on the exit code). `llms.txt` lists the four programme items (`buyers_includes`) under the visits link. Tests: `tests/test_photos.py`, `tests/test_check_content.py`, `tests/test_visits.py`.
