"""Tracks first-seen dates for events across runs.

Persists a JSON file mapping event UID -> first-seen ISO date string. This
enables two features:
  - Flagging events that first appeared in the last N days as 'new'.
  - Powering the weekly email digest's 'newly added' section.

The file is committed to the repo by the GitHub Action so it persists between
scheduled runs.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from scrapers.base import Event


class SeenTracker:
    """Reads/writes a seen.json keyed by event UID -> ISO date first observed."""

    NEW_WINDOW_DAYS = 7

    def __init__(self, path: str = "data/seen.json"):
        self.path = Path(path)
        self._seen: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._seen = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [warn] seen.json unreadable, starting fresh: {exc}")
                self._seen = {}
        else:
            self._seen = {}

    def annotate(self, events: List[Event]) -> List[Event]:
        """Mark each event with .first_seen and .is_new flags. Returns the same list."""
        today = datetime.now(timezone.utc).date().isoformat()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.NEW_WINDOW_DAYS)).date()

        for ev in events:
            if ev.uid not in self._seen:
                self._seen[ev.uid] = today
            ev.first_seen = self._seen[ev.uid]
            try:
                first_seen_date = datetime.fromisoformat(ev.first_seen).date()
                ev.is_new = first_seen_date >= cutoff
            except ValueError:
                ev.is_new = False
        return events

    def newly_added(self, events: List[Event], days: int = 7) -> List[Event]:
        """Return only events whose first_seen falls within the last `days` days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
        out = []
        for ev in events:
            try:
                fs = datetime.fromisoformat(getattr(ev, "first_seen", "")).date()
                if fs >= cutoff:
                    out.append(ev)
            except (ValueError, TypeError):
                pass
        return out

    def prune(self, valid_uids: set) -> None:
        """Remove entries for events that no longer appear in any source.
        Keeps the file from growing unbounded as old events fall out of feeds."""
        before = len(self._seen)
        self._seen = {uid: date for uid, date in self._seen.items() if uid in valid_uids}
        pruned = before - len(self._seen)
        if pruned:
            print(f"  Pruned {pruned} stale UIDs from seen.json")

    def save(self) -> None:
        """Write back to disk, creating parent dirs if needed."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._seen, indent=2, sort_keys=True))
        print(f"  Saved {len(self._seen)} entries to {self.path}")
