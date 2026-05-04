"""AIA San Francisco scraper.

Strategy: AIA SF events page lists upcoming events; each event detail page exposes
a per-event iCal endpoint (/events/event-ical?eventId=N). We fetch the listing,
follow each event link, fetch its iCal for clean structured data.
"""
import re
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from icalendar import Calendar
from datetime import datetime, date, timezone

from .base import BaseScraper, Event
from .http import get


class AIASFScraper(BaseScraper):
    name = "AIA San Francisco"
    region = "NorCal"
    source_url = "https://www.aiasf.org/events/"

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")

        # Extract unique event detail URLs from the listing page.
        # AIA SF event slugs live at /events/<slug> — exclude listing/calendar variants.
        seen = set()
        event_urls = []
        ignore_titles = {"Calendar", "List View", "Details", "View Past Events", "Next", ""}
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("/events/") or href == "/events/" or "?" in href:
                continue
            title = a.get_text(strip=True)
            if title in ignore_titles or len(title) < 5:
                continue
            full = urljoin(self.source_url, href)
            if full in seen:
                continue
            seen.add(full)
            event_urls.append((title, full))

        events: List[Event] = []
        for title, url in event_urls[:25]:  # cap for politeness; AIA SF rarely shows >12
            try:
                ev = self._fetch_event(title, url)
                if ev:
                    events.append(ev)
            except Exception as exc:
                print(f"  [warn] AIA SF: skipping {title!r}: {exc}")
        return events

    def _fetch_event(self, fallback_title: str, detail_url: str):
        r = get(detail_url, timeout=15)
        if not r or r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Find per-event iCal link
        ical_a = soup.find("a", href=re.compile(r"event-ical\?eventId="))
        if not ical_a:
            return None
        ical_url = urljoin(detail_url, ical_a["href"])
        ir = get(ical_url, timeout=15)
        if not ir or ir.status_code != 200:
            return None
        cal = Calendar.from_ical(ir.content)
        for comp in cal.walk("VEVENT"):
            start = self._to_dt(comp.get("DTSTART"))
            end = self._to_dt(comp.get("DTEND"))
            if not start:
                continue
            return Event(
                title=str(comp.get("SUMMARY") or fallback_title).strip(),
                start=start,
                end=end,
                url=detail_url,
                location=str(comp.get("LOCATION") or "").strip(),
                description=str(comp.get("DESCRIPTION") or "").strip()[:400],
            )
        return None

    @staticmethod
    def _to_dt(prop):
        if prop is None:
            return None
        v = prop.dt
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, date):
            return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
        return None
