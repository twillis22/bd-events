"""Base classes — Event dataclass and BaseScraper interface."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import hashlib
import re


@dataclass
class Event:
    """Normalized event representation across all sources."""
    title: str
    start: datetime               # timezone-aware
    end: Optional[datetime] = None
    url: str = ""
    location: str = ""
    description: str = ""
    source: str = ""              # human label, e.g. "AIA San Francisco"
    source_region: str = ""       # source's default bucket, fallback for classify()
    region: str = ""              # per-event submarket, set by regions.classify()
    first_seen: str = ""          # ISO date string set by SeenTracker
    is_new: bool = False          # set by SeenTracker (true if first_seen within N days)

    @property
    def uid(self) -> str:
        """Stable unique ID for dedup + iCal UID."""
        key = f"{self.source}|{self._normalize(self.title)}|{self.start.date().isoformat()}"
        return hashlib.md5(key.encode()).hexdigest() + "@bd-events"

    @staticmethod
    def _normalize(s: str) -> str:
        """Lowercase + strip punctuation for fuzzy comparison."""
        return re.sub(r'[^a-z0-9]+', '', (s or '').lower())


class BaseScraper:
    """One subclass per source. Implement `fetch()` returning a list of Events."""
    name: str = ""        # human label
    region: str = ""      # default submarket when classify() finds no city ("" = drop unmatched)
    source_url: str = ""  # the page being scraped (for fallback links)

    def fetch(self) -> List[Event]:
        raise NotImplementedError

    def safe_fetch(self) -> List[Event]:
        """Wrapper that catches errors so one broken scraper doesn't take down the run."""
        try:
            events = self.fetch() or []
            # tag every event with source metadata
            for e in events:
                if not e.source:
                    e.source = self.name
                if not e.source_region:
                    e.source_region = self.region
            return events
        except Exception as exc:
            print(f"  [error] {self.name}: {type(exc).__name__}: {exc}")
            return []
