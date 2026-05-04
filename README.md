# BD Events Aggregator

Auto-updating events feed pulling AEC industry events from associations across the Bay Area and San Diego. Outputs a single `.ics` calendar (subscribable in Outlook) and a bookmarkable web page, both updated daily.

## What this does

Every day at 6 AM Pacific, GitHub Actions runs `main.py`, which:

1. Runs every scraper in the `scrapers/` folder against its source site.
2. Deduplicates events by title + date + source.
3. Filters out anything older than yesterday or more than a year out.
4. Writes `docs/events.ics` (the subscribable calendar feed).
5. Writes `docs/index.html` (the bookmarkable web page).
6. Commits both files back to the repo. GitHub Pages serves the `docs/` folder live.

The result: one URL you subscribe to in Outlook, one URL you bookmark in your browser. Both update on their own.

---

## One-time deployment (~15 min)

You need a free GitHub account.

### 1. Create the repo

1. On github.com, click **New repository**.
2. Name it `bd-events` (or anything you want).
3. Set it to **Public** (required for free GitHub Pages and unlimited Actions minutes).
4. Don't initialize with a README — we already have one.
5. Click **Create repository**.

### 2. Push this folder to the repo

Open Terminal, navigate to this folder, and run:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/bd-events.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username.

### 3. Enable GitHub Pages

1. In the repo on github.com, go to **Settings → Pages**.
2. Under **Source**, choose **Deploy from a branch**.
3. Branch: `main`. Folder: `/docs`. Click **Save**.
4. Wait ~1 minute, then your page is live at:
   `https://YOUR-USERNAME.github.io/bd-events/`

### 4. Trigger the first run

1. Go to the **Actions** tab in the repo.
2. Click **Update BD Events** in the left sidebar.
3. Click **Run workflow** → **Run workflow**.
4. Wait ~2 minutes. When it's done, your live page has fresh events.

### 5. Subscribe in Outlook

1. The .ics URL is: `https://YOUR-USERNAME.github.io/bd-events/events.ics`
2. In Outlook web: left sidebar **Add calendar** → **Subscribe from web** → paste the URL.
3. Name it "BD Events", pick a color, click **Import**.
4. Outlook will refresh from the URL automatically (typically every few hours).

### 6. Bookmark the web page

`https://YOUR-USERNAME.github.io/bd-events/` — bookmark it.

That's it. Once a day, GitHub Actions runs the aggregator, the page and .ics update, your Outlook calendar refreshes.

---

## Source coverage

| Status | Source | Method |
|---|---|---|
| ✅ | AIA San Francisco | HTML + per-event iCal endpoints |
| ✅ | NAIOP Silicon Valley | iCal feed |
| ✅ | Lean Construction Institute | HTML scrape (month grid) |
| ✅ | CSHE | HTML scrape |
| ✅ | SPIRE Stanford | HTML scrape |
| ✅ | DBIA (national) | RSS |
| ✅ | Bisnow Events | RSS |
| ✅ | IIDA SoCal | RSS (events feed) |
| ✅ | San Diego BIA | RSS |
| ⚠️  | AIA Silicon Valley | Events sold as WooCommerce products without dates in the listing — would need per-product scraping |
| ⚠️  | ULI national, ULI SF | JS-rendered events list — needs headless browser (v2) |
| ⚠️  | CMAA NorCal, IIDA NorCal | JS-rendered (Wix / faceted search) |
| ⚠️  | SF Business Times, SV Business Journal | Cloudflare-protected, paywalled |
| ⚠️  | SD ULI, SD SMPS, SD CMAA, SD NAIOP | Cloudflare-protected |
| ⚠️  | SD CREW, SD NAWIC | Squarespace, no master feed |

Sources marked ⚠️ are still useful via the KTN newsletter approach in the BD-Events-Tracker spreadsheet — that flow remains the right tool for those.

---

## Adding a new source

1. Create a new file in `scrapers/`, e.g. `scrapers/my_new_source.py`.
2. Subclass `BaseScraper` (custom HTML scrape) or `RSSAdapter` / `ICalAdapter` (feed).
3. Implement `fetch()` to return a list of `Event` objects.
4. Register it in `aggregate.py` by importing the class and adding it to the `SCRAPERS` list.
5. Push to GitHub. The next scheduled run picks it up automatically.

See `scrapers/aia_sf.py` for a complete HTML scraper example, or `scrapers/feeds.py` for the simpler feed-based pattern.

---

## Project structure

```
bd-events/
├── main.py                  # entrypoint
├── aggregate.py             # registers scrapers, dedups, sorts
├── generate_ics.py          # writes events.ics
├── generate_html.py         # writes index.html
├── requirements.txt
├── scrapers/
│   ├── base.py              # Event dataclass + BaseScraper
│   ├── http.py              # shared requests helper
│   ├── rss_adapter.py       # generic RSS reader
│   ├── ical_adapter.py      # generic iCal reader
│   ├── feeds.py             # all feed-based source configs
│   ├── aia_sf.py            # custom scraper
│   ├── lean_construction.py # custom scraper
│   ├── spire_stanford.py    # custom scraper
│   └── cshe.py              # custom scraper
├── docs/                    # GitHub Pages output (auto-generated)
│   ├── events.ics
│   └── index.html
└── .github/workflows/
    └── update.yml           # daily cron
```

---

## Local testing

```bash
pip install -r requirements.txt
python main.py
open docs/index.html
```

Outputs land in `docs/`.

---

## Maintenance

When a site redesigns and a scraper breaks (typical: ~2-3 times/year):

1. The GitHub Action will fail — you'll get an email from GitHub.
2. The error log shows which scraper raised. The pipeline keeps running and other sources still update — one broken scraper doesn't take everything down.
3. Open the source page in a browser, find the new HTML structure, update the matching scraper file, push the fix.

Each scraper is ~30-60 lines of code. Most fixes are 5-10 minutes of CSS-selector adjustment.
