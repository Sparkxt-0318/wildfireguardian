#!/usr/bin/env python
"""WFG-262 — does `no_safe_route` contain origins that were never searched?

`routing/evacuation.py::future_aware_route` has a branch that returns
``reached=False`` **before any search runs**, when the origin's own node is
already at or above ``p_cut`` at departure::

    if table[s_idx, 0] >= p_cut:
        return RouteResult(..., reached=False, enters_hazard=True,
                           note="origin already at/above the impassable cutoff at departure")

The classifier in ``live/pipeline.py`` branches only on ``reached`` and
``enters_hazard`` and never reads ``note``, so such an origin would land in
``no_safe_route``, whose A4 dispatch sentence asserts that a budget was
consumed and that detours were tried. Neither happened for that member.

This script asks the question nobody had asked: **on the committed fields, does
that branch fire at all?** It does not re-run any scan, does not refit
anything, and moves no committed number.

The predicate, and why it can be measured without a DEM
-------------------------------------------------------
``build_time_expanded_field`` fills the first column of its table with

    table[:, k] = hazard.prob_at_points(nx, ny, departure_min + k * time_step_min)

so at ``k = 0`` and ``departure_min = 0`` the branch predicate is exactly
``hazard.prob_at_points(x, y, 0.0) >= p_cut`` on the origin's own coordinates.
It reads **node coordinates and the hazard surface only** — no edge, no weight,
no slope. That is what makes the slope arm measurable in a sandbox with no DEM:
the slope and flat networks are built from the same snapshot graphml and share
a node set. This is an argument rather than an observation, so the run pins it
with an identity control (below) instead of assuming it.

Identity controls, all three required to pass before any count is believed
--------------------------------------------------------------------------
1. ``n_nodes`` rebuilt from the snapshot equals the committed arm's ``n_nodes``.
2. ``n_origins_scanned`` from the committed origin rule equals the committed
   arm's ``n_origins_scanned``. A candidate set that does not reproduce is a
   different population and nothing downstream means anything.
3. Where the committed artifact recorded ``origin_nodes_by_bucket`` (the two
   multi-region rows), every listed ``no_safe_route`` member is checked against
   the predicate directly, not inferred from the aggregate.

The origin rule is IMPORTED from ``run_real_roads_real_hazard_slope``, never
restated here, so this run cannot silently mean something different by
"origin".

Output: ``data/processed/no_safe_route_origin_split/split_<stamp>.json``.
Registered additively by ``scripts/register_no_safe_route_split.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import build_time_expanded_field  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

from run_real_roads_real_hazard_slope import (  # noqa: E402
    REAL_OSM_SCAN_STRIDE, candidate_origins,
)
from run_multi_region_routing import snapshot_for  # noqa: E402

#: region key -> (committed artifact, arm name, hazard npz, snapshot region tag)
REGIONS: dict[str, dict] = {
    "yeongdeok_2025": {
        "artifact": "data/processed/real_roads_real_hazard_canonical.json",
        "arm": "slope_digraph_canonical",
        "npz": "data/processed/routing_demo_canonical.npz",
        "snapshot_region": "yeongdeok_2025",
        "label": "영덕 2025 (canonical, headline region)",
    },
    "uiseong_andong_2025": {
        "artifact": "data/processed/real_roads_real_hazard_uiseong_andong_2025.json",
        "arm": "slope_digraph_canonical",
        "npz": "data/processed/hazard_uiseong_andong_2025.npz",
        "snapshot_region": "uiseong_andong_2025",
        "label": "의성·안동 2025",
    },
    "uljin_samcheok_2022": {
        "artifact": "data/processed/real_roads_real_hazard_uljin_samcheok_2022.json",
        "arm": "slope_digraph_canonical",
        "npz": "data/processed/hazard_uljin_samcheok_2022.npz",
        "snapshot_region": "uljin_samcheok_2022",
        "label": "울진·삼척 2022",
    },
}


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load_hazard(npz_path: Path):
    z = np.load(npz_path)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    return hazard, haz, (xmin, ymin, xmax, ymax, cell)


def measure_region(key: str, spec: dict, *, p_cut: float, budget_min: float,
                   step_min: float) -> dict:
    committed = json.loads((REPO / spec["artifact"]).read_text(encoding="utf-8"))
    arm = committed["arms"][spec["arm"]]

    npz_path = REPO / spec["npz"]
    hazard, haz, extent = _load_hazard(npz_path)

    graphml = snapshot_for(spec["snapshot_region"], "walk")
    G = load_snapshot_graph(graphml)
    # Flat, undirected: the node SET is what the predicate reads, and it is the
    # same set the slope arm was built from (same graphml). No DEM is required
    # and none is available in the routine's sandbox.
    net, _ = build_walk_network(G, None, directed=False, apply_slope=False)

    n_nodes = int(net.graph.number_of_nodes())
    cand, ign = candidate_origins(net, hazard, haz, extent, p_cut)

    controls = {
        "n_nodes_rebuilt": n_nodes,
        "n_nodes_committed": int(arm["n_nodes"]),
        "n_nodes_match": n_nodes == int(arm["n_nodes"]),
        "n_origins_rebuilt": len(cand),
        "n_origins_committed": int(arm["n_origins_scanned"]),
        "n_origins_match": len(cand) == int(arm["n_origins_scanned"]),
    }

    # The branch predicate, read off the SAME table the router builds.
    field = build_time_expanded_field(net, hazard, departure_min=0.0,
                                      time_budget_min=budget_min, p_cut=p_cut,
                                      time_step_min=step_min)
    fired = [int(n) for n in cand if field.table[field.idx[n], 0] >= p_cut]

    # Control 3: the committed membership, where the artifact recorded it.
    members = arm.get("origin_nodes_by_bucket", {}).get("no_safe_route")
    member_check: dict | None = None
    if members is not None:
        per = {int(n): float(field.table[field.idx[n], 0])
               for n in members if n in field.idx}
        member_check = {
            "n_members_committed": len(members),
            "n_members_resolvable_in_rebuilt_graph": len(per),
            "n_members_at_or_above_p_cut_at_departure":
                sum(1 for v in per.values() if v >= p_cut),
            "max_prob_at_departure_over_members":
                round(max(per.values()), 6) if per else None,
        }

    margins = [float(field.table[field.idx[n], 0]) for n in cand]
    return {
        "region": key,
        "label": spec["label"],
        "committed_artifact": spec["artifact"],
        "committed_arm": spec["arm"],
        "hazard_npz": spec["npz"],
        "hazard_npz_sha256": _sha256(npz_path),
        "walk_snapshot": graphml.name,
        "identity_controls": controls,
        "committed_counts": arm["counts"],
        "no_safe_route_committed": int(arm["counts"]["no_safe_route"]),
        "n_origins_removed_before_search": len(fired),
        "origin_nodes_removed_before_search": fired,
        "committed_membership_check": member_check,
        "max_prob_at_departure_over_scanned_origins": round(max(margins), 6),
        "p_cut": p_cut,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p-cut", type=float,
                    default=float(_cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--time-budget-min", type=float,
                    default=float(_cfg("pedestrian.walk_budget_min", 600.0)))
    ap.add_argument("--time-step-min", type=float,
                    default=float(_cfg("time.routing_time_step_min", 10.0)))
    ap.add_argument("--out-dir",
                    default=str(REPO / "data/processed/no_safe_route_origin_split"))
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    rows = []
    for key, spec in REGIONS.items():
        print(f"[{key}] rebuilding node set and reading the departure column ...")
        row = measure_region(key, spec, p_cut=args.p_cut,
                             budget_min=args.time_budget_min,
                             step_min=args.time_step_min)
        c = row["identity_controls"]
        print(f"  nodes {c['n_nodes_rebuilt']} vs committed {c['n_nodes_committed']} "
              f"-> {'OK' if c['n_nodes_match'] else 'MISMATCH'}")
        print(f"  origins {c['n_origins_rebuilt']} vs committed "
              f"{c['n_origins_committed']} -> "
              f"{'OK' if c['n_origins_match'] else 'MISMATCH'}")
        print(f"  no_safe_route committed = {row['no_safe_route_committed']}; "
              f"origins removed before search = "
              f"{row['n_origins_removed_before_search']}")
        rows.append(row)

    failed = [r["region"] for r in rows
              if not (r["identity_controls"]["n_nodes_match"]
                      and r["identity_controls"]["n_origins_match"])]
    total_fired = sum(r["n_origins_removed_before_search"] for r in rows)

    out = {
        "schema_version": 1,
        "title": "WFG-262 — how many committed `no_safe_route` origins were "
                 "refused before any search ran",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git(),
        "config_hash": config_hash(),
        "row": "WFG-262",
        "question": "future_aware_route returns reached=False before any search "
                    "when table[origin, 0] >= p_cut. Does that branch fire for "
                    "any origin in the committed canonical scans?",
        "method": "No scan is re-run and no number is refit. For each region the "
                  "node set is rebuilt from the committed walk snapshot, the "
                  "committed origin rule is IMPORTED from "
                  "run_real_roads_real_hazard_slope.candidate_origins, and the "
                  "branch predicate is read off build_time_expanded_field's own "
                  "table at column 0. Identity controls on n_nodes and "
                  "n_origins_scanned gate every count below.",
        "why_no_dem_is_needed": "build_time_expanded_field sets "
                                "table[:, k] = hazard.prob_at_points(nx, ny, "
                                "departure_min + k*time_step_min), so at k=0 and "
                                "departure_min=0 the predicate reads node "
                                "coordinates and the hazard surface only. Slope "
                                "changes edges, not the node set, and both arms "
                                "are built from the same snapshot graphml. The "
                                "n_nodes control is what pins this.",
        "parameters": {
            "p_cut": args.p_cut,
            "time_budget_min": args.time_budget_min,
            "time_step_min": args.time_step_min,
            "origin_scan_stride": REAL_OSM_SCAN_STRIDE,
            "departure_min": 0.0,
            "source": "config/default.yaml — unchanged from every 459-series run",
        },
        "identity_controls_failed": failed,
        "total_origins_removed_before_search": total_fired,
        "finding": (
            "ZERO across all three regions: the branch cannot fire for any "
            "scanned origin, because all three copies of candidate_origins skip "
            "nodes with hazard.prob_at(x, y, 0.0) >= p_cut and that is the same "
            "predicate the branch tests. The `no_safe_route` bucket is NOT "
            "contaminated by unsearched origins on any committed field."
            if total_fired == 0 and not failed else
            f"{total_fired} scanned origin(s) would be refused before any search "
            f"runs; the bucket IS contaminated and the split is reported beside "
            f"`no_safe_route`."
        ),
        "what_this_is_not": (
            "This is NOT a licence for the A4 sheet sentence. `no_safe_route`'s "
            "code condition is only 「the naive route enters the hazard AND the "
            "future-aware search reached no refuge」. reached=False is also "
            "produced by the hazard gate blocking every alternative with the "
            "budget nowhere near binding — the identical mechanism "
            "docs/routing_limitations.md §1 established for fa_exceeds_budget, "
            "and it holds with zero unsearched members. This measurement changes "
            "the REASON the bucket is clean, not whether the sentence overclaims."
        ),
        "the_protection_is_unnamed": (
            "The invariant that keeps the bucket clean lives in "
            "candidate_origins, three files from the branch it protects, in "
            "three duplicated copies, and no test tied the two predicates "
            "together before this row. A scan called with departure_min > 0, or "
            "an origin rule that drops the p_cut filter, reintroduces the defect "
            "silently. tests/test_no_safe_route_origin_split.py is that tie."
        ),
        "regions": rows,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"split_{stamp}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n-> {out_path.relative_to(REPO)}")
    print(f"   total origins removed before search: {total_fired}")
    if failed:
        print(f"STOP: identity controls failed for {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
