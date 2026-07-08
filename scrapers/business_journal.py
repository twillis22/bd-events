"""Business Journal event calendars.

The San Francisco Business Times and Silicon Valley Business Journal event pages
render event cards with detail links under /event/<id>/<year>/<slug>. The detail
pages expose cleaner date/time/location blocks, so the scraper collects detail
URLs from the calendar page and parses each detail page.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .http import get


_EVENT_URL_RE = re.compile(r"/event/\d+/\d{4}/[A-Za-z0-9_-]+")
_WEEKDAY_DATE_RE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\b"
)
_TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*(?:am|pm))", re.IGNORECASE)


class BusinessJournalBaseScraper(BaseScraper):
    """Shared parser for American City Business Journals event pages."""

    max_detail_pages = 24

    def fetch(self) -> List[Event]:
        r = get(self.source_url, timeout=20)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        detail_urls = self._detail_urls(soup)

        events: List[Event] = []
        for url in detail_urls[: self.max_detail_pages]:
            try:
                ev = self._fetch_detail(url)
                if ev:
                    events.append(ev)
            except Exception as exc:
                print(f"  [warn] {self.name}: skipping {url}: {exc}")
        return events

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
            location=self._where(lines),
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
        # Fallback: detail pages usually put the event title directly before "When".
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
                    # The time range is usually the next line after the date.
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


class SiliconValleyBusinessJournalScraper(BusinessJournalBaseScraper):
    name = "Silicon Valley Business Journal"
    region = "Silicon Valley"
    source_url = "https://www.bizjournals.com/sanjose/event/"
