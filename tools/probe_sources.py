"""Probe candidate event sources from the GitHub Actions runner — phase 4.

Validate the three draft scrapers (BOMA SD with the strict=False JSON fix,
BOMA SF, NAIOP SFBA) and check whether the CREW Network Next.js pages embed
event data in __NEXT_DATA__ or fetch it client-side.
"""
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
}


def main():
    print("##### Draft scraper validation")
    from scrapers.boma_sd import BOMASDScraper
    from scrapers.boma_sf import BOMASFScraper
    from scrapers.naiop_sfba import NAIOPSFBAScraper
    for cls in (BOMASDScraper, BOMASFScraper, NAIOPSFBAScraper):
        s = cls()
        events = s.safe_fetch()
        print(f"\n  {s.name}: {len(events)} events")
        for e in events[:6]:
            print(f"    {e.start} | {e.title[:60]} | loc={e.location[:40]!r} | {e.url[:60]}")

    print("\n##### CREW SF __NEXT_DATA__")
    try:
        r = requests.get("https://san-francisco.crewnetwork.org/events/view-all-events",
                         headers=HEADERS, timeout=20)
        t = r.text
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.DOTALL)
        if not m:
            print("    no __NEXT_DATA__ script")
        else:
            blob = m.group(1)
            print(f"    __NEXT_DATA__ size: {len(blob)}")
            for key in ('"events"', '"eventList"', '"listings"', '"date"', '"title"'):
                idx = blob.find(key)
                print(f"    {key} at {idx}")
                if idx != -1:
                    print(f"      {' '.join(blob[max(0,idx-80):idx+600].split())[:600]}")
    except Exception as exc:
        print(f"    error: {exc}")


if __name__ == "__main__":
    main()
