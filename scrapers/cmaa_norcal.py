"""CMAA NorCal scraper — Wix Events.

The events list page renders <li data-hook='events-card'> items. Wix doesn't expose
date or location with their own data-hooks here, so we parse the card's innerText:

    Title                 (line 1)
    Day of week, Mon DD   (line 2)  e.g. 'Thu, May 14'
    Venue/Location text   (line 3+)
    More info / RSVP

The current visible year isn't on the card. We assume the current year, then
roll forward to next year if the resulting date is more than a month in the past.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .browser import BrowserScraper, BrowserSession


class CMAANorCalScraper(BrowserScraper, BaseScraper):
    name = "CMAA NorCal"
    region = "Bay Area"
    source_url = "https://www.cmaanorcal.org/events-list"

    # Lines we want to drop from the visible card text.
    _NOISE = {"more info", "rsvp", "details", "get tickets", "register"}

    async def fetch_with_browser(self, session: BrowserSession) -> List[Event]:
        page = await session.new_page()
        try:
            await page.goto(self.source_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector("[data-hook='events-card']", timeout=20000)
            except Exception:
                return []
            await page.wait_for_timeout(2000)

            raw = await page.evaluate("""() => {
              const out = [];
              document.querySelectorAll("[data-hook='events-card']").forEach(card => {
                const link = card.querySelector("a[href]");
                out.push({
                  href:    link?.href || '',
                  rawText: card.innerText || '',
                });
              });
              return out;
            }""")
        finally:
            await page.close()

        events: List[Event] = []
        for r in raw:
            parsed = self._parse_card(r["rawText"])
            if not parsed:
                continue
            title, dt, location = parsed
            events.append(Event(
                title=title,
                start=dt,
                url=r["href"] or self.source_url,
                location=location,
            ))
        return events

    def _parse_card(self, text: str):
        """Split a card's innerText into (title, datetime, location)."""
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        # Drop the action buttons
        lines = [ln for ln in lines if ln.lower() not in self._NOISE]
        if len(lines) < 2:
            return None
        title = lines[0]
        # Find the line that looks like a date — usually line 1 (zero-indexed)
        date_idx = None
        for i, ln in enumerate(lines[1:], start=1):
            if self._looks_like_date(ln):
                date_idx = i
                break
        if date_idx is None:
            return None
        dt = self._parse_date(lines[date_idx])
        if not dt:
            return None
        # Location is whatever non-noise lines come after the date line
        location_lines = lines[date_idx + 1:]
        location = ", ".join(location_lines)[:200]
        return title, dt, location

    @staticmethod
    def _looks_like_date(s: str) -> bool:
        return bool(re.search(
            r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
            s, re.IGNORECASE,
        ))

    @staticmethod
    def _parse_date(s: str) -> Optional[datetime]:
        """Parse Wix's 'Thu, May 14' style. Year is missing — use current and roll forward."""
        try:
            # Default year = current; dateutil will use it if year is missing.
            now = datetime.now(timezone.utc)
            dt = dateparser.parse(s, default=datetime(now.year, 1, 1, tzinfo=timezone.utc))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # If the parsed date is more than 30 days in the past, the event must
            # actually be in next year (Wix only shows upcoming events).
            if (now - dt).days > 30:
                dt = dt.replace(year=dt.year + 1)
            return dt
        except Exception:
            return None
