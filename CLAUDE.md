# CLAUDE.md — BD Events Aggregator

> This file is auto-loaded by Claude Code as project context. It explains what this
> repo is, how it's built, the conventions to follow, and the known gotchas. Read
> `NEXT_STEPS.md` for the specific work to do in this session.

## What this is

An automated tracker of AEC / commercial-real-estate / networking industry events,
built for **Tyler ("Ty") Willis**, a Business Development executive at **Level 10
Construction** (a Bay Area general contractor). It scrapes ~12 industry-association
websites daily, normalizes the events, and publishes:

- `docs/events.ics` — a calendar feed Ty subscribes to in Outlook
- `docs/index.html` — a filterable, bookmarkable web page (the primary deliverable)

It runs entirely free: GitHub Actions runs the scrapers daily on a cron, commits the
regenerated outputs back to the repo, and GitHub Pages serves `docs/` as a website.

**The goal:** one always-current place listing every construction / real-estate /
networking event worth knowing about in the firm's markets, so Ty never has to
check a dozen association sites by hand.

## How it runs

```
GitHub Actions (daily 13:00 UTC / 06:00 PT)
  └─ python main.py
       ├─ aggregate.collect_events()      # run all scrapers, dedupe, window-filter
       │    ├─ static scrapers (requests/RSS/iCal)  → synchronous
       │    └─ browser scrapers (Playwright)        → one shared Chromium session
       ├─ SeenTracker.annotate()          # mark first_seen / is_new from data/seen.json
       ├─ generate_ics.write_ics()        # → docs/events.ics
       └─ generate_html.write_html()      # → docs/index.html
  └─ git commit docs/ + data/seen.json, push   # Pages redeploys automatically
```

## Local dev

```bash
pip install -r requirements.txt
python -m playwright install chromium      # one-time, ~90s
python main.py                             # full run, writes docs/
open docs/index.html
```

To exercise a single scraper without the whole pipeline:

```python
# Static scraper:
from scrapers.cshe import CSHEScraper
for e in CSHEScraper().fetch(): print(e.start.date(), e.title)

# Browser scraper (spins up its own one-off Chromium via the sync .fetch() wrapper):
from scrapers.cmaa_norcal import CMAANorCalScraper
for e in CMAANorCalScraper().fetch(): print(e.start.date(), e.title, "|", e.location)
```

## Architecture notes

- **`Event` dataclass** (`scrapers/base.py`) is the single normalized shape. Its
  `.uid` = md5 of `source|normalized_title|date` — used for dedup AND for the
  iCal UID AND as the key in `data/seen.json`. **Do not put region in the UID** —
  region can be re-derived without invalidating first-seen history.
- **Two scraper flavors.** Static scrapers subclass `BaseScraper` and implement
  `fetch()`. JS-rendered scrapers subclass BOTH `BrowserScraper` and `BaseScraper`
  and implement `async fetch_with_browser(session)`. The aggregator detects which
  is which by `issubclass(cls, BrowserScraper)`.
- **One broken scraper never kills the run.** `BaseScraper.safe_fetch()` and the
  browser-scraper loop both catch per-scraper exceptions and print `[error] ...`,
  then continue. Preserve this resilience in any new code.
- **`data/seen.json` is sacred state.** It records the first date each event UID was
  observed, which powers the "NEW this week" badge (7-day window via
  `SeenTracker.NEW_WINDOW_DAYS`). The GitHub Action commits it back every run. When
  changing UID composition, you WILL reset everyone's "new" status — avoid unless
  intentional, and call it out.
- **Region is assigned per-event** by `scrapers/regions.py::classify(location,
  title, source_default)` during aggregation; each scraper's `region` class attr
  is just the fallback default for events with no recognizable city.

## Design system (the HTML page)

Matches Level 10 Construction's brand (level10gc.com). Tokens live at the top of
`generate_html.py`:

- Background `#262626` (solid warm grey — NOT a gradient; Ty explicitly asked for solid)
- Text `#f6f6f6`, muted `rgba(246,246,246,0.62)`
- Brand orange `#ff671f` (accents, hover, active states, NEW badge)
- Font: **Inter** (Google Fonts). No serif fonts anywhere.
- Cards are translucent glass (`rgba(255,255,255,0.04)`), each tinted by its region color
- Bloom/glow was deliberately toned down ~50% from an earlier draft — keep it restrained

Region tint colors (`REGION_COLORS` in `generate_html.py`): these will expand as part
of the submarket work in `NEXT_STEPS.md`.

## Conventions & gotchas

- **Outreach sign-off** (not relevant to this repo's output, but project-wide): Ty
  signs as "Ty". The page never needs a signature.
- **Region buckets** are per-event geographic submarkets (San Francisco / Silicon
  Valley / East Bay / Sacramento / San Diego / Bay Area / Online), assigned by
  `scrapers/regions.py::classify()` in the aggregator. A scraper's `region` class
  attr is only the *fallback* when no city matches; `""` means drop unmatched
  events (used for national feeds). `classify` returning `None` drops the event —
  that's how LA / Orange County / out-of-state events are excluded.
- **RSS sources use publish-date as event-date** (`scrapers/rss_adapter.py`). This is
  a real weakness — an event *announced* today may actually occur months later, so its
  date is wrong. Bisnow/DBIA/SDBIA all inherit this. Treat RSS dates as approximate.
- **Bisnow RSS is noisy** — it's a national news feed, not an events feed; many items
  are out-of-market news (e.g. a NYC rent story). It needs geographic + event filtering
  or it's mostly noise.
- **AIA SF occasionally emits a mojibake character** in titles (a mis-decoded en-dash
  shows as `�`). Worth hardening the encoding handling.
- **Deployment:** historically Ty deployed via the GitHub **web UI only** (no terminal).
  Now that he's using Claude Code, you (Claude Code) can run `git` directly on his local
  clone — that's the whole point of the switch. Still: explain commits in plain language,
  and prefer small, reviewable commits with clear messages.
- **No secrets required.** This project needs no API keys or logins. (A separate
  "BD Leads Tracker" project does deal with gated portals — that is NOT this repo.)

## Collaborator preferences (Ty)

- Direct, concise, no filler ("great question", needless preamble).
- Honest scope assessment **before** building — say what won't work, not just what will.
- Show real output; he iterates on visual design 2–3 rounds after seeing it rendered.
- Wants to understand tradeoffs, not just be handed a result.
