"""Build data/sites.json and data/places.json from the OpenStreetMap snapshot.

    python -m sidge_lunch.places [--data-dir ../data]

Input is scraper/osm/cambridge.json (see .github/workflows/osm.yml). Nothing is
fetched here.

- sites.json: the "where am I" picker. University sites (Sidgwick, Downing, ...)
  with the named buildings inside them, standalone University buildings, and
  the colleges.
- places.json: food places to show on the map, in the same shape as
  vendors.json: every college, University cafés, and commercial cafés, pubs and
  restaurants. None are scraped. Anything already in the hand-curated
  vendors.json (matched by OSM id, or by name for colleges) is left out, so
  curated entries always win.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .walking import slug

SNAPSHOT = Path(__file__).resolve().parents[1] / "osm" / "cambridge.json"

# University sites, by OSM way id. Named buildings inside these become the
# site's buildings. Other University areas become standalone buildings.
SITES = {
    82608357: ("sidgwick", "Sidgwick Site"),
    25802541: ("downing", "Downing Site"),
    25774974: ("new-museums", "New Museums Site"),
    164365655: ("cambridge-west", "Cambridge West"),
    239333572: ("old-addenbrookes", "Old Addenbrooke's Site"),
    136330943: ("mill-lane", "Silver Street & Mill Lane Site"),
    137226442: ("madingley-rise", "Madingley Rise Site"),
    28100828: ("forvie", "Forvie Site"),
    162786368: ("scroope-terrace", "Scroope Terrace Site"),
}
BIOMEDICAL = re.compile(r"^(Cambridge Biomedical Campus|Addenbrooke's Hospital)$")

COLLEGES = [
    "Christ's College", "Churchill College", "Clare College", "Clare Hall", "Corpus Christi College",
    "Darwin College", "Downing College", "Emmanuel College", "Fitzwilliam College", "Girton College",
    "Gonville & Caius College", "Homerton College", "Hughes Hall", "Jesus College", "King's College",
    "Lucy Cavendish College", "Magdalene College", "Murray Edwards College", "Newnham College",
    "Pembroke College", "Peterhouse", "Queens' College", "Robinson College", "St Catharine's College",
    "St Edmund's College", "St John's College", "Selwyn College", "Sidney Sussex College", "Trinity College",
    "Trinity Hall", "Wolfson College",
]

# Buildings that aren't places people work in.
NOT_WORKPLACES = re.compile(
    r"\b(hut|store|shed|garage|nursery|residence|substation|plant room|bike|cycle|car park|porters?' lodge|"
    r"data centre|court|hostel|house \d)\b|^\d+[a-z]? ",
    re.I,
)

# Who is in buildings whose names don't say, so people can find their department.
OCCUPANTS = {
    "Raised Faculty Building": "Modern & Medieval Languages, Philosophy",
    "Alison Richard Building": "POLIS, Sociology, HSPS",
    "Austin Robinson Building": "Economics",
    "History Building": "History",
    "Faculty of Law": "David Williams Building, Squire Law Library",
    "Pendlebury Music Library": "Faculty of Music",
    "11 West Road": "Faculty of Music",
    "West Hub": "Canteen and coffee bar",
    "William Gates Building": "Computer Science and Technology",
}

FOOD_AMENITIES = {"cafe": "Café", "restaurant": "Restaurant", "fast_food": "Takeaway", "pub": "Pub",
                  "food_court": "Food court"}
FOOD_SHOPS = {"bakery": "Bakery", "deli": "Deli", "sandwiches": "Sandwiches"}


def position(el: dict) -> tuple[float, float]:
    if "lat" in el:
        return el["lat"], el["lon"]
    if "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    b = el["bounds"]
    return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2


def ring(el: dict) -> list[tuple[float, float]] | None:
    if el.get("type") == "way" and el.get("geometry"):
        return [(g["lat"], g["lon"]) for g in el["geometry"]]
    return None


def inside(point: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    y, x = point
    hit = False
    for (y1, x1), (y2, x2) in zip(poly, poly[-1:] + poly[:-1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def area_size(el: dict) -> float:
    b = el.get("bounds")
    return (b["maxlat"] - b["minlat"]) * (b["maxlon"] - b["minlon"]) if b else 0.0


def osm_ref(el: dict) -> str:
    return f"{el['type']}/{el['id']}"


def college_for(name: str) -> str | None:
    """The college a campus area belongs to, if it is a college's main site."""
    base = name.replace(" (University of Cambridge)", "").replace("Gonville and Caius", "Gonville & Caius")
    return base if base in COLLEGES else None


def rounded(lat: float, lng: float) -> dict:
    return {"lat": round(lat, 6), "lng": round(lng, 6)}


def is_food(el: dict) -> bool:
    t = el.get("tags", {})
    return t.get("amenity") in FOOD_AMENITIES or t.get("amenity") == "canteen" or t.get("shop") in FOOD_SHOPS


def university_run(tags: dict) -> bool:
    return tags.get("operator", "").strip() == "University of Cambridge"


