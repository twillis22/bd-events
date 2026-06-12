"""BOMA San Francisco scraper.

bomasf.org's events calendar is a hand-maintained Drupal page whose body is a
plain list of lines like "01.22.2026 | BOMA Committee Open House". No times,
locations, or per-event links — but the dates and titles are reliable. Leave
location empty so the classifier uses the title (webinars -> Online) and falls
back to the San Francisco source default otherwise.
"""
import re
from datetime import datetime, timezone
from typing import List

from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from .http import get

_LINE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s*\|\s*([^\n|]+)")


class BOMASFScraper(BaseScraper):
    name = "BOMA San Francisco"
    region = "San Francisco"
    source_url = "https://bomasf.org/events/events-calendar"

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        text = BeautifulSoup(r.text, "html.parser").get_text("\n")
        events: List[Event] = []
        for m in _LINE_RE.finditer(text):
            month, day, year, title = m.groups()
            title = " ".join(title.split()).strip(" -–")
            if not title:
                continue
            try:
                start = datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
            except ValueError:
                continue
            events.append(Event(title=title, start=start, url=self.source_url))
        return events
