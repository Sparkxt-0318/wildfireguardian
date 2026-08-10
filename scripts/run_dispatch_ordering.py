#!/usr/bin/env python
"""Does 「시한이 임박한 순서로 배차한다」 actually rescue more people?

Round-4 PHASE 23.

THE QUESTION
------------
Contribution ② of this project is that the dispatch list is sorted by urgency —
``closing_window = ingress_survival − responder_ETA`` ascending. That ordering has
never been compared against any other ordering. This script compares it against
three alternatives on already-computed corridor closure times and responder ETAs.

⚠ NO ROUTING LOGIC IS MODIFIED. Every ``responder_eta_min`` and
``ingress_survival_time_min`` used here comes out of the committed pipeline
(``rescue_demo.run_pipeline`` → ``rescue.build_dispatch_list``) unchanged. Only the
ORDER in which the dispatch list is walked, and the unit-occupancy rule, vary.

⚠⚠ THIS CHANGES THE BEHAVIOUR OF THE COMMITTED CAPACITY MODEL
--------------------------------------------------------------
``rescue.py::capacity_triage`` (untouched by this script, still the shipped model)
sets a unit's next free time to ``departure + service``. Travel time therefore
never occupies a unit. STEP 0 measured the consequence: under that rule the
rescued count is ``slots × units`` and is **identical for every ordering** — four
fixed orderings and 200 random shuffles returned the same number at every unit
count and every delay, standard deviation 0.00. The committed model cannot answer
the question this script asks.

So this script replaces the occupancy rule with a travel-aware one:

  (나) depot_return   free_at' = arrival + service + travel_in     [HEADLINE]
  (가) inter_point    free_at' = arrival + service, and the NEXT trip departs from
                      the previous home over a HAZARD-UNCHECKED drive-network
                      shortest path                               [SENSITIVITY ONLY]

Success is UNCHANGED from the committed model:
``arrival ≤ deadline = min(ingress_survival_time, dispatch_delay + W)``.

⚠ (가) IS A SENSITIVITY ARM, NEVER A HEADLINE. Its inter-point legs are plain
``time_min`` shortest paths on the drive graph: the hazard model never checks
whether those roads are open. It bounds the effect from the optimistic side. Any
number read from it must carry the words 「구간 위험 미검사」.

⚠ THE YEONGDEOK ARMS ARE THE DRIFT ARM B, NOT THE COMMITTED 439 SERIES
-----------------------------------------------------------------------
The committed run (439 origins / 167 need rescue / 24 unreachable / 143 dispatch)
serialised only ``dispatch_top20``; its OSM graph was overwritten 2026-07-24 and is
unrecoverable. Rebuilding from the preserved snapshot reproduces the drift arm B
of ``docs/network_drift.md`` — **441 / 174 / 32 / 142** — which this script asserts.
Both are correct for their inputs. Do NOT reconcile, average or substitute them.

ARMS
----
  yeongdeok_2025 · synthetic   PRIMARY. The field every committed dispatch artifact
                               was built on; its corridors close in sequence.
  uljin_samcheok_2022 · real   SECOND ARM. The only REAL forward-simulated field
                               whose corridors close in sequence (measured).
  uljin_samcheok_2022 · synthetic  the strongest deadline signal available
                               (0.0 % of closures at t=0) — the fairest possible
                               test for the deadline ordering.
  yeongdeok_2025 · real        the WEAKEST signal: 42 of its 45 closures land at
                               t=0 and 79 corridors never close, so only 3 homes
                               carry a deadline that could order anything.

⚠ That last arm was slated for EXCLUSION at STEP 0, on the branch-only
`closure_time_distribution.json` (cutoff 0.30), which measured 40/40 closures at
t=0 and ONE distinct closure time — a constant key, hence no power. At THIS
repository's cutoff of 0.70 the profile is 42 at t=0 **and 3 at t=180**: two
distinct times, not one. A near-constant key is not a constant one, so the arm is
RUN rather than dropped on a premise that shifted under a different threshold.
The artifact records this under `⚠ arm_that_was_going_to_be_excluded`.

Writes ``data/processed/dispatch_ordering_comparison.json``. Touches no committed
artifact.

Run:  python scripts/run_dispatch_ordering.py
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import heapq
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import networkx as nx  # noqa: E402

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.routing.hazard import CoarseGrid, HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueCapacityConfig, RescueConfig, capacity_triage,
)
from wildfireguardian.routing.rescue_demo import (  # noqa: E402
    _scan_origins, build_real_demo, run_pipeline,
)

SNAP = REPO / "data" / "snapshots"
OUT = REPO / "data" / "processed" / "dispatch_ordering_comparison.json"

#: Snapshot stem -> OSM cache filename, so a run reads the evidence store and
#: never data/cache/** (git-ignored, may be regenerated underneath a run).
LAYOUT = {
    "osm-walk_{stem}_*.graphml.gz": "walk.graphml",
    "osm-drive_{stem}_*.graphml.gz": "drive.graphml",
    "osm-shelters_{stem}_*.geojson": "shelters.geojson",
    "osm-depots_{stem}_*.geojson": "depots.geojson",
    "osm-firestation_{stem}_*.geojson": "fire_station.geojson",
}

#: The arms, in report order. `npz` is None for the synthetic-envelope arms.
ARMS: list[dict] = [
    {"key": "yeongdeok_2025|synthetic", "region": "yeongdeok_2025",
     "stem": "yeongdeok-2025", "field": "synthetic", "npz": None, "ign_key": None,
     "role": "PRIMARY"},
    {"key": "uljin_samcheok_2022|real", "region": "uljin_samcheok_2022",
     "stem": "uljin-samcheok-2022", "field": "real",
     "npz": "data/processed/hazard_uljin_samcheok_2022.npz", "ign_key": "ignition_xy",
     "role": "SECOND ARM"},
    {"key": "uljin_samcheok_2022|synthetic", "region": "uljin_samcheok_2022",
     "stem": "uljin-samcheok-2022", "field": "synthetic", "npz": None, "ign_key": None,
     "role": "STRONGEST DEADLINE SIGNAL"},
    # ⚠ Slated for EXCLUSION on the branch-only 0.30 measurement (40/40 closures at
    # t=0, ONE distinct closure time -> a constant sort key -> no power). At THIS
    # repository's cutoff of 0.70 that premise does not hold exactly: 42 closures at
    # t=0 and 3 at t=180, i.e. TWO distinct times. A near-constant key is not a
    # constant one, so it is RUN rather than excluded on a premise that shifted.
    {"key": "yeongdeok_2025|real", "region": "yeongdeok_2025",
     "stem": "yeongdeok-2025", "field": "real",
     "npz": "data/processed/routing_demo_canonical.npz", "ign_key": "ign_xy",
     "role": "WEAKEST DEADLINE SIGNAL — 3 of its corridors carry a non-zero deadline"},
]

#: Drift arm B, quoted from data/processed/rescue_routing_full.json. Asserted, not
#: recomputed — a mismatch means the inputs differ and the run must stop.
DRIFT_ARM_B = {
    "artifact": "data/processed/rescue_routing_full.json",
    "n_origins": 441,
    "n_need_rescue": 174,
    "n_unreachable": 32,
    "n_dispatch": 142,
}

UNITS = [1, 2, 3, 5, 8]
DELAYS = [0.0, 30.0, 60.0]
SERVICE_BASELINE = 25.0                     # PoC, verify_rescue_routing.py:76
SERVICES = [12.5, 25.0, 50.0]               # baseline, half, double
WINDOWS = [75.0, 240.0]                     # committed W, and an exploratory long W
N_RANDOM = 200
OCCUPANCY = ["depot_return", "inter_point"]


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def materialise(stem: str, dest: Path) -> dict:
    """Lay a region's snapshot files out as an OSM cache directory."""
    dest.mkdir(parents=True, exist_ok=True)
    used = {}
    for pattern, cache_name in LAYOUT.items():
        hits = sorted(SNAP.glob(pattern.format(stem=stem)))
        if not hits:
            raise FileNotFoundError(f"no snapshot matching {pattern.format(stem=stem)}")
        src = hits[-1]
        raw = gzip.decompress(src.read_bytes()) if src.suffix == ".gz" else src.read_bytes()
        (dest / cache_name).write_bytes(raw)
        used[cache_name] = {"snapshot": src.name,
                            "sha256_uncompressed": hashlib.sha256(raw).hexdigest()}
    return used