def build(elements: list[dict], curated: list[dict]) -> tuple[dict, dict]:
    unique: dict[str, dict] = {}
    for e in elements:  # a feature can appear in more than one part of the query
        unique.setdefault(osm_ref(e), e)
    elements = list(unique.values())
    areas = [e for e in elements if e.get("tags", {}).get("amenity") in ("university", "college")
             or BIOMEDICAL.match(e.get("tags", {}).get("name", ""))]
    buildings = [e for e in elements if "building" in e.get("tags", {}) and e["tags"].get("name") and not is_food(e)]
    food = [e for e in elements if is_food(e)]

    # Colleges: one entry each, at the centre of its main (largest) area.
    colleges: dict[str, dict] = {}
    for a in areas:
        name = college_for(a["tags"].get("name", ""))
        if name and (name not in colleges or area_size(a) > area_size(colleges[name])):
            colleges[name] = a
    college_rings = [r for a in areas if a["tags"].get("amenity") == "college"
                     or "College" in a["tags"].get("operator", "") or college_for(a["tags"].get("name", ""))
                     if (r := ring(a))]

    # University sites and the named buildings inside them.
    site_rings = {sid: (label, ring(a)) for a in areas if a["type"] == "way" and a["id"] in SITES
                  for sid, label in [SITES[a["id"]]] if ring(a)}
    bio = next((a for a in areas if BIOMEDICAL.match(a["tags"].get("name", "")) and ring(a)), None)
    if bio:
        site_rings["biomedical"] = ("Cambridge Biomedical Campus", ring(bio))

    def entry(el: dict, name: str) -> dict:
        e = {"id": slug(name), "name": name, **rounded(*position(el))}
        if name in OCCUPANTS:
            e["occupants"] = OCCUPANTS[name]
        return e

    sites = []
    placed: set[str] = set()
    for sid, (label, poly) in site_rings.items():
        seen: dict[str, dict] = {}
        for b in buildings:
            name = b["tags"]["name"]
            if NOT_WORKPLACES.search(name) and name not in OCCUPANTS:
                continue
            if inside(position(b), poly) and name not in seen:
                seen[name] = entry(b, name)
                placed.add(osm_ref(b))
        if seen:
            sites.append({"id": sid, "name": label, "kind": "university",
                          "buildings": sorted(seen.values(), key=lambda x: x["name"])})

    # Standalone University areas (the UL, Engineering, Chemistry, ...) not inside a site.
    standalone = {}
    for a in areas:
        t = a["tags"]
        if not university_run(t) or college_for(t.get("name", "")):
            continue
        if a["type"] == "way" and a["id"] in SITES or a["type"] == "relation":
            continue
        pos = position(a)
        if any(inside(pos, poly) for _, poly in site_rings.values()):
            continue
        name = t["name"].replace(" (University of Cambridge)", "")
        standalone.setdefault(name, entry(a, name))
    sites.sort(key=lambda x: x["name"])
    if standalone:
        sites.append({"id": "other-university", "name": "Other University buildings", "kind": "university",
                      "buildings": sorted(standalone.values(), key=lambda x: x["name"])})

    sites.append({"id": "colleges", "name": "Colleges", "kind": "college", "buildings": [
        {"id": f"college-{slug(n)}", "name": n, **rounded(*position(a))} for n, a in sorted(colleges.items())
    ]})
    for s in sites:  # ids must be unique within a site
        ids: dict[str, int] = {}
        for b in s["buildings"]:
            ids[b["id"]] = ids.get(b["id"], 0) + 1
            if ids[b["id"]] > 1:
                b["id"] += f"-{ids[b['id']]}"

    # Places to eat.
    curated_osm = {v["osm"] for v in curated if v.get("osm")}
    curated_names = {v["name"] for v in curated}
    places = []
    for name, a in sorted(colleges.items()):
        if name in curated_names:
            continue
        v = {"id": f"college-{slug(name)}", "name": name, "type": "college",
             "about": "College hall and buttery. Usually for members, staff and their guests: check before going.",
             **rounded(*position(a)), "link_only": True}
        if url := a["tags"].get("website"):
            v["menu_url"] = url
        places.append(v)

    for f in food:
        t = f["tags"]
        name = t.get("name")
        if not name or osm_ref(f) in curated_osm:
            continue
        pos = position(f)
        university = university_run(t)
        if not university and (t.get("amenity") == "canteen" or any(inside(pos, r) for r in college_rings)):
            continue  # private staff canteens, and college bars/butteries (the college entry covers them)
        kind = FOOD_AMENITIES.get(t.get("amenity", "")) or FOOD_SHOPS.get(t.get("shop", "")) or "Café"
        cuisine = t.get("cuisine", "").replace("_", " ").replace(";", ", ")
        v = {"id": f"osm-{f['type'][0]}{f['id']}", "name": name, "type": "university" if university else "commercial",
             "about": f"{kind} · {cuisine}" if cuisine else kind, "osm": osm_ref(f), **rounded(*pos), "link_only": True}
        if url := t.get("website") or t.get("contact:website"):
            v["menu_url"] = url
        if hours := t.get("opening_hours"):
            v["hours"] = hours
        places.append(v)

    note = ("Generated by scraper/sidge_lunch/places.py from the OpenStreetMap snapshot. Don't edit: "
            "change the snapshot query, the builder, or the hand-curated vendors.json instead.")
    return ({"_note": note, "sites": sites}, {"_note": note, "vendors": places})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    args = ap.parse_args(argv)
    elements = json.loads(SNAPSHOT.read_text())["elements"]
    curated = json.loads((args.data_dir / "vendors.json").read_text())["vendors"]
    sites, places = build(elements, curated)
    for name, doc in (("sites.json", sites), ("places.json", places)):
        (args.data_dir / name).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    n_buildings = sum(len(s["buildings"]) for s in sites["sites"])
    print(f"{len(sites['sites'])} sites, {n_buildings} buildings, {len(places['vendors'])} places")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
