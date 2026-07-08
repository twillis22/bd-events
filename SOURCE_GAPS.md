# Source gaps and validation notes

_Last updated: 2026-07-07 from uploaded NorCal and SoCal source lists._

## Validation from first source-ingestion PR

After PR #14 merged and the site regenerated, the generated page showed:

- 81 upcoming events
- 10 active sources
- 24 new this week
- Updated 2026-07-08 00:24 UTC

The prior page had 9 active sources, so only one of the newly added source families appeared in the generated output. `I2SL San Diego` is present in the generated docs/ICS. `San Francisco Business Times`, `Silicon Valley Business Journal`, and `I2SL NorCal` were registered but did not appear as active sources in the generated output.

Follow-up in this PR:

- Business Journal scraper switched to listing-page parsing because the listing page exposes event date/title directly, while detail URLs are inconsistent.
- ISPE Conferences added with no fallback region so only in-market locations survive normal geographic classification.

## Added / tracked

### NorCal / Bay Area / Sacramento

- AIA San Francisco
- CoreNet NorCal
- DBIA national/conferences
- ULI national — scraper exists, but access remains unreliable from GitHub Actions
- ULI San Francisco — scraper exists, but access remains unreliable from GitHub Actions
- IIDA Northern California
- CSHE
- CMAA NorCal
- Lean Construction Institute
- Bisnow Events
- SPIRE Stanford
- NAIOP Silicon Valley
- NAIOP SF Bay Area
- BOMA San Francisco
- San Francisco Business Times
- Silicon Valley Business Journal
- I2SL NorCal
- ISPE Conferences

### San Diego / SoCal with San Diego filter

- IIDA SoCal, with LA/OC filtered out by geography
- San Diego BIA
- BOMA San Diego
- I2SL San Diego
- Bisnow Events, only if events classify into San Diego / kept markets
- Lean Construction Institute, only if events classify into San Diego / kept markets
- ISPE Conferences, only if events classify into San Diego / kept markets

## Remaining San Diego source-discovery targets

These are not yet added because the uploaded SoCal file listed source names but did not include stable event URLs except Bisnow.

Need exact event URLs and scraper validation:

- San Diego ISPE chapter-specific events, if separate from ISPE conferences
- San Diego NAIOP
- San Diego ULI, if access can avoid the existing ULI Cloudflare problem
- San Diego DBIA
- San Diego CREW
- San Diego SMPS
- San Diego CMAA
- San Diego NAWIC
- SD Construction Network
- CoreNet SoCal, only if San Diego events can be isolated cleanly from LA/OC

## Do not add yet

- AIA Silicon Valley supplied URL: currently shows no dated events.
- CoreNet global summits/conferences: broad national/global source; current CoreNet NorCal scraper is more useful.
- SCUP: broad national higher-ed/facilities source; add only if California market events can be isolated cleanly.

## Next recommended PR after this one

1. Add event-type filters for BD scanning.
2. Fix RSS/date quality for noisy feeds, especially Bisnow.
3. Revisit ULI through alternate access paths or source substitutes.
