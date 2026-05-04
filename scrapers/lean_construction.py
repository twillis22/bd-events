"""Lean Construction Institute scraper.

LCI organizes its events page as a month grid:
  - .ec-nav__month             contains "May 26" (May 2026)
  - .ec-day                    one block per day in the month
      - .ec-day__date          day number, e.g. "01"
      - .ec-day__day-of-week   abbreviated weekday
      - .ec-event              one or more events for that day
          - .ec-event__title1 a   title + link
          - .ec-event__time       time-of-day range (no date)
          - .ec-event__place      location text

Combine month/year with each day's date number to build full datetimes.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional
from dateutil import parser as dateparser
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from .http import get


class LeanConstructionScraper(BaseScraper):
    name = "Lean Construction Institute"
    region = "Both"
    source_url = "https://leanconstruction.org/events/"

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")

        month_year = self._parse_month_year(soup)
        if not month_year:
            return []
        month_num, year = month_year

        events: List[Event] = []
        for day_block in soup.select(".ec-day"):
            day_num_el = day_block.select_one(".ec-day__date")
            if not day_num_el:
                continue
            try:
                day_num = int(day_num_el.get_text(strip=True))
            except ValueError:
                continue
            try:
                day_dt = datetime(year, month_num, day_num, tzinfo=timezone.utc)
            except ValueError:
                continue

            for ev in day_block.select(".ec-event"):
                title_link = ev.select_one(".ec-event__title1 a, .ec-event__title a")
                if not title_link:
                    continue
                title = title_link.get_text(" ", strip=True)
                url = title_link.get("href", self.source_url)
                place_el = ev.select_one(".ec-event__place")
                location = place_el.get_text(" ", strip=True)[:120] if place_el else ""
                events.append(Event(title=title, start=day_dt, url=url, location=location))
        return events

    @staticmethod
    def _parse_month_year(soup) -> Optional[tuple]:
        """Pull 'May 26' from .ec-nav__month and turn into (5, 2026)."""
        el = soup.select_one(".ec-nav__month")
        if not el:
            return None
        text = el.get_text(" ", strip=True)
        # Match formats like "May 26", "May 2026", "May, 2026"
        m = re.search(r"([A-Z][a-z]+)[,\s]+(\d{2,4})", text)
        if not m:
            return None
        month_name, year_str = m.group(1), m.group(2)
        try:
            month_num = dateparser.parse(month_name).month
        except Exception:
            return None
        year = int(year_str)
        if year < 100:
            year += 2000
        return month_num, year
