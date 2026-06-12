"""Persistent archive of scraped events — powers the "Recently passed" section.

Sources delist events as soon as they occur, and the site regenerates from
scratch daily, so without state a past event vanishes the morning after it
happens. This module snapshots every event seen during a run into
data/archive.json (committed back by the Action, like seen.json) and re-adds
recently-passed events that the sources no longer list.

Retention: passed events stay on the site for RETAIN_DAYS after their start;
archive entries are pruned PRUNE_DAYS after start.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from dateutil import parser as dateparser

from scrapers.base import Event
from scrapers.regions import classify

RETAIN_DAYS = 14
PRUNE_DAYS = 21


class EventArchive:
    def __init__(self, path: str = "data/archive.json"):
        self.path = path
        self.data: dict = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except (ValueError, OSError):
                self.data = {}

    def merge(self, events: List[Event]) -> List[Event]:
        """Record current events, restore recently-passed delisted ones."""
        now = datetime.now(timezone.utc)
        current_uids = {e.uid for e in events}
        for e in events:
            self.data[e.uid] = self._snapshot(e)

        merged = list(events)
        restored = 0
        for uid, snap in list(self.data.items()):
            start = self._parse(snap.get("start"))
            if start is None or start < now - timedelta(days=PRUNE_DAYS):
                del self.data[uid]
                continue
            if uid in current_uids or start > now:
                # future events that vanish from a source (e.g. cancelled)
                # are not restored — only the recently-passed are.
                continue
            if start >= now - timedelta(days=RETAIN_DAYS):
                ev = self._restore(snap)
                if ev is not None:
                    merged.append(ev)
                    restored += 1
        if restored:
            print(f"  Restored {restored} recently-passed events from archive")
        return sorted(merged, key=lambda e: e.start)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=0, sort_keys=True)
        print(f"  Saved {len(self.data)} entries to {self.path}")

    @staticmethod
    def _snapshot(e: Event) -> dict:
        return {
            "title": e.title,
            "start": e.start.isoformat(),
            "end": e.end.isoformat() if e.end else None,
            "url": e.url,
            "location": e.location,
            "description": e.description,
            "source": e.source,
            "source_region": e.source_region,
        }

    def _restore(self, snap: dict) -> Optional[Event]:
        start = self._parse(snap.get("start"))
        if not snap.get("title") or start is None:
            return None
        ev = Event(
            title=snap["title"],
            start=start,
            end=self._parse(snap.get("end")),
            url=snap.get("url", ""),
            location=snap.get("location", ""),
            description=snap.get("description", ""),
            source=snap.get("source", ""),
            source_region=snap.get("source_region", ""),
        )
        # Region is never persisted (see CLAUDE.md on UIDs) — re-derive it.
        region = classify(ev.location, ev.title, ev.source_region)
        if region is None:
            return None
        ev.region = region
        return ev

    @staticmethod
    def _parse(s):
        if not s:
            return None
        try:
            dt = dateparser.parse(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
