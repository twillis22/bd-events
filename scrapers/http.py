"""Shared HTTP helpers."""
import time

import requests
from typing import Optional

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get(url: str, timeout: int = 20, **kwargs) -> Optional[requests.Response]:
    """GET with backoff retry on transient errors. Returns None on hard failure."""
    last_err = None
    for attempt in range(3):
        if attempt:
            time.sleep(2 * attempt)  # 2s, 4s — flaky association hosts (HL, ASP)
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, **kwargs)
            if r.status_code == 200:
                return r
            if 500 <= r.status_code < 600:
                last_err = f"HTTP {r.status_code}"
                continue
            return r  # return non-200 so caller can decide
        except requests.RequestException as exc:
            last_err = str(exc)
    raise RuntimeError(f"GET failed after retries: {url} ({last_err})")
