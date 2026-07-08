"""I2SL chapter scrapers.

Covers:
- I2SL NorCal: chapter page links through to an ISPE SF GrowthZone event detail.
- I2SL San Diego: chapter page lists upcoming dated events directly.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .http import get


_DETAIL_RE = re.compile(r"/event-calendar/Details/", re.IGNORECASE)
_DATE_LINE_RE = re.compile(
    r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\s*\(([^)]+)\)",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", re.IGNORECASE)
_SIMPLE_DATE_RE = re.compile(r"^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$")


class I2SLNorCalScraper(BaseScraper):
    name = "I2SL NorCal"
    region = "Bay Area"
    source_url = "https://www.i2slnorcal.org/events"

    def fetch(self) -> List[Event]:
        r = get(self.source_url, timeout=20)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")

        detail_urls = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not _DETAIL_RE.search(href):
                continue
            full = urljoin(self.source_url, href)
            if full in seen:
                continue
            seen.add(full)
            detail_urls.append(full)

        events: List[Event] = []
        for url in detail_urls[:10]:
            try:
                ev = self._fetch_growthzone_detail(url)
                if ev:
                    events.append(ev)
            except Exception as exc:
                print(f"  [warn] I2SL NorCal: skipping {url}: {exc}")
        return events

    def _fetch_growthzone_detail(self, url: str) -> Optional[Event]:
        r = get(url, timeout=20)
        if not r or r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        lines = _lines(soup)
        text = "\n".join(lines)

        m = _DATE_LINE_RE.search(text)
        if not m:
            return None
        start, end = _parse_date_and_times(m.group(1), m.group(2))
        if not start:
            return None

        title = _title(soup, lines)
        if not title:
            return None

        return Event(
            title=title,
            start=start,
            end=end,
            url=url,
            location=_growthzone_location(lines),
            description=_description(lines),
        )


class I2SLSanDiegoScraper(BaseScraper):
    name = "I2SL San Diego"
    region = "San Diego"
    source_url = "https://www.i2sl.org/san-diego"

    def fetch(self) -> List[Event]:
        r = get(self.source_url, timeout=20)
        if not r or r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        lines = _lines(soup)

        try:
            start_idx = lines.index("Upcoming Events") + 1
        except ValueError:
            return []
        try:
            end_idx = lines.index("Chapter Officers")
        except ValueError:
            end_idx = len(lines)

        events: List[Event] = []
        i = start_idx
        while i < end_idx:
            line = lines[i]
            if not _SIMPLE_DATE_RE.match(line):
                i += 1
                continue
            start = _parse_simple_date(line)
            title = _next_nonempty(lines, i + 1, end_idx)
            title_idx = lines.index(title, i + 1, end_idx) if title else i + 1
            location = _next_nonempty(lines, title_idx + 1, end_idx)
            if start and title:
                events.append(Event(
                    title=title,
                    start=start,
                    url=self.source_url,
                    location=location or "San Diego",
                ))
            i = title_idx + 2
        return events


def _lines(soup: BeautifulSoup) -> List[str]:
    return [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]


def _title(soup: BeautifulSoup, lines: List[str]) -> str:
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
        if title and len(title) > 2:
            return title
    for idx, line in enumerate(lines):
        if line == "Description" and idx > 0:
            return lines[idx - 1]
    return ""


def _parse_date_and_times(date_text: str, time_text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    times = _TIME_RE.findall(time_text or "")
    start_time = times[0] if times else "12:00 AM"
    start = _parse_dt(f"{date_text} {start_time}")
    end = None
    if start and len(times) > 1:
        end = _parse_dt(f"{date_text} {times[1]}")
        if end and end <= start:
            end = end + timedelta(days=1)
    return start, end


def _parse_simple_date(text: str) -> Optional[datetime]:
    return _parse_dt(f"{text} 12:00 AM")


def _parse_dt(text: str) -> Optional[datetime]:
    try:
        dt = dateparser.parse(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _growthzone_location(lines: List[str]) -> str:
    if "Location:" in lines:
        idx = lines.index("Location:")
        return ", ".join(lines[idx + 1 : idx + 3])[:200]
    for idx, line in enumerate(lines):
        if line.lower().startswith("location:"):
            loc = [line.split(":", 1)[1].strip()]
            loc.extend(lines[idx + 1 : idx + 2])
            return ", ".join([x for x in loc if x])[:200]
    return ""


def _description(lines: List[str]) -> str:
    if "Description" not in lines:
        return ""
    idx = lines.index("Description")
    desc = []
    for line in lines[idx + 1 : idx + 8]:
        if line in {"Date:", "Price:", "Meet the Speakers", "Additional Info"}:
            break
        desc.append(line)
    return " ".join(desc)[:400]


def _next_nonempty(lines: List[str], start: int, end: int) -> str:
    for line in lines[start:end]:
        if line and not line.lower().startswith("more details"):
            return line
    return ""
