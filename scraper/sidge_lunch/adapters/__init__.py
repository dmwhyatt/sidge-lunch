"""One parser per vendor, keyed by vendor id (see data/vendors.json).

Vendors marked ``link_only`` in vendors.json have no adapter and are never fetched.

An adapter takes the fetched HTML and today's date (Europe/London) and returns
the days it could parse. Raise ``NotImplementedError`` until the adapter is
written; raise anything else when the page can't be parsed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from ..schema import Day
from . import churchill, clare_hall, corpus, darwin, newnham, queens, robinson, selwyn, st_johns, the_mill, trinity

Adapter = Callable[[str, date], list[Day]]
# Adapters that follow a link from the page to a document (e.g. a weekly PDF) and so
# also need to fetch bytes: parse(html, today, get_bytes).
DocumentAdapter = Callable[[str, date, Callable[[str], bytes]], list[Day]]

ADAPTERS: dict[str, Adapter] = {
    "selwyn": selwyn.parse,
    "newnham": newnham.parse,
    "darwin": darwin.parse,
    "the-mill": the_mill.parse,
    "st-johns": st_johns.parse,
    "robinson": robinson.parse,
    "churchill": churchill.parse,
    "corpus": corpus.parse,
    "clare-hall": clare_hall.parse,
    "queens": queens.parse,  # reads rendered text: "render": true in vendors.json
}

DOCUMENT_ADAPTERS: dict[str, DocumentAdapter] = {
    "trinity": trinity.parse,
}
