# BD Events Aggregator (v2)

Auto-updating events feed pulling AEC industry events from associations across the Bay Area and San Diego. Outputs a single `.ics` calendar (subscribable in Outlook) and a bookmarkable web page, both updated daily.

## What's new in v2

- **Three new sources** via headless browser: ULI national, IIDA Northern California, CMAA NorCal
- **Playwright integration** — handles JS-rendered sites that v1 couldn't crack
- **Smarter filtering** — ULI's globally published events are filtered down to US-relevant ones
- **Total source count: 12** (was 9 in v1)

## Architecture

Every day at 6 AM Pacific, GitHub Actions runs `main.py`, which:

1. Runs each static scraper (RSS, iCal, simple HTML) — fast and cheap.
2. Launches a single headless Chromium browser, runs the JS-based scrapers in that shared session, then closes it.
3. Deduplicates events by title + date + source.
4. Filters out anything older than yesterday or more than a year out.
5. Writes `docs/events.ics` and `docs/index.html`.
6. Commits both files back to the repo. GitHub Pages serves the `docs/` folder live.

---

## One-time deployment (~15 min)

You need a free GitHub account.

### 1. Create the repo

1. On github.com, click **New repository**.
2. Name it `bd-events`.
3. Set it to **Public** (required for free Pages and unlimited Actions).
4. Don't initialize with a README.
5. Click **Create repository**.

### 2. Push this folder

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/bd-events.git
git push -u origin main
```

### 3. Enable GitHub Pages

1. **Settings → Pages**.
2. **Source:** Deploy from a branch. **Branch:** `main`. **Folder:** `/docs`. Save.

### 4. Trigger the first run

1. **Actions** tab → **Update BD Events** → **Run workflow**.
2. Wait ~3 minutes (longer than v1 — Playwright takes ~90 seconds to install browsers on first run, then is cached).

### 5. Subscribe in Outlook

iCal URL: `https://YOUR-USERNAME.github.io/bd-events/events.ics`

In Outlook web: **Add calendar → Subscribe from web** → paste URL.

### 6. Bookmark the page

`https://YOUR-USERNAME.github.io/bd-events/`

---

## Upgrading from v1 to v2

If you already have v1 deployed, just commit the new files:

```bash
# In your local clone:
git pull
# Replace files with v2 versions, then:
git add scrapers/browser.py scrapers/uli_national.py scrapers/iida_norcal.py scrapers/cmaa_norcal.py
git add aggregate.py requirements.txt .github/workflows/update.yml
git commit -m "v2: add Playwright + 3 new sources"
git push
```

The next scheduled run will pick up the changes. Or trigger manually from the Actions tab.

---

## Source coverage

| Status | Source | Method | Region |
|---|---|---|---|
| ✅ | AIA San Francisco | HTML + per-event iCal | NorCal |
| ✅ | NAIOP Silicon Valley | iCal feed | NorCal |
| ✅ | Lean Construction Institute | HTML scrape | Both |
| ✅ | CSHE | HTML scrape | NorCal |
| ✅ | SPIRE Stanford | HTML scrape | NorCal |
| ✅ | DBIA (national) | RSS | Both |
| ✅ | Bisnow Events | RSS | Both |
| ✅ | IIDA SoCal | RSS (events feed) | SoCal |
| ✅ | San Diego BIA | RSS | SoCal |
| ✅ **NEW** | ULI (national) | Browser scrape | Both |
| ✅ **NEW** | IIDA Northern California | Browser scrape | NorCal |
| ✅ **NEW** | CMAA NorCal | Browser scrape | NorCal |
| ⚠️  | AIA Silicon Valley | WooCommerce listing has no dates; needs per-product visit + content parse |
| ⚠️  | ULI SF | Cloudflare-protected — requires paid bypass service |
| ⚠️  | bizjournals (SF/SJ) | Cloudflare + paywall |
| ⚠️  | SD ULI, SD SMPS, SD CMAA, SD NAIOP | Cloudflare-protected |
| ⚠️  | SD CREW, SD NAWIC | Squarespace, no master feed |

For ⚠️ sources, the KTN newsletter approach in BD-Events-Tracker remains the fallback.

---

## Adding a new source

### If the site has an RSS or iCal feed

Add a class to `scrapers/feeds.py`:

```python
class MyNewSource(RSSAdapter):
    name = "My New Source"
    region = "NorCal"
    source_url = "https://example.com/events"
    feed_url = "https://example.com/feed/"
```

Or for iCal:

```python
class MyNewSource(ICalAdapter):
    name = "My New Source"
    region = "SoCal"
    source_url = "https://example.com/events"
    feed_url = "webcal://example.com/calendar.ics"
```

### If the site has clean HTML (no JS)

Subclass `BaseScraper` in a new file, implement `fetch()` returning a list of `Event` objects. See `scrapers/aia_sf.py` or `scrapers/lean_construction.py` for examples.

### If the site requires JavaScript rendering

Subclass both `BrowserScraper` and `BaseScraper`, implement `async fetch_with_browser(session)`. See `scrapers/uli_national.py` or `scrapers/cmaa_norcal.py`.

In any case: register the new class in `aggregate.py` by importing it and adding it to `ALL_SCRAPERS`.

---

## Project structure

```
bd-events/
├── main.py                  # entrypoint
├── aggregate.py             # scraper orchestration (handles sync + async)
├── generate_ics.py          # writes events.ics
├── generate_html.py         # writes index.html
├── requirements.txt
├── scrapers/
│   ├── base.py              # Event dataclass + BaseScraper
│   ├── http.py              # shared requests helper
│   ├── browser.py           # NEW — Playwright session manager
│   ├── rss_adapter.py       # generic RSS reader
│   ├── ical_adapter.py      # generic iCal reader
│   ├── feeds.py             # all feed-based source configs
│   ├── aia_sf.py            # static HTML scraper
│   ├── lean_construction.py # static HTML scraper
│   ├── spire_stanford.py    # static HTML scraper
│   ├── cshe.py              # static HTML scraper
│   ├── uli_national.py      # NEW — browser scraper
│   ├── iida_norcal.py       # NEW — browser scraper
│   └── cmaa_norcal.py       # NEW — browser scraper
├── docs/                    # GitHub Pages output (auto-generated)
│   ├── events.ics
│   └── index.html
└── .github/workflows/
    └── update.yml           # daily cron + Playwright install
```

---

## Local testing

```bash
pip install -r requirements.txt
python -m playwright install chromium
python main.py
open docs/index.html
```

---

## Maintenance

When a site redesigns and a scraper breaks (~2-3 times/year):

1. The GitHub Action will fail — you'll get an email.
2. The error log shows which scraper raised. The pipeline keeps running for everything else — one broken scraper doesn't take everything down.
3. Open the source page in a browser, inspect the new HTML structure, update the matching scraper file, push the fix.

Browser scrapers are slightly more fragile than static ones because they depend on JavaScript rendering timing. If a browser scraper starts returning zero events, the first thing to check is whether its `wait_for_selector` selector still exists on the page.
