"""Selwyn College Hall: today's lunch and dinner as numbered lists. No prices."""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import clean, split_labels

_NUMBERED = re.compile(r"^\d+\.\s*(.+)$")
_NOTE = re.compile(r"^\((.+)\)$")


def _menu_date(text: str) -> date:
    # "Menus for Wednesday 23rd September 2026"
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})", text)
    if not m:
        raise ValueError(f"can't read menu date from {text!r}")
    return datetime.strptime(" ".join(m.groups()), "%d %B %Y").date()


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    header = soup.select_one("#menuhdr")
    if header is None:
        raise ValueError("no #menuhdr on page")
    day = _menu_date(clean(header.get_text()))

    meals = []
    for block in soup.select(".hallmenu"):
        heading = block.select_one(".submenuhdr")
        meal_name = clean(heading.get_text()) if heading else "Menu"
        if heading:
            heading.extract()
        lines = [clean(line) for line in block.get_text("\n").split("\n")]
        items, notes = [], []
        for line in filter(None, lines):
            if m := _NUMBERED.match(line):
                name, dietary = split_labels(m.group(1))
                items.append(MenuItem(name=name, dietary=dietary))
            elif m := _NOTE.match(line):
                notes.append(m.group(1)[0].upper() + m.group(1)[1:])
            else:  # the unnumbered line lists the sides
                items.append(MenuItem(name="Sides", description=line, category="Sides"))
        if items:
            meals.append(Meal(meal_name, items, note="; ".join(notes) or None))

    return [Day(day, meals)] if meals else []