def load_real_hazard(npz_path: Path, ign_key: str):
    """The forward-simulated field as a HazardSequence, at its NATIVE slices."""
    z = np.load(npz_path)
    stack = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = (float(v) for v in z["grid_extent"])
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=stack.shape[1], ncols=stack.shape[2])
    haz = HazardSequence(grid=grid, times_min=times,
                         surfaces=[stack[i] for i in range(stack.shape[0])])
    return haz, tuple(float(v) for v in z[ign_key])


# ---------------------------------------------------------------------------
# The travel-aware occupancy model  (⚠ NOT rescue.py::capacity_triage)
# ---------------------------------------------------------------------------


def simulate(entries, order_idx, *, n_units, delay, service, window,
             occupancy, pp):
    """Walk ``entries`` in ``order_idx`` with ``n_units`` travel-aware teams.

    ``entries`` is a list of dicts carrying the COMMITTED ``responder_eta_min`` and
    ``ingress_survival_time_min``. ``pp`` is the hazard-unchecked point-to-point
    time matrix (``pp[i][j]`` minutes), used only by ``occupancy="inter_point"``.

    Rules held IDENTICAL to ``rescue.py::capacity_triage``:
      * every unit is mobilised at ``delay``;
      * the list is walked front to back and each home goes to the unit that
        becomes free earliest;
      * ``travel_in = max(0, responder_eta_min − delay)`` — the ETA already
        contains the mobilisation lag, so a home whose ETA is below the delay
        gets travel_in 0. Inherited quirk, kept so the contrast is single-variable;
      * a home is rescued iff ``arrival ≤ min(ingress_survival, delay + window)``;
      * a home that misses does NOT consume a unit.

    The ONE rule that changes: what a served unit's next free time is.
      depot_return  free_at' = arrival + service + travel_in   (drives home again)
      inter_point   free_at' = arrival + service, next departure from this home
    """
    # heap of (free_at, unit_id); loc[u] = index of the unit's current home, or
    # None when it is still at its depot.
    free = [(delay, u) for u in range(n_units)]
    heapq.heapify(free)
    loc: dict[int, int | None] = {u: None for u in range(n_units)}
    horizon = delay + window
    n = 0
    served_idx: list[int] = []
    for i in order_idx:
        e = entries[i]
        if not free:
            break
        t, uid = free[0]
        eta_leg = max(0.0, e["eta"] - delay)
        if occupancy == "inter_point" and loc[uid] is not None:
            leg = pp[loc[uid]][i]
            if not math.isfinite(leg):
                # no drive path between the two homes — the unit falls back to the
                # depot: it drives the previous home's corridor back, then this
                # home's corridor out. Skipping instead would bias (가) downward.
                leg = max(0.0, entries[loc[uid]]["eta"] - delay) + eta_leg
        else:
            leg = eta_leg
        arrival = t + leg
        if arrival > min(e["survival"], horizon) + 1e-9:
            continue
        if occupancy == "depot_return":
            heapq.heapreplace(free, (arrival + service + eta_leg, uid))
        else:
            heapq.heapreplace(free, (arrival + service, uid))
            loc[uid] = i
        n += 1
        served_idx.append(i)
    return n, served_idx


