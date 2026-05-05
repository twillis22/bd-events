"""Shared headless-browser helper for JS-rendered sites.

Playwright is heavy — we want a single browser instance reused across all JS scrapers
in a run rather than launching one per scraper. This module provides a context manager
that owns one browser/context for the duration of an aggregation pass.

Usage:
    from scrapers.browser import BrowserSession

    async with BrowserSession() as session:
        page = await session.new_page()
        await page.goto(url)
        ...
        await page.close()
"""
import asyncio
from typing import Optional


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


class BrowserSession:
    """Async context manager around a single Playwright browser + context.

    Pages are cheap to create from a context; the browser launch is the expensive
    bit, so we keep one alive for the whole aggregation run.
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None

    async def __aenter__(self):
        # Lazy import — playwright isn't always installed for static-only setups.
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch()
        self._context = await self._browser.new_context(user_agent=UA)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

    async def new_page(self):
        return await self._context.new_page()


class BrowserScraper:
    """Mixin/base for any scraper that needs a headless browser.

    Subclass and implement `async fetch_with_browser(session)`. The aggregator
    will pass in a BrowserSession instance. A sync `fetch()` wrapper is provided
    for compatibility with the existing pipeline.
    """
    name: str = ""
    region: str = ""
    source_url: str = ""

    async def fetch_with_browser(self, session: BrowserSession):
        raise NotImplementedError

    def fetch(self):
        # Synchronous fallback — runs its own one-off browser. Used for local
        # testing of an individual scraper outside the orchestrator.
        return asyncio.run(self._one_shot())

    async def _one_shot(self):
        async with BrowserSession() as session:
            return await self.fetch_with_browser(session)
