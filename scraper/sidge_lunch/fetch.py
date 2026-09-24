"""Polite HTTP fetching: identifiable User-Agent and robots.txt."""

from __future__ import annotations

import urllib.robotparser
from functools import lru_cache
from urllib.parse import urlsplit

import requests

USER_AGENT = (
    "sidge-lunch/0.1 (unofficial lunch menu aggregator; "
    "+https://github.com/dmwhyatt/sidge-lunch)"
)
TIMEOUT = 20


class RobotsDisallowed(Exception):
    pass


class BotCheck(Exception):
    """The site answered with a bot check (CAPTCHA or JavaScript challenge) instead of the page.
    It is reported, never worked around."""


# Markers of hosting providers' bot checks in the stub page they serve instead.
_BOT_CHECKS = {
    "/.well-known/sgcaptcha/": "SiteGround CAPTCHA",
    "sucuri_cloudproxy_js": "Sucuri JavaScript challenge",
}


def _check_for_bot_check(url: str, body: bytes) -> None:
    head = body[:4000].decode("utf-8", errors="replace")
    for marker, name in _BOT_CHECKS.items():
        if marker in head:
            raise BotCheck(f"{name} served instead of {url}; not worked around")


@lru_cache(maxsize=None)
def _robots(origin: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        rp.parse(r.text.splitlines() if r.ok else [])
    except requests.RequestException:
        rp.parse([])
    return rp


def fetch_bytes(url: str) -> bytes:
    parts = urlsplit(url)
    if not _robots(f"{parts.scheme}://{parts.netloc}").can_fetch(USER_AGENT, url):
        raise RobotsDisallowed(f"robots.txt disallows {url}")
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    _check_for_bot_check(url, r.content)
    return r.content


def fetch(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")
