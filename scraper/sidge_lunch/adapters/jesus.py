"""Jesus College Cafeteria: the college's lunch and dinner menu boards for one day.

The cafeteria lunch and dinner pages embed apps.jesus.cam.ac.uk/foodmenuview/,
whose script loads digiboard.php?event_id=<board>&date=YYYY-MM-DD: board 1 is
lunch, board 2 dinner. vendors.json fetches the lunch board; this adapter
fetches the dinner board for the same day. Each board is a table: "Cafeteria
Lunch" and "Monday 26th October" in <h2>s, a course in each <h4> row, then one
tr.fm-item per dish with its price, the college's dietary labels
(.fm-requirement) and allergens (.fm-allergen). Days without a menu say "No
menu available for the selected date". Both boards are published weeks ahead.

The traffic-light health dots are left out. Dishes marked sold out are kept:
a place is only scraped until its menu for the day is in.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..schema import DIETARY_TAGS, Day, Meal, MenuItem
from ._common import allergen, clean, parse_price

DINNER = "https://apps.jesus.cam.ac.uk/foodmenuview/digiboard.php?event_id=2&date={date}"
_DAY = re.compile(r"^[A-Za-z]+day\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)$")


def _date(text: str, today: date) -> date:
    m = _DAY.match(text)
    if not m:
        raise ValueError(f"can't read menu date from {text!r}")
    d = datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%d %B %Y").date()
    if (d - today).days > 180:  # a December menu read in January, or similar
        d = d.replace(year=today.year - 1)
    elif (today - d).days > 180:
        d = d.replace(year=today.year + 1)
    return d


def parse_board(html: str, today: date) -> tuple[date, Meal] | None:
    """One board: its day and meal, or None when it says there's no menu that day."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.fm-menu-courses")
    if table is None:
        if "No menu available" in soup.get_text():
            return None
        raise ValueError("no menu table on page")

    headings = [clean(h.get_text()) for h in table.find_all("h2")]
    day = next((_date(h, today) for h in headings if _DAY.match(h)), None)
    if day is None:
        raise ValueError(f"no menu date in headings {headings!r}")
    meal_name = next((h.removeprefix("Cafeteria ") for h in headings if not _DAY.match(h)), "Lunch")

    items, course = [], None
    for row in table.find_all("tr"):
        if heading := row.find("h4"):
            course = clean(heading.get_text()) or None
            continue
        label = row.select_one(".fm-item-label")
        if label is None:
            continue
        name = clean(label.get_text())
        price_el = row.select_one(".fm-item-price")
        price = parse_price(price_el.get_text() if price_el else None)
        dietary = [t for d in row.select(".fm-requirement") if (t := clean(d.get("title")).lower()) in DIETARY_TAGS]
        words = [clean(d.get("title")) for d in row.select(".fm-allergen")]
        unknown = [w for w in words if allergen(w) is None]
        items.append(MenuItem(
            name=name,
            # An allergen we can't map is shown in words rather than dropped.
            description=f"Also contains: {', '.join(unknown)}" if unknown else None,
            category=course,
            price=price,
            price_text=f"£{price.amount:.2f}" if price else None,
            dietary=dietary,
            allergens=[a for w in words if (a := allergen(w))],
        ))
    if not items:
        raise ValueError("no dishes on the menu board")
    return day, Meal(meal_name, items)


def parse(html: str, today: date, get_bytes: Callable[[str], bytes]) -> list[Day]:
    dinner = get_bytes(DINNER.format(date=today.isoformat())).decode("utf-8", errors="replace")
    days: dict[date, list[Meal]] = {}
    for board in (parse_board(html, today), parse_board(dinner, today)):
        if board:
            days.setdefault(board[0], []).append(board[1])
    return [Day(d, meals) for d, meals in sorted(days.items())]
