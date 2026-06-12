"""Probe candidate event sources from the GitHub Actions runner — phase 5.

CoreNet Global Northern California chapter (Higher Logic platform): see what
the upcoming-events page serves, whether events render server-side, and
whether an iCal/RSS export exists.
"""
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except Exception as exc:
        print(f"    FETCH ERROR: {type(exc).__name__}: {exc}")
        return None


def around(text, pattern, label, limit=3, width=800):
    print(f"    around {label}:")
    n = 0
    for m in re.finditer(pattern, text, re.IGNORECASE):
        snip = " ".join(text[max(0, m.start() - 150):m.start() + width].split())
        print(f"      ...{snip[:width]}")
        n += 1
        if n >= limit:
            break
    if not n:
        print("      (no matches)")


def page(label, url):
    print(f"\n=== {label}: {url}")
    r = fetch(url)
    if r is None:
        return None
    print(f"    {r.status_code} {r.headers.get('content-type','?').split(';')[0]} "
          f"{len(r.content)} bytes (final: {r.url[:100]})")
    if r.status_code != 200:
        print(f"    head: {' '.join(r.text[:250].split())!r}")
        return None
    return r.text


def main():
    t = page("CoreNet NoCal upcoming events", "https://nocal.corenetglobal.org/events/upcoming-events")
    if t:
        blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                            t, re.DOTALL | re.IGNORECASE)
        print(f"    ld+json blocks: {len(blocks)}")
        for b in blocks[:2]:
            print("      " + " ".join(b.split())[:700])
        around(t, r'CalendarEventKey=', "event detail links", limit=4, width=600)
        around(t, r'class="[^"]*event[^"]*"', "event classes", limit=3, width=500)
        around(t, r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', "month-day dates", limit=3, width=300)
        for m in re.findall(r'href="([^"]*(?:ical|\.ics|rss|feed)[^"]*)"', t, re.IGNORECASE)[:6]:
            print(f"    feed-ish href: {m[:140]}")

    # Higher Logic calendar page + common feed endpoints
    page("CoreNet NoCal calendar", "https://nocal.corenetglobal.org/events1/calendar")
    for u in (
        "https://nocal.corenetglobal.org/events/upcoming-events?format=rss",
        "https://nocal.corenetglobal.org/HigherLogic/Calendar/iCalFeed.ashx",
    ):
        r = fetch(u)
        if r is not None:
            ct = r.headers.get('content-type', '?').split(';')[0]
            print(f"    {r.status_code} {ct:26s} {u}")
            if r.status_code == 200 and any(k in ct for k in ("calendar", "xml", "rss")):
                print(f"      head: {' '.join(r.text[:300].split())!r}")


if __name__ == "__main__":
    main()