# ---------------------------------------------------------------------------
# The orderings under test
# ---------------------------------------------------------------------------


def fixed_orders(entries) -> dict[str, list[int]]:
    """Every ordering is a permutation of indices into ``entries``.

    ⚠ ``list_order`` must be the pre-sort SCAN order, not ``range(len(entries))``.
    ``build_dispatch_list`` ends with ``dispatch.sort(key=closing_window)``, so the
    list a caller receives is ALREADY the deadline order — using its index order as
    the "no sort" control would silently compare the shipped ordering against
    itself. Each entry therefore carries ``scan_rank``, recovered from the origin
    scan (see :func:`scan_ranks`).
    """
    idx = list(range(len(entries)))
    return {
        # the shipped rule: ingress_survival − responder_ETA ascending
        "deadline_closing_window": sorted(idx, key=lambda i: entries[i]["closing_window"]),
        # closest first
        "nearest_eta": sorted(idx, key=lambda i: entries[i]["eta"]),
        # earliest closure first, WITHOUT the ETA term — isolates which half of the
        # shipped key carries the signal
        "earliest_closure": sorted(idx, key=lambda i: entries[i]["survival"]),
        # no sort at all — the order the pipeline scanned the origins in
        "list_order": sorted(idx, key=lambda i: entries[i]["scan_rank"]),
    }


def scan_ranks(scenario, home_nodes: list[int]) -> list[int]:
    """Position of each dispatch home in the ORIGIN SCAN order.

    ``run_pipeline`` walks ``scenario.origins`` in order, appends the homes that
    cannot self-evacuate to ``needs_rescue``, maps them onto drive nodes and hands
    that list to ``build_dispatch_list``, which appends in the same order and only
    then sorts. So the scan order is recoverable by mapping the walk origins onto
    drive nodes exactly as ``run_pipeline`` does and taking first occurrence.
    Walk origins can collide onto one drive node, which is why it is FIRST
    occurrence and not a bijection.
    """
    pos: dict[int, int] = {}
    for rank, w in enumerate(scenario.origins):
        dn = scenario.drive.nearest_node(*scenario.walk.node_xy(w))
        pos.setdefault(int(dn), rank)
    fallback = len(scenario.origins)
    return [pos.get(int(h), fallback + i) for i, h in enumerate(home_nodes)]


def random_stats(entries, *, n_units, delay, service, window, occupancy, pp):
    vals = []
    for s in range(N_RANDOM):
        o = list(range(len(entries)))
        random.Random(s).shuffle(o)
        vals.append(simulate(entries, o, n_units=n_units, delay=delay, service=service,
                             window=window, occupancy=occupancy, pp=pp)[0])
    return {"mean": round(statistics.mean(vals), 2),
            "sd": round(statistics.pstdev(vals), 2),
            "min": min(vals), "max": max(vals), "n_seeds": N_RANDOM}


# ---------------------------------------------------------------------------
# One arm
# ---------------------------------------------------------------------------


