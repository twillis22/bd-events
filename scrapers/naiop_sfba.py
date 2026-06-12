"""NAIOP San Francisco Bay Area chapter scraper.

The GrowthZone member-portal calendar renders server-side with schema.org
microdata per card:

  .gz-events-card[itemtype="http://schema.org/Event"]
    a.gz-event-card-title[itemprop=url]      title + detail link
    meta[itemprop=startDate][content]        "6/18/2026 9:00:00 AM" (local)
    meta[itemprop=endDate][content]
    [itemprop=about]                         short description

Cards carry no venue; the classifier falls back to the Bay Area default
unless the title names a city.
"""
from datetime import timezone
from typing import List

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .http import get


class NAIOPSFBAScraper(BaseScraper):
    name = "NAIOP SF Bay Area"
    region = "Bay Area"
    source_url = "https://members.naiopsfba.org/event-calendar"

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        events: List[Event] = []
        for card in soup.select('.gz-events-card[itemtype="http://schema.org/Event"]'):
            title_a = card.select_one("a.gz-event-card-title, [itemprop=name] a")
            start_meta = card.select_one("meta[itemprop=startDate]")
            if not title_a or not start_meta:
                continue
            title = title_a.get_text(" ", strip=True)
            start = self._parse(start_meta.get("content"))
            if not title or not start:
                continue
            end_meta = card.select_one("meta[itemprop=endDate]")
            about = card.select_one("[itemprop=about]")
            events.append(Event(
                title=title,
                start=start,
                end=self._parse(end_meta.get("content")) if end_meta else None,
                url=title_a.get("href", self.source_url),
                description=about.get_text(" ", strip=True)[:400] if about else "",
            ))
        return events

    @staticmethod
    def _parse(s):
        if not s:
            return None
        try:
            dt = dateparser.parse(s)
            # Local wall-clock times stored naive-as-UTC, matching the other
            # scrapers, so the page displays them unchanged.
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
