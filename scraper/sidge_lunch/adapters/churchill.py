"""Churchill College Dining Hall: a weekly page with one table per day.

The first row of a day's table is "<Weekday> 23rd Sep | Lunch | Dinner"; the
second has opening times, then the lunch and dinner dishes, one per line,
starting "*". Labels in brackets are the college's own: (V), (VG), (H).
Days whose menu is just "*" haven't been published yet and are skipped.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import clean

_LABEL = re.compile(r"\((VG|V|H|GF)\)", re.I)
_LABELS = {"vg": "vegan", "v": "vegetarian", "h": "halal", "gf": "gluten-free"}


def _date(text: str, today: date) -> date:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})", text)
    if not m:
        raise ValueError(f"can't read date from {text!r}")
    d = datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%d %b %Y").date()
    return d.replace(year=today.year + 1) if (today - d).days > 180 else d


def _dishes(cell) -> list[MenuItem]:
    items = []
    for line in cell.get_text("\n").split("\n"):
        line = clean(line).lstrip("*").strip()
        if not line:
            continue
        dietary = [_LABELS[m.lower()] for m in _LABEL.findall(line)]
        items.append(MenuItem(name=clean(_LABEL.sub("", line)), dietary=dietary))
    return items


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    days = []
    for table in soup.select("figure.wp-block-table table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        head = [clean(td.get_text(" ")) for td in rows[0].find_all("td")]
        if not head or not re.match(r"(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day", head[0]):
            continue
        day = _date(head[0], today)
        cells = rows[1].find_all("td")
        meals = []
        for name, cell in zip(head[1:], cells[1:]):
            items = _dishes(cell)
            if items:
                meals.append(Meal(name, items, service="12:00–14:00" if name.lower() == "lunch" else None))
        if meals:
            days.append(Day(day, meals))
    if not days and not soup.find(string=re.compile("Week commencing")):
        raise ValueError("no weekly menu on page")
    return days
