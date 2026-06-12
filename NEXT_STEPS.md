# NEXT_STEPS.md — Work plan for this Claude Code session

This is the concrete to-do list. Read `CLAUDE.md` first for architecture and
conventions. Tackle these in order; each is independently shippable.

The north star (Ty's words): **"an up-to-date site that lists all industry events
related to construction, real estate, networking, etc. in the Bay Area, Sacramento,
and San Diego."** Bay Area, Sacramento, and San Diego are IN. Los Angeles / the rest
of SoCal is OUT.

---

## TASK 1 — Replace coarse regions with geographic submarkets ⭐ (biggest change)

> **STATUS: DONE** — `scrapers/regions.py` + `Event.region` + classification in
> `aggregate.py`; pills/tints render from `e.region`. East Bay kept as its own
> bucket (confirmed with Ty 2026-06-10).

**Problem:** Region is assigned per *source* today (`NorCal` / `SoCal` / `Other`), so
every AIA SF event is "NorCal" and every Bisnow event is "Both/Other" regardless of
where the event actually is. Ty wants to filter by **submarket**, and a single source
spans several submarkets.

**Target filter buckets** (Ty's priority four, plus catch-alls so nothing is lost):

1. **San Francisco**
2. **Silicon Valley** (San Jose, Santa Clara, Mountain View, Palo Alto, Sunnyvale, Cupertino, Menlo Park, Redwood City, San Mateo, Fremont, Milpitas)
3. **Sacramento** (Sacramento, Roseville, Folsom, Davis, Elk Grove, Rancho Cordova)
4. **San Diego** (San Diego, La Jolla, Carlsbad, Chula Vista, Oceanside, Escondido)
5. **East Bay** (Oakland, Berkeley, Walnut Creek, Emeryville, Pleasanton, Dublin) — keep; it's Bay Area
6. **Bay Area** — catch-all for Bay events with no identifiable city (North Bay, Peninsula-unspecified, "Bay Area", online-but-local, etc.)
7. **Online / Virtual** — Zoom/webinar events with no physical location
8. *(drop entirely)* Los Angeles, Orange County, Inland Empire, and any non-CA US city

> Confirm this bucket list with Ty before finalizing the pill set — he named SF /
> Silicon Valley / Sacramento / San Diego explicitly; East Bay + Bay Area catch-all
> are my suggestion so nothing gets silently dropped. If he wants only his four, fold
> East Bay into "Bay Area".

**Implementation plan:**

1. Create `scrapers/regions.py` with a `classify(location: str, title: str = "",
   source_default: str = "") -> str | None` function:
   - City/keyword → submarket lookup tables (case-insensitive, word-boundary matched).
   - Returns the submarket string, or `None` to signal **drop this event** (LA, other
     states, etc.).
   - Generalize the California city list already living in
     `scrapers/lean_construction.py` — move that logic here and have LCI import it.
   - When nothing matches but the source is clearly Bay Area, fall back to the source's
     default region rather than dropping.
2. Add a `region: str = ""` field to the `Event` dataclass (distinct from the existing
   `source_region`, which becomes the fallback default).
3. In `aggregate.py`, after collecting events, run each through `classify(...)`:
   - Set `e.region` to the result.
   - **Drop** events where `classify` returns `None` (this is how LA gets excluded).
4. Update `generate_html.py`:
   - `REGION_COLORS` → add entries for the new buckets (pick distinct, muted colors
     consistent with the existing palette; San Diego and Sacramento need their own).
   - Region pills render from `e.region` (event-level) instead of `source_region`.
   - The card `data-region` attribute + `--tint` use `e.region`.
5. Update `generate_ics.py` only if you want region in the event description (optional).

**Acceptance:** Region pills show SF / Silicon Valley / East Bay / Sacramento / San Diego /
Bay Area / Online with correct counts; an LA event from any feed does not appear; an
SF event and a San Jose event from the *same* source land in different buckets.

---

## TASK 2 — Keep San Diego, drop Los Angeles, in the SoCal feeds

> **STATUS: DONE** — IIDA SoCal and LCI now have no fallback region, so only
> events that classify into a kept bucket survive. Verify counts after the next
> Action run (live sites are unreachable from the dev sandbox).

This mostly falls out of Task 1 (the classifier drops LA). But also:

- `scrapers/feeds.py` → `IIDASoCalScraper` pulls the IIDA SoCal feed, which covers both
  LA and San Diego chapters. After Task 1, LA events auto-drop. Verify by running it and
  confirming only San Diego-area events survive.
- `LeanConstructionScraper` currently keeps ANY California event (incl. LA). After Task 1
  it should keep only events that classify into a kept bucket.

**Acceptance:** No Los Angeles / Orange County events anywhere in the output; San Diego
events still present.

---

## TASK 3 — Expand ULI coverage

> **STATUS: BLOCKED by Cloudflare (2026-06-10).** ULI national and ULI SF both return
> **0 events** and have since ~May 8. Diagnostics added to both scrapers confirm
> `*.uli.org` serves a **Cloudflare JS challenge** ("Just a moment...", HTTP 403,
> `noindex,nofollow`) to the GitHub Actions runner. The block is the **datacenter IP**,
> not the page markup — `sf.uli.org/events/` loads fine in a normal browser on a
> residential connection. So fixing selectors won't help, and adding more ULI district
> councils (SD–Tijuana, Sacramento) is pointless until the access path is solved.
>
> Options when we revisit (cleanest first):
> 1. **Run the scrape from a residential IP** (Ty's Mac on a schedule, or a small
>    always-on box) instead of GitHub Actions. Most reliable; stays free; loses pure-cloud.
> 2. **Alternate non-Cloudflare sources** that re-list ULI events (A.CRE Events, SV@Home,
>    etc.) — partial coverage but works from Actions.
> 3. **Member-assisted ingest** — Ty downloads the per-event `.ics` from his browser (or
>    forwards the ULI newsletter) into a watched path the pipeline reads. Unbreakable.
> 4. *(avoid)* Stealth tooling / Cloudflare solvers on Actions — fragile from datacenter
>    IPs, breaks silently, and paid solvers break the "free" constraint.
>
> The ULI scrapers stay registered (they fail gracefully and self-recover if the block
> ever lifts); the diagnostics print current status each run.

ULI is a priority for Ty. Currently we scrape ULI national (filtered) and ULI SF. Add the
other California district councils so we catch Sacramento + San Diego ULI events:

- **ULI San Diego–Tijuana** — district council site (find the events URL; likely
  `sandiego-tijuana.uli.org/events/` or similar, same WordPress `c-events-list__*`
  markup as SF/national).
- **ULI Sacramento** — (`sacramento.uli.org/events/` or similar).

Both can almost certainly reuse the `uli_sf.py` scraper pattern verbatim — just a new
subclass with a different `name`, `region`, and `source_url`. If the markup differs,
adapt. Set their `source_region` defaults appropriately (San Diego / Sacramento), though
Task 1's classifier will refine per-event.

Also reconsider `ULINationalScraper`: today it keeps all US events. For Ty's use case it
should probably keep only events that classify into a kept submarket (run national events
through the Task 1 classifier too, which it will get for free if classification happens in
`aggregate.py`).

**Acceptance:** ULI SD and ULI Sacramento events appear; ULI national still contributes
its big CA events (e.g. Spring/Fall meetings when in-region) but no longer dumps
irrelevant national/international ones.

---

## TASK 4 — Fix known bugs / data-quality issues

> **STATUS: items 1, 2(b), 4 DONE** — stale `Both` removed; Bisnow gated by the
> classifier (no fallback region); iCal decoding hardened + `\ufffd` → `–`.
> Item 3 (RSS publish-date-as-event-date) still open.

1. **Stale `region = "Both"`** on `BisnowScraper` in `scrapers/feeds.py`. After Task 1
   this attribute becomes just a fallback default; set it to something sane (`"Bay Area"`)
   or remove reliance on it.
2. **Bisnow noise.** The Bisnow RSS is a national news feed, not an events feed. Options,
   in order of preference: (a) point at a Bay Area-specific Bisnow events URL if one
   exists; (b) tighten `require_event_keyword` + run through the Task 1 classifier so only
   in-market *events* survive; (c) if it stays mostly noise, drop it and tell Ty why.
3. **RSS publish-date-as-event-date.** Document this clearly in the UI or, better, try to
   parse a real event date from the item summary where present. At minimum, don't let a
   months-old "event" with a recent publish date show as upcoming.
4. **AIA SF mojibake** (`�` in some titles — a mis-decoded en-dash). Harden the encoding:
   ensure the iCal bytes are decoded as UTF-8, and/or normalize/replace the bad char.

**Acceptance:** No `Both` region; Bisnow either contributes real in-market events or is
removed with a note; no `�` characters in titles.

---

## TASK 5 — Broaden source coverage (the "list ALL events" goal)

> **STATUS (2026-06-12): partial.** Added and live-validated via the "Probe
> Sources" workflow: **BOMA San Diego** (JSON-LD), **BOMA San Francisco**
> (curated date list), **NAIOP SF Bay Area** (GrowthZone microdata).
> Blocked by Cloudflare (same as ULI): SMPS SF + SD, BOMA Sacramento.
> Dead/unreachable: DBIA Western Pacific, BOMA Oakland/East Bay (hard 403).
> Needs a browser or API work (deferred): CREW Network chapters (client-side
> Next.js), CREW San Diego (Squarespace page blocks), USGBC-CA (AJAX grid),
> AIA East Bay (calendar not in static HTML), AIA Central Valley (Wix;
> Eventbrite page has no structured data and ~1 event).

To genuinely be the one-stop list, add more associations across the three markets.
Prioritized; do the easy structured ones first. For each: probe the site, pick the right
scraper flavor (prefer iCal feed > RSS > static HTML > Playwright), add the file, register
in `aggregate.py`, and verify it returns real dated events.

**High value, likely easy (feeds / The Events Calendar plugin):**
- NAIOP San Francisco Bay Area chapter (separate from NAIOP Silicon Valley)
- AIA East Bay, AIA Central Valley (Sacramento)
- DBIA Western Pacific Region (CA chapter; more local than DBIA national)
- USGBC California / community events
- BOMA — San Francisco, Oakland/East Bay, Sacramento, San Diego chapters
- SMPS (marketing pros) — SF Bay Area + San Diego chapters
- CREW (Commercial Real Estate Women) — SF, East Bay, Sacramento, San Diego

**Medium:**
- AGC of California / ABC NorCal (general-contractor associations — events + golf/networking)
- ASCE (civil engineers) regional sections
- The Registry SF events calendar
- AIA Silicon Valley — KNOWN HARD: their events are WooCommerce products with no dates in
  the listing; would need per-product page visits + content parsing. Probably skip unless
  Ty wants it badly.

> Don't add a source unless it actually returns clean, dated, in-market events. A flaky
> scraper that emits garbage is worse than an absent one. Add 4–6 solid ones rather than
> 15 shaky ones.

**Acceptance:** Source pill count grows meaningfully (target ~18–22 reliable sources),
all three markets well represented.

---

## TASK 6 — Validate + ship

1. `python main.py` locally; confirm event count is reasonable and no scraper errors.
2. Open `docs/index.html`; click each region pill; confirm counts and that LA is gone.
3. Spot-check 5–10 events against their source pages for correct date/location/link.
4. Commit in logical chunks (regions.py + Event field; then each source group; then bug
   fixes). Push. Confirm the GitHub Action goes green and Pages updates.

---

## Stretch ideas (only if time + Ty wants them)

- **Event-type facet** (Networking / Education / Conference / Social) as a second filter
  dimension, classified from the title.
- ~~**Past-events archive** page or a "recently passed" collapsed section.~~ DONE
  (2026-06-12): `data/archive.json` + collapsed "Recently passed" section, 14-day window.
- **De-dupe across sources** when two associations co-host the same event (currently dedup
  is per-source by UID; cross-source identical events show twice).
- **Bootstrap mode** for `seen.json` so a fresh deploy doesn't flag literally everything as
  "new" on day one.
