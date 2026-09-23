"""Clare Hall: the menu is a Microsoft Sway, which is drawn by JavaScript.

The HTML the server sends has no menu text in it, so an HTML-only adapter
can't read it.
"""

from __future__ import annotations

from datetime import date

from ..schema import Day


def parse(html: str, today: date) -> list[Day]:
    raise NotImplementedError("menu is a JavaScript-rendered Sway, not HTML")
