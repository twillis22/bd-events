"""Probe candidate event sources from the GitHub Actions runner — phase 2.

Phase 1 established which sites the runner can reach. This pass digs into the
reachable ones and dumps the structures a scraper would parse: JSON-LD blocks,
markup snippets around event links, the Squarespace JSON for CREW SD, and feed
item structure for USGBC-CA. Run via the manual "Probe Sources" workflow.
"""
import json
import re
import requests

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


def dump_jsonld(text, limit=3, width=900):
    blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                        text, re.DOTALL | re.IGNORECASE)
    print(f"    ld+json blocks: {len(blocks)}")
    for b in blocks[:limit]:
        compact = " ".join(b.split())
        print(f"      {compact[:width]}")


def dump_snippets(text, pattern, label, limit=3, width=700):
    print(f"    snippets matching {label}:")
    count = 0
    for m in re.finditer(pattern, text, re.IGNORECASE):
        start = max(0, m.start() - 100)
        snip = " ".join(text[start:m.start() + width].split())
        print(f"      ...{snip[:width]}")
        count += 1
        if count >= limit:
            break
    if not count:
        print("      (no matches)")


def page(label, url):
    print(f"\n=== {label}: {url}")
    r = fetch(url)
    if r is None or r.status_code != 200:
        if r is not None:
            print(f"    {r.status_code}; head: {r.text[:200]!r}")
        return None
    print(f"    200, {len(r.content)} bytes")
    return r.text


def main():
    # --- CREW San Diego: Squarespace JSON endpoint
    print("\n##### CREW San Diego (Squarespace JSON)")
    r = fetch("https://www.crewsandiego.org/events?format=json")
    if r is not None:
        print(f"    {r.status_code} {r.headers.get('content-type','?')}")
        if r.status_code == 200:
            try:
                data = r.json()
                items = data.get("items") or data.get("upcoming") or []
                print(f"    top-level keys: {sorted(data.keys())[:15]}")
                print(f"    items: {len(items)}")
                for it in items[:2]:
                    keep = {k: it.get(k) for k in
                            ("title", "startDate", "endDate", "fullUrl", "location", "excerpt")}
                    print(f"      {json.dumps(keep)[:600]}")
            except Exception as exc:
                print(f"    JSON parse failed: {exc}; head: {r.text[:200]!r}")

    # --- CREW Network platform (SF; same template as East Bay/Sacramento)
    t = page("CREW SF view-all-events", "https://san-francisco.crewnetwork.org/events/view-all-events")
    if t:
        dump_jsonld(t)
        dump_snippets(t, r'href="[^"]*/events/2\d{3}[^"]*"', "event detail links")
        dump_snippets(t, r'class="[^"]*event[^"]*card[^"]*"|class="[^"]*card[^"]*event[^"]*"', "event card classes", limit=2)

    # --- NAIOP SFBA GrowthZone calendar
    t = page("NAIOP SFBA calendar", "https://members.naiopsfba.org/event-calendar")
    if t:
        dump_jsonld(t)
        dump_snippets(t, r'/event-calendar/Details/|class="[^"]*gz-[^"]*event[^"]*"', "GrowthZone event links")
        m = re.findall(r'(https?://[^"\']*api[^"\']*)["\']', t)
        print(f"    api-ish urls: {m[:5]}")

    # --- AIA East Bay calendar
    t = page("AIA East Bay calendar", "https://aiaeb.org/calendar/")
    if t:
        dump_jsonld(t)
        dump_snippets(t, r'href="https://aiaeb\.org/calendar/[^"]+"', "calendar detail links")
        dump_snippets(t, r'class="[^"]*(?:event|calendar)[^"]*item[^"]*"', "calendar item classes", limit=2)

    # --- BOMA SF Drupal calendar
    t = page("BOMA SF events calendar", "https://bomasf.org/events/events-calendar")
    if t:
        dump_jsonld(t)
        dump_snippets(t, r'\d{2}\.\d{2}\.\d{4}', "MM.DD.YYYY dates")
        dump_snippets(t, r'class="[^"]*views-row[^"]*"', "drupal views rows", limit=2)

    # --- BOMA San Diego: find events nav link, then fetch it
    t = page("BOMA SD homepage", "https://www.bomasd.org/")
    if t:
        links = sorted(set(re.findall(r'href="([^"]*(?:event|calendar)[^"]*)"', t, re.IGNORECASE)))
        print(f"    event-ish links: {links[:10]}")
        for link in links:
            if "calendar" in link.lower() or "event" in link.lower():
                url = link if link.startswith("http") else "https://www.bomasd.org" + link
                t2 = page("BOMA SD events page", url)
                if t2:
                    dump_jsonld(t2)
                    dump_snippets(t2, r'class="[^"]*event[^"]*"', "event classes", limit=3)
                break

    # --- AIA Central Valley via Eventbrite organizer page
    t = page("AIA CV Eventbrite organizer", "https://www.eventbrite.com/o/aia-central-valley-30419137788")
    if t:
        dump_jsonld(t, limit=2, width=1200)
        dump_snippets(t, r'window\.__SERVER_DATA__', "__SERVER_DATA__", limit=1, width=1000)

    # --- USGBC-CA events RSS: item structure
    print("\n##### USGBC-CA events feed")
    r = fetch("https://usgbc-ca.org/events/?feed=rss2")
    if r is not None:
        print(f"    {r.status_code} {r.headers.get('content-type','?')}")
        if r.status_code == 200:
            items = re.findall(r'<item>(.*?)</item>', r.text, re.DOTALL)
            print(f"    items: {len(items)}")
            for it in items[:2]:
                print(f"      {' '.join(it.split())[:900]}")


if __name__ == "__main__":
    main()
