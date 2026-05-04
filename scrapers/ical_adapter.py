"""Generic iCal feed adapter."""
from typing import List
from icalendar import Calendar
from datetime import datetime, date, timezone

from .base import BaseScraper, Event
from .http import get


class ICalAdapter(BaseScraper):
    """Consumes a webcal/iCal feed. Best signal — full event details when available."""

    feed_url: str = ""

    def fetch(self) -> List[Event]:
        url = self.feed_url.replace("webcal://", "https://", 1)
        r = get(url)
        if not r or r.status_code != 200:
            return []
        cal = Calendar.from_ical(r.content)
        events: List[Event] = []
        for comp in cal.walk("VEVENT"):
            start = self._to_dt(comp.get("DTSTART"))
            end = self._to_dt(comp.get("DTEND"))
            if not start:
                continue
            events.append(Event(
                title=str(comp.get("SUMMARY") or "").strip(),
                start=start,
                end=end,
                url=str(comp.get("URL") or "").strip() or self.source_url,
                location=str(comp.get("LOCATION") or "").strip(),
                description=str(comp.get("DESCRIPTION") or "").strip()[:400],
                source=self.name,
            ))
        return events

    @staticmethod
    def _to_dt(prop):
        """Coerce icalendar's date/datetime into a tz-aware datetime."""
        if prop is None:
            return None
        v = prop.dt
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, date):
            return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
        return None
