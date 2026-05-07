"""ULI San Francisco district council scraper.

Scrapes https://sf.uli.org/events/, which uses the same WordPress event-list
markup as ULI national (c-events-list__*). Strategy mirrors uli_national.py:
render in a headless browser, then evaluate JS to pull structured data per
article. SF district events are local to the Bay Area, so no international
filtering is needed.
"""
from datetime import timezone
from typing import List
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .browser import BrowserScraper, BrowserSession


class ULISanFranciscoScraper(BrowserScraper, BaseScraper):
    name = "ULI San Francisco"
    region = "NorCal"
    source_url = "https://sf.uli.org/events/"

    async def fetch_with_browser(self, session: BrowserSession) -> List[Event]:
        page = await session.new_page()
        try:
            await page.goto(self.source_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector("article a.c-events-list__link", timeout=15000)
            except Exception:
                return []
            await page.wait_for_timeout(1500)

            raw = await page.evaluate("""() => {
              const out = [];
              document.querySelectorAll('article').forEach(art => {
                const link = art.querySelector('a.c-events-list__link, a[href*="/events/detail/"]');
                const dateSpan = art.querySelector('.c-events-list__snackbar [data-start]');
                const endSpan  = art.querySelector('.c-events-list__snackbar [data-end]');
                const title = art.querySelector('.c-events-list__title, h2, h3');
                const meta  = art.querySelector('.c-events-list__meta');
                if (!link || !title) return;
                out.push({
                  href:  link.href,
                  start: dateSpan?.getAttribute('data-start') || '',
                  end:   endSpan?.getAttribute('data-end') || '',
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
            events.append(Event(
                title=r["title"],
                start=start,
                end=end,
                url=r["href"] or self.source_url,
                location=self._extract_location(r.get("meta", "")),
            ))
        return events

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
        if not meta:
            return ""
        lines = [ln.strip() for ln in meta.splitlines() if ln.strip()]
        if lines and any(c.isdigit() for c in lines[0]) and "," in lines[0]:
            lines = lines[1:]
        return ", ".join(lines[:4])[:200]
