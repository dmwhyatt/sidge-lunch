"""Corpus Christi College cafeteria: /foodmenu/menu/?reference=1&date=YYYY-MM-DD.

One accordion panel per meal; in each, a table of section rows ("Plant Based",
"Vegetarian", "Meat/Fish 1", "Side dish", ...) followed by dish rows of name,
price and allergens. The section headings are the college's own labels, so
"Plant Based" dishes are recorded as vegan and "Vegetarian" ones as vegetarian.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import allergen, clean, parse_price

_SECTION_LABELS = {"plant based": ["vegan"], "vegan": ["vegan"], "vegetarian": ["vegetarian"]}


def _menu_date(soup: BeautifulSoup, today: date) -> date:
    m = re.search(r"\b(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\s+(\d{1,2})\s+([A-Za-z]+)", soup.get_text(" "))
    if not m:
        raise ValueError("no menu date on page")
    d = datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%d %B %Y").date()
    return d.replace(year=today.year + 1) if (today - d).days > 180 else d


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    day = _menu_date(soup, today)
    meals = []
    for table in soup.find_all("table"):
        heading = table.find_previous(string=re.compile(r"\S"))
        meal_name = clean(heading) if heading else "Menu"
        items, section = [], None
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if row.find("h3"):
                section = clean(row.find("h3").get_text())
                continue
            if len(cells) < 3 or not clean(cells[0].get_text()):
                continue
            price = parse_price(cells[1].get_text())
            label = _SECTION_LABELS.get(section.lower() if section else "", [])
            items.append(MenuItem(
                name=clean(cells[0].get_text()),
                category=re.sub(r"\s+\d+$", "", section) if section else None,  # "Meat/Fish 2" -> "Meat/Fish"
                price=price if price and price.amount > 0 else None,
                price_text=f"£{price.amount:.2f}" if price and price.amount > 0 else None,
                dietary=list(label),
                allergens=[a for w in cells[2].get_text().split(",") if (a := allergen(w))],
            ))
        if items:
            meals.append(Meal(meal_name, items))
    if not meals:
        raise ValueError("no menu tables on page")
    return [Day(day, meals)]