def build_arm(spec: dict) -> dict:
    """Build the dispatch list for one (region, field) and sweep every ordering."""
    region, stem, field = spec["region"], spec["stem"], spec["field"]
    t_start = time.time()
    out: dict = {"key": spec["key"], "region": region, "hazard_field": field,
                 "role": spec["role"]}

    npz_path = REPO / spec["npz"] if spec["npz"] else None
    sha_before = _sha(npz_path) if npz_path else None

    tmp = Path(tempfile.mkdtemp(prefix=f"wfg-ord-{stem}-"))
    try:
        prov = materialise(stem, tmp / region)
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp), region_name=region)
        print(f"  [{spec['key']}] building scenario from snapshots ...", flush=True)
        sc = build_real_demo(cfg)
        cfg = sc.cfg                      # build_real_demo RESOLVES scan_stride
        if sc.walk_source != "osm" or sc.drive_source != "osm":
            raise RuntimeError(f"network degraded to walk={sc.walk_source}/"
                               f"drive={sc.drive_source}; snapshot did not load")
        if field == "real":
            haz, ign = load_real_hazard(npz_path, spec["ign_key"])
            sc = replace(sc, hazard=haz, ignition_xy=ign,
                         hazard_source="real (spread_v2 forward simulation)")
            # origins depend on the hazard, so they MUST be re-derived
            sc = replace(sc, origins=_scan_origins(sc.walk, sc.hazard, sc.route_grid,
                                                   sc.ignition_xy, sc.cfg))
        print(f"  [{spec['key']}] walk={sc.walk.graph.number_of_nodes()} "
              f"drive={sc.drive.graph.number_of_nodes()} depots={len(sc.depots)} "
              f"origins={len(sc.origins)} ...", flush=True)

        res = run_pipeline(sc, cfg)
        disp = res.dispatch
        out["network"] = {
            "walk_nodes": sc.walk.graph.number_of_nodes(),
            "drive_nodes": sc.drive.graph.number_of_nodes(),
            "drive_edges": sc.drive.graph.number_of_edges(),
            "n_depots": len(sc.depots), "n_refuges": len(sc.destinations),
            "walk_source": sc.walk_source, "drive_source": sc.drive_source,
            "depots_source": sc.depots_source, "hazard_source": sc.hazard_source,
            "snapshots": prov,
        }
        out["pipeline"] = {
            "n_origins": len(sc.origins),
            "four_way_counts": res.four_way_counts,
            "n_need_rescue": res.responder_exposure["n_need_rescue"],
            "n_dispatch": len(disp),
            "n_unreachable": len(res.unreachable_homes),
        }

        ranks = scan_ranks(sc, [int(e.home_node) for e in disp])
        entries = [{"home_node": int(e.home_node),
                    "depot_index": e.depot_index,
                    "eta": float(e.responder_eta_min),
                    "survival": float(e.ingress_survival_time_min),
                    "closing_window": float(e.closing_window_min),
                    "scan_rank": r} for e, r in zip(disp, ranks, strict=True)]
        out["closure_profile"] = closure_profile(entries)
        # the shipped list is already deadline-sorted, so a scan order that came
        # back sorted would mean the control collapsed onto the treatment
        deadline_seq = [i for i in sorted(range(len(entries)),
                                          key=lambda i: entries[i]["closing_window"])]
        scan_seq = [i for i in sorted(range(len(entries)),
                                      key=lambda i: entries[i]["scan_rank"])]
        out["list_order_control"] = {
            "distinct_from_deadline_order": deadline_seq != scan_seq,
            "n_positions_differing": sum(1 for a, b in zip(deadline_seq, scan_seq,
                                                           strict=True) if a != b),
            "why": ("build_dispatch_list ends with dispatch.sort(closing_window), so "
                    "the delivered list IS the deadline order; the 하한 대조 has to be "
                    "the pre-sort origin scan order or it compares the shipped rule "
                    "against itself."),
        }
        if not out["list_order_control"]["distinct_from_deadline_order"]:
            raise AssertionError("list_order control collapsed onto the deadline order")

        # hazard-UNCHECKED point-to-point matrix, for the (가) sensitivity arm only
        print(f"  [{spec['key']}] point-to-point matrix ({len(entries)}²) ...", flush=True)
        t0 = time.time()
        pp = point_to_point(sc.drive, [e["home_node"] for e in entries])
        out["point_to_point_matrix"] = {
            "n": len(entries),
            "build_seconds": round(time.time() - t0, 2),
            "weight": "time_min (drive graph, flat vehicle speed)",
            "unreachable_pairs": sum(1 for row in pp for v in row if not math.isfinite(v)),
            "median_min": round(float(np.median([v for row in pp for v in row
                                                 if math.isfinite(v)])), 2),
            "⚠": ("구간 위험 미검사 — HAZARD-UNCHECKED. These legs are plain drive-network "
                  "shortest paths; the hazard model never tests whether they are open. "
                  "SENSITIVITY ARM ONLY, never a headline number."),
        }

        print(f"  [{spec['key']}] committed-model invariance check ...", flush=True)
        out["committed_model_order_invariance"] = committed_model_order_invariance(
            disp, cfg, ranks)
        out["grid"] = sweep(entries, pp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return _finish(out, spec, sha_before, t_start)


def _finish(out: dict, spec: dict, sha_before: str | None, t_start: float) -> dict:
    """Assert the input npz did not move under the run, and stamp the runtime."""
    if spec["npz"]:
        sha_after = _sha(REPO / spec["npz"])
        out["input_npz"] = {"path": spec["npz"], "sha256_before": sha_before,
                            "sha256_after": sha_after,
                            "unchanged": sha_before == sha_after}
        if sha_before != sha_after:
            raise AssertionError(f"input artifact {spec['npz']} CHANGED during the run")
    out["seconds"] = round(time.time() - t_start, 1)
    return out


def closure_profile(entries) -> dict:
    """How much ordering information the deadline key can possibly carry."""
    surv = [e["survival"] for e in entries]
    closed = [t for t in surv if math.isfinite(t)]
    at0 = [t for t in closed if t == 0.0]
    after = sorted(t for t in closed if t > 0.0)
    return {
        "n_corridors": len(surv),
        "n_closed": len(closed),
        "n_closed_at_t0": len(at0),
        "n_closed_after_t0": len(after),
        "n_never_closed": sum(1 for t in surv if not math.isfinite(t)),
        "pct_closed_at_t0_of_closed": (round(100.0 * len(at0) / len(closed), 1)
                                       if closed else None),
        "n_distinct_closure_times": len(set(closed)),
        "n_distinct_closure_times_after_t0": len(set(after)),
        "closure_time_histogram_min": {str(k): v for k, v in
                                       sorted(collections.Counter(closed).items())},
        "eta_min": {"min": round(min(e["eta"] for e in entries), 2),
                    "median": round(statistics.median(e["eta"] for e in entries), 2),
                    "max": round(max(e["eta"] for e in entries), 2)},
        "has_ordering_signal": len(set(closed)) >= 2,
        "rule": ("a corridor cut at t=0 was never open and carries no deadline; if "
                 "every closure lands on one value the sort key is constant and no "
                 "ordering can differ from any other"),
    }


def point_to_point(drive, home_nodes: list[int]) -> list[list[float]]:
    """Hazard-UNCHECKED time_min shortest paths between dispatch homes.

    ⚠ 구간 위험 미검사. The hazard model does not test these roads. Sensitivity only.
    """
    idx = {n: i for i, n in enumerate(home_nodes)}
    m = [[math.inf] * len(home_nodes) for _ in home_nodes]
    for i, src in enumerate(home_nodes):
        try:
            d = nx.single_source_dijkstra_path_length(drive.graph, src, weight="time_min")
        except nx.NodeNotFound:
            continue
        for n, t in d.items():
            j = idx.get(n)
            if j is not None:
                m[i][j] = float(t)
    return m


def committed_model_order_invariance(disp, cfg, ranks) -> dict:
    """Why the SHIPPED model cannot answer this question — measured on the shipped code.

    Calls ``rescue.py::capacity_triage`` itself (unmodified) on the same dispatch
    list under four fixed orderings and ``N_RANDOM`` shuffles. Its occupancy rule is
    ``free_at = departure + service``, so travel never occupies a unit and the
    rescued count is ``slots × units`` whatever the order. Recorded here so the
    claim rests on the shipped function rather than on a transcription of it.
    """
    by = {
        "deadline_closing_window": sorted(disp, key=lambda e: e.closing_window_min),
        "nearest_eta": sorted(disp, key=lambda e: e.responder_eta_min),
        "earliest_closure": sorted(disp, key=lambda e: e.ingress_survival_time_min),
        "list_order": [d for _, d in sorted(zip(ranks, disp, strict=True),
                                            key=lambda p: p[0])],
    }
    out: dict = {"model": "rescue.py::capacity_triage (UNMODIFIED, the shipped model)",
                 "service_min": SERVICE_BASELINE, "window_min": 75.0, "cells": {}}
    all_equal = True
    for delay in DELAYS:
        c = replace(cfg, responder_dispatch_delay_min=delay)
        cell: dict = {}
        for name, order in by.items():
            cell[name] = {str(u): capacity_triage(
                order, c, RescueCapacityConfig(n_rescue_units=u,
                                               rescue_service_time_min=SERVICE_BASELINE),
            ).n_rescued_in_time for u in UNITS}
        rnd: dict = {}
        for u in UNITS:
            vals = []
            for s in range(N_RANDOM):
                o = list(disp)
                random.Random(s).shuffle(o)
                vals.append(capacity_triage(
                    o, c, RescueCapacityConfig(n_rescue_units=u,
                                               rescue_service_time_min=SERVICE_BASELINE),
                ).n_rescued_in_time)
            rnd[str(u)] = {"mean": round(statistics.mean(vals), 2),
                           "sd": round(statistics.pstdev(vals), 2),
                           "min": min(vals), "max": max(vals)}
        cell["random"] = rnd
        vals_by_u = {str(u): {cell[n][str(u)] for n in by} | {rnd[str(u)]["min"],
                                                              rnd[str(u)]["max"]}
                     for u in UNITS}
        cell["identical_across_all_orderings"] = all(len(v) == 1 for v in vals_by_u.values())
        all_equal &= cell["identical_across_all_orderings"]
        out["cells"][f"d{delay:g}"] = cell
    out["order_invariant"] = all_equal
    out["why"] = ("free_at = departure + service, so a unit's occupancy does not "
                  "depend on how far it drove, and a home that misses its deadline "
                  "does not consume a unit. Departure slots are therefore fixed at "
                  "delay + k*service and the count is slots x units for ANY order.")
    return out


def binding_constraint(entries, *, delay: float, window: float) -> dict:
    """Which term of ``deadline = min(survival, delay + W)`` actually binds.

    This is the quantity that decides whether deadline information can matter at
    all. If the operational window closes before the corridors do, every home has
    the SAME deadline and the sort key is pure noise against throughput.
    """
    horizon = delay + window
    surv_binds = [e for e in entries if e["survival"] < horizon]
    win_binds = [e for e in entries if e["survival"] >= horizon]
    never = [e for e in entries if max(0.0, e["eta"] - delay) + delay
             > min(e["survival"], horizon) + 1e-9]
    return {
        "horizon_min": horizon,
        "n_survival_binds": len(surv_binds),
        "n_window_binds": len(win_binds),
        "pct_survival_binds": round(100.0 * len(surv_binds) / len(entries), 1),
        "n_distinct_deadlines": len({min(e["survival"], horizon) for e in entries}),
        "n_unreachable_even_at_slot_0": len(never),
        "note": ("n_window_binds homes share one identical deadline, so no ordering "
                 "can distinguish them; n_unreachable_even_at_slot_0 can never be "
                 "rescued under any ordering."),
    }


def served_mean_eta(entries, order_idx, **kw) -> float | None:
    _, served = simulate(entries, order_idx, **kw)
    return (round(statistics.mean(entries[i]["eta"] for i in served), 2)
            if served else None)


def sweep(entries, pp) -> dict:
    """Every (occupancy × window × service × delay × units × ordering) cell."""
    orders = fixed_orders(entries)
    grid: dict = {}
    for occ in OCCUPANCY:
        for window in WINDOWS:
            for service in SERVICES:
                for delay in DELAYS:
                    cell: dict = {"binding_constraint":
                                  binding_constraint(entries, delay=delay, window=window)}
                    for name, o in orders.items():
                        cell[name] = {str(u): simulate(
                            entries, o, n_units=u, delay=delay, service=service,
                            window=window, occupancy=occ, pp=pp)[0] for u in UNITS}
                    cell["random"] = {str(u): random_stats(
                        entries, n_units=u, delay=delay, service=service,
                        window=window, occupancy=occ, pp=pp) for u in UNITS}
                    cell["unlimited_units_ceiling"] = simulate(
                        entries, orders["deadline_closing_window"],
                        n_units=len(entries), delay=delay, service=service,
                        window=window, occupancy=occ, pp=pp)[0]
                    # why one ordering beats another: how far the served teams drove
                    cell["served_mean_eta_min"] = {
                        name: served_mean_eta(entries, o, n_units=8, delay=delay,
                                              service=service, window=window,
                                              occupancy=occ, pp=pp)
                        for name, o in orders.items()}
                    # ⚠ no '.' in a grid key: NUMBERS.json check paths are
                    # dot-separated, so `s12.5` would split into two segments.
                    key = (f"{occ}|W{window:g}|s{str(service).replace('.', 'p')}"
                           f"|d{delay:g}")
                    grid[key] = cell
    return grid


# ---------------------------------------------------------------------------
# Cross-arm summary — the questions the directive asks, answered from the grid
# ---------------------------------------------------------------------------


def summarise(arms: dict) -> dict:
    """Where does the deadline ordering win, where does it lose, and by how much."""
    rows = []
    for key, arm in arms.items():
        if "grid" not in arm:
            continue                      # profile-only arm: measured, not compared
        for cell_key, cell in arm["grid"].items():
            occ, w, s, d = cell_key.split("|")
            for u in UNITS:
                dl = cell["deadline_closing_window"][str(u)]
                near = cell["nearest_eta"][str(u)]
                early = cell["earliest_closure"][str(u)]
                lst = cell["list_order"][str(u)]
                rnd = cell["random"][str(u)]
                rows.append({
                    "arm": key, "occupancy": occ, "window": w, "service": s,
                    "delay": d, "units": u,
                    "deadline": dl, "nearest": near, "earliest_closure": early,
                    "list": lst, "random_mean": rnd["mean"], "random_sd": rnd["sd"],
                    "deadline_minus_nearest": dl - near,
                    "deadline_minus_random_mean": round(dl - rnd["mean"], 2),
                    "deadline_minus_list": dl - lst,
                })
    live = [r for r in rows if r["occupancy"] == "depot_return"]
    beats_nearest = [r for r in live if r["deadline_minus_nearest"] > 0]
    ties_nearest = [r for r in live if r["deadline_minus_nearest"] == 0]
    loses_nearest = [r for r in live if r["deadline_minus_nearest"] < 0]
    beats_random = [r for r in live if r["deadline_minus_random_mean"] > 0]
    beats_list = [r for r in live if r["deadline_minus_list"] > 0]

    def extreme(rs, key, want_max):
        if not rs:
            return None
        r = (max if want_max else min)(rs, key=lambda x: x[key])
        return {k: r[k] for k in ("arm", "occupancy", "window", "service", "delay",
                                  "units", "deadline", "nearest", "earliest_closure",
                                  "list", "random_mean", "random_sd", key)}

    def tally(rs: list) -> dict:
        return {"n": len(rs),
                "deadline_wins": sum(1 for r in rs if r["deadline_minus_nearest"] > 0),
                "ties": sum(1 for r in rs if r["deadline_minus_nearest"] == 0),
                "deadline_loses": sum(1 for r in rs if r["deadline_minus_nearest"] < 0)}

    return {
        "n_cells_headline_occupancy": len(live),
        # the axis that decides everything: does the corridor deadline bind before
        # the operational window does?
        "by_window": {w: tally([r for r in live if r["window"] == w])
                      for w in sorted({r["window"] for r in live})},
        "by_arm": {a: tally([r for r in live if r["arm"] == a])
                   for a in sorted({r["arm"] for r in live})},
        "sensitivity_arm_inter_point": tally(
            [r for r in rows if r["occupancy"] == "inter_point"]),
        "deadline_beats_nearest": {
            "n": len(beats_nearest), "pct": round(100.0 * len(beats_nearest) / len(live), 1),
            "configurations": [{k: r[k] for k in ("arm", "window", "service", "delay",
                                                  "units", "deadline", "nearest")}
                               for r in beats_nearest],
        },
        "deadline_ties_nearest": {"n": len(ties_nearest),
                                  "pct": round(100.0 * len(ties_nearest) / len(live), 1)},
        "deadline_loses_to_nearest": {
            "n": len(loses_nearest), "pct": round(100.0 * len(loses_nearest) / len(live), 1)},
        "deadline_beats_random_mean": {
            "n": len(beats_random), "pct": round(100.0 * len(beats_random) / len(live), 1)},
        "deadline_beats_list_order": {
            "n": len(beats_list), "pct": round(100.0 * len(beats_list) / len(live), 1)},
        "largest_gap_against_deadline": extreme(live, "deadline_minus_nearest", False),
        "largest_gap_for_deadline": extreme(live, "deadline_minus_nearest", True),
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--arms", nargs="+", default=[a["key"] for a in ARMS])
    ap.add_argument("--no-assert", action="store_true",
                    help="skip the drift arm-B reproduction assertion (diagnostic only)")
    args = ap.parse_args()

    t0 = time.time()
    arms: dict = {}
    for spec in ARMS:
        if spec["key"] not in args.arms:
            continue
        print(f"[{spec['key']}] ({spec['role']}) ...", flush=True)
        arms[spec["key"]] = build_arm(spec)

    # The Yeongdeok synthetic arm must reproduce drift arm B, or the inputs differ.
    yd = arms.get("yeongdeok_2025|synthetic")
    if yd and not args.no_assert:
        got = {"n_origins": yd["pipeline"]["n_origins"],
               "n_need_rescue": yd["pipeline"]["n_need_rescue"],
               "n_unreachable": yd["pipeline"]["n_unreachable"],
               "n_dispatch": yd["pipeline"]["n_dispatch"]}
        want = {k: v for k, v in DRIFT_ARM_B.items() if k != "artifact"}
        if got != want:
            raise AssertionError(
                f"Yeongdeok synthetic did NOT reproduce drift arm B.\n"
                f"  want {want}\n  got  {got}\n"
                "The inputs differ from the 2026-07-24 snapshot run; stopping rather "
                "than reporting a third number set.")
        yd["reproduces_drift_arm_b"] = True

    doc = {
        "schema_version": 1,
        "title": "Does deadline-first dispatch ordering rescue more people?",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "config_hash": config_hash(),
        "total_seconds": round(time.time() - t0, 1),
        "question": (
            "기여 ②는 「시한이 임박한 순서로 배차한다」입니다. 그 순서가 다른 순서보다 "
            "실제로 더 많은 사람을 구하는지 측정한 적이 없습니다."),
        "what_is_NOT_changed": [
            "라우팅 로직 — responder_eta_min 과 ingress_survival_time_min 은 커밋된 "
            "파이프라인이 계산한 값을 그대로 씁니다.",
            "구조 성공의 정의 — arrival <= min(ingress_survival, dispatch_delay + W), "
            "커밋된 capacity_triage 와 동일.",
            "rescue.py::capacity_triage — 수정하지 않았습니다. 출하 모형은 "
            "그대로입니다. 다만 호출은 합니다: committed_model_order_invariance "
            "블록이 그 함수를 직접 불러 순서 무감각을 측정하므로, 그 주장은 "
            "옮겨 적은 규칙이 아니라 출하 코드 자체에 근거합니다.",
        ],
        "⚠ behaviour_change_vs_committed_model": {
            "what": ("커밋된 capacity_triage 는 팀의 다음 가용 시각을 "
                     "`출발 + service` 로 둡니다. 이동 시간이 팀을 점유하지 않습니다."),
            "why_it_had_to_change": (
                "그 규칙 아래에서 구조 수 = 슬롯수 × 팀수 이고 순서와 무관합니다. "
                "STEP 0 측정: 고정 순서 4종 + 무작위 200회가 모든 팀 수·모든 지연에서 "
                "완전히 같은 값, 표준편차 0.00. 커밋된 모형으로는 이 질문에 답할 수 "
                "없습니다."),
            "new_rule": {
                "depot_return (나) — HEADLINE": "free_at' = arrival + service + travel_in",
                "inter_point (가) — SENSITIVITY ONLY": (
                    "free_at' = arrival + service; 다음 출발은 직전 지점에서, "
                    "⚠ 구간 위험 미검사 최단 경로로"),
            },
            "scope": ("이 스크립트가 쓰는 새 산출물에만 적용됩니다. 커밋된 "
                      "rescue_capacity.json 과 그 수치(8팀 14.4 %, 도달 불가 6/24/66)는 "
                      "여전히 커밋 모형의 것이며 이 실험이 바꾸지 않습니다."),
        },
        "⚠ yeongdeok_lineage": {
            "series": "drift arm B",
            "counts": DRIFT_ARM_B,
            "not_the_committed_439_series": (
                "커밋된 계열은 439 원점 / 167 구조 필요 / 24 도달 불가 / 143 배차이며 "
                "dispatch_top20 20건만 직렬화돼 있습니다. 그 OSM 그래프는 2026-07-24 에 "
                "덮어써져 복구 불가입니다. 두 수치 집합을 평균·조정·대체하지 마십시오 "
                "(HANDOFF §5 규칙 5)."),
        },
        "⚠ arm_that_was_going_to_be_excluded": {
            "key": "yeongdeok_2025|real",
            "planned": ("STEP 0 proposed dropping it for having NO power: the "
                        "branch-only closure_time_distribution.json measured 40 of 40 "
                        "closures at t=0 with ONE distinct closure time, which makes "
                        "the urgency key constant."),
            "measured_here": ("that measurement was taken at vehicle_cutoff 0.30 on "
                              "branch hazard-resolution. At THIS repository's 0.70 the "
                              "profile is 42 closures at t=0 and 3 at t=180 — TWO "
                              "distinct times over 124 corridors, 79 never closing."),
            "decision": ("RUN, not excluded. A near-constant key is not a constant "
                         "one, and dropping an arm on a premise that shifted is "
                         "exactly the failure §4-B records. It is reported as the "
                         "WEAKEST deadline signal of the four arms."),
        },
        "assumptions": {
            "service_time_min": {"baseline": SERVICE_BASELINE, "swept": SERVICES,
                                 "status": "PoC, NOT measured — verify_rescue_routing.py:76"},
            "window_min": {"committed": 75.0, "swept": WINDOWS,
                           "status": "responder.time_budget_min; 240 은 탐색용 추가 축"},
            "dispatch_delay_min": {"committed": 30.0, "swept": DELAYS},
            "return_to_depot": "arms `depot_return` (나) vs `inter_point` (가)",
            "team_assignment_rule": "earliest-free unit — capacity_triage 와 동일",
            "closure_interpretation": (
                "ingress_survival_time_min = 회랑 표본점 중 하나라도 vehicle_cutoff 를 "
                "넘는 최초 슬라이스. 커밋된 정의 그대로."),
            "⚠ inherited_quirk": (
                "travel_in = max(0, responder_eta_min − delay). responder_eta_min 이 "
                "이미 출동 지연을 포함하므로 지연 60분에서는 ETA<60 인 지점이 "
                "이동 0분(즉시 도착)이 됩니다. 커밋 모형에서 그대로 물려받았고, "
                "대조가 단일 변수로 남도록 고치지 않았습니다."),
        },
        "orderings": {
            "deadline_closing_window": "본 시스템 — ingress_survival − responder_ETA 오름차순",
            "nearest_eta": "가까운 순 — responder_ETA 오름차순",
            "earliest_closure": "폐쇄 이른 순 — ingress_survival 만, ETA 항 없음",
            "list_order": "목록 순 — 정렬 없음, 하한 대조",
            "random": f"무작위 — 시드 고정 0..{N_RANDOM - 1}, 평균·표준편차·최소·최대",
        },
        "arms": arms,
        "summary": summarise(arms) if arms else None,
    }

    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    print(f"\nwrote {args.out}  ({round(time.time() - t0, 1)} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
