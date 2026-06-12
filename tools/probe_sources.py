"""Probe candidate event sources from the GitHub Actions runner — phase 3.

1. Run the draft BOMA SD / BOMA SF scrapers for real and print their events.
2. Dig deeper on the holdouts whose data didn't surface in phase 2:
   NAIOP SFBA (full GrowthZone card), CREW network chapters (embedded JSON?),
   CREW San Diego (Squarespace collection shape), USGBC-CA (events markup),
   AIA East Bay (embedded calendar widget?).
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


def main():
    # --- 1) Draft scrapers, run for real
    print("##### Draft scraper validation")
    from scrapers.boma_sd import BOMASDScraper
    from scrapers.boma_sf import BOMASFScraper
    for cls in (BOMASDScraper, BOMASFScraper):
        s = cls()
        events = s.safe_fetch()
        print(f"\n  {s.name}: {len(events)} events")
        for e in events[:6]:
            print(f"    {e.start} | {e.title[:60]} | loc={e.location[:50]!r}")

    # --- 2) NAIOP SFBA: dump one full GrowthZone event card
    print("\n##### NAIOP SFBA full card")
    r = fetch("https://members.naiopsfba.org/event-calendar")
    if r is not None and r.status_code == 200:
        i = r.text.find('gz-events-card')
        # skip the commented-out template card if present; find a card with an href
        while i != -1:
            chunk = r.text[i:i + 5000]
            if 'href' in chunk:
                print("    " + " ".join(chunk.split())[:4500])
                break
            i = r.text.find('gz-events-card', i + 1)
        else:
            print("    (no card found)")

    # --- 3) CREW network platform: what holds the event data?
    print("\n##### CREW SF deep dig")
    r = fetch("https://san-francisco.crewnetwork.org/events/view-all-events")
    if r is not None and r.status_code == 200:
        t = r.text
        hrefs = sorted(set(re.findall(r'href="([^"]*event[^"]*)"', t, re.IGNORECASE)))
        print(f"    event-ish hrefs ({len(hrefs)}):")
        for h in hrefs[:15]:
            print(f"      {h[:140]}")
        around(t, r'"startDate"|"start_date"|data-start', "start date keys", limit=2)
        around(t, r'<(article|li|div)[^>]*class="[^"]*(listing|result|tile|teaser)[^"]*"', "listing classes", limit=2)

    # --- 4) CREW San Diego: Squarespace collection shape
    print("\n##### CREW SD JSON shape")
    r = fetch("https://www.crewsandiego.org/events?format=json")
    if r is not None and r.status_code == 200:
        try:
            data = r.json()
            coll = data.get("collection") or {}
            print(f"    collection.typeName={coll.get('typeName')!r} type={coll.get('type')!r} title={coll.get('title')!r}")
            raw = json.dumps(data)
            for key in ('"startDate"', '"eventStartDate"', '"upcoming"'):
                idx = raw.find(key)
                print(f"    {key} at {idx}")
                if idx != -1:
                    print(f"      {raw[max(0,idx-100):idx+500]}")
        except Exception as exc:
            print(f"    parse fail: {exc}")
    # the upcoming list may live on a sub-collection
    r = fetch("https://www.crewsandiego.org/events?format=json&past=false")
    if r is not None:
        print(f"    past=false variant: {r.status_code}")

    # --- 5) USGBC-CA events page markup
    print("\n##### USGBC-CA events page")
    r = fetch("https://usgbc-ca.org/events/")
    if r is not None and r.status_code == 200:
        t = r.text
        around(t, r'<(article|div|li)[^>]*class="[^"]*event[^"]*"', "event classes", limit=3)
        around(t, r'"@type"\s*:\s*"Event"', "JSON-LD events", limit=2)
        hrefs = sorted(set(re.findall(r'href="(https://usgbc-ca\.org/event[^"]*)"', t)))
        print(f"    event detail hrefs: {hrefs[:8]}")

    # --- 6) AIA East Bay: embedded calendar widget?
    print("\n##### AIA East Bay widget hunt")
    r = fetch("https://aiaeb.org/calendar/")
    if r is not None and r.status_code == 200:
        t = r.text
        around(t, r'<iframe[^>]*>', "iframes", limit=3, width=400)
        around(t, r'(ecwd|eventon|mec-|em-calendar|simcal|tribe|calendarize|wp-calendar)', "calendar plugin markers", limit=4, width=300)
        scripts = sorted(set(re.findall(r'src="([^"]*plugins/[^"]*)"', t)))
        print(f"    plugin script srcs:")
        for s in scripts[:10]:
            print(f"      {s[:140]}")


if __name__ == "__main__":
    main()
