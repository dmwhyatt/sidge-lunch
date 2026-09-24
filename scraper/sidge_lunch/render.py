"""Fetch a page the way a visitor's browser shows it, for menus drawn by JavaScript.

    python -m sidge_lunch.render URL        # print the rendered text

Opens the page in headless Chromium (Playwright), waits for the network to go
quiet, and returns the rendered HTML. robots.txt is checked first, as for every
other fetch. Playwright is only needed for vendors marked "render" in
vendors.json, so it is imported lazily.
"""

from __future__ import annotations

import sys
from urllib.parse import urlsplit

from .fetch import USER_AGENT, RobotsDisallowed, _robots

WAIT_MS = 60_000  # overall page load budget
SETTLE_MS = 3_000  # extra time after the network goes quiet, for late drawing


def render(url: str) -> str:
    parts = urlsplit(url)
    if not _robots(f"{parts.scheme}://{parts.netloc}").can_fetch(USER_AGENT, url):
        raise RobotsDisallowed(f"robots.txt disallows {url}")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=USER_AGENT, viewport={"width": 1280, "height": 2000})
            page.goto(url, wait_until="networkidle", timeout=WAIT_MS)
            page.wait_for_timeout(SETTLE_MS)
            return page.content()
        finally:
            browser.close()


def rendered_text(url: str) -> str:
    from playwright.sync_api import sync_playwright

    parts = urlsplit(url)
    if not _robots(f"{parts.scheme}://{parts.netloc}").can_fetch(USER_AGENT, url):
        raise RobotsDisallowed(f"robots.txt disallows {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=USER_AGENT, viewport={"width": 1280, "height": 2000})
            page.goto(url, wait_until="networkidle", timeout=WAIT_MS)
            page.wait_for_timeout(SETTLE_MS)
            return page.inner_text("body")
        finally:
            browser.close()


if __name__ == "__main__":
    print(rendered_text(sys.argv[1]))
