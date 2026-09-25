"""Fetch every vendor's menu and update data/menus.json.

The file is rewritten only when something meaningful changes (menu content,
status, or a day rolling off), so the scheduled workflow commits rarely.

    python -m sidge_lunch.run [--data-dir ../data] [--only selwyn]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .adapters import ADAPTERS, DOCUMENT_ADAPTERS
from .fetch import fetch, fetch_bytes

LONDON = ZoneInfo("Europe/London")
log = logging.getLogger("sidge_lunch")


def content_hash(days: list[dict]) -> str:
    return hashlib.sha256(json.dumps(days, sort_keys=True).encode()).hexdigest()[:16]


def current_days(days: list[dict], today: date) -> list[dict]:
    return [d for d in days if d["date"] >= today.isoformat()]


def update_vendor(
    vendor: dict,
    prev: dict | None,
    today: date,
    now: datetime,
    fetcher: Callable[[str], str] = fetch,
    byte_fetcher: Callable[[str], bytes] = fetch_bytes,
) -> dict:
    prev = prev or {}
    entry = {
        "source_url": vendor["menu_url"],
        "status": "ok",
        "error": None,
        "updated_at": prev.get("updated_at"),
        "content_hash": prev.get("content_hash"),
        "days": current_days(prev.get("days", []), today),
    }
    if vendor["id"] in DOCUMENT_ADAPTERS:
        doc_adapter = DOCUMENT_ADAPTERS[vendor["id"]]
        adapter = lambda html, day: doc_adapter(html, day, byte_fetcher)  # noqa: E731
    else:
        adapter = ADAPTERS.get(vendor["id"])
    if adapter is None:
        return entry | {"status": "unsupported", "error": "no adapter registered"}

    try:
        # fetch_url, if set, is the page the adapter reads (it may differ from the page people are sent to);
        # "{date}" in it becomes today's date, and "{now}" the time of this run, for pages whose cache
        # (e.g. Sucuri's) would otherwise hand the scraper a copy from a previous day.
        url = (vendor.get("fetch_url", vendor["menu_url"])
               .replace("{date}", today.isoformat()).replace("{now}", now.strftime("%Y%m%d%H%M")))
        days = [d.to_json() for d in adapter(fetcher(url), today)]
    except NotImplementedError as e:
        return entry | {"status": "unsupported", "error": str(e) or "adapter not written yet"}
    except Exception as e:  # any fetch or parse failure: keep the last good menu
        log.warning("%s: %s: %s", vendor["id"], type(e).__name__, e)
        return entry | {"status": "error", "error": f"{type(e).__name__}: {e}"}

    days = current_days(days, today)
    h = content_hash(days)
    if h != prev.get("content_hash"):
        entry["updated_at"] = now.isoformat(timespec="seconds")
    return entry | {"content_hash": h, "days": days}


def has_todays_menu(prev: dict | None, today: date) -> bool:
    """Whether the last scrape succeeded and already holds a menu for today, so another fetch can wait."""
    return bool(prev) and prev.get("status") == "ok" and any(d["date"] == today.isoformat() for d in prev["days"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    ap.add_argument("--only", action="append", help="vendor id(s) to update")
    ap.add_argument("--rendered", action="store_true",
                    help='update only vendors marked "render" (they need a headless browser); '
                         "without this flag they are skipped")
    ap.add_argument("--force", action="store_true",
                    help="scrape even vendors that already have today's menu (normally they wait until tomorrow)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    vendors = json.loads((args.data_dir / "vendors.json").read_text())["vendors"]
    menus_path = args.data_dir / "menus.json"
    menus = json.loads(menus_path.read_text()) if menus_path.exists() else {"vendors": {}}

    now = datetime.now(LONDON)
    out = {"vendors": {}}
    for v in vendors:
        if v.get("link_only"):
            continue  # never fetched; the site links to the vendor's page
        prev = menus["vendors"].get(v["id"])
        if (args.only and v["id"] not in args.only) or bool(v.get("render")) != args.rendered:
            if prev is not None:
                out["vendors"][v["id"]] = prev
            continue
        # Once a vendor's menu for today is in, leave it alone until tomorrow: fewer requests to the
        # colleges. Naming a vendor with --only, or --force, scrapes it anyway.
        if not (args.force or args.only) and has_todays_menu(prev, now.date()):
            out["vendors"][v["id"]] = prev
            log.info("%s: already have today's menu, skipped", v["id"])
            continue
        fetcher = fetch
        if v.get("render"):  # drawn by JavaScript: fetch through a headless browser
            from .render import rendered_text as fetcher  # Playwright is only needed for these
        out["vendors"][v["id"]] = update_vendor(v, prev, now.date(), now, fetcher)
        log.info("%s: %s", v["id"], out["vendors"][v["id"]]["status"])

    if out != menus:
        menus_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        log.info("menus.json updated")
    else:
        log.info("no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
