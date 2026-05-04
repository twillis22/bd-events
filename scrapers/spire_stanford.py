"""SPIRE Stanford scraper.

Each event is in .inspire-events-widget-post with:
  - h4.inspire-events-widget-title > a       (title + URL)
  - .inspire-events-widget-meta .nie-dates   (date text like 'Feb 26, 2026 12:00PM—1:00PM')
"""
import re
from datetime import datetime, timezone
from typing import List, Optional
from dateutil import parser as dateparser
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from .http import get


class SPIREStanfordScraper(BaseScraper):
    name = "SPIRE Stanford"
    region = "NorCal"
    source_url = "https://spirestanford.org/inspire_events/"

    DATE_RE = re.compile(r"([A-Z][a-z]+\s+\d{1,2},\s*\d{4})")

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        events: List[Event] = []
        for post in soup.select(".inspire-events-widget-post"):
            link = post.select_one("h4.inspire-events-widget-title a, .inspire-events-widget-title a")
            date_block = post.select_one(".inspire-events-widget-meta .nie-dates, .inspire-events-widget-meta")
            if not link or not date_block:
                continue
            title = link.get_text(strip=True)
            url = link.get("href", self.source_url)
            dt = self._parse_date(date_block.get_text(" ", strip=True))
            if not title or not dt:
                continue
            events.append(Event(title=title, start=dt, url=url))
        return events

    def _parse_date(self, text: str) -> Optional[datetime]:
        m = self.DATE_RE.search(text)
        if not m:
            return None
        try:
            dt = dateparser.parse(m.group(1))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
