"""Helpers shared by vendor adapters."""

from __future__ import annotations

import re

from ..schema import Price

_SPACE = re.compile(r"\s+")
_PRICE = re.compile(r"£\s*(\d*\.\d{1,2}|\d+)")  # "£4", "£4.50", and "£.95"

# Labels vendors put in dish names. Only explicit labels count: "(vegan)", "(V)",
# a leading "Vegan"/"Halal", or "(halal)". Never guess from ingredients.
_TAG_IN_PARENS = re.compile(r"\(\s*(vegan|vg|v|vegetarian|halal|gf|gluten[- ]free)\s*\)", re.I)
_LEADING_TAG = re.compile(r"^(vegan|halal)\b", re.I)
_TAG_NAMES = {
    "vegan": "vegan",
    "vg": "vegan",
    "v": "vegetarian",
    "vegetarian": "vegetarian",
    "halal": "halal",
    "gf": "gluten-free",
    "gluten-free": "gluten-free",
    "gluten free": "gluten-free",
}

# Vendor wording → schema allergen names.
_ALLERGEN_WORDS = {
    "celery": "celery",
    "gluten": "gluten",
    "cereals containing gluten": "gluten",
    "wheat": "gluten",
    "crustaceans": "crustaceans",
    "crustacean": "crustaceans",
    "egg": "eggs",
    "eggs": "eggs",
    "fish": "fish",
    "lupin": "lupin",
    "lupen": "lupin",
    "milk": "milk",
    "dairy": "milk",
    "molluscs": "molluscs",
    "mollusc": "molluscs",
    "mustard": "mustard",
    "nuts": "nuts",
    "tree nuts": "nuts",
    "peanuts": "peanuts",
    "peanut": "peanuts",
    "sesame": "sesame",
    "soya": "soya",
    "soy": "soya",
    "sulphites": "sulphites",
    "sulphur dioxide": "sulphites",
    "sulphur dioxide/sulphites": "sulphites",
    "sesame seed": "sesame",
    "sesame seeds": "sesame",
    "contains nuts": "nuts",
}


def clean(text: str | None) -> str:
    return _SPACE.sub(" ", text or "").strip()


def parse_price(text: str | None) -> Price | None:
    m = _PRICE.search(text or "")
    return Price(float(m.group(1))) if m else None


def split_labels(name: str) -> tuple[str, list[str]]:
    """Pull explicit dietary labels out of a dish name. Returns (clean name, tags)."""
    tags = [_TAG_NAMES[m.group(1).lower()] for m in _TAG_IN_PARENS.finditer(name)]
    name = clean(_TAG_IN_PARENS.sub("", name)).strip(" ,-")
    m = _LEADING_TAG.match(name)
    if m:
        tags.append(_TAG_NAMES[m.group(1).lower()])
    return name, tags


def allergen(word: str) -> str | None:
    """Map a vendor's allergen wording to the schema name, ignoring detail like "Gluten (wheat)"."""
    word = re.sub(r"\s*\(.*?\)", "", clean(word)).lower()
    return _ALLERGEN_WORDS.get(word)


def split_sides(name: str) -> tuple[str, str] | None:
    """'Sides - Chips, peas' → ('Sides', 'Chips, peas')."""
    m = re.match(r"^sides?\s*[-–:]\s*(.+)$", name, re.I)
    return ("Sides", clean(m.group(1))) if m else None
