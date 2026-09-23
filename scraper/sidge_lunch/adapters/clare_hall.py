from __future__ import annotations

from datetime import date

from ..schema import Day


def parse(html: str, today: date) -> list[Day]:
    raise NotImplementedError("adapter not written yet")
