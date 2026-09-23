"""Robinson College Garden Restaurant ("JCR Menu"): today's menu, one column per meal.

Within a column, a <strong> starts a section and dishes are separated by blank
lines. Icons after each dish carry the college's labels and allergens in their
alt text ("Vegetarian", "Vegan", "Milk", ...). Prices aren't per dish; the
"Notes" block (e.g. a fixed meal price) becomes the meal's note.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup, NavigableString, Tag

from ..schema import Day, Meal, MenuItem
from ._common import allergen, clean

_LABELS = {"vegetarian": "vegetarian", "vegan": "vegan", "halal": "halal"}


def _dishes(item: Tag) -> list[MenuItem]:
    dishes: list[MenuItem] = []
    name: list[str] = []
    dietary: list[str] = []
    allergens: list[str] = []
    section = None
    breaks = 0

    def flush():
        nonlocal name, dietary, allergens
        text = clean(" ".join(name))
        if text:
            dishes.append(MenuItem(name=text, category=section, dietary=dietary, allergens=allergens))
        name, dietary, allergens = [], [], []

    for el in item.descendants:
        if isinstance(el, Tag) and el.name == "strong":
            flush()
            section = clean(el.get_text())
        elif isinstance(el, Tag) and el.name == "img":
            alt = clean(el.get("alt", ""))
            if label := _LABELS.get(alt.lower()):
                dietary.append(label)
            elif a := allergen(alt):
                allergens.append(a)
        elif isinstance(el, Tag) and el.name == "br":
            breaks += 1
            if breaks >= 2:
                flush()
        elif isinstance(el, NavigableString) and el.parent.name != "strong" and el.strip():
            breaks = 0
            name.append(el)
    flush()
    return dishes


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    header = soup.find(string=re.compile(r"Menus for \w{3} \d{1,2} \w{3} \d{4}"))
    if header is None:
        raise ValueError("no menu date on page")
    day = datetime.strptime(re.search(r"\w{3} \d{1,2} \w{3} \d{4}", header).group(), "%a %d %b %Y").date()

    text = clean(soup.get_text(" "))
    notes = re.search(r"\bNotes\b(.+?)\bKey\b", text)
    meals = []
    for col in soup.select(".menuColumn"):
        heading = col.find("h3")
        if heading is None:
            continue
        name = re.sub(r"^On Offer for ", "", clean(heading.get_text()))
        items = [d for it in col.select(".menuItem") for d in _dishes(it)]
        if items:
            meals.append(Meal(name, items, note=clean(notes.group(1)) if notes else None))
    if not meals:
        raise ValueError("no menu columns on page")
    return [Day(day, meals)]
