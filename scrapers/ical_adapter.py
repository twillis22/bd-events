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
        # Some feeds (AIA SF) mix cp1252 bytes into a nominally UTF-8 feed,
        # which decodes to U+FFFD mojibake. Decode explicitly with a fallback.
        try:
            raw = r.content.decode("utf-8")
        except UnicodeDecodeError:
            raw = r.content.decode("cp1252", errors="replace")
        cal = Calendar.from_ical(raw)
        events: List[Event] = []
        for comp in cal.walk("VEVENT"):
            start = self._to_dt(comp.get("DTSTART"))
            end = self._to_dt(comp.get("DTEND"))
            if not start:
                continue
            events.append(Event(
                title=self._clean(comp.get("SUMMARY")),
                start=start,
                end=end,
                url=self._clean(comp.get("URL")) or self.source_url,
                location=self._clean(comp.get("LOCATION")),
                description=self._clean(comp.get("DESCRIPTION"))[:400],
                source=self.name,
            ))
        return events

    @staticmethod
    def _clean(prop) -> str:
        # U+FFFD in source text is almost always a mangled en-dash.
        return str(prop or "").strip().replace("�", "–")

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
