"""CoreNet Global Northern California chapter scraper.

The upcoming-events page (Higher Logic CMS) is hand-maintained HTML where each
event is introduced by a heading of the form:

  <h3>Chapter Meeting // Thursday, June 18 // Santa Clara</h3>
  <h4><span>Location, Mobility, Talent: ...</span></h4>
  <p>description ...</p>

No year appears in the heading; assume the current year and roll forward when
the date would be more than 60 days in the past (the page only lists current/
upcoming events). The city segment feeds the classifier directly.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .http import get

_HEADING_RE = re.compile(r"^(.{2,40}?)\s*//\s*(.+?)\s*//\s*(.+)$")


class CoreNetNorCalScraper(BaseScraper):
    name = "CoreNet NorCal"
    region = "Bay Area"
    source_url = "https://nocal.corenetglobal.org/events/upcoming-events"

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        now = datetime.now(timezone.utc)
        events: List[Event] = []
        for h3 in soup.find_all("h3"):
            m = _HEADING_RE.match(h3.get_text(" ", strip=True))
            if not m:
                continue
            kind, date_txt, city = (part.strip() for part in m.groups())
            start = self._parse_date(date_txt, now)
            if not start:
                continue
            h4 = h3.find_next("h4")
            title = h4.get_text(" ", strip=True) if h4 else ""
            if not title:
                title = f"{kind} — {city}"
            link = h3.find_next("a", href=re.compile(r"CalendarEventKey|event-description", re.IGNORECASE))
            p = h3.find_next("p")
            events.append(Event(
                title=title,
                start=start,
                url=link["href"] if link and link.get("href", "").startswith("http") else self.source_url,
                location=f"{city}, CA",
                description=p.get_text(" ", strip=True)[:400] if p else "",
            ))
        return events

    @staticmethod
    def _parse_date(text: str, now: datetime) -> Optional[datetime]:
        try:
            dt = dateparser.parse(text, default=datetime(now.year, 1, 1))
        except Exception:
            return None
        dt = dt.replace(tzinfo=timezone.utc)
        # Headings carry no year; the page only lists current/upcoming events,
        # so a date far in the past means it belongs to next year.
        if dt < now - timedelta(days=60):
            dt = dt.replace(year=dt.year + 1)
        return dt
