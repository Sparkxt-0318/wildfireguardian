#!/usr/bin/env python
"""NH-057 (author, 2026-09-12: 「run the whole thing」): the rescue pipeline on the
REAL 영덕 hazard, end to end, so a dispatch sheet made from the real spread
surface exists.

What is real here
  - hazard: `haz_stack` from data/processed/routing_demo_canonical.npz, the
    leave-one-fire-out forward simulation on the real 2025 영덕 fire (the same
    field every routing surface already cites);
  - walk + drive networks, refuges, depots: the 2026-07-24 OSM snapshots in
    data/snapshots/ (NOT data/cache/), laid out exactly as
    scripts/run_rescue_routing_full.py lays them out.
What is still a stand-in, stated on every output
  - origins are sampled walk-network candidates (stride 18), not households;
  - walk timing is flat (the OSM loader attaches no slope);
  - the vehicle cutoff, speeds, delays are the config assumptions.
Nothing synthetic drives a number: no synthetic terrain, no synthetic envelope,
no synthetic coastline. The hazard grid is the canonical 500 m grid.

Writes ONLY data/processed/rescue_routing_real_hazard.json. Then run
  python scripts/generate_dispatch_outputs.py --full \
      --source data/processed/rescue_routing_real_hazard.json \
      --out-root outputs/dispatch_real_hazard
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueConfig, load_depots, load_drive_network, load_shelters, load_walk_network,
)
from wildfireguardian.routing.rescue_demo import (  # noqa: E402
    _TO_5179, RescueScenario, _scan_origins, run_pipeline,
)
from wildfireguardian.spread_v2 import grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402
from wildfireguardian.utils import regions  # noqa: E402

from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import classify_all, materialise_snapshots  # noqa: E402

NPZ = REPO / "data/processed/routing_demo_canonical.npz"
OUT = REPO / "data/processed/rescue_routing_real_hazard.json"

LABEL_KO = (
    "본 출동 지시서는 2025년 영덕 산불의 실제 확산면(관측 기반 전방 시뮬레이션, "
    "routing_demo_canonical.npz)과 2026-07-24 도로망 스냅샷으로 만든 것입니다. "
    "출발지는 실제 가구가 아니라 도로망에서 표본추출한 후보 지점이며, 보행 시간은 "
    "경사를 반영하지 않은 평지 속도입니다. 합성 확산면으로 만든 기존 지시서"
    "(outputs/dispatch_full/)와 수치를 합치거나 비교하지 마십시오."
)


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def canonical_hazard() -> tuple[HazardSequence, np.ndarray, tuple, tuple]:
    z = np.load(NPZ)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    core = haz[0] >= 0.5                       # slice-0 burning core = ignition proxy
    rr, cc = np.where(core)
    ign = (float(xmin + (cc.mean() + 0.5) * cell), float(ymax - (rr.mean() + 0.5) * cell))
    return hazard, haz, (xmin, ymin, xmax, ymax, cell), ign


def build_scenario(cfg: RescueConfig) -> RescueScenario:
    region = regions.lookup(cfg.region_name)
    bbox = region.bbox_wgs84
    hazard, haz, extent, ign = canonical_hazard()
    route_grid = gridmod.build_grid(bbox, cell_size_m=cfg.route_cell_m)
    # Real inputs only. The elevation/burnable arguments are the loaders' synthetic
    # fallback; we pass empty arrays and REFUSE any fallback below.
    empty = np.zeros((route_grid.nrows, route_grid.ncols), dtype=float)
    walk, walk_source = load_walk_network(cfg, route_grid, empty, empty, bbox)
    drive, drive_source = load_drive_network(cfg, route_grid, empty, empty, bbox)
    dests, shelters_source = load_shelters(cfg, bbox, to_5179=_TO_5179)
    depots, depots_source = load_depots(cfg, bbox, to_5179=_TO_5179)
    srcs = {"walk": walk_source, "drive": drive_source,
            "shelters": shelters_source, "depots": depots_source}
    if any(s != "osm" for s in srcs.values()) or not dests or not depots:
        raise RuntimeError(f"a real input fell back to synthetic: {srcs}; refusing to run")
    origins = _scan_origins(walk, hazard, route_grid, ign, cfg)
    return RescueScenario(
        cfg=cfg, route_grid=route_grid, hazard_grid=hazard.grid,
        elevation=empty, burnable_frac=empty, hazard=hazard,
        walk=walk, drive=drive, destinations=dests, depots=depots, origins=origins,
        shelters_source=shelters_source, depots_source=depots_source,
        hazard_source="real (LOFO forward simulation, routing_demo_canonical.npz)",
        ignition_xy=ign, walk_source=walk_source, drive_source=drive_source,
        terrain_source="none (no terrain enters this run; walk timing is flat)",
        origins_source="sampled candidates (walk-network stride "
                       f"{cfg.scan_stride}, not households)",
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="wfg-snap-osm-"))
    try:
        prov = materialise_snapshots(tmp / "yeongdeok_2025")
        print("[1/4] snapshots materialised (data/cache/ NOT read)")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp),
                           scan_stride=REAL_OSM_SCAN_STRIDE)
        print("[2/4] building scenario on the real hazard ...")
        sc = build_scenario(cfg)
        print(f"      walk={sc.walk.graph.number_of_nodes()} drive={sc.drive.graph.number_of_nodes()} "
              f"refuges={len(sc.destinations)} depots={len(sc.depots)} origins={len(sc.origins)}")
        print("[3/4] running pipeline + per-origin classification ...")
        results = run_pipeline(sc, cfg)
        rows, n_collision = classify_all(sc, cfg, results)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    pe = results.responder_exposure
    print(f"      four-way: {results.four_way_counts}")
    print(f"      need_rescue={pe['n_need_rescue']} unreachable={pe['n_unreachable']}")
    doc = {
        "schema_version": 1,
        "title": "Rescue pipeline on the REAL 영덕 hazard (NH-057, 2026-09-12)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "label_ko": LABEL_KO,
        "what_is_real": {
            "hazard": "data/processed/routing_demo_canonical.npz haz_stack (LOFO forward sim, 500 m, 0-720 min)",
            "hazard_sha256": hashlib.sha256(NPZ.read_bytes()).hexdigest(),
            "networks_refuges_depots": "data/snapshots/ 2026-07-24 OSM (same layout as rescue_routing_full)",
            "files": prov,
        },
        "what_is_not": {
            "origins": sc.origins_source,
            "walk_timing": "flat elderly speed; no slope (OSM loader carries no DEM)",
            "vehicle_side": "config assumptions (cutoff 0.7, 40 km/h, delays); no vehicle field data",
            "terrain": sc.terrain_source,
        },
        "relationship_to_other_runs": {
            "synthetic_hazard_runs": ["data/processed/rescue_routing.json",
                                      "data/processed/rescue_routing_full.json"],
            "do_not": "compare, reconcile or average with the synthetic-hazard counts; "
                      "the hazard, the extent and the origin set all differ",
        },
        "parameters": {"budget_min": cfg.resident_time_budget_min,
                       "responder_budget_min": cfg.responder_time_budget_min,
                       "scan_stride": cfg.scan_stride, "walk_cutoff": cfg.walk_cutoff,
                       "vehicle_cutoff": cfg.vehicle_cutoff,
                       "immobile_fraction": cfg.immobile_fraction,
                       "ignition_proxy_xy_5179": list(sc.ignition_xy)},
        "provenance": results.provenance,
        "n_origins": results.n_origins,
        "four_way_counts": results.four_way_counts,
        "four_way_sums_to_n": sum(results.four_way_counts.values()) == results.n_origins,
        "n_refuges": len(results.dest_assessments),
        "n_refuges_rescue_reachable": results.n_refuges_rescue_reachable,
        "destinations": [a.as_dict() for a in results.dest_assessments],
        "resident_exposure": results.resident_exposure,
        "responder_exposure": pe,
        "dispatch_full": [e.as_dict() for e in results.dispatch],
        "unreachable_homes": results.unreachable_homes,
        "origins_full": rows,
        "serialization": {"n_origins_serialized": len(rows),
                          "n_dispatch_serialized": len(results.dispatch),
                          "n_unreachable_serialized": len(results.unreachable_homes),
                          "walk_to_drive_node_collisions": n_collision},
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[4/4] wrote {OUT.relative_to(REPO)} ({len(rows)} origins)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
