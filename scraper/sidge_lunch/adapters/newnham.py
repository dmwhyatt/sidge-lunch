"""Newnham College Buttery: today's lunch only, one ``.food-item`` per dish.

Each dish has two prices: "Newnham card" and "All others". Most visitors from
the Sidgwick Site won't have a Newnham card, so ``price`` is the "All others"
price and the card price goes in the description.
"""

from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import allergen, clean, parse_price, split_labels


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one(".menu-day-container")
    if container is None:
        raise ValueError("no .menu-day-container on page")

    time = container.select_one(".menu-day-header time[datetime]")
    if time is None:
        raise ValueError("no menu date on page")
    day = date.fromisoformat(time["datetime"][:10])
    meal_name = clean(container.select_one(".menu-day-header h1").get_text()).removesuffix(" menu")

    items = []
    for row in container.select(".food-item"):
        name_el = row.select_one(".item-description h2")
        if name_el is None:  # the price column headings row
            continue
        name, dietary = split_labels(clean(name_el.get_text()))
        detail_el = row.select_one(".item-description p")
        lines = [clean(l) for l in detail_el.get_text("\n").split("\n")] if detail_el else []
        detail = "; ".join(filter(None, lines))
        prices = [parse_price(p.get_text()) for p in row.select(".item-price")]
        member, other = (prices + [None, None])[:2]

        # The detail line is either an allergen list ("Gluten, Eggs, Dairy") or free text.
        words = [w for w in detail.split(",") if w.strip()]
        allergens = [allergen(w) for w in words]
        if words and all(allergens):
            description = None
        else:
            allergens, description = [], detail or None

        if other and member:
            card = f"£{member.amount:.2f} with a Newnham card"
            description = f"{description}; {card}" if description else card
        items.append(MenuItem(
            name=name,
            description=description,
            price=other,
            price_text=f"£{other.amount:.2f}" if other else None,
            dietary=dietary,
            allergens=allergens,
        ))

    return [Day(day, [Meal(meal_name or "Lunch", items)])] if items else []
