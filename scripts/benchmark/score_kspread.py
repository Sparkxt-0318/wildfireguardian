#!/usr/bin/env python
"""Score K-SPREAD-2025 entrants (protocol: ``docs/benchmark/K_SPREAD_2025.md``, v0.1).

Reads one entrant bundle per directory --- ``entrant.json`` plus ``<event>.npz`` holding
``grid_extent``, ``times_min`` and ``stack`` --- builds truth from the committed observed
detections under ``docs/regrade_three_way.md`` §2 (A1-A6), computes the four metrics of
protocol §5 and writes ``data/processed/benchmark/<entrant>/<event>.json`` plus
``data/processed/benchmark/leaderboard.json``. The scorer's declared conventions C1-C6 are
in ``scripts/benchmark/kspread_metrics.py``'s docstring and repeated in
``docs/benchmark/results_v0.1.md``; they were fixed before any entrant was run.

Forecast-track and hindcast-track entrants are tallied into SEPARATE leaderboard tables
and are never averaged together (protocol §3).

Metric 4 (decision shift) is behind ``--with-decision-shift`` because it re-plans every
building node under two hazard fields and costs minutes, not seconds. It is the only metric
that goes through the committed router's sampler --- bilinear in space, and therefore the
softer reading of a binary footprint (``docs/regrade_three_way.md`` §A5, §6). Its truth
field is a STEP field in time: a cumulative footprint does not fade up between overpasses,
and protocol §4 forbids interpolating detections into smooth truth.

    python scripts/benchmark/score_kspread.py
    python scripts/benchmark/score_kspread.py --with-decision-shift
    python scripts/benchmark/score_kspread.py --entrant data/processed/benchmark/entrants/e0_persistence
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kspread_metrics import (  # noqa: E402
    arrival_time_error, auc_iou_at_horizon, crossing_grid, decision_shift, lsd_class,
)
from kspread_truth import first_seen_grid, node_truth  # noqa: E402

ENTRANTS = REPO / "data/processed/benchmark/entrants"
OUT = REPO / "data/processed/benchmark"
PROTOCOL_VERSION = "v0.1"
HORIZONS_MIN = (180.0, 300.0, 480.0)          # protocol §2: T0 + 3 h, 5 h, 8 h
P_CUT = 0.5

#: event -> the committed artifact carrying its observed detection stack.
TRUTH_SOURCES = {"yeongdeok_2025": "data/processed/routing_demo_canonical.npz"}

#: The six protocol §2 events, so a run says what it could not score rather than omitting it.
PROTOCOL_EVENTS = ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022",
                   "gangneung_2023", "hongseong_2023", "miryang_2022")


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def crossing_series(ps: np.ndarray, times: np.ndarray, p_cut: float = P_CUT) -> float:
    """First time a 1-D probability series reaches ``p_cut``, linear in time; ``inf`` if never."""
    ps = np.asarray(ps, float)
    times = np.asarray(times, float)
    if ps[0] >= p_cut:
        return float(times[0])
    for k in range(1, len(times)):
        if ps[k] >= p_cut:
            denom = ps[k] - ps[k - 1]
            frac = (p_cut - ps[k - 1]) / denom if denom > 0 else 0.0
            return float(times[k - 1] + min(max(frac, 0.0), 1.0) * (times[k] - times[k - 1]))
    return math.inf


def canonical_scene():
    """The canonical 영덕 scene and its 458-origin scan (C5). Heavy; built once per run."""
    from measure_present_perimeter_yeongdeok import EXPECTED_ORIGINS, build
    from run_real_roads_real_hazard_slope import candidate_origins

    canon, prm, hazard, haz, extent, net, snaps = build()
    cand, ign = candidate_origins(net, hazard, haz, extent, float(prm["p_cut"]))
    if len(cand) != EXPECTED_ORIGINS:
        raise SystemExit(f"STOP: canonical scan gave {len(cand)} origins, expected {EXPECTED_ORIGINS}")
    return {"canon": canon, "prm": prm, "hazard": hazard, "haz": haz, "extent": extent,
            "net": net, "origins": cand,
            "snapshots": {k: str(v.relative_to(REPO)) for k, v in snaps.items()}}


def step_hazard_from_observation(z):
    """The observed cumulative footprint as a HazardSequence that STEPS, not fades (metric 4).

    ``HazardSequence`` interpolates linearly between surface times. A cumulative detection
    footprint does not fade up between overpasses, so each observation time is doubled with
    an epsilon-earlier copy of the PREVIOUS footprint; the interpolation then reproduces a
    step to within epsilon. Nothing in the committed class is changed.
    """
    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.spread_v2.grid import CoarseGrid

    obs = z["obs_stack"].astype(np.float32)
    t = np.asarray(z["obs_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax, cell_size_m=cell,
                      nrows=obs.shape[1], ncols=obs.shape[2])
    eps = 1e-6
    times, surfaces = [float(t[0])], [obs[0]]
    for k in range(1, len(t)):
        times.append(float(t[k]) - eps)
        surfaces.append(obs[k - 1])
        times.append(float(t[k]))
        surfaces.append(obs[k])
    return HazardSequence(grid=grid, times_min=np.asarray(times, float), surfaces=list(surfaces))


def hazard_from_entrant(extent, times, stack):
    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.spread_v2.grid import CoarseGrid

    xmin, ymin, xmax, ymax, cell = [float(v) for v in extent]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax, cell_size_m=cell,
                      nrows=stack.shape[1], ncols=stack.shape[2])
    return HazardSequence(grid=grid, times_min=np.asarray(times, float),
                          surfaces=[np.asarray(stack[i], np.float32) for i in range(stack.shape[0])])


def _nodes_metric3(scene, extent7, stack, times, fs, t, nodes, m):
    """Per-node model/observed arrival rows, cell membership (primary) and bilinear (beside it)."""
    net = scene["net"]
    cross = crossing_grid(stack, times, P_CUT)
    hz = hazard_from_entrant(extent7[:5], times, stack)
    xs = np.array([net.node_xy(n)[0] for n in nodes], float)
    ys = np.array([net.node_xy(n)[1] for n in nodes], float)
    bil = np.array([hz.prob_at_points(xs, ys, float(tk)) for tk in times])   # (T, N)
    rows, rows_bilinear = [], []
    for i, n in enumerate(nodes):
        x, y = float(xs[i]), float(ys[i])
        tr = node_truth(x, y, fs, t, extent7, m)
        model = math.inf
        if tr["supported"]:
            row_i = int(math.floor((extent7[3] - y) / extent7[4]))
            col_i = int(math.floor((x - extent7[0]) / extent7[4]))
            model = float(cross[row_i, col_i])
        base = {"node": int(n), "supported": tr["supported"],
                "observed_min": tr["observed_min"], "earliest_min": tr["earliest_min"]}
        rows.append(dict(base, model_min=model))
        rows_bilinear.append(dict(base, model_min=crossing_series(bil[:, i], times, P_CUT)))
    window = float(times[-1])
    out = arrival_time_error(rows, window)
    out["sampling"] = "A5 cell membership (primary)"
    out["bilinear_variant"] = dict(
        arrival_time_error(rows_bilinear, window),
        sampling="router bilinear (docs/regrade_three_way.md A5 correction)")
    # C1's clamp: a node the entrant calls safe whose probability is still above zero at
    # the last surface may simply cross after the horizon. Counted, never corrected.
    last = np.asarray(stack[-1], float)
    rising = 0
    for i, r in enumerate(rows):
        if r["supported"] and not np.isfinite(r["model_min"]):
            row_i = int(math.floor((extent7[3] - ys[i]) / extent7[4]))
            col_i = int(math.floor((xs[i] - extent7[0]) / extent7[4]))
            if last[row_i, col_i] > 0.0:
                rising += 1
    out["nodes_called_safe_with_nonzero_p_at_last_surface"] = rising
    out["last_surface_min"] = float(times[-1])
    return out


def road_nodes_per_cell(scene, extent7) -> np.ndarray:
    """How many canonical walk-network nodes sit in each grid cell (A5 membership)."""
    net = scene["net"]
    out = np.zeros((extent7[5], extent7[6]), int)
    for n in net.graph.nodes:
        x, y = net.node_xy(n)
        row_i = int(math.floor((extent7[3] - y) / extent7[4]))
        col_i = int(math.floor((x - extent7[0]) / extent7[4]))
        if 0 <= row_i < extent7[5] and 0 <= col_i < extent7[6]:
            out[row_i, col_i] += 1
    return out


def metric3(scene, extent7, stack, times, fs, t, m=0):
    """Protocol §5.3 on the canonical walk network, with the 458-origin subset beside it.

    ⚠ **Which nodes, and why the primary set changed after the first run.** C5 first read
    「every walk-network node the canonical routing scans」 as the canonical scan's 458
    ORIGINS. Run on those, the metric is degenerate BY CONSTRUCTION and not by any property
    of an entrant: ``candidate_origins`` refuses an origin whose hazard at T0 is already
    >= p_cut, so almost no origin node can ever be one an entrant burns. Measured on the
    first run, every entrant burned 2 of the 458 and the median was taken over those 2.
    The primary set is therefore every node of the canonical walk network --- the road nodes
    the canonical scan uses --- and the 458-origin subset is reported beside it, unchanged.
    The reason is structural and applies identically to every entrant; no score chose it,
    and both sets are in the artifact so the reading can be checked either way.
    """
    all_nodes = sorted(scene["net"].graph.nodes)
    out = _nodes_metric3(scene, extent7, stack, times, fs, t, all_nodes, m)
    out["node_set"] = "canonical walk network (all nodes)"
    out["canonical_scan_origins_subset"] = dict(
        _nodes_metric3(scene, extent7, stack, times, fs, t, scene["origins"], m),
        node_set=f"canonical scan origins ({len(scene['origins'])})")
    # Why an entrant can burn many cells and move almost no road node: the walk network
    # covers a small minority of the canvas, so an advance onto unroaded slope is invisible
    # to metric 3 by geography rather than by any fault of the metric. Counted, so the
    # reading is a number.
    per_cell = road_nodes_per_cell(scene, extent7)
    burns = np.isfinite(crossing_grid(stack, times, P_CUT))
    window = float(times[-1])
    out["cell_coverage"] = {
        "cells_total": int(burns.size),
        "cells_with_a_road_node": int((per_cell > 0).sum()),
        "road_nodes_on_grid": int(per_cell.sum()),
        "cells_entrant_burns": int(burns.sum()),
        "cells_entrant_burns_with_a_road_node": int((burns & (per_cell > 0)).sum()),
        "road_nodes_in_cells_entrant_burns": int(per_cell[burns].sum()),
        "cells_observation_burns_in_window": int((fs <= window).sum()),
        "cells_observation_burns_in_window_with_a_road_node": int(((fs <= window) & (per_cell > 0)).sum()),
        "road_nodes_in_cells_observation_burns_in_window": int(per_cell[fs <= window].sum()),
    }
    return out, None


def building_nodes(scene) -> tuple[dict[int, int], int, int]:
    """The 영덕 building population on the canonical walk network, fixed across entrants.

    Same rule as ``scripts/measure_last_safe_departure.py``: 도로명주소 주건물 snapped to the
    nearest walk node within 500 m, minus the buildings standing in the CANONICAL field at
    T0. The filter is the canonical one and not the entrant's, for the reason C5 gives ---
    an entrant does not get to choose which buildings it is judged on
    (``run_leakfree_yeongdeok_fold.py`` fixes the same set the same way).
    """
    from wildfireguardian.buildings import load_buildings

    from measure_last_safe_departure import MAX_SNAP
    from run_building_origin_routing import origin_filter

    net = scene["net"]
    bld = load_buildings("yeongdeok_2025", source="juso_main", repo=REPO)
    snap, dist = [], []
    for i in range(len(bld)):
        nid = net.nearest_node(float(bld.xy[i, 0]), float(bld.xy[i, 1]))
        x, y = net.node_xy(nid)
        snap.append(nid)
        dist.append(math.hypot(x - bld.xy[i, 0], y - bld.xy[i, 1]))
    keep, _, _ = origin_filter(bld.xy, scene["haz"], scene["extent"], float(scene["prm"]["p_cut"]))
    routable = (np.asarray(dist) <= MAX_SNAP) & keep
    nodes = np.asarray(snap, dtype=np.int64)[routable]
    uniq, counts = np.unique(nodes, return_counts=True)
    return ({int(n): int(c) for n, c in zip(uniq, counts)}, int(routable.sum()), int(len(bld)))


def lsd_over(scene, hazard, nodes) -> dict[int, float]:
    from measure_last_safe_departure import lsd_search

    net = scene["net"]
    out = {}
    for k, n in enumerate(nodes):
        out[int(n)] = float(lsd_search(net, int(n), hazard))
        if (k + 1) % 500 == 0:
            print(f"      LSD [{k + 1}/{len(nodes)}]", flush=True)
    return out


def metric4(scene, entrant_hazard, truth_lsd, weights, n_buildings, n_total) -> dict:
    """Protocol §5.4: buildings whose LSD class differs between entrant field and truth field.

    The policy is held fixed --- the committed time-aware search --- and only the hazard
    field changes, so what the count measures is the field and not the router. ⚠ Both LSD
    sweeps read their field through ``HazardSequence``, which is BILINEAR in space; on the
    observation's binary footprint that is the softer reading (``docs/regrade_three_way.md``
    §A5's correction, §6). Metrics 1-3 use cell membership; this one does not, and the
    artifact says so rather than letting the two be assumed identical.
    """
    nodes = sorted(weights)
    lsd_e = lsd_over(scene, entrant_hazard, nodes)
    out = decision_shift(lsd_e, truth_lsd, weights)
    out["nodes"] = len(nodes)
    out["buildings_routable"] = n_buildings
    out["buildings_total"] = n_total
    out["policy"] = "time-aware search, 600 min budget, 10 min step (measure_last_safe_departure.lsd_search)"
    out["spatial_sampling"] = "router bilinear (not A5 cell membership); see docs/regrade_three_way.md §A5"
    out["lsd_class_buildings_entrant"] = _tally(lsd_e, weights)
    out["lsd_class_buildings_truth"] = _tally(truth_lsd, weights)
    return out


def _tally(lsd: dict[int, float], weights: dict[int, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for n, v in lsd.items():
        k = lsd_class(v)
        out[k] = out.get(k, 0) + weights.get(n, 0)
    return out


def score_entrant(dirpath: Path, scene, with_decision_shift: bool, m4cache: dict) -> dict:
    meta = json.loads((dirpath / "entrant.json").read_text(encoding="utf-8"))
    results = {"entrant": meta["id"], "protocol_entrant": meta.get("protocol_entrant"),
               "name": meta.get("name"), "track": meta["track"],
               "resolution_m": meta.get("resolution_m"), "inputs_used": meta.get("inputs_used"),
               "events": {}, "events_not_scored": {}}
    for event in PROTOCOL_EVENTS:
        if event not in meta.get("events", {}):
            results["events_not_scored"][event] = "no entrant field committed for this event"
            continue
        if event not in TRUTH_SOURCES:
            results["events_not_scored"][event] = "no committed observed detection stack for this event"
            continue
        z = np.load(REPO / TRUTH_SOURCES[event])
        fs, t = first_seen_grid(z)
        e = np.load(REPO / meta["events"][event]["npz"])
        stack, times = np.asarray(e["stack"], float), np.asarray(e["times_min"], float)
        xmin, ymin, xmax, ymax, cell = [float(v) for v in e["grid_extent"]]
        extent7 = (xmin, ymin, xmax, ymax, cell, stack.shape[1], stack.shape[2])
        if stack.shape[1:] != fs.shape:
            raise SystemExit(f"STOP: {meta['id']}/{event} grid {stack.shape[1:]} != truth {fs.shape}")
        ev = {"truth_source": TRUTH_SOURCES[event],
              "overpass_times_min": [float(v) for v in t],
              "entrant_times_min": [float(v) for v in times],
              "grid": {"cell_size_m": cell, "nrows": int(stack.shape[1]), "ncols": int(stack.shape[2])},
              "horizons": {}}
        for h in HORIZONS_MIN:
            ev["horizons"][f"{int(h)}min"] = {
                m if isinstance(m, str) else f"m{m}": auc_iou_at_horizon(stack, times, fs, t, h, m, P_CUT)
                for m in (0, 1, "inf")}
        m3, _ = metric3(scene, extent7, stack, times, fs, t, 0)
        ev["arrival_time_error"] = m3
        if with_decision_shift:
            if "weights" not in m4cache:
                print("      building population + truth-field LSD (once) ...", flush=True)
                w, nb, nt = building_nodes(scene)
                m4cache.update(weights=w, n_buildings=nb, n_total=nt,
                               truth_lsd=lsd_over(scene, step_hazard_from_observation(z), sorted(w)))
            ev["decision_shift"] = metric4(
                scene, hazard_from_entrant(extent7[:5], times, stack), m4cache["truth_lsd"],
                m4cache["weights"], m4cache["n_buildings"], m4cache["n_total"])
        else:
            ev["decision_shift"] = {"not_run": "pass --with-decision-shift"}
        results["events"][event] = ev
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrant", action="append", default=None,
                    help="entrant bundle directory (repeatable); default: every bundle under "
                         "data/processed/benchmark/entrants")
    ap.add_argument("--with-decision-shift", action="store_true", help="also compute protocol §5.4")
    args = ap.parse_args()
    t_start = time.monotonic()

    dirs = ([Path(p) for p in args.entrant] if args.entrant
            else sorted(d for d in ENTRANTS.iterdir() if (d / "entrant.json").exists()))
    if not dirs:
        print("no entrant bundles found", file=sys.stderr)
        return 2
    print("[1/2] canonical scene + 458-origin scan ...", flush=True)
    scene = canonical_scene()
    m4cache: dict = {}

    board = {"schema_version": 1, "title": "K-SPREAD-2025 leaderboard",
             "protocol": "docs/benchmark/K_SPREAD_2025.md", "protocol_version": PROTOCOL_VERSION,
             "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "git_commit": _commit(),
             "truth_rule": "docs/regrade_three_way.md §2 (A1-A6), m = 0 headline",
             "scorer": "scripts/benchmark/score_kspread.py",
             "conventions": "C1-C6 in scripts/benchmark/kspread_metrics.py",
             "horizons_min": list(HORIZONS_MIN), "p_cut": P_CUT,
             "metric3_node_set": {"rule": "every node of the canonical walk network (C5)",
                                  "n_nodes": scene["net"].graph.number_of_nodes(),
                                  "origins_subset_n": len(scene["origins"]),
                                  "source": "data/processed/real_roads_real_hazard_canonical.json",
                                  "snapshots": scene["snapshots"]},
             "events_scored": sorted(TRUTH_SOURCES),
             "events_unscorable": {e: "no committed observed detection stack"
                                   for e in PROTOCOL_EVENTS if e not in TRUTH_SOURCES},
             "tracks": {"forecast": [], "hindcast": []}}
    for i, d in enumerate(dirs, 1):
        print(f"[2/2] scoring {d.name} ({i}/{len(dirs)}) ...", flush=True)
        res = score_entrant(d, scene, args.with_decision_shift, m4cache)
        outdir = OUT / res["entrant"]
        outdir.mkdir(parents=True, exist_ok=True)
        for event, ev in res["events"].items():
            payload = {k: v for k, v in res.items() if k != "events"} | {"event": event, **ev}
            payload["generated_utc"] = board["generated_utc"]
            payload["git_commit"] = board["git_commit"]
            (outdir / f"{event}.json").write_text(
                json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        board["tracks"][res["track"]].append({
            "entrant": res["entrant"], "protocol_entrant": res["protocol_entrant"],
            "name": res["name"], "resolution_m": res["resolution_m"],
            "per_event": {e: {
                "roc_auc": {k: v["m0"]["roc_auc"] for k, v in ev["horizons"].items()},
                "iou_at_p_ge_0.5": {k: v["m0"]["iou_at_p_ge_0.5"] for k, v in ev["horizons"].items()},
                "cells_unscorable_indeterminate": {k: v["m0"]["cells_unscorable_indeterminate"]
                                                   for k, v in ev["horizons"].items()},
                "arrival_median_abs_error_min": ev["arrival_time_error"]["median_abs_error_min"],
                "arrival_median_signed_error_min": ev["arrival_time_error"]["median_signed_error_min"],
                "false_safe_rate": ev["arrival_time_error"]["false_safe_rate"],
                "false_safe_nodes": ev["arrival_time_error"]["false_safe_nodes"],
                "nodes_model_calls_safe": ev["arrival_time_error"]["nodes_model_calls_safe"],
                "decision_shift": ev["decision_shift"],
            } for e, ev in res["events"].items()},
            "events_not_scored": res["events_not_scored"],
        })
    board["seconds"] = round(time.monotonic() - t_start, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "leaderboard.json").write_text(json.dumps(board, indent=1, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    print(f"wrote {(OUT / 'leaderboard.json').relative_to(REPO)} in {board['seconds']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
