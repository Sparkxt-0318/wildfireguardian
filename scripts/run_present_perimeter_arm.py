#!/usr/bin/env python
"""WFG-114 — the fair opponent for the headline: present perimeter + buffer.

Round-4. Decided by the author on 2026-09-05 (NH-027 option A), whose text is
「Run it in the sprint now, P0 ... report the number whatever it says」.

WHAT QUESTION THIS ANSWERS
--------------------------
The committed 459-series headline says that on 의성·안동 2025, **91 of 368**
scanned origins (24.7 %) reach a refuge safely on the forecast-aware route and
walk into the fire on the baseline route. Four consecutive critic laps have
written down the same objection, and it is correct: that baseline (`naive_route`)
is **fire-blind**. It takes the shortest path to the nearest shelter and never
looks at the fire at all. Beating it does not show that the FORECAST is worth
anything; it shows that looking at the fire is worth something.

The fair opponent is the one a county emergency office actually has today: a
map of where the fire **is right now**, plus a safety margin. So this script
adds a third planner —

    naive            sees nothing                     (the committed control)
    present + buffer sees the perimeter at slice 0,    (THIS ARM)
                     dilated by a fixed buffer, and
                     nothing about how it will move
    forecast-aware   sees the whole simulated          (the committed headline)
                     evolution of the hazard field

— routes the SAME origins to the SAME refuges under the SAME budget on the SAME
committed hazard field, and reports how many of the 91 forecast-aware-only
origins the present-aware arm also saves.

HOW THE PRESENT-AWARE PLANNER IS BUILT, AND WHY THIS WAY
--------------------------------------------------------
It is the identical router (`future_aware_route`) run against a **frozen**
hazard: a `HazardSequence` whose every time slice is the same static mask, 1.0
inside (slice-0 core dilated by the buffer) and 0.0 outside. That is exactly
"refuse the cells that are burning now, plus a margin, and otherwise take the
quickest way out" — with a binary field the exposure objective is flat outside
the mask, so the tie-break on earliest arrival decides the path.

Reusing the same router is the point. The only thing that differs between the
present-aware arm and the forecast-aware arm is **what the planner was allowed
to know**. Graph, refuges, budget, `p_cut`, time step, origin rule: identical.

Then the planned path is scored against the **true** hazard sequence with
`_evaluate_path`, the same scorer the committed run uses. Planning on the frozen
field and grading on the real one is the whole experiment; grading on the frozen
field would be marking your own homework.

THE BUFFER IS SWEPT, NOT CHOSEN
-------------------------------
The author's row names 1 km. Reporting only 1 km would invite the obvious
objection that the opponent's one free parameter was picked to make it lose, so
the buffer is swept over 0 / 0.5 / 1 / 2 / 3 / 5 km and the whole curve is
reported. 1 km stays the headline because the author named it.

WHAT THIS DOES NOT SHOW
-----------------------
- Nothing about 영덕. Its July walk graph is unrecoverable
  (docs/DATA_LOSS_2026-07-24.md) and is never re-derived; see
  docs/HANDOFF_ROUND3.md §5.4.
- Nothing about real evacuation behaviour. Origins are road-network nodes at a
  fixed stride, not households (docs/building_origins.md).
- Nothing about a real fire's real perimeter. Both arms are graded against the
  SIMULATED hazard field, so this compares planners on one common synthetic
  ground truth, not against observation.

Run:  python scripts/run_present_perimeter_arm.py
      python scripts/run_present_perimeter_arm.py --limit-origins 20   (smoke)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy import ndimage

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import (  # noqa: E402
    _evaluate_path, build_time_expanded_field, future_aware_route, naive_route,
)
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import Destination  # noqa: E402
from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph  # noqa: E402
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

REGION = "uiseong_andong_2025"
SNAPSHOTS = REPO / "data" / "snapshots"
MANIFEST = SNAPSHOTS / "MANIFEST.json"
OUT = REPO / "data" / "processed" / "present_perimeter_arm_uiseong_andong_2025.json"

#: The committed 459-series artifact this arm is bolted onto. Its canonical arm
#: supplies the 91 forecast-aware-only origins, and this run re-derives them as
#: a self-check rather than trusting the file.
COMMITTED = REPO / "data" / "processed" / "real_roads_real_hazard_uiseong_andong_2025.json"

#: Buffer radii in metres. 1000 is the author's; the rest exist so the headline
#: is read off a curve instead of a single point.
BUFFER_SWEEP_M = (0.0, 500.0, 1000.0, 2000.0, 3000.0, 5000.0)
HEADLINE_BUFFER_M = 1000.0

#: Every one of these matches the committed run and is NOT varied here.
REAL_OSM_SCAN_STRIDE = int(_cfg("origin_scan.real_osm_stride", 18))
P_CUT = 0.5
TIME_BUDGET_MIN = 600.0
TIME_STEP_MIN = 10.0
SAMPLING_M = 60.0
MAX_ABS_SLOPE = 0.6

#: Committed artifacts this run must not disturb. It writes one new file and
#: reads everything else, but the check is cheap and the failure it guards
#: against (a library with a side effect on a cache) is not hypothetical.
PROTECTED = (
    "data/processed/real_roads_real_hazard_uiseong_andong_2025.json",
    "data/processed/hazard_uiseong_andong_2025.npz",
)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_for(source: str, region: str = REGION) -> Path:
    """Resolve one snapshot file from MANIFEST.json, or raise.

    ``source`` is the manifest's full source string (``osm-walk``,
    ``osm-shelters``, ``srtm-dem``). Unlike the multi-region script this also
    resolves the DEM from the snapshot store: `data/raw/**` is git-ignored and
    never reaches a fresh clone, so a cloud lap that read the DEM from there
    could not run this at all (CHARTER §4, sandbox facts).
    """
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    want_region = region.replace("_", "-")
    hits = [s for s in man["snapshots"]
            if s.get("source") == source and s.get("region") == want_region
            and s.get("stored_file")]
    if len(hits) != 1:
        raise FileNotFoundError(
            f"expected exactly 1 snapshot for source={source!r} "
            f"region={want_region!r}; found {len(hits)}")
    p = SNAPSHOTS / hits[0]["stored_file"]
    if not p.exists():
        raise FileNotFoundError(f"manifest lists {p.name} but it is not on disk")
    return p


def load_hazard():
    """The committed hazard field, read exactly as run_multi_region_routing does."""
    npz = REPO / f"data/processed/hazard_{REGION}.npz"
    z = np.load(npz)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    return hazard, haz, grid, (xmin, ymin, xmax, ymax, cell), _sha256(npz)


def read_shelters(path: Path) -> list[Destination]:
    import geopandas as gpd

    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf.to_crs("EPSG:5179")
    out = []
    for i, row in gdf.iterrows():
        g = row.geometry
        if g is None or g.is_empty:
            continue
        out.append(Destination(str(row.get("name") or f"shelter_{i}"),
                               float(g.x), float(g.y), kind="shelter", source="osm"))
    return out


def candidate_origins(net, hazard, haz, extent, p_cut=P_CUT):
    """Byte-for-byte the committed origin rule (run_multi_region_routing:269)."""
    xmin, ymin, xmax, ymax, cell = extent
    core = haz[0] >= 0.5
    rr, cc = np.where(core)
    ign_y = float(ymax - (rr.mean() + 0.5) * cell)
    ign_x = float(xmin + (cc.mean() + 0.5) * cell)
    band = 0.45 * (ymax - ymin)
    cand = []
    for i, n in enumerate(sorted(net.graph.nodes)):
        if i % REAL_OSM_SCAN_STRIDE:
            continue
        x, y = net.node_xy(n)
        if hazard.prob_at(x, y, 0.0) >= p_cut:
            continue
        if abs(y - ign_y) > band:
            continue
        cand.append(n)
    return cand, (ign_x, ign_y), band


# ---------------------------------------------------------------------------
# The present-perimeter planner
# ---------------------------------------------------------------------------


def disk(radius_cells: int) -> np.ndarray:
    """A boolean disk of the given radius in cells (radius 0 -> the 1x1 identity).

    A disk rather than scipy's default cross or a square: a buffer is a distance,
    and the cross under-buffers the diagonals by 40 % while the square
    over-buffers them by the same amount.
    """
    if radius_cells <= 0:
        return np.ones((1, 1), dtype=bool)
    r = int(radius_cells)
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return (yy * yy + xx * xx) <= r * r


def present_mask(haz: np.ndarray, cell_m: float, buffer_m: float,
                 p_cut: float = P_CUT) -> np.ndarray:
    """Slice-0 core dilated by ``buffer_m``, as a boolean grid.

    The buffer is rounded UP to a whole cell, because a planner that under-runs
    the margin it was told to keep is not the planner being tested. At the
    committed 500 m grid, 1 km is exactly 2 cells and no rounding occurs.
    """
    core = haz[0] >= p_cut
    r_cells = int(np.ceil(buffer_m / cell_m - 1e-9)) if buffer_m > 0 else 0
    if r_cells <= 0:
        return core.copy()
    return ndimage.binary_dilation(core, structure=disk(r_cells))


def frozen_sequence(mask: np.ndarray, grid: CoarseGrid,
                    times_min: np.ndarray) -> HazardSequence:
    """A HazardSequence that never changes: 1.0 inside ``mask``, 0.0 outside.

    Same grid and same time stamps as the real field, so the router's bin
    arithmetic is unchanged and the two arms differ in content only.
    """
    surf = mask.astype(np.float64)
    return HazardSequence(grid=grid, times_min=np.asarray(times_min, float),
                          surfaces=[surf.copy() for _ in range(len(times_min))])


def route_present(net, origin, planning_hazard, true_hazard, field):
    """Plan on the frozen field, then grade the plan against the real one.

    Returns ``(result_or_None, reason)``. ``None`` means the present-aware
    planner produced no route, and ``reason`` then says WHICH of the two very
    different things happened:

    ``refused_to_start``
        The origin is inside the buffer. The planner will not let anyone leave;
        the advice a resident receives is "do not move".
    ``walled_off_from_every_refuge``
        The origin is outside the buffer and free to leave, but the static mask
        separates it from every refuge within the budget. The advice is "there
        is nowhere to go", which is a different failure with a different fix.

    These were one merged bucket in the first version of this script, and the
    lap's own reviewer showed the prose had invented a mechanism for the whole
    of it (all 12 "inside their own buffer") when the artifact measured only the
    union. The predicate below is the router's own refusal test, read off the
    same time-expanded table the router uses, not a re-derivation of it.
    """
    plan = future_aware_route(net, origin, planning_hazard, departure_min=0.0,
                              time_budget_min=TIME_BUDGET_MIN, p_cut=P_CUT,
                              time_step_min=TIME_STEP_MIN, field=field)
    if not plan.reached or not plan.route:
        inside = bool(field.table[field.idx[origin], 0] >= P_CUT)
        return None, ("refused_to_start" if inside
                      else "walled_off_from_every_refuge")
    graded = _evaluate_path(net, list(plan.route), true_hazard, 0.0, P_CUT,
                            "present_aware", plan.target)
    return graded, "routed"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-origins", type=int, default=0,
                    help="smoke-test only: scan the first N origins")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    t_start = time.monotonic()
    before = {p: _sha256(REPO / p) for p in PROTECTED if (REPO / p).exists()}

    hazard, haz, grid, extent, npz_sha = load_hazard()
    cell = extent[4]
    print(f"hazard {haz.shape} cell {cell:g} m  sha256 {npz_sha[:16]}...")

    G = load_snapshot_graph(snapshot_for("osm-walk"))
    dem = snapshot_for("srtm-dem")
    print(f"walk graph {G.number_of_nodes():,} nodes; DEM {dem.name}")

    net, _stats = build_walk_network(G, dem, sampling_m=SAMPLING_M,
                                     max_abs_slope=MAX_ABS_SLOPE,
                                     directed=True, apply_slope=True)
    dests = read_shelters(snapshot_for("osm-shelters"))
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    print(f"refuges: {len(dests)} POIs -> {len(net.shelters)} nodes")

    cand, ign, band = candidate_origins(net, hazard, haz, extent)
    if args.limit_origins:
        cand = cand[:args.limit_origins]
    print(f"origins scanned: {len(cand)}")

    # -- the two committed arms, re-derived here rather than read off the file --
    #    If this reproduces the committed 91, the whole comparison stands on the
    #    same network the headline stands on. If it does not, the run says so and
    #    the new numbers are not comparable to the committed ones.
    print("[1/3] re-deriving the committed naive and forecast-aware arms ...")
    true_field = build_time_expanded_field(
        net, hazard, departure_min=0.0, time_budget_min=TIME_BUDGET_MIN,
        p_cut=P_CUT, time_step_min=TIME_STEP_MIN)
    naive_res, fa_res = {}, {}
    for n in cand:
        naive_res[n] = naive_route(net, n, hazard, departure_min=0.0, p_cut=P_CUT)
        fa_res[n] = future_aware_route(net, n, hazard, departure_min=0.0,
                                       time_budget_min=TIME_BUDGET_MIN, p_cut=P_CUT,
                                       time_step_min=TIME_STEP_MIN, field=true_field)
    fa_only = [n for n in cand
               if naive_res[n].reached and naive_res[n].enters_hazard
               and fa_res[n].reached and not fa_res[n].enters_hazard]
    print(f"  forecast-aware-only origins re-derived here: {len(fa_only)}")

    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    canon = committed["arms"]["slope_digraph_canonical"]
    committed_fa_only = [int(v) for v in canon["origin_nodes_by_bucket"]["naive_into_FA_safe"]]
    reproduces = (not args.limit_origins
                  and sorted(fa_only) == sorted(committed_fa_only)
                  and len(cand) == canon["n_origins_scanned"])
    print(f"  matches the committed artifact node-for-node: {reproduces}"
          f"  (committed {len(committed_fa_only)} of {canon['n_origins_scanned']})")

    # -- how well does a fixed buffer stand in for the forecast, geometrically? --
    final_core = haz[-1] >= P_CUT
    geometry = []
    for b in BUFFER_SWEEP_M:
        m = present_mask(haz, cell, b)
        inter = int((m & final_core).sum())
        geometry.append({
            "buffer_m": b,
            "mask_cells": int(m.sum()),
            "mask_area_km2": float(m.sum() * cell * cell / 1e6),
            "final_core_cells": int(final_core.sum()),
            "final_core_cells_covered": inter,
            "final_core_fraction_covered": inter / max(int(final_core.sum()), 1),
        })

    # -- the present-aware arm, once per buffer radius ------------------------
    print("[2/3] present-perimeter arm, one pass per buffer radius ...")
    arms = []
    for b in BUFFER_SWEEP_M:
        t0 = time.monotonic()
        mask = present_mask(haz, cell, b)
        plan_hazard = frozen_sequence(mask, grid, hazard.times_min)
        plan_field = build_time_expanded_field(
            net, plan_hazard, departure_min=0.0, time_budget_min=TIME_BUDGET_MIN,
            p_cut=P_CUT, time_step_min=TIME_STEP_MIN)
        buckets: dict[str, list[int]] = {
            "present_safe": [], "present_enters": [], "present_no_route": [],
            # The two halves of present_no_route, kept apart because they are
            # different advice to a resident and a merged count let this lap's
            # first draft assert a mechanism it had not measured.
            "refused_to_start": [], "walled_off_from_every_refuge": []}
        differs_from_naive = 0
        for n in cand:
            graded, reason = route_present(net, n, plan_hazard, hazard, plan_field)
            if graded is None:
                buckets["present_no_route"].append(n)
                buckets[reason].append(n)
                continue
            if naive_res[n].reached and list(graded.route) != list(naive_res[n].route):
                differs_from_naive += 1
            buckets["present_enters" if graded.enters_hazard else "present_safe"].append(n)
        safe = set(buckets["present_safe"])
        recovered = [n for n in fa_only if n in safe]
        arms.append({
            "buffer_m": b,
            # `counts` partitions the scan; `no_route_causes` decomposes one of
            # its cells. Keeping them in separate dicts is what stops a later
            # reader from summing five numbers that overlap.
            "counts": {k: len(buckets[k]) for k in
                       ("present_safe", "present_enters", "present_no_route")},
            "no_route_causes": {k: len(buckets[k]) for k in
                                ("refused_to_start", "walled_off_from_every_refuge")},
            "n_paths_differing_from_naive": differs_from_naive,
            "fa_only_n": len(fa_only),
            "fa_only_recovered_by_present": len(recovered),
            "fa_only_still_forecast_only": len(fa_only) - len(recovered),
            "fa_only_recovered_fraction": len(recovered) / max(len(fa_only), 1),
            "origin_nodes_by_bucket": {k: [int(v) for v in vs] for k, vs in buckets.items()},
            "no_route_cause_by_node": {
                str(int(v)): ("refused_to_start" if v in set(buckets["refused_to_start"])
                              else "walled_off_from_every_refuge")
                for v in buckets["present_no_route"]},
            "fa_only_recovered_nodes": [int(v) for v in recovered],
            "runtime_s": round(time.monotonic() - t0, 1),
        })
        a = arms[-1]
        print(f"  buffer {b / 1000:>4.1f} km  safe={a['counts']['present_safe']:4d} "
              f"enters={a['counts']['present_enters']:4d} "
              f"no_route={a['counts']['present_no_route']:4d}  "
              f"recovers {a['fa_only_recovered_by_present']:3d}/{len(fa_only)} of the "
              f"FA-only origins  [{a['runtime_s']:.0f}s]")

    headline = next(a for a in arms if a["buffer_m"] == HEADLINE_BUFFER_M)

    # -- the one comparison a judge actually asks for -------------------------
    #    "How many of these 368 people get to a refuge without walking into the
    #    fire, under each planner?" Same origins, same refuges, same budget.
    #    The naive and forecast-aware rows are the committed counts, taken from
    #    the artifact whose buckets this run reproduced node-for-node above.
    cc = canon["counts"]
    # The naive planner reaches a refuge safely in TWO of the committed buckets.
    # `both_safe` is the obvious one; `fa_exceeds_budget` is entered only when
    # `not nv.enters_hazard and not fa.reached` (run_multi_region_routing.py's
    # classify), i.e. the naive route WAS safe there and it is the forecast-aware
    # arm that failed. Reporting only both_safe understates the opponent this
    # project is trying to beat, which is the wrong direction to be wrong in.
    naive_safe = cc["both_safe"] + cc["fa_exceeds_budget"]
    ladder = [{"planner": "fire-blind (naive shortest path)",
               "reaches_refuge_safely": naive_safe,
               "source": "committed artifact, both_safe + fa_exceeds_budget",
               "note": ("fa_exceeds_budget is by definition 'naive safe, "
                        "forecast-aware did not reach', so those origins are "
                        "naive successes. The naive router carries NO time "
                        "budget at all, so its row answers a slightly easier "
                        "question than the budgeted rows below it.")}]
    for a in arms:
        ladder.append({
            "planner": f"present perimeter + {a['buffer_m'] / 1000:g} km buffer",
            "reaches_refuge_safely": a["counts"]["present_safe"],
            "unsafe_routes": a["counts"]["present_enters"],
            "refused_to_move_or_no_path": a["counts"]["present_no_route"],
            "source": "this run",
        })
    ladder.append({"planner": "forecast-aware (the committed headline)",
                   "reaches_refuge_safely": cc["both_safe"] + cc["naive_into_FA_safe"],
                   "source": "committed artifact, both_safe + naive_into_FA_safe",
                   "note": ("Optimistic in its own way, and the mirror of the "
                            "present-aware arm's upper bound: this planner is "
                            "handed a NOISELESS oracle of the exact field it is "
                            "then graded on. Neither aware arm is what a real "
                            "office would run.")})

    # -- Does the forecast-aware arm escape through ground that BURNS? --------
    #    The lap's reviewer refused the sentence "the forecast planner gets them
    #    out because it knows which side stays open" as an unmeasured mechanism,
    #    and it was right: 80 of the 203 cells in the 1 km mask never reach p_cut
    #    at any slice, so a path crossing the mask may simply be crossing ground
    #    that never burns — which needs no knowledge of timing at all. This
    #    distinguishes the two explanations. For every origin the present-aware
    #    arm walls off, take the forecast-aware path it DID find and count the
    #    nodes it puts inside the mask, split by whether the true hazard at that
    #    node ever reaches p_cut. Timing knowledge is doing the work only for the
    #    nodes that do burn.
    node_ever_burns = {
        n: bool(np.isfinite(true_field.t_cut[true_field.idx[n]])) for n in true_field.nodes
    }
    for b, a in zip(BUFFER_SWEEP_M, arms):
        mask = present_mask(haz, cell, b)
        walled = [int(v) for v in a["origin_nodes_by_bucket"]["walled_off_from_every_refuge"]]
        detail = []
        for n in walled:
            fa = fa_res.get(n)
            if fa is None or not fa.reached or not fa.route:
                continue
            burning, never = 0, 0
            for node in fa.route:
                x, y = net.node_xy(node)
                col = int((x - extent[0]) // cell)
                row = int((extent[3] - y) // cell)
                if not (0 <= row < mask.shape[0] and 0 <= col < mask.shape[1]):
                    continue
                if not mask[row, col]:
                    continue
                if node_ever_burns.get(node, False):
                    burning += 1
                else:
                    never += 1
            detail.append({"origin": n, "fa_nodes_in_mask_that_ever_burn": burning,
                           "fa_nodes_in_mask_that_never_burn": never})
        n_timing = sum(1 for d in detail if d["fa_nodes_in_mask_that_ever_burn"] > 0)
        a["walled_off_escape_analysis"] = {
            "n_walled_off_with_a_forecast_route": len(detail),
            "n_whose_forecast_route_crosses_ground_that_does_burn": n_timing,
            "n_whose_forecast_route_only_crosses_ground_that_never_burns":
                len(detail) - n_timing,
            "per_origin": detail,
            "note": ("The first count is the one where TIMING knowledge is doing "
                     "the work: the forecast-aware path crosses cells inside the "
                     "present-aware arm's refused mask that DO reach p_cut later, "
                     "so it is passing before they burn. The second is where the "
                     "buffer was simply too wide — the path crosses only ground "
                     "that never burns at all, which needs no forecast."),
        }
    mask_1km = present_mask(haz, cell, HEADLINE_BUFFER_M)
    ever = (haz >= P_CUT).any(axis=0)
    mask_burn = {
        "mask_cells": int(mask_1km.sum()),
        "mask_cells_that_ever_burn": int((mask_1km & ever).sum()),
        "mask_cells_that_never_burn": int((mask_1km & ~ever).sum()),
        "fraction_of_mask_that_never_burns":
            float((mask_1km & ~ever).sum()) / max(int(mask_1km.sum()), 1),
        "note": ("How much of the 1 km refused region is margin over ground that "
                 "never burns. A large number here means the buffer is wide, not "
                 "that the forecast is clever."),
    }

    # -- WHY each unrecovered forecast-only origin was not recovered -----------
    #    Load-bearing for the prose: an origin the present-aware arm sends into
    #    the fire and an origin it refuses to move are different failures, and
    #    only the second one is what happens at 1 km.
    fa_only_set = set(fa_only)
    for a in arms:
        en = set(a["origin_nodes_by_bucket"]["present_enters"])
        refused = set(a["origin_nodes_by_bucket"]["refused_to_start"])
        walled = set(a["origin_nodes_by_bucket"]["walled_off_from_every_refuge"])
        missed = fa_only_set - set(a["fa_only_recovered_nodes"])
        a["fa_only_missed_because"] = {
            "refused_to_start": len(missed & refused),
            "walled_off_from_every_refuge": len(missed & walled),
            "route_entered_the_fire": len(missed & en),
        }

    print("[3/3] writing ...")
    after = {p: _sha256(REPO / p) for p in before}
    if after != before:
        raise RuntimeError(f"a protected artifact changed during the run: "
                           f"{[k for k in before if before[k] != after[k]]}")

    out = {
        "title": "Present-perimeter + buffer arm (the fair opponent), uiseong_andong_2025",
        "schema_version": 1,
        "row": "WFG-114",
        "decided_by": "the author, 2026-09-05, NH-027 option A",
        "region": REGION,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "config_hash": config_hash(),
        "runtime_s": round(time.monotonic() - t_start, 1),
        "inputs": {
            "hazard_npz_sha256": npz_sha,
            "walk_graph_snapshot": snapshot_for("osm-walk").name,
            "dem_snapshot": dem.name,
            "shelters_snapshot": snapshot_for("osm-shelters").name,
            "committed_artifact": str(COMMITTED.relative_to(REPO)),
        },
        "parameters": {
            "p_cut": P_CUT, "time_budget_min": TIME_BUDGET_MIN,
            "time_step_min": TIME_STEP_MIN, "origin_scan_stride": REAL_OSM_SCAN_STRIDE,
            "slope_sampling_m": SAMPLING_M, "max_abs_slope": MAX_ABS_SLOPE,
            "routing_objective": "length_m (naive) / exposure-min (both aware arms)",
            "identical_to_committed_run": True,
            "source": "config/default.yaml + run_multi_region_routing.py — NOT varied",
        },
        "n_origins_scanned": len(cand),
        "ignition_proxy_xy_5179": [ign[0], ign[1]],
        "reach_band_m": band,
        "committed_arm_reproduction": {
            "fa_only_here": len(fa_only),
            "fa_only_committed": len(committed_fa_only),
            "n_origins_committed": canon["n_origins_scanned"],
            "node_for_node_match": bool(reproduces),
            "note": ("The committed 91 is re-derived on this machine from the "
                     "snapshot graph before any new arm is run. A False here means "
                     "the new numbers are NOT comparable to the committed headline "
                     "and must not be quoted beside it."),
        },
        # Everything is keyed by buffer radius in metres, never by list
        # position. A registered `json_path` like `arms.1.counts` silently
        # changes meaning the day someone adds a radius to BUFFER_SWEEP_M, and a
        # number in prose should not depend on the order of a list. The arms are
        # stored ONCE, here, so there is no second copy to drift.
        "geometry_by_buffer_m": {f"{g['buffer_m']:.0f}": g for g in geometry},
        "arms_by_buffer_m": {f"{b:.0f}": a for b, a in zip(BUFFER_SWEEP_M, arms)},
        "mask_1km_vs_what_actually_burns": mask_burn,
        "planner_ladder": ladder,
        "ladder_safe_counts": {
            "naive": naive_safe,
            **{f"present_{b:.0f}m": a["counts"]["present_safe"]
               for b, a in zip(BUFFER_SWEEP_M, arms)},
            "forecast_aware": cc["both_safe"] + cc["naive_into_FA_safe"],
        },
        "headline_buffer_m": HEADLINE_BUFFER_M,
        "gaps": {
            "forecast_minus_present_1km": (cc["both_safe"] + cc["naive_into_FA_safe"])
            - next(a for a in arms if a["buffer_m"] == 1000.0)["counts"]["present_safe"],
            "forecast_minus_present_best": (cc["both_safe"] + cc["naive_into_FA_safe"])
            - max(a["counts"]["present_safe"] for a in arms),
            "note": ("The two numbers §5 of the doc leads with. Both are UPPER "
                     "bounds on the forecast's advantage: the opponent never "
                     "re-plans, and the forecast arm is graded on the field it "
                     "was shown."),
        },
        "headline": {
            "fa_only_n": headline["fa_only_n"],
            "fa_only_recovered_by_present": headline["fa_only_recovered_by_present"],
            "fa_only_still_forecast_only": headline["fa_only_still_forecast_only"],
            "fa_only_recovered_fraction": headline["fa_only_recovered_fraction"],
            "present_safe": headline["counts"]["present_safe"],
            "present_enters": headline["counts"]["present_enters"],
            "present_no_route": headline["counts"]["present_no_route"],
        },
        "limitations": [
            "THE PRESENT-AWARE ARM NEVER RE-PLANS. Its frozen field pins slice-0 "
            "knowledge for the whole 600-minute horizon, so it is a single-shot "
            "planner. A county office with a perimeter map re-runs it as the map "
            "updates. A receding-horizon present-aware replanner would be a "
            "STRICTLY STRONGER opponent than this one and has not been built, so "
            "the residual forecast advantage reported here is an UPPER bound on "
            "the forecast's advantage.",
            "The two aware arms are therefore NOT identical except in knowledge: "
            "they also differ in whether the planner may update its plan, and in "
            "whether it may refuse to start at all.",
            "The forecast-aware arm is optimistic in the mirror-image way: it is "
            "given a noiseless oracle of the exact hazard field it is graded on. "
            "That is a LARGER optimism than the present-aware arm's true "
            "perimeter, and correcting it would narrow the gap further.",
            "Both arms are graded against the SIMULATED hazard field, not an "
            "observed perimeter. This ranks planners on one common synthetic "
            "ground truth; it does not validate the spread model.",
            "Origins are road-network nodes at stride 18, not households "
            "(docs/building_origins.md).",
            "One region, one ignition, one weather realisation. 영덕 is not run "
            "(docs/DATA_LOSS_2026-07-24.md).",
            "The present-aware planner is given the TRUE slice-0 perimeter. A "
            "real office works from a detection product with its own error, so "
            "this arm is an UPPER bound on what present-perimeter routing achieves.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"wrote {args.out}  ({args.out.stat().st_size:,} bytes)")
    print(f"HEADLINE (1 km buffer): the present-aware arm recovers "
          f"{headline['fa_only_recovered_by_present']} of {headline['fa_only_n']} "
          f"forecast-aware-only origins; "
          f"{headline['fa_only_still_forecast_only']} remain forecast-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
