#!/usr/bin/env python
"""How many of the 44 Yeongdeok origins a PRESENT-PERIMETER-ONLY router already saves.

WFG-129, the row `paper/GAPS.md` G7 specified and no dev lap had taken.

THE QUESTION
------------
The canonical Yeongdeok scan partitions 458 scanned origins as 414 / 42 / 2: 414
where both routers are safe, 42 where the FIRE-BLIND route enters the forecast
hazard and the forecast-aware route does not, and 2 where the fire-blind route
enters and the forecast-aware router cannot finish.  The headline the booth says
out loud is the **42**, and its opponent is the fire-blind router --- a router
that does not look at the fire **at all**.  That opponent is too weak to carry
the sentence the project wants to say, because the realistic status quo is not a
blind walker: it is somebody who can see where the fire is **now**.

So the number the headline is missing is: of the **44** origins whose fire-blind
route enters the forecast (42 + 2), how many does a router that avoids only the
PRESENT perimeter already save?  Whatever is left is the share that needs the
forecast.

WHAT THE PRESENT-PERIMETER ARM IS
---------------------------------
Slice 0 of the committed hazard field as a **node filter**, and then the
repository's existing :func:`naive_route` over the filtered graph.  Concretely a
node is removed when ``hazard.prob_at(x, y, 0.0) >= p_cut`` --- which is
character for character the predicate
``scripts/run_real_roads_real_hazard_slope.candidate_origins`` already uses to
refuse an origin that is standing in the fire, so the arm introduces no new rule
and no new parameter.  A shelter inside the present perimeter is removed with
the rest.

The arm is then SCORED exactly as the other two arms are: against the full
forecast :class:`HazardSequence`, at the same ``departure_min`` and the same
``p_cut``.  Planning sees the present only; scoring sees the forecast.  That is
the whole contrast, and it is the only difference between this arm and the
fire-blind one.

ZERO buffer.  This is deliberately **not** WFG-033(b) and does not pre-empt
NH-027: no width is swept, so no width can be chosen after the answer.

WHAT IT REFUSES TO DO
---------------------
It writes nothing unless the committed 414 / 42 / 2 partition re-derives first
in this process, from the committed snapshots, with the committed parameters
(the WFG-114 reproduction-gate pattern).  A count measured on a tree that no
longer reproduces its own baseline is not a measurement of anything.

THE CAVEAT IT MEASURES RATHER THAN ASSERTS
------------------------------------------
A node filter can cut a village off from every refuge for a reason that has
nothing to do with the fire --- the filter deletes nodes, and a graph with nodes
deleted can simply be disconnected.  If that happened and the outcome were
reported as one number, "the present perimeter does not save them" would be
indistinguishable from "my filter cut the graph".  So the three outcomes are
reported SEPARATELY --- saved, still enters the forecast, and not reached --- and
for the not-reached group the artifact records how many of those origins the
fire-blind router reached on the UNFILTERED graph.  All 44 were reached
fire-blind by construction (both committed buckets require ``nv.reached``), so
every not-reached origin here is the filter's doing and is counted as such.

Run:  python scripts/measure_present_perimeter_yeongdeok.py
      python scripts/measure_present_perimeter_yeongdeok.py --out <path>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.evacuation import (  # noqa: E402
    future_aware_route, naive_route,
)
from wildfireguardian.routing.future_front import RoadNetwork  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402
from run_multi_region_routing import read_poi_snapshot  # noqa: E402

NPZ = REPO / "data/processed/routing_demo_canonical.npz"
CANON = REPO / "data/processed/real_roads_real_hazard_canonical.json"
MANIFEST = REPO / "data/snapshots/MANIFEST.json"
OUT = REPO / "data/processed/present_perimeter_yeongdeok_2025.json"

#: The committed partition this run must reproduce before it writes anything.
EXPECTED = {"both_safe": 414, "naive_into_FA_safe": 42, "no_safe_route": 2}
EXPECTED_ORIGINS = 458


def snapshot(source: str, region: str) -> Path:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    hits = [s for s in man.get("snapshots", [])
            if s.get("source") == source and s.get("region") == region
            and s.get("stored_file")]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one {source} snapshot for {region}, got {len(hits)}")
    p = REPO / "data" / "snapshots" / hits[0]["stored_file"]
    if not p.exists():
        raise SystemExit(f"snapshot missing on disk: {p}")
    return p


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build() -> tuple:
    """The canonical scene: hazard field, walk network, refuges, parameters."""
    canon = json.loads(CANON.read_text(encoding="utf-8"))
    prm = canon["parameters"]
    z = np.load(NPZ)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])

    dem_p = snapshot("srtm-dem", "yeongdeok-2025")
    walk_p = snapshot("osm-walk", "yeongdeok-2025")
    shel_p = snapshot("osm-shelters", "yeongdeok-2025")
    G = load_snapshot_graph(walk_p)
    net, _ = build_walk_network(
        G, dem_p, sampling_m=float(prm["slope_sampling_m"]),
        max_abs_slope=float(prm["max_abs_slope"]), directed=True, apply_slope=True,
    )
    dests, _n_pois = read_poi_snapshot(shel_p, kind="shelter")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    return canon, prm, hazard, haz, (xmin, ymin, xmax, ymax, cell), net, \
        {"dem": dem_p, "walk": walk_p, "shelters": shel_p}


def reproduce_partition(net, cand, hazard, prm) -> tuple[dict, dict]:
    """The committed three-way classification, recomputed here.

    Returns (counts, per-origin fire-blind results for the origins whose
    fire-blind route enters the hazard).
    """
    p_cut = float(prm["p_cut"])
    classes = {"both_safe": [], "naive_into_FA_safe": [], "no_safe_route": [], "other": []}
    blind: dict[int, dict] = {}
    for i, n in enumerate(cand):
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m")
        fa = future_aware_route(net, n, hazard, departure_min=0.0,
                                time_budget_min=float(prm["time_budget_min"]),
                                p_cut=p_cut, time_step_min=float(prm["time_step_min"]))
        if nv.reached and nv.enters_hazard and fa.reached and not fa.enters_hazard:
            bucket = "naive_into_FA_safe"
        elif nv.reached and nv.enters_hazard and not fa.reached:
            bucket = "no_safe_route"
        elif nv.reached and not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            bucket = "both_safe"
        else:
            bucket = "other"
        classes[bucket].append(n)
        if bucket in ("naive_into_FA_safe", "no_safe_route"):
            blind[n] = {"bucket": bucket, "blind_reached": bool(nv.reached),
                        "blind_distance_m": float(nv.total_distance_m)}
        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{len(cand)}] scanned", file=sys.stderr, flush=True)
    counts = {k: len(v) for k, v in classes.items()}
    return counts, blind


def present_perimeter_view(net, hazard, p_cut: float) -> tuple[RoadNetwork, dict]:
    """The walk graph with every node standing in the PRESENT fire removed.

    ``hazard.prob_at(x, y, 0.0)`` is the same predicate ``candidate_origins``
    uses to refuse an origin that is already burning, so no new rule is
    introduced here and no parameter is free.
    """
    keep = set()
    burning = set()
    for n in net.graph.nodes:
        x, y = net.node_xy(n)
        if float(hazard.prob_at(x, y, 0.0)) >= p_cut:
            burning.add(n)
        else:
            keep.add(n)
    sub = net.graph.subgraph(keep).copy()
    view = RoadNetwork(graph=sub, shelters=set(net.shelters) & keep)
    stats = {
        "n_nodes_before": int(net.graph.number_of_nodes()),
        "n_nodes_removed": int(len(burning)),
        "n_nodes_after": int(sub.number_of_nodes()),
        "n_edges_before": int(net.graph.number_of_edges()),
        "n_edges_after": int(sub.number_of_edges()),
        "n_shelters_before": int(len(net.shelters)),
        "n_shelters_removed": int(len(set(net.shelters) - keep)),
        "n_shelters_after": int(len(view.shelters)),
    }
    return view, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    canon, prm, hazard, haz, extent, net, snaps = build()
    p_cut = float(prm["p_cut"])
    cand, _ign = candidate_origins(net, hazard, haz, extent, p_cut)
    print(f"[pp] {len(cand)} candidate origins", file=sys.stderr, flush=True)
    if len(cand) != EXPECTED_ORIGINS:
        print(f"[pp] REFUSING TO WRITE: {len(cand)} origins, expected {EXPECTED_ORIGINS}",
              file=sys.stderr)
        return 1

    counts, blind = reproduce_partition(net, cand, hazard, prm)
    print(f"[pp] recomputed partition: {counts}", file=sys.stderr, flush=True)
    if any(counts.get(k) != v for k, v in EXPECTED.items()) or counts.get("other"):
        print(f"[pp] REFUSING TO WRITE: partition {counts} != committed {EXPECTED}",
              file=sys.stderr)
        return 1

    view, filt = present_perimeter_view(net, hazard, p_cut)
    print(f"[pp] present-perimeter view: {filt}", file=sys.stderr, flush=True)

    per_origin = []
    for n in sorted(blind):
        if n not in view.graph:
            res = {"origin": int(n), "bucket": blind[n]["bucket"],
                   "outcome": "origin_removed_by_filter",
                   "pp_reached": False, "pp_enters_hazard": None,
                   "pp_distance_m": None,
                   "blind_distance_m": blind[n]["blind_distance_m"]}
            per_origin.append(res)
            continue
        if not view.shelters:
            raise SystemExit("the present-perimeter filter removed every shelter")
        r = naive_route(view, n, hazard, departure_min=0.0, p_cut=p_cut,
                        objective="length_m")
        if not r.reached:
            outcome = "not_reached"
        elif r.enters_hazard:
            outcome = "still_enters_forecast"
        else:
            outcome = "saved"
        per_origin.append({
            "origin": int(n), "bucket": blind[n]["bucket"], "outcome": outcome,
            "pp_reached": bool(r.reached),
            "pp_enters_hazard": bool(r.enters_hazard),
            "pp_distance_m": float(r.total_distance_m),
            "blind_distance_m": blind[n]["blind_distance_m"],
        })

    outcomes = {k: sum(1 for r in per_origin if r["outcome"] == k)
                for k in ("saved", "still_enters_forecast", "not_reached",
                          "origin_removed_by_filter")}
    n_target = len(per_origin)
    needs_forecast = outcomes["still_enters_forecast"]

    payload = {
        "_readme": (
            "WFG-129. Of the origins whose FIRE-BLIND route enters the forecast on the "
            "canonical Yeongdeok field, how many a PRESENT-PERIMETER-ONLY router already "
            "saves. The present-perimeter arm is slice 0 of the committed hazard field "
            "used as a node filter (prob_at(x, y, 0.0) >= p_cut, the same predicate "
            "candidate_origins uses to refuse a burning origin), then the repository's "
            "own naive_route over the filtered graph, SCORED against the full forecast "
            "exactly as the other two arms are. Zero buffer: this is NOT WFG-033(b). "
            "Read docs/present_perimeter_yeongdeok.md, section 5, before quoting any "
            "number here."
        ),
        "written_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ"),
        "region": "yeongdeok-2025",
        "parameters": {k: prm[k] for k in sorted(prm)},
        "inputs": {
            "canonical_npz": {"path": str(NPZ.relative_to(REPO)), "sha256": sha256(NPZ)},
            "canonical_json": {"path": str(CANON.relative_to(REPO)), "sha256": sha256(CANON)},
            "snapshots": {k: {"path": str(v.relative_to(REPO)), "sha256": sha256(v)}
                          for k, v in snaps.items()},
        },
        "reproduction_gate": {
            "_readme": "The run writes nothing unless these reproduce the committed artifact.",
            "expected": {**EXPECTED, "n_origins_scanned": EXPECTED_ORIGINS},
            "recomputed": {**{k: counts[k] for k in EXPECTED}, "n_origins_scanned": len(cand)},
            "passed": True,
        },
        "present_perimeter_filter": filt,
        "target_set": {
            "n": n_target,
            "definition": ("every origin whose fire-blind route REACHES a refuge and "
                           "ENTERS the forecast hazard: the committed naive_into_FA_safe "
                           "(42) plus no_safe_route (2)"),
            "by_bucket": {k: sum(1 for r in per_origin if r["bucket"] == k)
                          for k in ("naive_into_FA_safe", "no_safe_route")},
            "all_reached_fire_blind": True,
        },
        "outcomes": outcomes,
        "headline": {
            "n_target": n_target,
            "n_saved_by_present_perimeter": outcomes["saved"],
            "n_still_entering_the_forecast": needs_forecast,
            "n_not_reached_under_the_filter": outcomes["not_reached"]
            + outcomes["origin_removed_by_filter"],
        },
        "what_this_is_not": (
            "It is NOT a margin, and no width was swept, so no width could be chosen "
            "after the answer. It is NOT a re-scoring of the committed 42: that number "
            "and its fire-blind opponent are untouched, and nothing here moves a "
            "registered value. It is NOT transferable to the 91 on Uiseong-Andong, which "
            "is a different region measured with a different arm "
            "(docs/present_perimeter_arm.md). It is ONE fire, ONE region, ONE horizon, "
            "and the 32.6 % envelope-coverage caveat of the canonical field applies to it "
            "unchanged. An origin counted as not_reached is the FILTER's doing and not "
            "the fire's: every origin in the target set was reached by the fire-blind "
            "router on the unfiltered graph, so a large not_reached group would mean the "
            "filter disconnected the graph rather than that the present perimeter failed."
        ),
        "per_origin": per_origin,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"[pp] wrote {args.out.relative_to(REPO)}")
    print(f"[pp] of {n_target} fire-blind-failing origins: "
          f"{outcomes['saved']} saved by the present perimeter alone, "
          f"{needs_forecast} still enter the forecast, "
          f"{outcomes['not_reached'] + outcomes['origin_removed_by_filter']} not reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
