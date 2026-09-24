"""Clare Hall: a weekly menu published as a Microsoft Sway.

The Sway is drawn by JavaScript, so this vendor is fetched through a headless
browser (``"render": true`` in vendors.json) and the adapter reads the text a
visitor sees. Days are headed "Monday 21st September 2026", meals "LUNCH" and
"DINNER"; each dish is its own paragraph (long names wrap within it), with the
college's labels after a dash: "PB" (plant based), "V", "GF", "Halal". "GF
available (on request)" isn't a gluten-free dish, so it goes in the description.
A meal that is just "CLOSED FOR ..." is left out.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from ..schema import Day, Meal, MenuItem
from ._common import clean

_DAY = re.compile(r"^(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})$")
_MEAL = re.compile(r"^(BREAKFAST|BRUNCH|LUNCH|DINNER)$")
_LABELS = re.compile(r"\s+-\s*((?:PB|V|GF|Halal)\b.*)$", re.I)
_TAGS = {"pb": "vegan", "v": "vegetarian", "gf": "gluten-free", "halal": "halal"}
_END = re.compile(r"^(Our Sustainability Initiatives|Made with Microsoft Sway)$")


def _dish(text: str) -> MenuItem:
    m = _LABELS.search(text)
    if not m:
        return MenuItem(name=clean(text).rstrip(" -"))
    dietary, notes = [], []
    for part in (clean(p) for p in m.group(1).split(",")):
        tag = _TAGS.get(part.lower())
        if tag:
            dietary.append(tag)
        elif part:
            notes.append(part)  # e.g. "GF available on request"
    return MenuItem(name=clean(text[:m.start()]).rstrip(" -,"), description="; ".join(notes) or None, dietary=dietary)


def parse(text: str, today: date) -> list[Day]:
    days: list[Day] = []
    meal: Meal | None = None
    for block in re.split(r"\n\s*\n", text):
        line = clean(block.replace("\n", " "))
        if not line:
            continue
        if _END.match(line):
            break
        if m := _DAY.match(line):
            day = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").date()
            days.append(Day(day, []))
            meal = None
        elif not days:
            continue  # title and key, before the first day
        elif m := _MEAL.match(line):
            meal = Meal(m.group(1).title(), [])
            days[-1].meals.append(meal)
        elif meal is not None and not line.upper().startswith("CLOSED"):
            meal.items.append(_dish(line))
    for d in days:
        d.meals = [m for m in d.meals if m.items]
    days = [d for d in days if d.meals]
    if not days:
        raise ValueError("no days on the rendered menu")
    return days
