#!/usr/bin/env python
"""The fair opponent for the headline: present perimeter + a fixed buffer (WFG-114).

WHY THIS EXISTS
---------------
Every comparison the project ships is future-aware routing against `naive`, and
`naive` is **fire-blind**: it walks the shortest path to the nearest refuge and
only afterwards is told whether that path burned
(`src/wildfireguardian/routing/evacuation.py`, `naive_route`). Three consecutive
critic laps wrote the same objection — the headline credits the FORECAST with
what merely SEEING the present fire would already have bought — and the author
settled it on 2026-09-05 (NH-027, option A): run the fair opponent inside the
sprint and report the number whatever it says.

The fair opponent is the arm a county office can actually run today with no
model at all: refuse everything that is burning **now** plus a fixed safety
buffer, then take the shortest path through what is left.

WHAT THE ARM IS, EXACTLY
------------------------
    present_perimeter   the SAME fire-blind objective (shortest path by
                        `length_m` to the nearest surviving refuge) on the SAME
                        network, with every node within `--buffer-m`
                        (default 1,000 m) of the centre of a slice-0 cell at
                        p >= p_cut refused.

The arm must differ from the control in WHAT IT KNOWS and in nothing else, so
the difference between the columns cannot be a difference between two route
finders. A refuge inside the buffer is not a refuge and is dropped.

TWO ORIGIN RULES, BOTH REPORTED
-------------------------------
Some origins stand inside the buffer: outside the fire at slice 0 (the origin
rule guarantees that) but within a kilometre of it. What the arm is allowed to
tell them is a modelling convention, and it turned out to be worth several times
the headline, so both conventions are computed for every origin:

    walk_out (PRIMARY)   you may move within the buffer to get out, and once you
                         stand outside it you may never re-enter. Two-layer
                         Dijkstra over (node, left).
    strict               only the origin's own node is kept, so an origin whose
                         every neighbour is also buffered is scored "no route".

`walk_out` is primary because it is what a present-aware operator would actually
say, and because `strict` biases the experiment IN THE PROJECT'S FAVOUR: every
origin it strands is counted against the fair opponent and inflates the
forecast's apparent margin. The lap's own reviewer measured that inflation at
roughly fourfold, which is the exact bias this row exists to remove.

Both are scored against the FULL hazard sequence by the same `_evaluate_path`
every other arm uses, so "safe" means the same thing in every column: reached a
refuge, and never stood on a cell at p >= p_cut at the time it was standing
there.

THE CANONICAL ARM, AND A LIMITATION THAT WAS INVENTED AND THEN WITHDRAWN
-----------------------------------------------------------------------
This runs against `slope_digraph_canonical` — the arm the headline's **91**
comes from — and the script REFUSES TO WRITE unless it first reproduces that
committed arm's bucket counts and the origin ids of the two buckets the
artifact actually stores (`--verify-only` runs that check alone).

⚠ The first version of this script ran on the flat arm instead and said in
prose that the canonical arm was out of reach in the cloud, because its SRTM
raster lives at `data/raw/firms_data/uiseong_andong_2025_dem.tif` and
`data/raw/**` is git-ignored. That was FALSE, and the lap's reviewer falsified
it in 103 seconds: the same raster, byte for byte, is committed to the snapshot
store, and its MANIFEST entry records that exact `origin_path` and the same
sha256. CHARTER §4 "Sandbox facts" tells every lap to work from
`data/snapshots/` for precisely this reason. The limitation was invented by not
looking, and an invented limitation is the same defect as an invented result
(CHARTER §3.5). It is recorded here rather than quietly deleted.

Run:
    python scripts/run_present_perimeter_arm.py
    python scripts/run_present_perimeter_arm.py --verify-only
    python scripts/run_present_perimeter_arm.py --buffer-m 500 --out /tmp/x.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

# The origin rule, the classification, the snapshot resolution and the hazard
# loader are IMPORTED, not copied: a second definition of "which origins" is
# exactly how two numbers with the same name stop meaning the same thing.
import run_multi_region_routing as mrr  # noqa: E402

import heapq  # noqa: E402
import math  # noqa: E402

import networkx as nx  # noqa: E402

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.routing.evacuation import (  # noqa: E402
    _evaluate_path, naive_route,
)
from wildfireguardian.routing.future_front import RoadNetwork  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph,
)

#: The region the author's decision names. Yeongdeok is not runnable at all
#: (HANDOFF_ROUND3.md §5.4) and Uljin-Samcheok's DEM gap is a separate caveat.
REGION = "uiseong_andong_2025"

#: The committed experiment this run stands on, and the arm inside it. This is
#: the CANONICAL arm — the one the headline's 91 comes from.
#:
#: ⚠ An earlier version of this script ran on `flat_digraph_regression` and said
#: in prose that the canonical arm was unreachable in the cloud because its SRTM
#: raster lives at `data/raw/firms_data/uiseong_andong_2025_dem.tif`, which is
#: git-ignored. That was FALSE and the lap's own reviewer falsified it in 103
#: seconds: the same raster, byte for byte, is committed to the snapshot store as
#: `data/snapshots/srtm-dem_uiseong-andong-2025_*.tif`, whose MANIFEST entry
#: records that exact `origin_path` and the same sha256. CHARTER §4 "Sandbox
#: facts" says to work from `data/snapshots/` for precisely this reason. The
#: limitation was invented by not looking, and inventing a limitation is the same
#: defect as inventing a result (CHARTER §3.5).
COMMITTED = f"data/processed/real_roads_real_hazard_{REGION}.json"
COMMITTED_ARM = "slope_digraph_canonical"

#: The flat arm, reproduced as a secondary check and quoted for the crosswalk.
FLAT_ARM = "flat_digraph_regression"

#: The canonical arm's terrain parameters. NOT varied: they are what makes the
#: reproduction a reproduction (config/default.yaml, not per-region).
CANONICAL_SAMPLING_M = 60.0
CANONICAL_MAX_ABS_SLOPE = 0.60

DEFAULT_BUFFER_M = 1000.0

#: Exit codes. 4 is the repository's "a committed artifact moved" convention.
EXIT_REPRO_FAILED = 4


def _git() -> str | None:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def dem_snapshot_for(region: str) -> Path:
    """The region's SRTM raster, from the committed snapshot store.

    Resolved through `MANIFEST.json` exactly as the OSM layers are, and for the
    same reason: `data/raw/**` is git-ignored and never reaches a fresh clone,
    while the snapshot store is the evidence layer that does. The manifest
    records the raster's `origin_path` under `data/raw/firms_data/` and the same
    sha256, so this is not a substitute DEM — it is the same bytes, and CHARTER
    §3.11 (no mosaicking, no partial DEM) is untouched.
    """
    man = json.loads((REPO / "data/snapshots/MANIFEST.json").read_text(encoding="utf-8"))
    want = region.replace("_", "-")
    hits = [s for s in man["snapshots"]
            if s.get("source") == "srtm-dem" and s.get("region") == want
            and s.get("stored_file")]
    if len(hits) != 1:
        raise FileNotFoundError(
            f"expected exactly 1 srtm-dem snapshot for region={want!r}, "
            f"found {len(hits)}")
    p = REPO / "data/snapshots" / hits[0]["stored_file"]
    if not p.exists():
        raise FileNotFoundError(f"manifest lists {p.name} but it is not on disk")
    return p


def present_perimeter_nodes(net: RoadNetwork, haz: np.ndarray, extent,
                            *, p_cut: float, buffer_m: float) -> tuple[set[int], int]:
    """Nodes the present-aware arm refuses: within ``buffer_m`` of the fire now.

    "The fire now" is every grid cell at ``p >= p_cut`` in hazard **slice 0** —
    the perimeter an operator can see at the moment the decision is taken, with
    no model of where it goes next. Distance is straight-line from the node to
    the nearest such cell's centre, computed on the projected coordinates
    (EPSG:5179, metres), so the answer does not depend on how the hazard grid
    happens to be tiled. A cell is 500 m across and its half-diagonal is 354 m,
    so "inside a burning cell" is contained in "within 1 km of one" and needs no
    separate rule.
    """
    xmin, ymin, xmax, ymax, cell = extent
    rr, cc = np.where(haz[0] >= p_cut)
    if rr.size == 0:
        raise RuntimeError(
            "no cell is at or above the cutoff in slice 0: there is no present "
            "perimeter to route around, and this arm has no meaning")
    core_x = xmin + (cc + 0.5) * cell
    core_y = ymax - (rr + 0.5) * cell
    nodes = list(net.graph.nodes)
    nx_arr = np.array([net.graph.nodes[n]["x"] for n in nodes], float)
    ny_arr = np.array([net.graph.nodes[n]["y"] for n in nodes], float)
    # (n_nodes, n_core) is 6,678 x 53 here — small enough to do exactly.
    d2 = ((nx_arr[:, None] - core_x[None, :]) ** 2
          + (ny_arr[:, None] - core_y[None, :]) ** 2)
    dmin = np.sqrt(d2.min(axis=1))
    refused = {n for n, d in zip(nodes, dmin) if d <= buffer_m}
    return refused, int(rr.size)


def pruned_network(net: RoadNetwork, refused: set[int]) -> RoadNetwork:
    """The same network with the refused nodes deleted, refuges included.

    A refuge inside the present perimeter's buffer is not a refuge. Dropping it
    is the honest reading of the arm — an operator who refuses to send anyone
    within 1 km of the fire does not make an exception for the building they
    were going to send them to.
    """
    keep = [n for n in net.graph.nodes if n not in refused]
    sub = net.graph.subgraph(keep).copy()
    return RoadNetwork(graph=sub, shelters={s for s in net.shelters if s not in refused})


def present_perimeter_route(net: RoadNetwork, pruned: RoadNetwork, start: int,
                            hazard, *, p_cut: float):
    """STRICT rule: the origin's own node is kept, and nothing else inside the buffer.

    An origin inside the buffer therefore has a route only if one of its
    immediate neighbours is already outside. This is the harsher of the two
    conventions and it is reported beside, not instead of, :func:`walk_out_route`
    — see that function for why it is not the primary one.
    """
    if start in pruned.graph:
        return naive_route(pruned, start, hazard, departure_min=0.0, p_cut=p_cut)
    g = pruned.graph.copy()
    g.add_node(start, **net.graph.nodes[start])
    for _u, v, d in net.graph.out_edges(start, data=True):
        if v in g:
            g.add_edge(start, v, **d)
    return naive_route(RoadNetwork(graph=g, shelters=set(pruned.shelters)),
                       start, hazard, departure_min=0.0, p_cut=p_cut)


def walk_out_route(net: RoadNetwork, refused: set[int], shelters: set[int],
                   start: int, hazard, *, p_cut: float):
    """WALK-OUT rule (the primary one): you may leave the buffer, never re-enter.

    WHY THIS EXISTS, AND WHY IT IS THE HONEST ONE
    ---------------------------------------------
    The strict rule above scores a resident 900 m from the fire as "no route"
    whenever all of their immediate neighbours are also inside the buffer — even
    though a road out plainly exists. That is not what a present-aware operator
    would say to them, and it is not what this document's own prose promised
    ("you start where you stand"). It also biases the experiment in the
    PROJECT'S FAVOUR: every origin the convention strands is counted against the
    fair opponent and so inflates the forecast's apparent margin. The lap's
    reviewer measured that inflation and it is roughly fourfold, which is the
    exact bias this row existed to remove.

    So the rule is: while you are still inside the buffer you may move within it
    to get out; the moment you stand on a node outside it, you may never enter it
    again. Implemented as a two-layer Dijkstra over states ``(node, left)`` where
    ``left`` is 0 while still inside and 1 once out; the 0 -> 1 transition
    happens on first arrival at an unbuffered node and there is no 1 -> 0 edge.
    An origin already outside the buffer starts at ``left = 1``, where the state
    graph collapses to the pruned network and the two rules agree exactly.

    Ranked by ``length_m``, like the fire-blind control, and scored by the same
    ``_evaluate_path`` as every other arm.
    """
    g = net.graph
    start_left = 0 if start in refused else 1
    goals = {s for s in shelters if s not in refused}
    if not goals:
        raise ValueError("no refuge survives the buffer")
    dist: dict[tuple[int, int], float] = {(start, start_left): 0.0}
    prev: dict[tuple[int, int], tuple[int, int]] = {}
    pq: list[tuple[float, int, int]] = [(0.0, start, start_left)]
    seen: set[tuple[int, int]] = set()
    goal_state = None
    while pq:
        d_u, u, left = heapq.heappop(pq)
        if (u, left) in seen:
            continue
        seen.add((u, left))
        if u in goals:
            goal_state = (u, left)
            break
        for v in g.neighbors(u):
            v_ref = v in refused
            if left == 1 and v_ref:
                continue  # out already: the buffer is closed behind you
            nleft = 0 if (left == 0 and v_ref) else 1
            nd = d_u + g[u][v]["length_m"]
            if nd < dist.get((v, nleft), math.inf) - 1e-12:
                dist[(v, nleft)] = nd
                prev[(v, nleft)] = (u, left)
                heapq.heappush(pq, (nd, v, nleft))
    if goal_state is None:
        return _no_route(start, "walk_out")
    chain = [goal_state]
    while chain[-1] != (start, start_left):
        chain.append(prev[chain[-1]])
    chain.reverse()
    path = [n for (n, _l) in chain]
    return _evaluate_path(net, path, hazard, 0.0, p_cut, "present_walk_out",
                          goal_state[0])


def _no_route(start: int, why: str):
    from wildfireguardian.routing.evacuation import RouteResult
    return RouteResult(kind="present_walk_out", reached=False, route=[], target=None,
                       departure_min=0.0, total_distance_m=0.0, total_time_min=0.0,
                       note=f"no route to any refuge outside the buffer ({why})")


def reproduce_committed_arm(net, cand, hazard, args) -> tuple[dict, dict, dict]:
    """Re-run the committed flat/DiGraph arm and refuse to continue if it moved.

    This is the whole warrant for the third column. If the two fire-blind and
    future-aware columns here are the committed ones, origin for origin, then
    the only thing that differs between them and the new column is the
    information the router has. If they are not, every number below is about
    this script instead of about the question, and it must not be written.
    """
    counts, classes = mrr.classify(net, cand, hazard, args.p_cut,
                                   args.time_budget_min, args.time_step_min)
    committed = json.loads((REPO / COMMITTED).read_text(encoding="utf-8"))
    arm = committed["arms"][COMMITTED_ARM]
    diffs = []
    if counts != arm["counts"]:
        diffs.append(f"bucket counts differ: got {counts}, committed {arm['counts']}")
    for bucket, ids in arm["origin_nodes_by_bucket"].items():
        got = sorted(classes.get(bucket, []))
        if got != sorted(int(i) for i in ids):
            diffs.append(f"bucket {bucket!r}: {len(got)} nodes here vs "
                         f"{len(ids)} committed, and the id sets differ")
    if len(cand) != arm["n_origins_scanned"]:
        diffs.append(f"scanned {len(cand)} origins, committed {arm['n_origins_scanned']}")
    # ⚠ Be exact about what the id check covers. The committed artifact stores
    # NO `both_safe` list (263 of 368 origins here) and several of the lists it
    # does store are empty, so "every origin node id" would be an overstatement:
    # what is graded is every id of every bucket the artifact actually carries,
    # plus the scan size, which pins `both_safe` by complement.
    graded = {b: len(ids) for b, ids in arm["origin_nodes_by_bucket"].items() if ids}
    return counts, classes, {
        "arm": COMMITTED_ARM, "reproduced": not diffs, "differences": diffs,
        "committed_counts": arm["counts"], "recomputed_counts": counts,
        "id_buckets_graded": sorted(graded),
        "n_id_buckets_graded": len(graded),
        "n_ids_graded": sum(graded.values()),
        "buckets_without_stored_ids": sorted(
            set(arm["counts"]) - set(arm["origin_nodes_by_bucket"])),
        "note": ("bucket counts are graded for all seven buckets; origin ids are "
                 "graded for every bucket the committed artifact stores a list "
                 "for. `both_safe` has no stored list and is pinned by complement "
                 "(counts match and the scan size matches)."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--buffer-m", type=float, default=DEFAULT_BUFFER_M,
                    help="fixed safety buffer around the slice-0 perimeter (m)")
    # The three routing parameters come from the same config keys the committed
    # run read, not from literals: a divergence here would be invisible.
    ap.add_argument("--p-cut", type=float,
                    default=float(mrr._cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--time-budget-min", type=float,
                    default=float(mrr._cfg("pedestrian.walk_budget_min", 600.0)))
    ap.add_argument("--time-step-min", type=float,
                    default=float(mrr._cfg("time.routing_time_step_min", 10.0)))
    ap.add_argument("--verify-only", action="store_true",
                    help="reproduce the committed arm and stop; write nothing")
    ap.add_argument("--out", default=None,
                    help="output path (default: the committed data/processed name)")
    args = ap.parse_args()

    t0 = time.monotonic()
    print(f"=== present-perimeter arm · {REGION} · buffer {args.buffer_m:.0f} m")

    hazard, haz, grid, extent, npz_sha, npz_path = mrr.load_hazard(REGION)
    snap_walk = mrr.snapshot_for(REGION, "walk")
    snap_dem = dem_snapshot_for(REGION)
    G = load_snapshot_graph(snap_walk)
    net, slope_stats = build_walk_network(
        G, snap_dem, sampling_m=CANONICAL_SAMPLING_M,
        max_abs_slope=CANONICAL_MAX_ABS_SLOPE, directed=True, apply_slope=True)
    print(f"  DEM: {snap_dem.name} (snapshot store)")
    snap_shelters = mrr.snapshot_for(REGION, "shelters")
    dests, n_shelter_features = mrr.read_poi_snapshot(snap_shelters, kind="shelter")
    if not dests:
        raise RuntimeError("zero refuges — the run would be meaningless")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    cand, ign, band = mrr.candidate_origins(net, hazard, haz, extent, args.p_cut)
    print(f"  network {net.graph.number_of_nodes():,} nodes · "
          f"{len(net.shelters)} refuge nodes · {len(cand)} origins")

    print("[1/3] reproducing the committed canonical arm ...")
    counts, classes, repro = reproduce_committed_arm(net, cand, hazard, args)
    if not repro["reproduced"]:
        print("REFUSING TO CONTINUE — the committed arm did not reproduce:")
        for d in repro["differences"]:
            print(f"  - {d}")
        return EXIT_REPRO_FAILED
    print(f"  OK — {COMMITTED_ARM} reproduces: all seven bucket counts, and the "
          f"origin ids of the {repro['n_id_buckets_graded']} non-empty bucket(s) "
          f"the committed artifact stores ({repro['n_ids_graded']} ids)")
    if args.verify_only:
        print(f"  ({time.monotonic() - t0:.1f}s)")
        return 0

    print("[2/3] building the present perimeter ...")
    refused, n_core_cells = present_perimeter_nodes(
        net, haz, extent, p_cut=args.p_cut, buffer_m=args.buffer_m)
    pruned = pruned_network(net, refused)
    lost_shelters = len(net.shelters) - len(pruned.shelters)
    print(f"  slice-0 cells at p >= {args.p_cut}: {n_core_cells}")
    print(f"  nodes refused: {len(refused)} of {net.graph.number_of_nodes():,}"
          f"  ({len(refused) / net.graph.number_of_nodes() * 100:.2f}%)")
    print(f"  refuges lost to the buffer: {lost_shelters} of {len(net.shelters)}")
    origins_in_buffer = [n for n in cand if n in refused]
    print(f"  origins standing inside the buffer: {len(origins_in_buffer)}")

    print("[3/3] routing the present-aware arm ...")
    fa_only = set(classes["naive_into_FA_safe"])

    def _score(r):
        within = r.reached and r.total_time_min <= args.time_budget_min + 1e-9
        return {
            "reached": bool(r.reached),
            "enters_hazard": bool(r.enters_hazard),
            "within_budget": bool(within),
            "safe": bool(r.reached and not r.enters_hazard and within),
            "distance_m": float(r.total_distance_m),
            "time_min": float(r.total_time_min),
        }

    # BOTH origin rules, every origin. The walk-out rule is the primary one; the
    # strict rule is kept beside it because the difference between them is a
    # modelling convention worth several times the headline, and burying either
    # would be choosing the number instead of reporting it.
    pp: dict[int, dict] = {}
    pp_strict: dict[int, dict] = {}
    for n in cand:
        pp[n] = _score(walk_out_route(net, refused, net.shelters, n, hazard,
                                      p_cut=args.p_cut))
        pp_strict[n] = _score(present_perimeter_route(net, pruned, n, hazard,
                                                      p_cut=args.p_cut))

    # The question the author asked, and its two honest neighbours.
    recovered = sorted(n for n in fa_only if pp[n]["safe"])
    still_fa_only = sorted(n for n in fa_only if not pp[n]["safe"])
    # Fire-blind routes, once: the control column, the paired detour, and the
    # budget check all read them. The detour is PAIRED — mean(present) over the
    # origins that reached minus mean(blind) over a different set of origins is
    # not a detour, it is two averages subtracted.
    blind = {n: naive_route(net, n, hazard, departure_min=0.0, p_cut=args.p_cut)
             for n in cand}

    # The cost side: origins the fire-blind control already got right, that the
    # buffer breaks. An arm that saves 40 and breaks 40 has bought nothing.
    #
    # ⚠ "already safe on the fire-blind route" is `both_safe` PLUS
    # `fa_exceeds_budget` — the latter is defined as "fire-blind route is safe
    # but the future-aware route is not", so those origins are fire-blind-safe
    # too. Scanning only `both_safe` under-counts the buffer's cost and breaks
    # the arithmetic identity by exactly that bucket's size; the lap's own test
    # caught it.
    both_safe = sorted(classes["both_safe"])
    # The committed classification scores the FIRE-BLIND route with no time
    # budget, while the forecast-aware router enforces one internally and the
    # present-aware arm is held to the same 600 minutes. Comparing them as they
    # stand is two rules in one table, and it runs in this project's favour: it
    # inflates the control AND, because those origins are counted as
    # "already safe", inflates the buffer's apparent damage. So the budget is
    # applied to the fire-blind column too, and the committed (unbudgeted)
    # figure is kept beside it rather than replaced.
    fire_blind_committed = set(classes["both_safe"]) | set(classes["fa_exceeds_budget"])
    fire_blind_late = sorted(
        n for n in fire_blind_committed
        if blind[n].total_time_min > args.time_budget_min + 1e-9)
    fire_blind_safe_set = fire_blind_committed - set(fire_blind_late)
    broken = sorted(n for n in fire_blind_safe_set if not pp[n]["safe"])
    # And the mirror term: origins NO arm saved on the fire-blind or
    # forecast-aware route that the present-aware arm nonetheless gets out.
    # "Not already safe under the consistent rule": the buckets no arm saved,
    # PLUS the fire-blind routes that arrive after the budget. Those last ones
    # must land here and not in the already-safe set, or the identity below
    # would not close and the buffer would be blamed for origins the control
    # never actually saved.
    hopeless = (set(classes["no_safe_route"]) | set(classes["both_enter"])
                | set(classes["naive_unreachable"]) | set(classes["unclassified"])
                | set(fire_blind_late))
    saved_from_hopeless = sorted(n for n in hopeless if pp[n]["safe"])

    def _modes(ids):
        """Why each arm failed, never just how often — a route that is refused
        for want of a reachable refuge and one that walks into the fire are
        different operational answers and must not be pooled."""
        return {
            "safe": sum(1 for n in ids if pp[n]["safe"]),
            "unreachable": sum(1 for n in ids if not pp[n]["reached"]),
            "enters_hazard": sum(1 for n in ids
                                 if pp[n]["reached"] and pp[n]["enters_hazard"]),
            "over_budget": sum(1 for n in ids if pp[n]["reached"]
                               and not pp[n]["enters_hazard"]
                               and not pp[n]["within_budget"]),
        }

    # The three arms on one denominator. "Safe" is the committed meaning in all
    # three columns: reached a refuge and never stood on a cell at p >= p_cut
    # while it was at p >= p_cut.
    fire_blind_safe = len(fire_blind_safe_set)
    forecast_aware_safe = len(classes["both_safe"]) + len(classes["naive_into_FA_safe"])
    present_safe = sum(1 for n in cand if pp[n]["safe"])
    # The fire-blind control is scored WITHOUT a time budget in the committed
    # classification, so the present arm is reported both ways rather than
    # letting one asymmetric rule carry the conclusion.
    present_safe_no_budget = sum(1 for n in cand
                                 if pp[n]["reached"] and not pp[n]["enters_hazard"])

    n_fa_only = len(fa_only)
    print(f"  forecast-only origins (canonical arm): {n_fa_only}")
    print(f"  of those, ALSO safe on present+buffer: {len(recovered)}"
          f"  ({len(recovered) / n_fa_only * 100:.1f}%)")
    print(f"  still forecast-only: {len(still_fa_only)}")
    print(f"  already-safe origins the buffer breaks: {len(broken)} of {len(both_safe)}")

    # The FLAT arm is now the secondary one, quoted from the committed artifact
    # so the earlier (withdrawn) flat-denominator run stays traceable.
    committed = json.loads((REPO / COMMITTED).read_text(encoding="utf-8"))
    flat_fa_only = [int(i) for i in
                    committed["arms"][FLAT_ARM]["origin_nodes_by_bucket"]["naive_into_FA_safe"]]
    canon_in_flat = sorted(set(fa_only) & set(flat_fa_only))

    def _cost(ids):
        pair = [(pp[n]["distance_m"], blind[n].total_distance_m) for n in ids
                if pp[n]["reached"] and blind[n].reached]
        if not pair:
            return None
        a = np.array([p[0] for p in pair], float)
        b = np.array([p[1] for p in pair], float)
        return {"n_paired": len(pair), "present_mean_m": round(float(a.mean()), 1),
                "fire_blind_mean_m": round(float(b.mean()), 1),
                "mean_detour_m": round(float((a - b).mean()), 1),
                "max_detour_m": round(float((a - b).max()), 1)}

    # ------------------------------------------------------------------
    # Is 1 km the answer, or is 1 km doing the work?
    # ------------------------------------------------------------------
    # Nothing in the data chose the buffer width, so the headline is reported
    # beside the same counts at four other widths. This is a SENSITIVITY BAND,
    # not a tuning exercise: no width is selected on its result, and the
    # committed number stays the one the author's decision named.
    print("[4/4] buffer sensitivity ...")
    sweep = []
    for width in sorted({250.0, 500.0, args.buffer_m, 2000.0, 3000.0}):
        ref_w, _ = present_perimeter_nodes(net, haz, extent, p_cut=args.p_cut,
                                           buffer_m=width)
        pruned_w = pruned_network(net, ref_w)
        rec = brk = safe = unreach = burns = over = hope = 0
        for n in cand:
            r = walk_out_route(net, ref_w, net.shelters, n, hazard, p_cut=args.p_cut)
            ok = bool(r.reached and not r.enters_hazard
                      and r.total_time_min <= args.time_budget_min + 1e-9)
            safe += ok
            if not r.reached:
                unreach += 1
            elif r.enters_hazard:
                burns += 1
            elif not ok:
                over += 1
            if n in fa_only and ok:
                rec += 1
            elif n in fire_blind_safe_set and not ok:
                brk += 1
            elif n in hopeless and ok:
                hope += 1
        sweep.append({"buffer_m": width, "nodes_refused": len(ref_w),
                      "refuges_left": len(pruned_w.shelters),
                      "recovered_of_forecast_only": rec,
                      "already_safe_broken": brk, "safe_total": safe,
                      "saved_from_no_safe_route": hope,
                      "forecast_margin": forecast_aware_safe - safe,
                      # WHY it fails is the whole story of this table: a small
                      # buffer fails by walking into the fire as it grows, a
                      # large one by cutting the refuges off.
                      "failed_enters_hazard": burns,
                      "failed_unreachable": unreach,
                      "failed_over_budget": over})
        print(f"  {width:6.0f} m  recovered {rec:3d}/{n_fa_only}  "
              f"broken {brk:3d}  safe {safe:3d}/{len(cand)}  "
              f"margin {forecast_aware_safe - safe:+4d}  "
              f"(burns {burns:3d} / unreachable {unreach:3d} / late {over:2d})")

    out = {
        "title": f"Present perimeter + {args.buffer_m:.0f} m buffer — the fair "
                 f"opponent for the forecast-aware headline ({REGION})",
        "schema_version": 1,
        "row": "WFG-114",
        "decision": "NH-027 option A (author, 2026-09-05); report the number whatever it says",
        "region": REGION,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "config_hash": config_hash(),
        "runtime_s": round(time.monotonic() - t0, 1),
        "parameters": {
            "buffer_m": args.buffer_m,
            "p_cut": args.p_cut,
            "time_budget_min": args.time_budget_min,
            "time_step_min": args.time_step_min,
            "routing_objective": "length_m (distance-ranked, identical to the control)",
            "timing_model": "SLOPE 60 m / DiGraph (CANONICAL) — the arm the "
                            "headline's 91 comes from, rebuilt from the SRTM "
                            "raster in the committed snapshot store",
            "slope_sampling_m": CANONICAL_SAMPLING_M,
            "max_abs_slope": CANONICAL_MAX_ABS_SLOPE,
            "origin_rule_primary": "walk_out (may leave the buffer, never re-enter)",
            "budget_rule": ("the 600-minute budget is applied to ALL THREE "
                            "columns. The committed classification does not "
                            "budget the fire-blind route; that unbudgeted figure "
                            "is kept as headline.safe_fire_blind_unbudgeted."),
            "origin_rule": "imported from run_multi_region_routing.candidate_origins",
        },
        "sources": {
            "committed_experiment": COMMITTED,
            "committed_arm": COMMITTED_ARM,
            "hazard_npz": str(npz_path.relative_to(REPO)),
            "hazard_npz_sha256": npz_sha,
            "snapshot_walk": snap_walk.name,
            "snapshot_shelters": snap_shelters.name,
        },
        "reproduction_gate": repro,
        "perimeter": {
            "slice0_core_cells": n_core_cells,
            "n_nodes_refused": len(refused),
            "n_nodes_total": net.graph.number_of_nodes(),
            "refused_fraction": round(len(refused) / net.graph.number_of_nodes(), 6),
            "refuges_before": len(net.shelters),
            "refuges_after": len(pruned.shelters),
            "origins_inside_buffer": len(origins_in_buffer),
        },
        "headline": {
            "n_origins_scanned": len(cand),
            "forecast_only": n_fa_only,
            "recovered_by_present_perimeter": len(recovered),
            "still_forecast_only": len(still_fa_only),
            "recovered_fraction": round(len(recovered) / n_fa_only, 6),
            "already_safe_broken_by_buffer": len(broken),
            "saved_from_no_safe_route": len(saved_from_hopeless),
            "saved_from_no_safe_route_note": (
                "⚠ NAME IS NARROWER THAN THE SET. It counts origins no arm saved "
                "under the uniform rule that the present-aware arm does save, "
                "which is no_safe_route + both_enter + naive_unreachable + "
                "unclassified PLUS the fire-blind routes that miss the budget. "
                "It is 0 at every width in this run."),
            "broken_by_mode": None,  # filled below from failure_modes
            "n_both_safe": len(both_safe),
            "n_fire_blind_safe_set": len(fire_blind_safe_set),
            "safe_fire_blind_unbudgeted": len(fire_blind_committed),
            "fire_blind_late_past_budget": len(fire_blind_late),
            # The arrival times themselves, so the correction in the doc quotes
            # a registered value rather than a remembered one.
            "fire_blind_late_arrivals_min": sorted(
                round(float(blind[n].total_time_min), 1) for n in fire_blind_late),
            "safe_fire_blind": fire_blind_safe,
            "safe_present_perimeter": present_safe,
            "safe_present_perimeter_no_budget": present_safe_no_budget,
            "safe_forecast_aware": forecast_aware_safe,
            "forecast_margin_over_present": forecast_aware_safe - present_safe,
        },
        "failure_modes": {
            "all_origins": _modes(sorted(cand)),
            "still_forecast_only": _modes(still_fa_only),
            "already_safe_broken_by_buffer": _modes(broken),
            "origins_inside_buffer": _modes(sorted(origins_in_buffer)),
        },
        "per_origin": {str(n): pp[n] for n in
                       sorted(set(recovered) | set(still_fa_only) | set(broken))},
        "flat_arm_crosswalk": {
            "flat_forecast_only": len(flat_fa_only),
            "canonical_forecast_only": len(fa_only),
            "ids_in_both": len(canon_in_flat),
            "note": "the flat/DiGraph arm is QUOTED from the committed artifact, "
                    "not recomputed. It is here because the first version of this "
                    "run used it as the denominator on a limitation that turned "
                    "out to be false; keeping the crosswalk makes that withdrawal "
                    "checkable rather than merely stated.",
        },
        "cost": {
            "on_recovered_origins": _cost(recovered),
            "on_all_origins": _cost(sorted(cand)),
        },
        "buffer_sensitivity": sweep,
        # What the origin convention alone is worth. Reported because the
        # difference between the two rules is several times the headline, and
        # the harsher rule is the one that flatters the forecast.
        "origin_rule_comparison": {
            "primary": "walk_out",
            "walk_out": {
                "safe_total": present_safe,
                "recovered_of_forecast_only": len(recovered),
                "forecast_margin": forecast_aware_safe - present_safe,
                "unreachable": sum(1 for n in cand if not pp[n]["reached"]),
            },
            "strict": {
                "safe_total": sum(1 for n in cand if pp_strict[n]["safe"]),
                "recovered_of_forecast_only": sum(
                    1 for n in fa_only if pp_strict[n]["safe"]),
                "forecast_margin": forecast_aware_safe - sum(
                    1 for n in cand if pp_strict[n]["safe"]),
                "unreachable": sum(1 for n in cand if not pp_strict[n]["reached"]),
            },
            "origins_inside_buffer": len(origins_in_buffer),
            "note": "strict keeps only the origin's own node inside the buffer, so "
                    "an origin whose every neighbour is also buffered is scored "
                    "'no route'. walk_out lets it leave and never re-enter. Every "
                    "origin the strict rule strands is counted against the fair "
                    "opponent, so strict inflates the forecast's margin.",
        },
        "origin_nodes": {
            "forecast_only": sorted(fa_only),
            "recovered_by_present_perimeter": recovered,
            "still_forecast_only": still_fa_only,
            "already_safe_broken_by_buffer": broken,
            "origins_inside_buffer": sorted(origins_in_buffer),
        },
        "what_this_does_not_show": [
            "The forecast-aware arm plans on the same hazard field it is scored "
            "against, so it carries NO forecast error: the margin here is what a "
            "PERFECT forecast buys over a present-perimeter policy, and this "
            "project's real model buys less by an amount this run does not "
            "measure.",
            "The buffer width is a free parameter and 1 km is the best of five "
            "widths tried on ONE fire, sitting on the crossing of two failure "
            "regimes; it is not a constant and an operator cannot know which "
            "width they are on.",
            "One region, one ignition, one departure time. The buffer band "
            "(250 m to 3 km) is a sensitivity check on this single run, not "
            "evidence that any width generalises to another fire.",
            "'Safe' is the committed definition (reached a refuge without "
            "standing on a cell at p >= p_cut when it was there), not survival.",
        ],
    }
    out["headline"]["broken_by_mode"] = out["failure_modes"][
        "already_safe_broken_by_buffer"]

    # The arithmetic identity, checked here so a wrong bucket cannot reach disk.
    h = out["headline"]
    assert h["safe_present_perimeter"] == (
        h["safe_fire_blind"] + h["recovered_by_present_perimeter"]
        + h["saved_from_no_safe_route"] - h["already_safe_broken_by_buffer"]), h
    for row in sweep:
        assert row["safe_total"] == (
            h["safe_fire_blind"] + row["recovered_of_forecast_only"]
            + row["saved_from_no_safe_route"] - row["already_safe_broken"]), row

    dest = Path(args.out) if args.out else (
        REPO / f"data/processed/present_perimeter_arm_{REGION}.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {dest.relative_to(REPO) if dest.is_relative_to(REPO) else dest}"
          f"  ({out['runtime_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
