"""Trinity College servery: a weekly PDF, linked from a stable download page.

``parse`` gets the download page; it finds this week's PDF link and fetches it
with ``get_bytes``. The PDF's first table has one column per day: a header row
("MONDAY 14th September", ...) and a menu row. In each menu cell, "LUNCH",
"BRUNCH", "DINNER" start a meal and "NO LUNCH"/"NO DINNER" mean that meal isn't
served (the lines after it are skipped). Section lines end with ":" ("Mains:").

Dish names wrap inside narrow columns. A line continues on the next one when
the next line's first word wouldn't have fitted and the text agrees (the line
ends in "–", "&", ",", "with", ..., or the next line is one word or starts in
lower case); a line of labels only, like "(vegan)", belongs to the dish above.
This is a heuristic: an occasional long dish name may still show as two. Labels are the college's own: (v), (vegan), GF, and
(wf/df), of which only "df" (dairy-free) maps to a schema tag.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from datetime import date, datetime

import pdfplumber
from bs4 import BeautifulSoup

from ..schema import Day, Meal, MenuItem
from ._common import clean

_MEAL = re.compile(r"^(NO\s+)?(LUNCH|BRUNCH|DINNER)$", re.I)
_SECTION = re.compile(r"^([A-Za-z][A-Za-z ]+):\s*(.*)$")
_LABEL = re.compile(r"\((v|vegan|vg|wf/df|df|gf)\)|^GF\s+", re.I)
_LABELS_ONLY = re.compile(r"^(\s*\((v|vegan|vg|wf/df|df|gf)\)\s*)+$", re.I)


def _labels(text: str) -> list[str]:
    tags = []
    for m in _LABEL.finditer(text):
        label = (m.group(1) or "gf").lower()
        tags += {"v": ["vegetarian"], "vegan": ["vegan"], "vg": ["vegan"], "gf": ["gluten-free"],
                 "df": ["dairy-free"], "wf/df": ["dairy-free"]}[label]
    return tags


def _pdf_link(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        if "wpdmdl=" in a["href"] and ".pdf" in a["href"].lower():
            return a["href"]
    raise ValueError("no PDF link on the download page")


def _header_date(text: str, today: date) -> date:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)", text)
    if not m:
        raise ValueError(f"can't read date from {text!r}")
    d = datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%d %B %Y").date()
    return d.replace(year=today.year + 1) if (today - d).days > 180 else d


_CONNECTOR = re.compile(r"(–|-|&|,|\b(with|and|of|in|on|or))$", re.I)


def _wraps(prev: dict, nxt: dict, first_word_width: float, right: float) -> bool:
    """Whether ``nxt`` continues ``prev``: the next word didn't fit on the line, and the text agrees."""
    if (prev["x1"] + first_word_width + 3) <= right:
        return False  # the next word would have fitted, so the line ended on purpose
    text, following = clean(prev["text"]), clean(nxt["text"])
    words = clean(_LABEL.sub(" ", following)).split()
    return bool(_CONNECTOR.search(text) or following[:1].islower() or len(words) == 1)


def _cell_lines(page, bbox) -> list[str]:
    """Text lines in a cell, with wrapped dish names joined."""
    cell = page.crop(bbox)
    lines = [ln for ln in cell.extract_text_lines() if clean(ln["text"])]
    if not lines:
        return []
    padding = min(ln["x0"] for ln in lines) - bbox[0]
    right = bbox[2] - padding
    out: list[str] = []
    for i, line in enumerate(lines):
        text = clean(line["text"])
        heading = _MEAL.match(text) or _SECTION.match(text)
        prev = lines[i - 1] if i else None
        first = line["chars"][0]["x0"], next(
            (c["x0"] for c in line["chars"] if c["text"] == " "), line["x1"])
        joins = out and not heading and prev is not None and not _MEAL.match(clean(prev["text"])) and (
            _LABELS_ONLY.match(text) or _wraps(prev, line, first[1] - first[0], right))
        if joins:
            out[-1] = f"{out[-1]} {text}"
        else:
            out.append(text)
    return out


def _meals(lines: list[str]) -> list[Meal]:
    meals: list[Meal] = []
    current: list[MenuItem] | None = None
    section = None
    for line in lines:
        if m := _MEAL.match(line):
            current = None if m.group(1) else []
            if current is not None:
                meals.append(Meal(m.group(2).title(), current))
            section = None
            continue
        if current is None:
            continue  # not served, or before the first meal heading
        if m := _SECTION.match(line):
            section = m.group(1).strip()
            rest = m.group(2).strip()
            if section.lower() == "starter soup":
                section = "Soup"
                soup_labels = _labels(rest)
                current.append(MenuItem(name="Soup", category=section, dietary=soup_labels))
            continue
        name = clean(_LABEL.sub(" ", line)).strip(" -–,")
        if not name:
            continue
        if section == "Soup" and current and current[-1].name == "Soup":
            soup = current.pop()  # the soup's name comes on the line after "Starter Soup: (v)"
            current.append(MenuItem(name=f"Soup: {name}", category="Soup", dietary=soup.dietary + _labels(line)))
            continue
        current.append(MenuItem(name=name, category=section, dietary=_labels(line)))
    return [m for m in meals if m.items]


def parse_pdf(data: bytes, today: date) -> list[Day]:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        tables = page.find_tables()
        if not tables:
            raise ValueError("no menu table in PDF")
        rows = tables[0].rows
        if len(rows) < 2:
            raise ValueError("menu table has no menu row")
        days = []
        for head, body in zip(rows[0].cells, rows[1].cells):
            if head is None or body is None:
                continue
            day = _header_date(clean(page.crop(head).extract_text() or ""), today)
            meals = _meals(_cell_lines(page, body))
            if meals:
                days.append(Day(day, meals))
    return days


def parse(html: str, today: date, get_bytes: Callable[[str], bytes]) -> list[Day]:
    return parse_pdf(get_bytes(_pdf_link(html)), today)
