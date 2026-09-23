"""One parser per vendor, keyed by vendor id (see data/vendors.json).

Vendors marked ``link_only`` in vendors.json (e.g. Queens', whose page is behind
a bot check) have no adapter and are never fetched.

An adapter takes the fetched HTML and today's date (Europe/London) and returns
the days it could parse. Raise ``NotImplementedError`` until the adapter is
written; raise anything else when the page can't be parsed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from ..schema import Day
from . import darwin, newnham, selwyn

Adapter = Callable[[str, date], list[Day]]

ADAPTERS: dict[str, Adapter] = {
    "selwyn": selwyn.parse,
    "newnham": newnham.parse,
    "darwin": darwin.parse,
}
