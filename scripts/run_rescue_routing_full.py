#!/usr/bin/env python
"""Re-run the rescue pipeline and serialize EVERY origin, not the top 20.

Round-3 PHASE 3-B.

WHY
---
The committed ``rescue_routing.json`` serialises ``dispatch_top20`` — 20 of its
143 dispatch points — so the PHASE-3 operational sheets covered 44 points of 167
and 25 of 33 clusters were singletons. That is a serialization limit, not a
modelling one: the pipeline computes every origin and then writes a slice.

⚠ THIS PRODUCES DRIFT VALUES, NOT THE COMMITTED VALUES
------------------------------------------------------
The committed run used an OSM graph that was overwritten on 2026-07-24 and is
unrecoverable (``docs/DATA_LOSS_2026-07-24.md``). This re-run uses the preserved
2026-07-24 snapshot, so it reproduces the drift arm B measured in
``docs/network_drift.md``:

    committed   439 origins · 167 need rescue · 24 unreachable
    this re-run 441 origins · 174 need rescue · 32 unreachable

Both are correct for their inputs. **Do not reconcile them, average them, or
substitute one for the other.** The script asserts the arm-B figures and stops if
they do not appear, because a mismatch would mean the conditions differ.

INPUT IS THE SNAPSHOT, NOT THE CACHE
------------------------------------
``data/cache/`` is a cache: it may be regenerated at any time. The snapshot is
evidence. This script materialises the snapshot graphs into a temporary
cache-shaped directory and points the loader there, so ``data/cache/`` is never
read.

Writes ``data/processed/rescue_routing_full.json``. Never touches the committed
``rescue_routing.json``.

Run:  python scripts/run_rescue_routing_full.py
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pyproj import Transformer  # noqa: E402

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig, build_dispatch_list  # noqa: E402
from wildfireguardian.routing.rescue_demo import (  # noqa: E402
    _immobile_homes, _refuge_node_sets, build_real_demo, resident_policies,
    run_pipeline,
)

SNAP_DIR = REPO / "data" / "snapshots"
COMMITTED = REPO / "data" / "processed" / "rescue_routing.json"
OUT = REPO / "data" / "processed" / "rescue_routing_full.json"
DRIFT = REPO / "data" / "processed" / "network_drift_experiment.json"

#: snapshot stem -> the filename the OSM loader expects in a cache directory.
SNAPSHOT_LAYOUT = {
    "osm-walk_yeongdeok-2025_20260724_2bff8d85.graphml.gz": "walk.graphml",
    "osm-drive_yeongdeok-2025_20260724_f537bdf5.graphml.gz": "drive.graphml",
    "osm-shelters_yeongdeok-2025_20260724_ac42a42b.geojson": "shelters.geojson",
    "osm-depots_yeongdeok-2025_20260724_ab512d83.geojson": "depots.geojson",
    "osm-firestation_yeongdeok-2025_20260724_ab512d83.geojson": "fire_station.geojson",
}

_TO_WGS = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

#: The drift arm-B figures this run must reproduce.
EXPECT = {"n_origins": 441, "n_need_rescue": 174, "n_unreachable": 32}

LABEL_KO = (
    "본 산출물은 2026-07-24 도로망 스냅샷 기준 재실행값(출발지 441곳, 구조 필요 "
    "174곳)이며, 제출 문서가 인용하는 커밋값(439곳, 167곳)과 다릅니다. 도로망 "
    "재취득에 따른 차이이며 자세한 내용은 docs/network_drift.md를 참조하십시오."
)


def materialise_snapshots(dest: Path) -> dict:
    """Lay the snapshot files out as an OSM cache directory. Returns provenance."""
    dest.mkdir(parents=True, exist_ok=True)
    used = {}
    for snap_name, cache_name in SNAPSHOT_LAYOUT.items():
        src = SNAP_DIR / snap_name
        if not src.exists():
            raise FileNotFoundError(f"missing snapshot {src}")
        raw = gzip.decompress(src.read_bytes()) if snap_name.endswith(".gz") \
            else src.read_bytes()
        (dest / cache_name).write_bytes(raw)
        used[cache_name] = {"snapshot": snap_name,
                            "sha256_uncompressed": hashlib.sha256(raw).hexdigest()}
    return used


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def classify_all(scenario, cfg, results) -> list[dict]:
    """Per-origin four-way class, re-derived with the pipeline's own helpers.

    ``run_pipeline`` returns aggregate counts but no per-origin labels. Rather
    than reimplement the rule, this calls the same functions in the same order
    and then ASSERTS its counts equal ``results.four_way_counts`` — so any
    divergence is a hard failure instead of a silently different table.
    """
    _assess, all_walk, rr_walk = _refuge_node_sets(scenario, cfg)
    immobile = set(_immobile_homes(scenario, cfg))
    rows, needs_rescue = [], []
    for n in scenario.origins:
        x, y = scenario.walk.node_xy(n)
        lon, lat = _TO_WGS.transform(x, y)
        row = {"origin_walk_node": int(n), "x_5179": float(x), "y_5179": float(y),
               "lon_wgs84": float(lon), "lat_wgs84": float(lat),
               "immobile": bool(n in immobile)}
        if n in immobile:
            row["four_way_class"] = "needs_rescue"
            needs_rescue.append(n)
        else:
            pol = resident_policies(scenario.walk, n, scenario.hazard,
                                    all_walk, rr_walk, cfg)
            naive, fa_rr = pol["naive"], pol["future_aware_rescue"]
            if naive.reached and not naive.enters_hazard:
                row["four_way_class"] = "already_safe"
            elif fa_rr.reached and not fa_rr.enters_hazard:
                row["four_way_class"] = "saved_by_rescue_reachable_refuge"
            else:
                row["four_way_class"] = "needs_rescue"
                needs_rescue.append(n)
        rows.append(row)

    # Split needs_rescue into dispatchable / unreachable with the same call.
    drive_nodes = [scenario.drive.nearest_node(*scenario.walk.node_xy(n))
                   for n in needs_rescue]
    depot_nodes = [scenario.drive.nearest_node(d.x, d.y) for d in scenario.depots]
    dispatch, unreach = build_dispatch_list(drive_nodes, scenario.drive,
                                            depot_nodes, scenario.depots,
                                            scenario.hazard, cfg)
    by_drive_dispatch = {int(e.home_node): e.as_dict() for e in dispatch}
    unreach_nodes = {int(u["home_node"]) for u in unreach}
    by_drive_unreach = {int(u["home_node"]): u for u in unreach}

    walk_to_drive = dict(zip(needs_rescue, drive_nodes))
    for row in rows:
        n = row["origin_walk_node"]
        if row["four_way_class"] != "needs_rescue":
            continue
        d = walk_to_drive.get(n)
        row["drive_node"] = int(d) if d is not None else None
        if d in unreach_nodes:
            row["four_way_class"] = "no_surviving_vehicle_ingress"
            u = by_drive_unreach[d]
            row["best_closing_window_min"] = u.get("best_closing_window_min")
            row["nearest_depot_index"] = u.get("nearest_depot_index")
            row["reason"] = u.get("reason")
        elif d in by_drive_dispatch:
            row["four_way_class"] = "no_safe_pedestrian_route"
            row.update({k: v for k, v in by_drive_dispatch[d].items()
                        if k not in ("home_node", "x", "y")})
        else:                                    # pragma: no cover - defensive
            row["four_way_class"] = "unresolved"

    got = {k: sum(1 for r in rows if r["four_way_class"] == k)
           for k in ("saved_by_rescue_reachable_refuge", "already_safe",
                     "no_safe_pedestrian_route", "no_surviving_vehicle_ingress")}
    if got != results.four_way_counts:
        raise AssertionError(
            "per-origin classification disagrees with run_pipeline:\n"
            f"  re-derived : {got}\n  pipeline   : {results.four_way_counts}")
    n_collision = len(needs_rescue) - len(set(drive_nodes))
    return rows, n_collision


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--no-assert", action="store_true",
                    help="report a drift mismatch instead of failing")
    args = ap.parse_args()

    before = hashlib.sha256(COMMITTED.read_bytes()).hexdigest()
    print(f"committed artifact sha256 (before): {before}")

    tmp = Path(tempfile.mkdtemp(prefix="wfg-snap-osm-"))
    try:
        # The loader resolves {osm_cache_dir}/{region_name}/, so materialise into
        # a region-shaped subdirectory rather than the bare temp root.
        prov = materialise_snapshots(tmp / "yeongdeok_2025")
        print(f"[1/4] snapshot materialised into {tmp} "
              "(data/cache/ NOT read)")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp))
        print("[2/4] building scenario from the snapshot graphs ...")
        scenario = build_real_demo(cfg)
        print(f"      walk={scenario.walk.graph.number_of_nodes()} nodes  "
              f"drive={scenario.drive.graph.number_of_nodes()} nodes  "
              f"refuges={len(scenario.destinations)}  "
              f"depots={len(scenario.depots)}  origins={len(scenario.origins)}")
        print("[3/4] running pipeline + per-origin classification ...")
        results = run_pipeline(scenario, cfg)
        rows, n_collision = classify_all(scenario, cfg, results)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    pe = results.responder_exposure
    got = {"n_origins": results.n_origins,
           "n_need_rescue": pe["n_need_rescue"],
           "n_unreachable": pe["n_unreachable"]}
    print(f"      four-way: {results.four_way_counts}")
    print(f"      arm-B check: {got}  expected {EXPECT}")
    if got != EXPECT:
        msg = (f"re-run does not reproduce drift arm B.\n  got      {got}\n"
               f"  expected {EXPECT}\nConditions differ; investigate before using "
               "this artifact.")
        if not args.no_assert:
            print(f"STOP: {msg}", file=sys.stderr)
            return 3
        print(f"WARNING: {msg}", file=sys.stderr)

    print("[4/4] writing ...")
    doc = {
        "schema_version": 1,
        "title": "Full-coverage rescue re-run with complete origin serialization",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "label_ko": LABEL_KO,
        "relationship_to_committed": {
            "committed_artifact": "data/processed/rescue_routing.json",
            "committed_sha256": before,
            "committed_values": {"n_origins": 439, "n_need_rescue": 167,
                                 "n_unreachable": 24},
            "this_run_values": got,
            "why_they_differ": "OSM road network re-acquired 2026-07-24; the graph "
                               "behind the committed run is unrecoverable. See "
                               "docs/network_drift.md and docs/DATA_LOSS_2026-07-24.md.",
            "do_not": "reconcile, average, or substitute one set for the other",
        },
        "input_provenance": {
            "source": "data/snapshots/ (NOT data/cache/)",
            "files": prov,
        },
        "parameters": {"budget_min": 600.0, "objective": "length_m (distance)",
                       "slope_applied": False,
                       "note": "config defaults, matching the committed run's "
                               "conditions so the only difference is the network"},
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
        "serialization": {
            "n_origins_serialized": len(rows),
            "n_dispatch_serialized": len(results.dispatch),
            "n_unreachable_serialized": len(results.unreachable_homes),
            "walk_to_drive_node_collisions": n_collision,
            "note": "every origin is serialized; the committed artifact carried "
                    "dispatch_top20 only",
        },
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    after = hashlib.sha256(COMMITTED.read_bytes()).hexdigest()
    print(f"committed artifact sha256 (after) : {after}")
    print(f"committed artifact UNCHANGED      : {before == after}")
    if before != after:
        print("STOP: the committed artifact changed!", file=sys.stderr)
        return 4
    o = Path(args.out)
    print(f"wrote {o.relative_to(REPO) if o.is_relative_to(REPO) else o}  "
          f"({len(rows)} origins serialized)")
    _ = np
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
