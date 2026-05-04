"""CSHE (California Society for Healthcare Engineering) scraper.

Each event sits in a div.UpcomingEvents with inline format:
  <p>M/D/YYYY<br><a href="...">Title</a></p>
"""
import re
from datetime import datetime, timezone
from typing import List, Optional
from dateutil import parser as dateparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import BaseScraper, Event
from .http import get


class CSHEScraper(BaseScraper):
    name = "CSHE"
    region = "NorCal"
    source_url = "https://cshe.org/events/event_list.asp"

    DATE_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        events: List[Event] = []
        for el in soup.select(".UpcomingEvents"):
            text = el.get_text(" ", strip=True)
            link = el.select_one("a[href]")
            m = self.DATE_RE.search(text)
            if not link or not m:
                continue
            try:
                dt = dateparser.parse(m.group(1))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            title = link.get_text(strip=True)
            url = urljoin(self.source_url, link.get("href", ""))
            if title:
                events.append(Event(title=title, start=dt, url=url))
        return events
