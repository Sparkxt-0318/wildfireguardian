"""Write the list of real origins the 시·군 labels are computed for (input of label_sigungu.py).

One row per origin of the two replayed regions: id, region, the OSM point (WGS84) and the road-entry node (WGS84).
Python 3.12, standard library only. Usage: python3.12 export_places.py [out.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REGIONS = ("uiseong_andong_2025", "yeongdeok_2025")


def rows() -> list[dict]:
    out = []
    for region in REGIONS:
        doc = json.loads((ROOT / "planner/public/data/regions" / region / "places.geojson").read_text(encoding="utf-8"))
        for f in doc["features"]:
            p = f["properties"]
            if p.get("role") != "origin":
                continue
            lon, lat = f["geometry"]["coordinates"]
            e = p.get("entry") or {}
            out.append({
                "id": p["id"],
                "region": region,
                "name": p.get("name"),
                "point": {"lon": lon, "lat": lat},
                "entry": {"node": e.get("node"), "lon": e.get("lon"), "lat": e.get("lat")} if e else None,
            })
    return out


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("places_input.json")
    data = {"schema": "wfg.wkit.sigungu_input/1", "crs": "EPSG:4326", "regions": list(REGIONS), "places": rows()}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(data['places'])} origins -> {out}")


if __name__ == "__main__":
    main()
