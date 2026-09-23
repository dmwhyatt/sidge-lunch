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

from .adapters import ADAPTERS
from .fetch import fetch

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
    adapter = ADAPTERS.get(vendor["id"])
    if adapter is None:
        return entry | {"status": "unsupported", "error": "no adapter registered"}

    try:
        days = [d.to_json() for d in adapter(fetcher(vendor["menu_url"]), today)]
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    ap.add_argument("--only", action="append", help="vendor id(s) to update")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    vendors = json.loads((args.data_dir / "vendors.json").read_text())["vendors"]
    menus_path = args.data_dir / "menus.json"
    menus = json.loads(menus_path.read_text()) if menus_path.exists() else {"vendors": {}}

    now = datetime.now(LONDON)
    out = {"vendors": {}}
    for v in vendors:
        prev = menus["vendors"].get(v["id"])
        if args.only and v["id"] not in args.only:
            if prev is not None:
                out["vendors"][v["id"]] = prev
            continue
        out["vendors"][v["id"]] = update_vendor(v, prev, now.date(), now)
        log.info("%s: %s", v["id"], out["vendors"][v["id"]]["status"])

    if out != menus:
        menus_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        log.info("menus.json updated")
    else:
        log.info("no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
