"""Queens' College dining hall.

The menu page sits behind a SiteGround bot check (a captcha redirect) that
turns away automated visitors, so the scraper can't read it. Not worked around
on purpose; the site links to the page instead.
"""

from __future__ import annotations

from datetime import date

from ..schema import Day


def parse(html: str, today: date) -> list[Day]:
    raise NotImplementedError("page is behind a bot check")
