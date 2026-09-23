"""St John's College Buttery: menu.joh.cam/today.

The page shows the day's current and coming sittings (so lunch drops off in the
afternoon). Each dish has vendor labels ("Vegan", "Vegetarian") and a
"Contains:" list of allergens. No prices are published.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import allergen, clean

_LABELS = {"vegan": "vegan", "vegetarian": "vegetarian", "halal": "halal",
           "gluten free": "gluten-free", "dairy free": "dairy-free"}


def _menu_date(soup: BeautifulSoup, today: date) -> date:
    m = re.search(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})\s+([A-Za-z]+)",
                  soup.get_text(" "))
    if not m:
        raise ValueError("no menu date on page")
    d = datetime.strptime(f"{m.group(2)} {m.group(3)} {today.year}", "%d %B %Y").date()
    return d.replace(year=today.year + 1) if (today - d).days > 180 else d


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    day = _menu_date(soup, today)
    meals = []
    for card in soup.select("div.rounded.bg-white"):
        heading = card.find("p", class_="text-center")
        if heading is None:
            continue
        items, category = [], None
        for el in card.find_all(["p", "div"], recursive=False):
            classes = el.get("class", [])
            if el.name == "p" and "border-b" in classes:
                category = clean(el.get_text())
            elif el.name == "div" and "flex-col" in classes:
                name = el.find("p")
                if name is None:
                    continue
                dietary, allergens = [], []
                for tag in el.select("span"):
                    text = clean(tag.get_text())
                    if "ring" in tag.get("class", []):
                        if label := _LABELS.get(text.lower()):
                            dietary.append(label)
                    elif a := allergen(text):
                        allergens.append(a)
                items.append(MenuItem(name=clean(name.get_text()), category=category,
                                      dietary=dietary, allergens=allergens))
        if items:
            meals.append(Meal(clean(heading.get_text()), items))
    if not meals:
        raise ValueError("no meals on page")
    return [Day(day, meals)]
