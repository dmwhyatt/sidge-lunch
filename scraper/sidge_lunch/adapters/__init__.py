"""One parser per vendor, keyed by vendor id (see data/vendors.json).

An adapter takes the fetched HTML and today's date (Europe/London) and returns
the days it could parse. Raise ``NotImplementedError`` until the adapter is
written; raise anything else when the page can't be parsed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from ..schema import Day
from . import clare_hall, darwin, newnham, queens, selwyn

Adapter = Callable[[str, date], list[Day]]

ADAPTERS: dict[str, Adapter] = {
    "selwyn": selwyn.parse,
    "newnham": newnham.parse,
    "clare-hall": clare_hall.parse,
    "darwin": darwin.parse,
    "queens": queens.parse,
}
