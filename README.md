# BD Events Aggregator (v3)

Auto-updating events feed pulling AEC industry events from associations across the Bay Area and San Diego. Outputs:

- A subscribable `.ics` calendar (Outlook, Apple Calendar, Google Calendar)
- A bookmarkable web page with **filtering UI** and **"new this week" highlights**

All updated automatically every day.

## What's new in v3

- **Filter UI on the bookmark page** — search box, region pills (NorCal/SoCal/Other), source pills, and "✨ New only" toggle. All client-side, instant.
- **"New this week" highlights** — events first seen in the last 7 days get an amber border, a pulsing NEW badge, and show in the new-only filter.
- **Persistent state** via `data/seen.json` — tracks first-seen date per event so "new" actually means new.

## What's new in v2 (still applies)

- **Browser sources** via headless Chromium: ULI national, ULI San Francisco, IIDA Northern California, CMAA NorCal
- **Playwright integration** for JS-rendered sites
- **Smart international filtering** for ULI's globally-published events

## Architecture

Every day at 6 AM Pacific, GitHub Actions runs `main.py`, which:

1. Runs each static scraper (RSS, iCal, simple HTML) — fast and cheap.
2. Launches a single headless Chromium browser, runs the JS-based scrapers in that shared session, then closes it.
3. Deduplicates events by title + date + source.
4. Filters out anything older than yesterday or more than a year out.
5. Writes `docs/events.ics` and `docs/index.html`.
6. Commits both files back to the repo. GitHub Pages serves the `docs/` folder live.

## Local testing

```bash
pip install -r requirements.txt
python -m playwright install chromium
python main.py
open docs/index.html
```

## Project structure

```
bd-events/
├── main.py                  # entrypoint
├── aggregate.py             # scraper orchestration (sync + async)
├── generate_ics.py          # writes events.ics
├── generate_html.py         # writes index.html with filter UI
├── seen_tracker.py          # persistent first-seen tracking
├── requirements.txt
├── scrapers/
│   ├── base.py              # Event dataclass + BaseScraper
│   ├── http.py              # shared requests helper
│   ├── browser.py           # Playwright session manager
│   ├── rss_adapter.py       # generic RSS reader
│   ├── ical_adapter.py      # generic iCal reader
│   ├── feeds.py             # all feed-based source configs
│   ├── aia_sf.py            # static HTML scraper
│   ├── lean_construction.py # static HTML scraper
│   ├── spire_stanford.py    # static HTML scraper
│   ├── cshe.py              # static HTML scraper
│   ├── uli_national.py      # browser scraper
│   ├── uli_sf.py            # browser scraper
│   ├── iida_norcal.py       # browser scraper
│   └── cmaa_norcal.py       # browser scraper
├── data/seen.json           # event UID -> first-seen date
├── docs/                    # GitHub Pages output (auto-generated)
└── .github/workflows/update.yml

```

## Adding a new source

- **RSS/iCal feed** → add a config class to `scrapers/feeds.py`.
- **Static HTML** → subclass `BaseScraper` in its own file, implement `fetch()`.
- **JS-rendered** → subclass `BrowserScraper` + `BaseScraper`, implement `async fetch_with_browser(session)`.

In all cases, register the class in `aggregate.py` → `ALL_SCRAPERS`.

---

See `CLAUDE.md` for full context and `NEXT_STEPS.md` for the current work plan.
