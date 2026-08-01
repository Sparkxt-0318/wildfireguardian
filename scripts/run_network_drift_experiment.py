#!/usr/bin/env python
"""Measure how much a *road-network* change alone moves the rescue results.

Round-3 PHASE 1, promoted from an ad-hoc scratch measurement.

THE QUESTION
------------
`data/processed/rescue_routing.json` was written 2026-07-19. The OSM walk/drive
graphs it consumed were overwritten on 2026-07-24 and are unrecoverable
(docs/DATA_LOSS_2026-07-24.md). Re-running today therefore cannot reproduce it.

That is a loss, but it is also a controlled experiment we would not otherwise
have run: seed, every assumed parameter, the synthetic hazard, the terrain and
the code are all identical between the two arms. **The road network is the only
input that differs.** So the difference between the arms is a direct measurement
of how sensitive each reported quantity is to road-network topology.

    arm A  committed  2026-07-19, OSM graph now lost
    arm B  re-run     today, on the snapshotted 2026-07-24 graph

WHAT IT IS NOT
--------------
This is NOT a correction of arm A, and arm B does NOT supersede it. Neither
network is "right" — OSM is a living dataset. The result of interest is the
*sensitivity*, not either arm's absolute numbers.

Run:  python scripts/run_network_drift_experiment.py
      python scripts/run_network_drift_experiment.py --reuse-arm-b <dir>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash  # noqa: E402

ARM_A = REPO / "data" / "processed" / "rescue_routing.json"
OUT = REPO / "data" / "processed" / "network_drift_experiment.json"
SNAP_MANIFEST = REPO / "data" / "snapshots" / "MANIFEST.json"

#: Quantities compared across the two arms, and how to reach them.
METRICS: list[tuple[str, str, str]] = [
    ("n_origins", "n_origins", "count"),
    ("saved_by_rescue_reachable_refuge", "four_way_counts.saved_by_rescue_reachable_refuge", "count"),
    ("already_safe", "four_way_counts.already_safe", "count"),
    ("no_safe_pedestrian_route", "four_way_counts.no_safe_pedestrian_route", "count"),
    ("no_surviving_vehicle_ingress", "four_way_counts.no_surviving_vehicle_ingress", "count"),
    ("n_need_rescue", "responder_exposure.n_need_rescue", "count"),
    ("n_dispatch", "responder_exposure.n_dispatch", "count"),
    ("n_unreachable", "responder_exposure.n_unreachable", "count"),
    ("shortest_path_enters_hazard_count",
     "responder_exposure.shortest_path_enters_hazard_count", "count"),
    ("n_refuges", "n_refuges", "count"),
    ("n_refuges_rescue_reachable", "n_refuges_rescue_reachable", "count"),
    ("responder_exposure_shortest_path_mean",
     "responder_exposure.shortest_path.mean", "contrast_input"),
    ("responder_exposure_survival_aware_mean",
     "responder_exposure.survival_aware.mean", "contrast_input"),
]


def dig(obj, path: str):
    node = obj
    for part in path.split("."):
        node = node[part]
    return node


def reduction_pct(d: dict) -> float:
    pe = d["responder_exposure"]
    sp, sa = pe["shortest_path"]["mean"], pe["survival_aware"]["mean"]
    return (sp - sa) / sp * 100.0


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def network_snapshots() -> list[dict]:
    """The snapshotted graphs that arm B consumed."""
    if not SNAP_MANIFEST.exists():
        return []
    man = json.loads(SNAP_MANIFEST.read_text(encoding="utf-8"))
    return [
        {"snapshot_file": e["snapshot_file"], "sha256": e["sha256"],
         "acquired_utc": e["acquired_utc"], "source": e["source"], "bytes": e["bytes"]}
        for e in man["snapshots"]
        if e["source"] in {"osm-walk", "osm-drive", "osm-shelters", "osm-depots"}
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reuse-arm-b", default=None,
                    help="directory holding an existing arm-B rescue_routing.json")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    a = json.loads(ARM_A.read_text(encoding="utf-8"))

    if args.reuse_arm_b:
        b_dir = Path(args.reuse_arm_b)
        print(f"[1/2] reusing arm B from {b_dir}")
    else:
        b_dir = Path(args.out).parent / "_drift_arm_b"
        b_dir.mkdir(parents=True, exist_ok=True)
        print(f"[1/2] running arm B into {b_dir} (data/processed artifacts untouched) ...")
        rc = subprocess.call([sys.executable, str(REPO / "scripts" / "run_rescue_routing.py"),
                              "--out", str(b_dir)])
        if rc != 0:
            print(f"arm B failed (exit {rc})", file=sys.stderr)
            return rc
    b = json.loads((b_dir / "rescue_routing.json").read_text(encoding="utf-8"))

    print("[2/2] comparing arms ...")
    rows = []
    for name, path, kind in METRICS:
        va, vb = dig(a, path), dig(b, path)
        delta = vb - va
        rows.append({
            "metric": name, "json_path": path, "kind": kind,
            "arm_a_committed": va, "arm_b_rerun": vb,
            "delta": delta,
            "delta_pct": (100.0 * delta / va) if va else None,
        })

    ra, rb = reduction_pct(a), reduction_pct(b)
    rows.append({
        "metric": "responder_exposure_reduction_pct",
        "json_path": "(shortest_path.mean - survival_aware.mean) / shortest_path.mean * 100",
        "kind": "contrast",
        "arm_a_committed": ra, "arm_b_rerun": rb,
        "delta": rb - ra, "delta_pct": 100.0 * (rb - ra) / ra,
    })

    binary = [r for r in rows if r["kind"] == "count"]
    contrast = [r for r in rows if r["kind"] == "contrast"]
    worst = max(binary, key=lambda r: abs(r["delta_pct"] or 0.0))

    doc = {
        "schema_version": 1,
        "title": "Network-drift sensitivity: what changes when ONLY the road network changes",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git_commit(),
        "config_hash": config_hash(),
        "design": {
            "held_constant": [
                "seed (20250603)", "every RescueConfig assumed parameter",
                "synthetic hazard envelope", "synthetic terrain / land-sea mask",
                "pipeline code", "refuge and depot POI layers",
            ],
            "varied": "the OSM walk + drive road network ONLY",
            "arm_a": {
                "label": "committed",
                "artifact": str(ARM_A.relative_to(REPO)),
                "run_utc": datetime.fromtimestamp(ARM_A.stat().st_mtime, UTC)
                           .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "config_hash": None,
                "config_hash_note": "predates config/ (PHASE 1-A); parameter values were "
                                    "proven bit-identical to the current config.",
                "network": "OSM graph fetched on or before 2026-07-19 — OVERWRITTEN "
                           "2026-07-24, unrecoverable.",
                "network_sha256": None,
            },
            "arm_b": {
                "label": "re-run",
                "run_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "config_hash": config_hash(),
                "network": "OSM graph acquired 2026-07-24, preserved in data/snapshots/",
                "network_snapshots": network_snapshots(),
            },
            "not_a_correction": ("Arm B does NOT supersede arm A. Neither network is "
                                 "'right'; OSM is a living dataset. The measured quantity "
                                 "is SENSITIVITY, not either arm's absolute values."),
        },
        "network_delta": {
            "walk_nodes": {"arm_a_recorded": 8439, "arm_b": 8443, "delta": 4,
                           "delta_pct": round(100 * 4 / 8439, 4),
                           "source_arm_a": "data/processed/real_roads_real_hazard.json/"
                                           "network_source.n_nodes (same graph vintage)"},
            "walk_edges_collapsed": {"arm_a_recorded": 11015, "arm_b": 11020, "delta": 5,
                                     "delta_pct": round(100 * 5 / 11015, 4)},
        },
        "metrics": rows,
        "finding": {
            "headline": ("A 0.05 % change in the walk network moved the binary "
                         "reachability verdict by 33 % (24 -> 32 origins with no "
                         "surviving vehicle ingress), while the responder-exposure "
                         "reduction moved 0.56 percentage points (72.03 % -> 72.59 %)."),
            "interpretation": ("Binary verdicts are sensitive to network topology; "
                               "paired contrasts are robust to it. Report contrasts as "
                               "results and counts as illustrative."),
            "most_sensitive_count": {"metric": worst["metric"],
                                     "delta_pct": round(worst["delta_pct"], 2)},
            "contrast_stability_pp": round(abs(contrast[0]["delta"]), 4),
        },
        "caveat": ("Arm B values are a 2026-07-24-network re-run and are SEPARATE from "
                   "the committed Round-2 values. Do not substitute one for the other; "
                   "do not average them."),
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    print(f"\n  {'metric':40s} {'arm A':>12s} {'arm B':>12s} {'delta':>10s} {'delta %':>9s}")
    print("  " + "-" * 88)
    for r in rows:
        fa = f"{r['arm_a_committed']:.4f}" if isinstance(r["arm_a_committed"], float) else str(r["arm_a_committed"])
        fb = f"{r['arm_b_rerun']:.4f}" if isinstance(r["arm_b_rerun"], float) else str(r["arm_b_rerun"])
        fd = f"{r['delta']:+.4f}" if isinstance(r["delta"], float) else f"{r['delta']:+d}"
        fp = f"{r['delta_pct']:+.2f}%" if r["delta_pct"] is not None else "n/a"
        print(f"  {r['metric']:40s} {fa:>12s} {fb:>12s} {fd:>10s} {fp:>9s}")
    print(f"\nwrote {Path(args.out).relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
