"""ISPE conferences scraper.

ISPE's conference page is national/global. Keep the scraper's fallback region blank
so the aggregator only preserves events whose location text classifies into the
configured markets. This intentionally drops Long Beach / LA / Orange County /
out-of-state / global conferences.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .http import get


_DATE_RANGE_RE = re.compile(
    r"^(\d{1,2})\s*-\s*(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})$|"
    r"^([A-Z][a-z]+)\s+(\d{1,2})\s*-\s*(\d{1,2}),\s*(\d{4})$",
    re.IGNORECASE,
)
_SINGLE_DATE_RE = re.compile(r"^[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}$")
_TITLE_RE = re.compile(r"^\d{4}\s+ISPE\s+.+")


class ISPEConferencesScraper(BaseScraper):
    name = "ISPE Conferences"
    region = ""  # national/global source; classifier must find an in-market location
    source_url = "https://ispe.org/conferences"

    def fetch(self) -> List[Event]:
        r = get(self.source_url, timeout=20)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

        events: List[Event] = []
        for idx, line in enumerate(lines):
            title = line.strip("# ").strip()
            if not _TITLE_RE.match(title):
                continue
            date_line = self._next_matching(lines, idx + 1, _DATE_RANGE_RE, max_scan=5)
            if not date_line:
                date_line = self._next_matching(lines, idx + 1, _SINGLE_DATE_RE, max_scan=5)
            if not date_line:
                continue
            start, end = self._parse_dates(date_line)
            if not start:
                continue
            location = self._next_location(lines, lines.index(date_line, idx + 1) + 1)
            events.append(Event(
                title=title,
                start=start,
                end=end,
                url=self.source_url,
                location=location,
            ))
        return events

    @staticmethod
    def _next_matching(lines: List[str], start: int, pattern: re.Pattern, max_scan: int = 5) -> str:
        for line in lines[start : start + max_scan]:
            cleaned = line.strip("# ").strip()
            if pattern.match(cleaned):
                return cleaned
        return ""

    @staticmethod
    def _next_location(lines: List[str], start: int) -> str:
        for line in lines[start : start + 4]:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("Image"):
                continue
            if cleaned == "Conference Platform":
                continue
            if _TITLE_RE.match(cleaned) or _DATE_RANGE_RE.match(cleaned) or _SINGLE_DATE_RE.match(cleaned):
                return ""
            return cleaned[:200]
        return ""

    @staticmethod
    def _parse_dates(text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        m = _DATE_RANGE_RE.match(text)
        if m:
            if m.group(1):
                # "18 - 21 October 2026"
                start_day, end_day, month, year = m.group(1), m.group(2), m.group(3), m.group(4)
            else:
                # "October 18 - 21, 2026"
                month, start_day, end_day, year = m.group(5), m.group(6), m.group(7), m.group(8)
            start = ISPEConferencesScraper._parse_dt(f"{month} {start_day}, {year}")
            end = ISPEConferencesScraper._parse_dt(f"{month} {end_day}, {year}")
            return start, end
        if _SINGLE_DATE_RE.match(text):
            return ISPEConferencesScraper._parse_dt(text), None
        return None, None

    @staticmethod
    def _parse_dt(text: str) -> Optional[datetime]:
        try:
            dt = dateparser.parse(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
