"""BOMA San Diego scraper.

The calendar list page (classic ASP) embeds a schema.org JSON-LD array with
one Event object per upcoming event — name, startDate/endDate (US-format,
naive local time), venue Place, and description. Parse that; no HTML digging.
"""
import json
import re
from datetime import timezone
from html import unescape
from typing import List

from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .http import get


class BOMASDScraper(BaseScraper):
    name = "BOMA San Diego"
    region = "San Diego"
    source_url = "https://www.bomasd.org/calendar_list.asp"

    def fetch(self) -> List[Event]:
        r = get(self.source_url)
        if not r or r.status_code != 200:
            return []
        events: List[Event] = []
        for block in re.findall(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                r.text, re.DOTALL | re.IGNORECASE):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict) or item.get("@type") != "Event":
                    continue
                ev = self._to_event(item)
                if ev:
                    events.append(ev)
        return events

    def _to_event(self, item) -> Event | None:
        title = unescape(item.get("name") or "").strip()
        start = self._parse(item.get("startDate"))
        if not title or not start:
            return None
        end = self._parse(item.get("endDate"))
        loc = item.get("location") or {}
        parts = [loc.get("name") or ""]
        addr = loc.get("address") or {}
        for key in ("streetAddress", "addressLocality", "addressRegion"):
            v = (addr.get(key) or "").strip()
            if v:
                parts.append(v)
        location = ", ".join(p for p in parts if p)[:200]
        return Event(
            title=title,
            start=start,
            end=end,
            url=(item.get("url") or "").strip() or self.source_url,
            location=location,
            description=unescape(item.get("description") or "")[:400],
        )

    @staticmethod
    def _parse(s):
        if not s:
            return None
        try:
            dt = dateparser.parse(s)
            # Site times are local (Pacific); store naive-as-UTC like other
            # scrapers so the page displays the wall-clock time unchanged.
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
