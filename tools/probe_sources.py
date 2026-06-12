"""Probe candidate event sources from the GitHub Actions runner.

The dev sandbox can't reach association sites, but the Actions runner can.
This script fetches each candidate events page, fingerprints the platform,
lists advertised feeds, and tests common feed endpoints, so scrapers can be
written against real responses. Run via the manual "Probe Sources" workflow;
results land in the job log.
"""
import re
import requests

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CANDIDATES = [
    # (label, events page URL)
    ("NAIOP SF Bay Area",      "https://naiopsfba.org/programs/events/"),
    ("NAIOP SFBA members",     "https://members.naiopsfba.org/event-calendar"),
    ("AIA East Bay",           "https://aiaeb.org/calendar/"),
    ("AIA Central Valley",     "https://aiacv.org/events/"),
    ("AIA CV Eventbrite",      "https://www.eventbrite.com/o/aia-central-valley-30419137788"),
    ("BOMA San Francisco",     "https://bomasf.org/events/events-calendar"),
    ("BOMA Oakland/East Bay",  "https://www.bomaoeb.org/events"),
    ("BOMA Sacramento",        "https://www.bomasacramento.org/"),
    ("BOMA San Diego",         "https://www.bomasd.org/"),
    ("CREW San Francisco",     "https://san-francisco.crewnetwork.org/events/view-all-events"),
    ("CREW East Bay",          "https://east-bay.crewnetwork.org/events/view-all-events"),
    ("CREW Sacramento",        "https://sacramento.crewnetwork.org/events/view-all-events"),
    ("CREW San Diego",         "https://www.crewsandiego.org/events"),
    ("SMPS SF Bay Area",       "https://smpssf.org/meetinginfo.php"),
    ("SMPS San Diego",         "https://smpssd.starchapter.com/meetinginfo.php"),
    ("DBIA Western Pacific",   "https://dbiawpr.org/news-events/"),
    ("USGBC California",       "https://usgbc-ca.org/events/"),
]

# Tried against each site root when the page itself isn't a feed.
FEED_PATHS = [
    "/?post_type=tribe_events&ical=1&eventDisplay=list",   # The Events Calendar
    "/events/feed/",
    "/feed/",
    "/calendar/feed/",
]

FINGERPRINTS = [
    ("The Events Calendar", r"tribe-events|tribe_events"),
    ("WordPress",           r"wp-content|wp-json"),
    ("StarChapter",         r"starchapter"),
    ("GrowthZone",          r"growthzone|MicroNet"),
    ("Wild Apricot",        r"wildapricot"),
    ("Squarespace",         r"squarespace"),
    ("Wix",                 r"wix\.com|wixstatic"),
    ("Drupal",              r"/sites/default/files|drupal"),
    ("iMIS/ASP portal",     r"\.aspx|\.asp\b"),
    ("Cloudflare challenge", r"Just a moment|cf-challenge|challenge-platform"),
    ("JSON-LD events",      r'"@type"\s*:\s*"Event"'),
    ("iCal links",          r'\.ics|ical=1|text/calendar'),
]


def fetch(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except Exception as exc:
        print(f"    FETCH ERROR: {type(exc).__name__}: {exc}")
        return None


def describe(label, url):
    print(f"\n=== {label}: {url}")
    r = fetch(url)
    if r is None:
        return
    ct = r.headers.get("content-type", "?").split(";")[0]
    print(f"    {r.status_code} {ct} {len(r.content)} bytes  (final: {r.url})")
    if r.status_code != 200:
        print(f"    body head: {r.text[:200]!r}")
        return
    text = r.text
    hits = [name for name, pat in FINGERPRINTS if re.search(pat, text, re.IGNORECASE)]
    print(f"    fingerprints: {', '.join(hits) or 'none'}")
    alts = re.findall(r'<link[^>]+rel=["\']alternate["\'][^>]*>', text, re.IGNORECASE)
    for a in alts[:6]:
        print(f"    alternate: {a[:160]}")
    ld = len(re.findall(r'"@type"\s*:\s*"Event"', text))
    if ld:
        print(f"    JSON-LD Event objects: {ld}")
    # surface any explicit ics/ical hrefs
    for m in re.findall(r'href=["\']([^"\']*(?:\.ics|ical=1)[^"\']*)["\']', text)[:5]:
        print(f"    ics href: {m[:160]}")


def probe_feeds(root):
    print(f"\n--- feed candidates for {root}")
    for path in FEED_PATHS:
        url = root.rstrip("/") + path
        r = fetch(url)
        if r is None:
            continue
        ct = r.headers.get("content-type", "?").split(";")[0]
        ok = r.status_code == 200 and any(k in ct for k in ("xml", "calendar", "rss"))
        flag = "FEED!" if ok else "     "
        print(f"  {flag} {r.status_code} {ct:28s} {url}")
        if ok:
            print(f"        head: {' '.join(r.text[:300].split())!r}")


def main():
    for label, url in CANDIDATES:
        describe(label, url)
    roots = sorted({re.match(r"https?://[^/]+", u).group(0) for _, u in CANDIDATES})
    for root in roots:
        probe_feeds(root)


if __name__ == "__main__":
    main()
