"""Aggregator — runs every registered scraper, dedupes, filters, sorts.

Two scraper flavors:
  - Static (BaseScraper subclasses): synchronous .fetch() that uses requests.
  - Browser-based (BrowserScraper subclasses): async fetch_with_browser(session)
    that needs a Playwright browser. We run all of these in a single shared
    browser session per pass to avoid 4x browser startup cost.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Type

from scrapers.base import BaseScraper, Event
from scrapers.browser import BrowserScraper, BrowserSession

# Static scrapers
from scrapers.aia_sf import AIASFScraper
from scrapers.spire_stanford import SPIREStanfordScraper
from scrapers.lean_construction import LeanConstructionScraper
from scrapers.cshe import CSHEScraper
from scrapers.feeds import (
    NAIOPSVScraper, IIDASoCalScraper, DBIANationalScraper,
    BisnowScraper, SDBIAScraper,
)

# Browser scrapers (v2)
from scrapers.uli_national import ULINationalScraper
from scrapers.uli_sf import ULISanFranciscoScraper
from scrapers.iida_norcal import IIDANorCalScraper
from scrapers.cmaa_norcal import CMAANorCalScraper

ALL_SCRAPERS: List[Type[BaseScraper]] = [
    # Static / feed scrapers
    AIASFScraper,
    SPIREStanfordScraper,
    LeanConstructionScraper,
    CSHEScraper,
    NAIOPSVScraper,
    IIDASoCalScraper,
    DBIANationalScraper,
    BisnowScraper,
    SDBIAScraper,
    # Browser scrapers
    ULINationalScraper,
    ULISanFranciscoScraper,
    IIDANorCalScraper,
    CMAANorCalScraper,
]


def collect_events(lookback_days: int = 1, lookahead_days: int = 365) -> List[Event]:
    """Run every scraper, dedupe, filter, sort chronologically."""
    now = datetime.now(timezone.utc)
    earliest = now - timedelta(days=lookback_days)
    latest = now + timedelta(days=lookahead_days)

    static_classes  = [c for c in ALL_SCRAPERS if not issubclass(c, BrowserScraper)]
    browser_classes = [c for c in ALL_SCRAPERS if     issubclass(c, BrowserScraper)]

    print(f"\nRunning {len(static_classes)} static + {len(browser_classes)} browser scrapers...")
    all_events: List[Event] = []

    # 1) Static scrapers (cheap, sequential)
    for cls in static_classes:
        scraper = cls()
        events = scraper.safe_fetch()
        kept = [e for e in events if earliest <= e.start <= latest]
        suffix = f" ({len(events) - len(kept)} outside window)" if len(kept) < len(events) else ""
        print(f"  {scraper.name}: {len(kept)} events{suffix}")
        all_events.extend(kept)

    # 2) Browser scrapers (one shared Playwright session)
    if browser_classes:
        print("  Launching headless browser for JS-rendered sites...")
        browser_events = asyncio.run(_run_browser_scrapers(browser_classes))
        for scraper_name, events in browser_events:
            kept = [e for e in events if earliest <= e.start <= latest]
            suffix = f" ({len(events) - len(kept)} outside window)" if len(kept) < len(events) else ""
            print(f"  {scraper_name}: {len(kept)} events{suffix}")
            all_events.extend(kept)

    # 3) Dedupe + sort
    by_uid = {}
    for e in all_events:
        if e.uid not in by_uid:
            by_uid[e.uid] = e
    deduped = sorted(by_uid.values(), key=lambda e: e.start)
    print(f"\nTotal: {len(deduped)} unique upcoming events")
    return deduped


async def _run_browser_scrapers(classes):
    """Run each browser scraper in a shared session, collecting (name, events) pairs."""
    results = []
    async with BrowserSession() as session:
        for cls in classes:
            scraper = cls()
            try:
                events = await scraper.fetch_with_browser(session)
                # tag with source metadata
                for e in events:
                    if not e.source:
                        e.source = scraper.name
                    if not e.source_region:
                        e.source_region = scraper.region
                results.append((scraper.name, events))
            except Exception as exc:
                print(f"  [error] {scraper.name}: {type(exc).__name__}: {exc}")
                results.append((scraper.name, []))
    return results
