"""Precompute walking times from each faculty to each vendor into data/walking.json.

Uses the FOSSGIS OSRM foot-routing server (OpenStreetMap data). Faculties and
vendors rarely move, so this runs on demand, not on a schedule.

    python -m sidge_lunch.walking [--data-dir ../data]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from .fetch import TIMEOUT, USER_AGENT

OSRM_TABLE = "https://routing.openstreetmap.de/routed-foot/table/v1/driving/"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    args = ap.parse_args(argv)

    faculties = json.loads((args.data_dir / "faculties.json").read_text())["faculties"]
    vendors = json.loads((args.data_dir / "vendors.json").read_text())["vendors"]
    points = faculties + vendors
    coords = ";".join(f"{p['lng']},{p['lat']}" for p in points)
    sources = ";".join(str(i) for i in range(len(faculties)))
    destinations = ";".join(str(i) for i in range(len(faculties), len(points)))

    r = requests.get(
        OSRM_TABLE + coords,
        params={"sources": sources, "destinations": destinations, "annotations": "duration,distance"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "Ok":
        raise SystemExit(f"OSRM error: {body}")

    times = {
        f["id"]: {
            v["id"]: {
                "seconds": round(body["durations"][i][j]),
                "metres": round(body["distances"][i][j]),
            }
            for j, v in enumerate(vendors)
            if body["durations"][i][j] is not None
        }
        for i, f in enumerate(faculties)
    }
    out = {
        "source": "OSRM foot profile, routing.openstreetmap.de (OpenStreetMap contributors)",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "times": times,
    }
    (args.data_dir / "walking.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
