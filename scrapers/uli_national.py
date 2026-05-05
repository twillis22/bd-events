"""ULI National scraper — renders /events/ in a headless browser.

The events page hydrates client-side from a JSON API. Each event lives inside an
<article> with:
  - <a class="c-events-list__link"> wrapping the whole card; href is the detail page
  - .c-events-list__snackbar [data-start] / [data-end]  with ISO timestamps
  - .c-events-list__title  with the event title
  - .c-events-list__meta   with location/address (multi-line)

Strategy: navigate, wait for the article elements, then evaluate JS in the page to
extract structured data per article. Cleaner than CSS-selecting from Python.
"""
from datetime import datetime, timezone
from typing import List
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .browser import BrowserScraper, BrowserSession


class ULINationalScraper(BrowserScraper, BaseScraper):
    name = "ULI (national)"
    region = "Other"
    source_url = "https://uli.org/events/"

    async def fetch_with_browser(self, session: BrowserSession) -> List[Event]:
        page = await session.new_page()
        try:
            await page.goto(self.source_url, wait_until="domcontentloaded", timeout=30000)
            # Wait for hydration — articles only exist after JS runs.
            try:
                await page.wait_for_selector("article a.c-events-list__link", timeout=15000)
            except Exception:
                return []
            await page.wait_for_timeout(1500)  # let titles paint

            raw = await page.evaluate("""() => {
              const out = [];
              document.querySelectorAll('article').forEach(art => {
                const link = art.querySelector('a.c-events-list__link, a[href*="/events/detail/"]');
                const dateSpan = art.querySelector('.c-events-list__snackbar [data-start]');
                const endSpan  = art.querySelector('.c-events-list__snackbar [data-end]');
                const tzSpan   = art.querySelector('.c-events-list__snackbar [data-timezone]');
                const title = art.querySelector('.c-events-list__title, h2, h3');
                const meta  = art.querySelector('.c-events-list__meta');
                if (!link || !title) return;
                out.push({
                  href:  link.href,
                  start: dateSpan?.getAttribute('data-start') || '',
                  end:   endSpan?.getAttribute('data-end') || '',
                  tz:    tzSpan?.getAttribute('data-timezone') || '',
                  title: title.innerText.trim(),
                  meta:  meta?.innerText?.trim() || '',
                });
              });
              return out;
            }""")
        finally:
            await page.close()

        events: List[Event] = []
        for r in raw:
            start = self._parse(r.get("start"))
            end = self._parse(r.get("end"))
            if not r.get("title") or not start:
                continue
            location = self._extract_location(r.get("meta", ""))
            # Filter out clearly international events. ULI publishes globally;
            # the BD use case is US-focused. Drop events whose location/meta
            # explicitly names a non-US country.
            if self._is_international(location, r.get("title", "")):
                continue
            events.append(Event(
                title=r["title"],
                start=start,
                end=end,
                url=r["href"] or self.source_url,
                location=location,
            ))
        return events

    # Substrings that, if present in title or location, mark an event as non-US.
    _INTL_MARKERS = (
        "CHINA", "GERMANY", "FRANCE", "UNITED KINGDOM", "JAPAN", "KOREA",
        "INDIA", "SINGAPORE", "AUSTRALIA", "Hong Kong", "Tokyo", "Berlin",
        "Shanghai", "Mumbai", "Sydney", "Seoul", "Bangkok", "Manila",
        "ULI Asia", "ULI Europe", "ULI India", "ULI Hong Kong", "ULI Singapore",
        "ULI Philippines", "ULI Korea", "ULI Japan", "ULI China",
    )

    @classmethod
    def _is_international(cls, location: str, title: str) -> bool:
        haystack = f"{location} {title}"
        return any(marker in haystack for marker in cls._INTL_MARKERS)

    @staticmethod
    def _parse(s):
        if not s:
            return None
        try:
            dt = dateparser.parse(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _extract_location(meta: str) -> str:
        """Pull the venue + address out of ULI's multi-line meta text.

        Format observed: "May 25, 2026 - May 29, 2026\n\nVenue Name\nStreet\nCity, ST ZIP\nCOUNTRY"
        Skip the first line (date range). Take up to the next 4 non-empty lines as address.
        """
        if not meta:
            return ""
        lines = [ln.strip() for ln in meta.splitlines() if ln.strip()]
        # Drop date-only first line if present
        if lines and any(c.isdigit() for c in lines[0]) and "," in lines[0]:
            lines = lines[1:]
        return ", ".join(lines[:4])[:200]
