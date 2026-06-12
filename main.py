"""Entrypoint — run all scrapers, write events.ics, index.html, seen.json.

Usage:
    python main.py                # full run, writes all outputs

Run as part of GitHub Actions or locally.
"""
import os
from aggregate import collect_events
from event_archive import EventArchive, RETAIN_DAYS
from generate_ics import write_ics
from generate_html import write_html
from seen_tracker import SeenTracker


def main():
    out_dir = os.environ.get("OUTPUT_DIR", "docs")
    os.makedirs(out_dir, exist_ok=True)

    # 1) Aggregate events (lookback covers the "Recently passed" window)
    events = collect_events(lookback_days=RETAIN_DAYS, lookahead_days=365)

    # 1b) Restore recently-passed events the sources have already delisted
    archive = EventArchive("data/archive.json")
    events = archive.merge(events)

    # 2) Annotate with first-seen / is-new from persistent state
    tracker = SeenTracker("data/seen.json")
    tracker.annotate(events)
    new_count = sum(1 for e in events if e.is_new)
    if new_count:
        print(f"  {new_count} events flagged as new (first seen within last 7 days)")

    # 3) Prune stale UIDs from the seen file (events that aged out of all feeds)
    current_uids = {e.uid for e in events}
    tracker.prune(current_uids)
    tracker.save()
    archive.save()

    # 4) Write all output formats
    print("\nWriting outputs...")
    write_ics(events, os.path.join(out_dir, "events.ics"))
    write_html(events, os.path.join(out_dir, "index.html"))
    print("\nDone.")


if __name__ == "__main__":
    main()
