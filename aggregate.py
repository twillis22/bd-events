"""Aggregator — runs every registered scraper, dedupes, filters, sorts."""
from datetime import datetime, timedelta, timezone
from typing import List, Type

from scrapers.base import BaseScraper, Event

# All scrapers registered here. Adding a new source = appending one class.
from scrapers.aia_sf import AIASFScraper
from scrapers.spire_stanford import SPIREStanfordScraper
from scrapers.lean_construction import LeanConstructionScraper
from scrapers.cshe import CSHEScraper
from scrapers.feeds import (
    NAIOPSVScraper, IIDASoCalScraper, DBIANationalScraper,
    BisnowScraper, SDBIAScraper,
)

SCRAPERS: List[Type[BaseScraper]] = [
    AIASFScraper,
    SPIREStanfordScraper,
    LeanConstructionScraper,
    CSHEScraper,
    NAIOPSVScraper,
    IIDASoCalScraper,
    DBIANationalScraper,
    BisnowScraper,
    SDBIAScraper,
]


def collect_events(lookback_days: int = 1, lookahead_days: int = 365) -> List[Event]:
    """Run every scraper, dedupe, filter to a date window, sort chronologically."""
    now = datetime.now(timezone.utc)
    earliest = now - timedelta(days=lookback_days)
    latest = now + timedelta(days=lookahead_days)

    all_events: List[Event] = []
    print(f"\nRunning {len(SCRAPERS)} scrapers...")
    for cls in SCRAPERS:
        scraper = cls()
        events = scraper.safe_fetch()
        kept = [e for e in events if earliest <= e.start <= latest]
        dropped = len(events) - len(kept)
        suffix = f" ({dropped} outside window)" if dropped else ""
        print(f"  {scraper.name}: {len(kept)} events{suffix}")
        all_events.extend(kept)

    # Dedupe by uid
    by_uid = {}
    for e in all_events:
        if e.uid not in by_uid:
            by_uid[e.uid] = e
    deduped = list(by_uid.values())

    # Sort chronologically
    deduped.sort(key=lambda e: e.start)
    print(f"\nTotal: {len(deduped)} unique upcoming events")
    return deduped
