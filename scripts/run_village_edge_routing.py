#!/usr/bin/env python
"""Re-centre the demo origins on VILLAGE-EDGE households and re-run rescue routing.

Session 8, Phase 2. Motivation (현장 실무자 자문, N = 1, qualitative —
docs/firefighter_consultation.md §5; a statement, not a measurement): mid-slope
residents are 극소수 and deaths at genuinely inaccessible points are rare; the
recurring fatal pattern is fire jumping to 민가 at village edges and valley
mouths. The demo geography should match.

OPERATIONAL DEFINITION (2a)
---------------------------
"Village-edge household" is operationalised as the **wildland–urban interface**
of Radeloff et al. (2005, *Ecological Applications* 15(3)), who distinguish
*intermix* (housing interspersed WITHIN wildland vegetation) from *interface*
(housing ADJACENT TO but not within vegetation). We use the **interface** form
— a building footprint centroid that is NOT inside a wildland-vegetation
polygon but lies within a distance threshold ``D`` of one — because the
consultation's described pattern (마을·계곡 근처 민가 연소) is adjacency, not
interspersion. ``D`` is a parameter and is swept; intermix counts are reported
alongside for transparency. Radeloff's census-block density/buffer constants
(6.17 units/km², 2.4 km) are block-level US census operationalisations and are
NOT transplanted; the building-level distance threshold is this project's
parameterisation of the same concept, and is labelled as such.

DATA (2b — gated)
-----------------
1. VWorld (국토교통부 GIS건물통합정보) is attempted first; the HTTP outcome is
   recorded verbatim in the output and in docs/BLOCKERS.md on failure.
2. Fallback: OSM ``building=*`` footprints from the pinned snapshot
   (``source = "osm"``). ⚠ OSM building coverage in rural Korea is a SMALL,
   REGION-DEPENDENT fraction of the real building stock
   (src/wildfireguardian/buildings/__init__.py) — counts here are never
   building counts.
3. Wildland vegetation: OSM ``natural=wood`` / ``landuse=forest`` polygons,
   disk-cached (``source = "osm"``).

Output: data/processed/rescue_routing_village_edge.json
Run:  python scripts/run_village_edge_routing.py
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.buildings import OSMBuildingSource  # noqa: E402
from wildfireguardian.buildings.wui import (  # noqa: E402
    WUI_INTERFACE_DISTANCE_SWEEP_M, interface_mask, wui_distances,
)
from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402
from wildfireguardian.routing.rescue_demo import build_real_demo, run_pipeline  # noqa: E402
from wildfireguardian.utils import regions  # noqa: E402

#: Interface distance thresholds (m) — the parameterised, swept form of the
#: Radeloff et al. (2005) adjacency concept at building level
#: (src/wildfireguardian/buildings/wui.py).
D_SWEEP: list[float] = [float(v) for v in WUI_INTERFACE_DISTANCE_SWEEP_M]

VEG_CACHE = REPO / "data/cache/osm/yeongdeok_2025/vegetation.geojson"


def try_vworld(bbox_wgs84, key: str | None) -> tuple[None, str]:
    """One honest VWorld attempt; returns (None, recorded outcome).

    A successful integration would parse GetFeature pages of the 건물통합정보
    layer into footprint centroids tagged ``source="vworld"`` — the seam is
    :class:`wildfireguardian.buildings.BuildingSource`. As of this session the
    gateway answers 502 on every endpoint (data, search), so the attempt is
    recorded and the loader falls back.
    """
    if not key:
        return None, "vworld: no VWORLD_API_KEY available"
    minlon, minlat, maxlon, maxlat = bbox_wgs84
    q = urllib.parse.urlencode({
        "service": "data", "request": "GetFeature", "data": "LT_C_SPBD",
        "key": key, "geomFilter": f"BOX({minlon},{minlat},{maxlon},{maxlat})",
        "size": "10", "format": "json", "crs": "EPSG:4326"})
    url = f"https://api.vworld.kr/req/data?{q}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            body = r.read(200).decode("utf-8", "replace")
            if r.status == 200 and '"featureCollection"' in body:
                return None, ("vworld: HTTP 200 but full-page ingestion is not "
                              "implemented in this session — recorded, fell back")
            return None, f"vworld: HTTP {r.status}, body head {body[:80]!r}"
    except urllib.error.HTTPError as e:
        return None, f"vworld: HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return None, f"vworld: {type(e).__name__}: {e}"


def _read_env_key(name: str) -> str | None:
    p = REPO / ".env"
    if not p.exists():
        return None
    for line in p.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip() or None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / "data" / "processed"))
    args = ap.parse_args()

    region = regions.lookup("yeongdeok_2025")
    bbox = region.bbox_wgs84

    print("[1/5] data path (gated): VWorld -> OSM -> synthetic ...")
    _, vworld_status = try_vworld(bbox, _read_env_key("VWORLD_API_KEY"))
    print(f"      {vworld_status}")
    bs = OSMBuildingSource().load("yeongdeok_2025", repo=REPO)
    print(f"      buildings: {len(bs)} (source={bs.source}, {bs.source_file})")

    print("[2/5] wildland vegetation (OSM natural=wood / landuse=forest) ...")
    import geopandas as gpd
    if not VEG_CACHE.exists():
        print("STOP: vegetation cache missing; run the fetch in "
              "scripts/run_village_edge_routing.py docstring first",
              file=sys.stderr)
        return 2
    veg = gpd.read_file(VEG_CACHE).set_crs("EPSG:4326").to_crs("EPSG:5179")
    print(f"      vegetation polygons: {len(veg)} (source=osm, cached)")

    print("[3/5] WUI classification (Radeloff 2005 interface, parameterised) ...")
    cls = wui_distances(bs.xy, list(veg.geometry.values))
    n_intermix = int(cls["inside"].sum())
    counts_by_d = {f"{d:g}": int(interface_mask(cls, d).sum()) for d in D_SWEEP}
    print(f"      intermix (within vegetation): {n_intermix}")
    print(f"      interface counts by D: {counts_by_d}")

    print("[4/5] building the REAL scenario once (OSM roads; synthetic hazard) ...")
    cfg = RescueConfig(use_osm=True)
    scenario = build_real_demo(cfg)
    lattice_origins = list(scenario.origins)

    runs = {}
    for d in D_SWEEP:
        mask = interface_mask(cls, d)
        pts = bs.xy[mask]
        nodes = []
        seen = set()
        for x, y in pts:
            n = scenario.walk.nearest_node(float(x), float(y))
            if n not in seen:
                seen.add(n)
                nodes.append(n)
        scenario.origins = nodes
        scenario.origins_source = (
            f"osm building footprints (snapshot), WUI-interface distance <= {d:g} m "
            f"(Radeloff 2005 interface, building-level parameterisation)")
        print(f"[5/5] D={d:g} m: {int(mask.sum())} buildings -> {len(nodes)} "
              f"distinct walk nodes; running pipeline ...")
        res = run_pipeline(scenario, cfg)
        runs[f"{d:g}"] = {
            "interface_distance_m": d,
            "n_buildings": int(mask.sum()),
            "n_origins": res.n_origins,
            "four_way_counts": res.four_way_counts,
            "n_dispatch": len(res.dispatch),
            "n_unreachable": len(res.unreachable_homes),
            "advisory_recommendations": {
                k: sum(1 for a in res.advisories if a["recommendation"] == k)
                for k in ("진입 권장", "진입 보류 권장", "철수 권장")},
        }
        print(f"      four-way: {res.four_way_counts}")

    # restore, out of caution, though the scenario object is not reused
    scenario.origins = lattice_origins

    doc = {
        "schema_version": 1,
        "title": "village-edge (WUI-interface) re-centred rescue routing "
                 "(Session 8 Phase 2)",
        "config_hash": config_hash(),
        "definition": {
            "concept": "wildland-urban interface, Radeloff et al. (2005, "
                       "Ecological Applications 15(3))",
            "form_used": "interface (adjacent to, not within, wildland "
                         "vegetation); intermix reported for transparency",
            "parameterisation": "building-centroid distance to nearest OSM "
                                "wildland polygon <= D; D swept",
            "D_sweep_m": D_SWEEP,
            "not_transplanted": "Radeloff's census-block density/buffer "
                                "constants (6.17 units/km^2, 2.4 km) are US "
                                "block-level operationalisations and are not "
                                "used here",
        },
        "data_path": {
            "vworld_attempt": vworld_status,
            "buildings": {"source": bs.source, "source_file": bs.source_file,
                          "n": len(bs),
                          "coverage_caveat": (
                              "OSM building coverage in rural Korea is a "
                              "small, region-dependent fraction of the real "
                              "building stock; counts are never building "
                              "counts")},
            "vegetation": {"source": "osm", "tags": "natural=wood|landuse=forest",
                           "file": str(VEG_CACHE.relative_to(REPO)), "n": len(veg)},
            "hazard": "synthetic (unchanged; FIRMS bundle git-ignored)",
            "terrain": "synthetic (unchanged)",
        },
        "n_intermix_within_vegetation": n_intermix,
        "baseline_for_comparison": {
            "note": ("lattice-scan origins on the SAME network vintage (arm B, "
                     "current snapshot). The committed 439-series artifact is "
                     "the unrecoverable 2026-07-19 arm-A network "
                     "(docs/network_drift.md) and is quoted only with that "
                     "label."),
            "arm_b_lattice_n_origins": 441,
            "arm_b_lattice_four_way": {"saved_by_rescue_reachable_refuge": 12,
                                       "already_safe": 255,
                                       "no_safe_pedestrian_route": 142,
                                       "no_surviving_vehicle_ingress": 32},
        },
        "runs": runs,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "rescue_routing_village_edge.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
