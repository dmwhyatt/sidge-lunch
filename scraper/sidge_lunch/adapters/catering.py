"""University Catering Services cafés with a weekly menu (West Hub Canteen, Greenwich House Café).

The café's page has "Week commencing 21st September 2026" in an <h4>, then each
weekday in its own paragraph followed by a list of that day's hot dishes.
Greenwich House ends each day with "Sides: ...". No prices, dietary labels or
allergens are published, beyond words like "Vegan" at the start of a dish name.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import clean, split_labels, split_sides

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _week_start(soup: BeautifulSoup) -> date:
    heading = soup.find(string=re.compile(r"Week commencing", re.I))
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", heading or "")
    if not m:
        raise ValueError("no 'Week commencing' date on page")
    return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y").date()


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    start = _week_start(soup)
    monday = start - timedelta(days=start.weekday())
    days = []
    for para in soup.find_all("p"):
        weekday = clean(para.get_text()).lower()
        listing = para.find_next_sibling()
        if weekday not in _WEEKDAYS or listing is None or listing.name != "ul":
            continue
        items = []
        for li in listing.find_all("li", recursive=False):
            dish = clean(li.get_text(" "))
            if sides := split_sides(dish):
                name, description, category = *sides, "Sides"
            else:
                name, description, category = dish, None, None
            name, dietary = split_labels(name)
            if name:
                items.append(MenuItem(name=name, description=description, category=category, dietary=dietary))
        if items:
            days.append(Day(monday + timedelta(days=_WEEKDAYS.index(weekday)), [Meal("Lunch", items)]))
    if not days:
        raise ValueError("no days on the weekly menu")
    return days
