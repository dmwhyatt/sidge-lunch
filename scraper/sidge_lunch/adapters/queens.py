"""Queens' College Dining Hall: a weekly menu page.

"Week Commencing 21st September" heads the week; each day is an accordion
entry (<dt> weekday, <dd> content) with "Monday Lunch" / "Monday Dinner"
headings in <strong>, each followed by a list of dishes. The college's labels
lead a dish: "(Vegan)", "(V)", "(Halal)". A meal heading with no list after it
(e.g. "Saturday Brunch") is left out.

The site sits behind SiteGround, which challenges some networks with a CAPTCHA;
GitHub's runners are served the page normally. If that changes, this adapter
fails and the site says it couldn't read the menu. Nothing gets round the check.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import clean, split_labels

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _week_start(soup: BeautifulSoup, today: date) -> date:
    heading = soup.find(string=re.compile(r"Week Commencing", re.I))
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(\d{4}))?", heading or "")
    if not m:
        raise ValueError("no 'Week Commencing' date on page")
    year = int(m.group(3)) if m.group(3) else today.year
    start = datetime.strptime(f"{m.group(1)} {m.group(2)} {year}", "%d %B %Y").date()
    if not m.group(3) and (today - start).days > 180:  # a January page seen in December, or similar
        start = start.replace(year=year + 1)
    return start


def parse(html: str, today: date) -> list[Day]:
    soup = BeautifulSoup(html, "lxml")
    start = _week_start(soup, today)
    monday = start - timedelta(days=start.weekday())
    days = []
    for dt in soup.select("dl.accordion-wrapper dt"):
        weekday = clean(dt.get_text()).lower()
        dd = dt.find_next_sibling("dd")
        if weekday not in _WEEKDAYS or dd is None:
            continue
        meals: list[Meal] = []
        for heading in dd.find_all("strong"):
            if heading.find_parent("li"):
                continue  # a dish label like "(Vegan)", not a meal heading
            name = clean(heading.get_text())
            name = re.sub(rf"^{weekday}\s+", "", name, flags=re.I).title() or "Menu"
            block = heading.find_parent("p") or heading
            listing = block.find_next_sibling()
            if listing is None or listing.name != "ul":
                continue
            items = []
            for li in listing.find_all("li", recursive=False):
                dish, dietary = split_labels(clean(li.get_text(" ")))
                if dish:
                    items.append(MenuItem(name=dish, dietary=dietary))
            if items:
                meals.append(Meal(name, items))
        if meals:
            days.append(Day(monday + timedelta(days=_WEEKDAYS.index(weekday)), meals))
    if not days:
        raise ValueError("no days on the weekly menu")
    return days
