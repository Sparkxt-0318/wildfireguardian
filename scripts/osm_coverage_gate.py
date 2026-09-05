#!/usr/bin/env python
"""Phase 4 GATE — does OSM carry enough to support a household-level analysis?

Session 14. Before running the vulnerability layer anywhere new, count what OSM
actually has there. A household-level claim on a site with 40 mapped buildings
is not a household-level claim, and finding that out after a run is finding it
out too late.

Every candidate is counted whether or not it is chosen, because the comparison
across sites IS a portability result: it says where in the world this layer can
be run today without new survey data.

    python scripts/osm_coverage_gate.py --write

Writes docs/osm_coverage_gate.json. Read-only against OSM (Overpass count only).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "osm_coverage_gate.json"
OVERPASS = "https://overpass-api.de/api/interpreter"

#: Candidate sites, each with a documented evacuation failure. Bounding boxes
#: are (south, west, north, east) and cover the settlement, not the whole burn.
CANDIDATES = {
    "paradise_ca_2018": {
        "bbox": (39.730, -121.665, 39.790, -121.575),
        "event": "Camp Fire, 8 Nov 2018",
        "why": ("A documented evacuation failure: 86 deaths; two of the three "
                "escape routes were closed by fire leaving one; 17 burnovers "
                "were identified, 12 of them on major evacuation roadways."),
        "sources": ["Britannica, Camp Fire of 2018",
                    "Burnover events identified during the 2018 Camp Fire "
                    "(nwfirescience.org)"],
    },
    "mati_gr_2018": {
        "bbox": (38.030, 23.960, 38.075, 24.020),
        "event": "Attica wildfires, 23 Jul 2018",
        "why": ("A documented evacuation failure: 104 deaths. People burned to "
                "death in cars caught in traffic jams while fleeing; others "
                "drowned after wading into the sea to escape the flames. Six "
                "officials were convicted over the response in 2024."),
        "sources": ["VOA News, 'Six convicted amid fury over 2018 wildfires that "
                    "killed 104 at Greek resort' (2024)",
                    "ABC News, 'Six convicted, 15 cleared over response to deadly "
                    "2018 wildfire in Mati, Greece' (2024)"],
    },
    "pedrogao_pt_2017": {
        "bbox": (39.900, -8.220, 39.980, -8.100),
        "event": "Pedrógão Grande, 17 Jun 2017",
        "why": ("A documented evacuation failure: at least 66 deaths in the June "
                "2017 fires, the majority in Pedrógão Grande, where 47 people "
                "died in their cars on a road while fleeing."),
        "sources": ["Wikipedia, 'June 2017 Portugal wildfires'",
                    "International Association of Wildland Fire, 'The Open "
                    "Wounds of Pedrógão Grande'"],
    },
    "yeongdeok_kr_2025": {
        "bbox": (36.380, 129.320, 36.480, 129.430),
        "event": "reference — the Korean site this layer was built on",
        "why": "Included so every foreign count has a familiar yardstick.",
        "sources": ["repo snapshot data/snapshots/osm-buildings"],
    },
}

#: Below this many buildings a per-household surface is not a per-household
#: surface. Set to the count the Korean reference site itself carries, so the
#: threshold is "at least as well mapped as the site we already accept".
MIN_BUILDINGS = 124


def overpass_counts(bbox, *, timeout: int = 90) -> dict:
    s, w, n, e = bbox
    q = f"""[out:json][timeout:{timeout}];
(
  way["building"]({s},{w},{n},{e});
  relation["building"]({s},{w},{n},{e});
);
out count;
"""
    q2 = f"""[out:json][timeout:{timeout}];
way["highway"]({s},{w},{n},{e});
out count;
"""
    q3 = f"""[out:json][timeout:{timeout}];
(
  node["amenity"~"shelter|community_centre|school"]({s},{w},{n},{e});
  way["leisure"="park"]({s},{w},{n},{e});
);
out count;
"""
    out = {}
    for key, body in (("buildings", q), ("highways", q2), ("refuge_pois", q3)):
        t0 = time.time()
        last = None
        for attempt in range(3):                       # Overpass 500s are common
            req = urllib.request.Request(
                OVERPASS, data=body.encode(),
                headers={"User-Agent": "wildfireguardian-portability-audit"})
            try:
                with urllib.request.urlopen(req, timeout=timeout + 10) as r:
                    data = json.loads(r.read().decode())
                tags = data.get("elements", [{}])[0].get("tags", {})
                out[key] = int(tags.get("total", 0))
                out[f"{key}_seconds"] = round(time.time() - t0, 1)
                out[f"{key}_attempts"] = attempt + 1
                last = None
                break
            except Exception as ex:                    # noqa: BLE001
                last = f"{type(ex).__name__}: {str(ex)[:120]}"
                time.sleep(5 * (attempt + 1))
        if last is not None:
            out[key] = None
            out[f"{key}_error"] = last
            out[f"{key}_attempts"] = 3
        time.sleep(3)                                  # be polite to Overpass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    results = {}
    for name, spec in CANDIDATES.items():
        print(f"  querying {name} ...", flush=True)
        c = overpass_counts(spec["bbox"])
        b = c.get("buildings")
        # ⚠ A failed sub-query must BLOCK the pass. The first version marked
        # Paradise PASS while its road and refuge queries had both errored, so
        # the gate was passing a site on one third of the evidence. A gate that
        # passes on partial data is not a gate.
        complete = all(c.get(k) is not None
                       for k in ("buildings", "highways", "refuge_pois"))
        c["all_subqueries_returned"] = complete
        c["passes_gate"] = bool(complete and b is not None and b >= MIN_BUILDINGS)
        if not complete:
            c["gate_note"] = ("BLOCKED: at least one sub-query failed, so "
                              "coverage is unknown rather than sufficient")
        results[name] = {**spec, **c}
        print(f"    buildings={b} highways={c.get('highways')} "
              f"refuge_pois={c.get('refuge_pois')} "
              f"gate={'PASS' if c['passes_gate'] else 'FAIL'}", flush=True)

    payload = {
        "schema_version": 1,
        "title": "OSM coverage gate for the vulnerability layer",
        "provenance": "external (Overpass API, live query)",
        "arm": "L0_vulnerability",
        "generated_by": "scripts/osm_coverage_gate.py",
        "min_buildings_threshold": MIN_BUILDINGS,
        "threshold_rationale": (
            "Set to the building count of the Korean reference site, so the bar "
            "is 'at least as well mapped as the site this layer was built on' "
            "rather than an invented number."),
        "queried_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "candidates": results,
    }
    if args.write:
        OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
