"""The common menu format every adapter produces.

Adapters return a list of ``Day`` objects. Only record dietary tags the vendor
itself publishes; never infer them from dish names.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Literal

Dietary = Literal["vegan", "vegetarian", "gluten-free", "dairy-free", "halal"]
DIETARY_TAGS: frozenset[str] = frozenset(Dietary.__args__)  # type: ignore[attr-defined]


@dataclass
class Price:
    amount: float
    currency: str = "GBP"


@dataclass
class MenuItem:
    name: str
    description: str | None = None
    category: str | None = None  # e.g. "Main", "Soup", "Dessert"
    price: Price | None = None  # None means "price not listed"
    price_text: str | None = None  # the vendor's own wording, e.g. "£4.50" or "£2.10/100g"
    dietary: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        unknown = set(self.dietary) - DIETARY_TAGS
        if unknown:
            raise ValueError(f"unknown dietary tags {sorted(unknown)} on {self.name!r}")
        if "vegan" in self.dietary and "vegetarian" not in self.dietary:
            self.dietary.append("vegetarian")
        self.dietary.sort()


@dataclass
class Meal:
    name: str  # e.g. "Lunch", "Brunch", "Dinner"
    items: list[MenuItem]
    service: str | None = None  # serving times as published, e.g. "12:00–13:45"


@dataclass
class Day:
    date: date
    meals: list[Meal]

    def to_json(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        return d
