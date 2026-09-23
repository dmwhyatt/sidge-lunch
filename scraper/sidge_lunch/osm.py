"""OpenStreetMap helpers for vendor and faculty locations (via the Overpass API).

    python -m sidge_lunch.osm survey [--radius 800]   # list food places near the Sidgwick Site
    python -m sidge_lunch.osm buildings               # list named buildings on/around the site
    python -m sidge_lunch.osm sync                    # set lat/lng from each entry's "osm" id

Entries in data/vendors.json and data/faculties.json can carry an "osm" id such
as "way/123456" or "node/42". ``sync`` replaces their coordinates with the OSM
feature's position (a node's point, or the centre of a way/relation), so the
map follows OpenStreetMap rather than hand-typed guesses.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from .fetch import TIMEOUT, USER_AGENT

OVERPASS = "https://overpass-api.de/api/interpreter"
SIDGWICK = (52.2016, 0.1089)  # centre of the Sidgwick Site

FOOD = {
    "amenity": "cafe|restaurant|fast_food|pub|food_court|canteen|bar|ice_cream",
    "shop": "bakery|deli|sandwiches|convenience|supermarket",
}


def overpass(query: str) -> list[dict]:
    r = requests.post(OVERPASS, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT * 3)
    r.raise_for_status()
    return r.json()["elements"]


def position(el: dict) -> tuple[float, float]:
    if "lat" in el:
        return el["lat"], el["lon"]
    return el["center"]["lat"], el["center"]["lon"]


def osm_id(el: dict) -> str:
    return f"{el['type']}/{el['id']}"


def survey(radius: int) -> list[dict]:
    lat, lng = SIDGWICK
    parts = "".join(
        f'nwr["{key}"~"^({values})$"](around:{radius},{lat},{lng});' for key, values in FOOD.items()
    )
    found = []
    for el in overpass(f"[out:json][timeout:60];({parts});out center tags;"):
        tags = el.get("tags", {})
        found.append({
            "osm": osm_id(el),
            "name": tags.get("name"),
            "kind": tags.get("amenity") or tags.get("shop"),
            "operator": tags.get("operator"),
            "website": tags.get("website") or tags.get("contact:website"),
            "opening_hours": tags.get("opening_hours"),
            "access": tags.get("access"),
            "lat": position(el)[0],
            "lng": position(el)[1],
        })
    return sorted(found, key=lambda p: (p["kind"] or "", p["name"] or ""))


def buildings(radius: int) -> list[dict]:
    lat, lng = SIDGWICK
    query = (
        f'[out:json][timeout:60];(nwr["building"]["name"](around:{radius},{lat},{lng});'
        f'nwr["amenity"="college"](around:{radius},{lat},{lng}););out center tags;'
    )
    return sorted(
        ({"osm": osm_id(el), "name": el["tags"].get("name"), "lat": position(el)[0], "lng": position(el)[1]}
         for el in overpass(query)),
        key=lambda b: b["name"] or "",
    )


def sync(data_dir: Path) -> None:
    files = {"vendors.json": "vendors", "faculties.json": "faculties"}
    docs = {name: json.loads((data_dir / name).read_text()) for name in files}
    wanted = {e["osm"] for name, key in files.items() for e in docs[name][key] if e.get("osm")}
    if not wanted:
        print("no entries have an osm id")
        return
    by_type: dict[str, list[str]] = {}
    for ref in wanted:
        kind, num = ref.split("/")
        by_type.setdefault(kind, []).append(num)
    query = "[out:json];(" + "".join(f"{k}(id:{','.join(v)});" for k, v in by_type.items()) + ");out center;"
    positions = {osm_id(el): position(el) for el in overpass(query)}

    missing = wanted - positions.keys()
    if missing:
        raise SystemExit(f"not found in OpenStreetMap: {sorted(missing)}")
    for name, key in files.items():
        for e in docs[name][key]:
            if e.get("osm"):
                lat, lng = positions[e["osm"]]
                e["lat"], e["lng"] = round(lat, 6), round(lng, 6)
        (data_dir / name).write_text(json.dumps(docs[name], indent=2, ensure_ascii=False) + "\n")
    print(f"updated {len(wanted)} locations")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["survey", "buildings", "sync"])
    ap.add_argument("--radius", type=int, default=800, help="metres from the Sidgwick Site")
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    args = ap.parse_args(argv)
    if args.command == "sync":
        sync(args.data_dir)
    else:
        rows = survey(args.radius) if args.command == "survey" else buildings(args.radius)
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
