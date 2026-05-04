"""Entrypoint — run all scrapers, write events.ics and index.html into ./docs/.

Run locally:
    python main.py

In CI (GitHub Actions): the workflow runs this and commits the docs/ folder so
GitHub Pages serves the updated calendar.
"""
import os
from aggregate import collect_events
from generate_ics import write_ics
from generate_html import write_html


def main():
    out_dir = os.environ.get("OUTPUT_DIR", "docs")
    os.makedirs(out_dir, exist_ok=True)

    events = collect_events(lookback_days=1, lookahead_days=365)

    print("\nWriting outputs...")
    write_ics(events, os.path.join(out_dir, "events.ics"))
    write_html(events, os.path.join(out_dir, "index.html"))
    print("\nDone.")


if __name__ == "__main__":
    main()
