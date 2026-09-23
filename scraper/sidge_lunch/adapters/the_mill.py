"""The Mill pub, Mill Lane: a regular (not daily) menu, published as HTML.

The page's class names carry build hashes (``MenuItem-module-scss-module__Jn8USG__wrapper``),
so elements are matched on the stable part. ``data-dietary`` is "v" or "ve".
Only the "Main Menu" tab is read; drinks and spritz menus are skipped. The menu
is reported as today's, since it's what the pub serves every day.
"""

from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import clean, parse_price

_DIETARY = {"v": ["vegetarian"], "ve": ["vegan"]}


def _find(el, module: str, part: str):
    return el.select(f'[class*="{module}-module"][class*="__{part}"]')


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    panel = next(
        (p for p in soup.select('[role="tabpanel"]')
         if (h := p.find("h2")) and clean(h.get_text()).lower() == "main menu"),
        None,
    )
    if panel is None:
        raise ValueError("no Main Menu tab on page")

    items = []
    for category in _find(panel, "MenuCategory", "wrapper"):
        heading = _find(category, "MenuCategory", "categoryTitle")
        cat = clean(heading[0].get_text()) if heading else None
        for el in _find(category, "MenuItem", "wrapper"):
            title = _find(el, "MenuItem", "title")
            if not title:
                continue
            price_el = title[0].find("span")
            price_text = clean(price_el.get_text()) if price_el else None
            if price_el:
                price_el.extract()
            desc = _find(el, "MenuItem", "desc")
            price = parse_price(price_text)
            items.append(MenuItem(
                name=clean(title[0].get_text()),
                description=clean(desc[0].get_text()) or None if desc else None,
                category=cat,
                price=price,
                price_text=f"£{price.amount:.2f}" if price else None,
                dietary=list(_DIETARY.get(el.get("data-dietary", ""), [])),
            ))
    if not items:
        raise ValueError("Main Menu tab has no items")
    return [Day(today, [Meal("Menu", items)])]
