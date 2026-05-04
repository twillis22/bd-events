"""Generic RSS / Atom feed adapter.

Used for sources that publish event announcements as feed items. Pulls each item's
publish date as a fallback for the event date when no other date is exposed.
Heuristic filters drop pure-news items by requiring event-y keywords.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional
from dateutil import parser as dateparser
import feedparser

from .base import BaseScraper, Event
from .http import HEADERS

EVENT_KEYWORDS = re.compile(
    r"\b(event|webinar|conference|summit|symposium|forum|gala|breakfast|"
    r"luncheon|panel|tour|workshop|register|RSVP|join us|save the date|"
    r"happy hour|networking|workshop|meetup|seminar|expo)\b",
    re.IGNORECASE,
)


class RSSAdapter(BaseScraper):
    """Generic RSS reader. Subclass to override filters or override `is_event`."""

    feed_url: str = ""
    require_event_keyword: bool = True   # filter out pure-news items
    days_lookahead: int = 180

    def is_event(self, title: str, summary: str) -> bool:
        if not self.require_event_keyword:
            return True
        text = f"{title}\n{summary or ''}"
        return bool(EVENT_KEYWORDS.search(text))

    def fetch(self) -> List[Event]:
        # feedparser handles user-agent via request_headers
        parsed = feedparser.parse(self.feed_url, request_headers=HEADERS)
        events: List[Event] = []
        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            summary = (entry.get("summary") or "")
            if not title:
                continue
            if not self.is_event(title, summary):
                continue
            # Date fallback: use publish date as event date (best effort for RSS)
            dt = self._parse_date(entry)
            if not dt:
                continue
            events.append(Event(
                title=title,
                start=dt,
                url=link or self.source_url,
                description=self._clean_html(summary)[:400],
                source=self.name,
            ))
        return events

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        for key in ("published", "updated", "created"):
            v = entry.get(key)
            if v:
                try:
                    dt = dateparser.parse(v)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    pass
        return None

    @staticmethod
    def _clean_html(s: str) -> str:
        return re.sub(r"<[^>]+>", " ", s or "").strip()
