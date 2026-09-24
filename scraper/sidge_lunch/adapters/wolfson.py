"""Wolfson College cafeteria: a page listing the next few days.

Each day is an <h3> ("Thursday 24 September 2026") followed by a
ul.food-menu__list with one <li> per meal (Breakfast, Lunch, Dinner). A dish is
a .single-food-menu-item: its <h4> holds a course span ("Main Course", empty at
breakfast) and the dish name, then the allergens the college lists, then a
student price and an "others" price.

The site sits behind Sucuri. GitHub's runners were served the real page when
this was written; if they are challenged, fetch() raises BotCheck and the last
good menu is kept.
"""

from __future__ import annotations

from datetime import date, datetime

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import allergen, clean, parse_price, split_labels


def _prices(item) -> dict[str, float]:
    prices = {}
    for pair in item.select(".food-menu__prices > span"):
        label, *rest = [clean(s.get_text()) for s in pair.find_all("span")]
        price = parse_price(" ".join(rest))
        if price:
            prices[label.lower()] = price
    return prices


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    days = []
    for heading in soup.select(".food-menu .view-content > h3"):
        try:
            day = datetime.strptime(clean(heading.get_text()), "%A %d %B %Y").date()
        except ValueError:
            continue
        listing = heading.find_next_sibling("ul")
        if listing is None or "food-menu__list" not in listing.get("class", []):
            continue
        meals = []
        for meal in listing.find_all("li", recursive=False):
            title = meal.select_one(".collapse__top h4")
            items = []
            for item in meal.select(".single-food-menu-item"):
                spans = [clean(s.get_text()) for s in item.select("h4 span")]
                course, name = (spans[0] or None, spans[-1]) if len(spans) > 1 else (None, spans[0] if spans else "")
                name, dietary = split_labels(name)
                if not name:
                    continue
                prices = _prices(item)
                other, student = prices.get("others"), prices.get("student")
                items.append(MenuItem(
                    name=name,
                    description=f"£{student.amount:.2f} for students" if student else None,
                    category=course,
                    price=other,
                    price_text=f"£{other.amount:.2f}" if other else None,
                    dietary=dietary,
                    allergens=[a for w in item.select(".field--name-field-allergy-information .field__item")
                               if (a := allergen(w.get_text()))],
                ))
            if title and items:
                meals.append(Meal(clean(title.get_text()), items))
        if meals:
            days.append(Day(day, meals))
    if not days:
        raise ValueError("no days on the cafeteria menu")
    return days
