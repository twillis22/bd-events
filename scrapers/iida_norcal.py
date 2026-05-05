"""IIDA Northern California scraper.

The /attend/ page uses the FacetWP plugin which renders client-side. Each event:
  - .edate    contains <span class='emonth'>, <span class='eday'>, <span class='eyear'>
  - .edeets   contains <h3><a href>title</a></h3>
  - .etype    chapter/category tags (e.g. "Silicon Valley", "Sacramento")

The first .facetwp-template item is a heading ("Upcoming Events"); skip anything
without a parseable date.
"""
from datetime import datetime, timezone
from typing import List
from dateutil import parser as dateparser

from .base import BaseScraper, Event
from .browser import BrowserScraper, BrowserSession


class IIDANorCalScraper(BrowserScraper, BaseScraper):
    name = "IIDA Northern California"
    region = "NorCal"
    source_url = "https://iidanc.org/attend/"

    async def fetch_with_browser(self, session: BrowserSession) -> List[Event]:
        page = await session.new_page()
        try:
            await page.goto(self.source_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(".facetwp-template .edate, .facetwp-template .edeets", timeout=15000)
            except Exception:
                return []
            await page.wait_for_timeout(1500)

            raw = await page.evaluate("""() => {
              const out = [];
              document.querySelectorAll('.facetwp-template > *').forEach(item => {
                const month = item.querySelector('.emonth')?.innerText?.trim();
                const day   = item.querySelector('.eday')?.innerText?.trim();
                const year  = item.querySelector('.eyear')?.innerText?.trim();
                const link  = item.querySelector('.edeets a, h3 a');
                const tags  = Array.from(item.querySelectorAll('.etype li')).map(li => li.innerText.trim());
                if (!month || !day || !year || !link) return;
                out.push({
                  month, day, year,
                  title: link.innerText.trim(),
                  href:  link.href,
                  tags,
                });
              });
              return out;
            }""")
        finally:
            await page.close()

        events: List[Event] = []
        for r in raw:
            try:
                dt_text = f"{r['month']} {r['day']}, {r['year']}"
                dt = dateparser.parse(dt_text)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            tags = ", ".join(r.get("tags") or [])
            events.append(Event(
                title=r["title"],
                start=dt,
                url=r["href"] or self.source_url,
                description=f"Categories: {tags}" if tags else "",
            ))
        return events
