"""Precompute walking times from each building to nearby places, one file per site.

    python -m sidge_lunch.walking [--data-dir ../data] [--only sidgwick]

Writes data/walking/<site>.json: {"times": {building_id: {vendor_id: [seconds, metres]}}}.
Uses the FOSSGIS OSRM foot-routing server (OpenStreetMap data). Only places
within RADIUS of a site's buildings are routed, requests are batched to stay
under the server's table-size limit, and there is a pause between requests.
Runs in GitHub Actions when places or sites change, not on a schedule.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

from .fetch import TIMEOUT, USER_AGENT

OSRM_TABLE = "https://routing.openstreetmap.de/routed-foot/table/v1/driving/"
SOURCE = "OSRM foot profile, routing.openstreetmap.de (OpenStreetMap contributors)"
RADIUS = 1600  # metres, straight line; about a 20-minute walk once paths bend
MAX_COORDS = 100  # sources + destinations per request
PAUSE = 1.0  # seconds between requests


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", "and").replace("'", "")).strip("-")


def metres(a: dict, b: dict) -> float:
    rad = math.pi / 180
    dlat, dlng = (b["lat"] - a["lat"]) * rad, (b["lng"] - a["lng"]) * rad
    h = math.sin(dlat / 2) ** 2 + math.cos(a["lat"] * rad) * math.cos(b["lat"] * rad) * math.sin(dlng / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def chunks(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def table(sources: list[dict], destinations: list[dict]) -> tuple[list, list]:
    points = sources + destinations
    r = requests.get(
        OSRM_TABLE + ";".join(f"{p['lng']},{p['lat']}" for p in points),
        params={
            "sources": ";".join(str(i) for i in range(len(sources))),
            "destinations": ";".join(str(i) for i in range(len(sources), len(points))),
            "annotations": "duration,distance",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT * 3,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {body}")
    return body["durations"], body["distances"]


def site_times(buildings: list[dict], vendors: list[dict], pause: float = PAUSE) -> dict:
    nearby = [v for v in vendors if any(metres(b, v) <= RADIUS for b in buildings)]
    times: dict[str, dict[str, list[int]]] = {b["id"]: {} for b in buildings}
    src_size = min(len(buildings), MAX_COORDS // 3)
    first = True
    for srcs in chunks(buildings, src_size):
        for dsts in chunks(nearby, MAX_COORDS - len(srcs)):
            if not first:
                time.sleep(pause)
            first = False
            durations, distances = table(srcs, dsts)
            for i, b in enumerate(srcs):
                for j, v in enumerate(dsts):
                    if durations[i][j] is not None and metres(b, v) <= RADIUS:
                        times[b["id"]][v["id"]] = [round(durations[i][j]), round(distances[i][j])]
    return times


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    ap.add_argument("--only", action="append", help="site id(s) to recompute")
    args = ap.parse_args(argv)

    sites = json.loads((args.data_dir / "sites.json").read_text())["sites"]
    vendors = [v for name in ("vendors.json", "places.json") if (args.data_dir / name).exists()
               for v in json.loads((args.data_dir / name).read_text())["vendors"]]
    out_dir = args.data_dir / "walking"
    out_dir.mkdir(exist_ok=True)
    for s in sites:
        if args.only and s["id"] not in args.only:
            continue
        times = site_times(s["buildings"], vendors)
        pairs = sum(len(t) for t in times.values())
        path = out_dir / f"{s['id']}.json"
        if path.exists() and json.loads(path.read_text()).get("times") == times:
            print(f"{s['id']}: unchanged")  # keep the old file so nothing is committed or redeployed
            time.sleep(PAUSE)
            continue
        path.write_text(json.dumps({
            "source": SOURCE,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "times": times,
        }, separators=(",", ":")) + "\n")
        print(f"{s['id']}: {len(s['buildings'])} buildings, {pairs} routes")
        time.sleep(PAUSE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
