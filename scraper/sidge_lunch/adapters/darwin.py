"""Darwin College servery: tabbed weekly menus, one table per meal, allergen codes per dish.

Tabs are "This week", "Next week", then "w/c 5th Oct" and so on. Only the first
two are read: later weeks are provisional. Day headings are weekday names only,
so dates come from the week the tab refers to.
"""

from __future__ import annotations

from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import allergen, clean, parse_price, split_labels, split_sides

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_TAB_OFFSETS = {"this week": 0, "next week": 7}


def _meal(table) -> Meal | None:
    heading = table.select_one("thead th")
    name = clean(heading.get_text()) if heading else "Menu"
    items, notes = [], []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        dish = clean(cells[0].get_text())
        if not dish:
            continue
        codes = row.select(".menus-allergenlist li[title]")
        price = parse_price(cells[-1].get_text()) if len(cells) > 1 else None
        if not codes and price is None and dish.lower().startswith("see "):
            notes.append(dish)  # e.g. "See daily specials board for more"
            continue
        if sides := split_sides(dish):
            dish_name, description, category = *sides, "Sides"
        else:
            dish_name, description, category = dish, None, None
        dish_name, dietary = split_labels(dish_name)
        items.append(MenuItem(
            name=dish_name,
            description=description,
            category=category,
            price=price,
            price_text=f"£{price.amount:.2f}" if price else None,
            dietary=dietary,
            allergens=[a for li in codes if (a := allergen(li["title"]))],
        ))
    return Meal(name, items, note="; ".join(notes) or None) if items else None


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    tabs = soup.select(".menus-tabs .menus-tab[data-target]")
    if not tabs:
        raise ValueError("no menu tabs on page")
    monday = today - timedelta(days=today.weekday())

    days = []
    for tab in tabs:
        offset = _TAB_OFFSETS.get(clean(tab.get_text()).lower())
        panel = soup.find(id=tab["data-target"])
        if offset is None or panel is None:
            continue
        current: tuple[date, list[Meal]] | None = None
        for el in panel.find_all(["h3", "table"]):
            if el.name == "h3":
                weekday = clean(el.get_text()).lower()
                if weekday not in _WEEKDAYS:
                    raise ValueError(f"unexpected day heading {weekday!r}")
                current = (monday + timedelta(days=offset + _WEEKDAYS.index(weekday)), [])
                days.append(current)
            elif current is not None and (meal := _meal(el)):
                current[1].append(meal)

    return [Day(d, meals) for d, meals in days if meals]
