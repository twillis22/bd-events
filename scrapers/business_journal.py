"""Business Journal event calendars.

The San Francisco Business Times and Silicon Valley Business Journal event pages
expose event dates and titles directly on the calendar listing page. Detail links
are inconsistent, so listing-page parsing is the primary strategy and detail-page
parsing enriches/replaces listing events when available.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .http import get


_EVENT_URL_RE = re.compile(r"/event/\d+/\d{4}/[A-Za-z0-9_-]+")
_LISTING_DT_RE = re.compile(
    r"^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)$",
    re.IGNORECASE,
)
_WEEKDAY_DATE_RE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\b"
)
_TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*(?:am|pm))", re.IGNORECASE)
_NOISE = {
    "IN-PERSON", "VIRTUAL", "HYBRID", "Register", "Events Calendar", "Events Newsletter",
    "Back to Top", "Subscribe", "Nominations", "Event Photos", "Business Events Calendar",
}


class BusinessJournalBaseScraper(BaseScraper):
    """Shared parser for American City Business Journals event pages."""

    max_detail_pages = 24

    def fetch(self) -> List[Event]:
        r = get(self.source_url, timeout=20)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")

        events_by_key: Dict[str, Event] = {
            self._event_key(e): e for e in self._listing_events(soup)
        }

        for url in self._detail_urls(soup)[: self.max_detail_pages]:
            try:
                ev = self._fetch_detail(url)
                if not ev:
                    continue
                key = self._event_key(ev)
                existing = events_by_key.get(key)
                events_by_key[key] = self._prefer_detail(ev, existing)
            except Exception as exc:
                print(f"  [warn] {self.name}: skipping {url}: {exc}")
        return list(events_by_key.values())

    @staticmethod
    def _prefer_detail(detail: Event, listing: Optional[Event]) -> Event:
        """Prefer venue/url/description from the detail page for listing duplicates."""
        if not listing:
            return detail
        return Event(
            title=detail.title or listing.title,
            start=detail.start or listing.start,
            end=detail.end or listing.end,
            url=detail.url or listing.url,
            location=detail.location or listing.location,
            description=detail.description or listing.description,
        )

    def _listing_events(self, soup: BeautifulSoup) -> List[Event]:
        lines = self._lines(soup)
        try:
            start_idx = lines.index("Events Calendar") + 1
        except ValueError:
            start_idx = 0
        end_idx = len(lines)
        for marker in ("Events Newsletter", "Find out how our events can impact your business and your career"):
            if marker in lines[start_idx:]:
                end_idx = min(end_idx, lines.index(marker))

        events: List[Event] = []
        i = start_idx
        while i < end_idx:
            line = lines[i]
            if not _LISTING_DT_RE.match(line):
                i += 1
                continue
            start = self._parse_dt(line)
            title, title_idx = self._next_title(lines, i + 1, end_idx)
            desc = self._next_description(lines, title_idx + 1, end_idx) if title_idx >= 0 else ""
            if start and title:
                events.append(Event(
                    title=title,
                    start=start,
                    url=self.source_url,
                    location=self.default_location,
                    description=desc,
                ))
            i = max(i + 1, title_idx + 1)
        return events

    @property
    def default_location(self) -> str:
        return self.region

    @staticmethod
    def _next_title(lines: List[str], start: int, end: int) -> Tuple[str, int]:
        for idx in range(start, min(end, start + 8)):
            line = lines[idx].strip("# ").strip()
            if not line or line in _NOISE or line.isdigit():
                continue
            if _LISTING_DT_RE.match(line):
                return "", -1
            if len(line) >= 5:
                return line, idx
        return "", -1

    @staticmethod
    def _next_description(lines: List[str], start: int, end: int) -> str:
        desc = []
        for line in lines[start : min(end, start + 4)]:
            cleaned = line.strip("# ").strip()
            if not cleaned or cleaned in _NOISE or cleaned.isdigit():
                continue
            if _LISTING_DT_RE.match(cleaned):
                break
            desc.append(cleaned)
        return " ".join(desc)[:400]

    @staticmethod
    def _event_key(ev: Event) -> str:
        return f"{Event._normalize(ev.title)}|{ev.start.date().isoformat()}"

    def _detail_urls(self, soup: BeautifulSoup) -> List[str]:
        seen = set()
        urls: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not _EVENT_URL_RE.search(href):
                continue
            full = urljoin(self.source_url, href).split("?")[0]
            if full in seen:
                continue
            seen.add(full)
            urls.append(full)
        return urls

    def _fetch_detail(self, url: str) -> Optional[Event]:
        r = get(url, timeout=20)
        if not r or r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        lines = self._lines(soup)

        title = self._title(soup, lines)
        start, end = self._date_times(lines)
        if not title or not start:
            return None

        return Event(
            title=title,
            start=start,
            end=end,
            url=url,
            location=self._where(lines) or self.default_location,
            description=self._description(lines),
        )

    @staticmethod
    def _lines(soup: BeautifulSoup) -> List[str]:
        return [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

    @staticmethod
    def _title(soup: BeautifulSoup, lines: List[str]) -> str:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
            if title and len(title) > 2:
                return title
        for idx, line in enumerate(lines):
            if line == "When" and idx > 0:
                return lines[idx - 1]
        return ""

    @staticmethod
    def _date_times(lines: List[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
        date_line = ""
        time_line = ""
        for idx, line in enumerate(lines):
            if line == "When":
                for candidate in lines[idx + 1 : idx + 5]:
                    if _WEEKDAY_DATE_RE.search(candidate):
                        date_line = _WEEKDAY_DATE_RE.search(candidate).group(0)
                        break
                if date_line:
                    after_date = lines[idx + 2 : idx + 7]
                    time_line = next((ln for ln in after_date if _TIME_RE.search(ln)), "")
                    break
        if not date_line:
            joined = "\n".join(lines)
            m = _WEEKDAY_DATE_RE.search(joined)
            if not m:
                return None, None
            date_line = m.group(0)

        times = _TIME_RE.findall(time_line or "")
        start_time = times[0] if times else "12:00am"
        start = BusinessJournalBaseScraper._parse_dt(f"{date_line} {start_time}")
        end = None
        if start and len(times) > 1:
            end = BusinessJournalBaseScraper._parse_dt(f"{date_line} {times[1]}")
            if end and end <= start:
                end = end + timedelta(days=1)
        return start, end

    @staticmethod
    def _parse_dt(text: str) -> Optional[datetime]:
        try:
            dt = dateparser.parse(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _where(lines: List[str]) -> str:
        if "Where" not in lines:
            return ""
        idx = lines.index("Where")
        location_lines = []
        for line in lines[idx + 1 : idx + 8]:
            if line in {"Social", "About the Event", "Read More", "Get Tickets"}:
                break
            if line.upper() in {"IN-PERSON", "VIRTUAL", "HYBRID"}:
                continue
            if line.startswith("Image"):
                continue
            location_lines.append(line)
        return ", ".join(location_lines)[:200]

    @staticmethod
    def _description(lines: List[str]) -> str:
        markers = ["About the Event", "Description"]
        for marker in markers:
            if marker not in lines:
                continue
            idx = lines.index(marker)
            desc = []
            for line in lines[idx + 1 : idx + 6]:
                if line in {"Read More", "Get Tickets", "Speakers", "Sponsors"}:
                    break
                desc.append(line)
            return " ".join(desc)[:400]
        return ""


class SanFranciscoBusinessTimesScraper(BusinessJournalBaseScraper):
    name = "San Francisco Business Times"
    region = "Bay Area"
    source_url = "https://www.bizjournals.com/sanfrancisco/event/"

    @property
    def default_location(self) -> str:
        return "San Francisco"


class SiliconValleyBusinessJournalScraper(BusinessJournalBaseScraper):
    name = "Silicon Valley Business Journal"
    region = "Silicon Valley"
    source_url = "https://www.bizjournals.com/sanjose/event/"

    @property
    def default_location(self) -> str:
        return "San Jose"
