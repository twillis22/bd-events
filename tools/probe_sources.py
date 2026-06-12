"""Probe candidate event sources from the GitHub Actions runner — phase 6.

Run the draft CoreNet NorCal scraper for real and print what it returns.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("##### Draft scraper validation")
    from scrapers.corenet_norcal import CoreNetNorCalScraper
    from scrapers.regions import classify
    s = CoreNetNorCalScraper()
    events = s.safe_fetch()
    print(f"\n  {s.name}: {len(events)} events")
    for e in events[:12]:
        region = classify(e.location, e.title, s.region)
        print(f"    {e.start} | {region!s:14.14} | {e.title[:55]} | loc={e.location[:30]!r} | {e.url[:70]}")


if __name__ == "__main__":
    main()
