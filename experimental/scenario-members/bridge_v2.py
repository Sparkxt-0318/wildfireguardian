"""Hazard construction law v2 (Contract B): members are Monte Carlo trajectories, not independent per-cell draws.

This module imports, and never modifies, the frozen bridge `integration/src/wfg_latest/bridge.py` and packet writer
`integration/src/wfg_latest/packets.py`. The frozen writer already injects one full-event ignition array into every
window construction (`packets.construct_regional`); bridge v2 supplies that array from trajectories instead of from
`bridge.draw_ignitions`. Everything downstream (scalar duration T, present-fire enclosure [0, R_max), the inherited
radiation operator, breakpoints, extinction rounding, the edge-grid layout and its validator) is the unchanged v1 code,
so every existing checker runs on a v2 packet without change.

Member k is trajectory j_k of the export v3 array `trajectory_first_burn_hour`; a cell with first-burn hour h >= 1 is
given an ignition second inside hour h by the sub-hour rule `settings["timing"]`:
  "uniform"  t = (h - 1) * 3600 + 3600 u with u ~ U[0, 1) drawn per (timing seed, trajectory index, cell); this matches
             the v1 timing semantics.
  "ordered"  the same multiset of uniform seconds inside the hour, reassigned within the trajectory so that cells closer
             (Euclidean, cell centres) to the set burned at the end of the previous hour ignite no later than cells
             farther away (ties broken by the uniform draw). This is a heuristic ordering, not a physical spread model;
             track 1A's isochrone timing can replace it later.

Recorded settings: `dependence = "trajectory"`, `timing`, `member_selection` (method, distance, reduction cost, selected
trajectory indices and their weights), `acceptance` ({"rule": "all" | "k_of_m", "k", "m"}, default "all"),
`construction_version = "wfg.hazard.construction/2"`. `source_law_version` stays "wfg.hazard.construction/1": the scalar
per-member source law the unchanged checkers recompute (birth + T, present fire [0, R)) is identical; only the way the
members are made changed. A checker therefore never flags a v2 packet as an unsupported source law.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE / "src") not in sys.path:
    sys.path.insert(0, str(HERE / "src"))
from wfg_members import kit  # noqa: E402

CONSTRUCTION_VERSION = "wfg.hazard.construction/2"
TIMINGS = ("uniform", "ordered")
INTERVAL_S = 3600.0
DEFAULT_TIMING_SEED = 20261029


def ignition_seconds(first_burn_hour, indices, *, timing="uniform", timing_seed=DEFAULT_TIMING_SEED, horizon_s=3600.0,
                     interval_s=INTERVAL_S):
    """[S,H,W] float64 ignition seconds (inf: no first-new ignition within the horizon) for the selected trajectories."""
    if timing not in TIMINGS:
        raise ValueError("timing must be one of %s" % (TIMINGS,))
    fbh = np.asarray(first_burn_hour)
    if fbh.ndim != 3 or fbh.dtype != np.int16:
        raise ValueError("trajectory_first_burn_hour must be int16 [N,H,W]")
    N, H, W = fbh.shape
    hours = int(math.ceil(horizon_s / interval_s))
    rows, cols = np.mgrid[0:H, 0:W]
    out = np.full((len(indices), H, W), np.inf)
    for s, k in enumerate(indices):
        k = int(k)
        f = fbh[k]
        u = np.random.default_rng([int(timing_seed), k]).random((H, W))
        for h in range(1, hours + 1):
            cells = f == h
            if not cells.any():
                continue
            base = (h - 1) * interval_s
            if timing == "uniform":
                out[s][cells] = base + u[cells] * interval_s
                continue
            prev = (f == 0) | ((f >= 1) & (f < h))
            r, c = rows[cells], cols[cells]
            if prev.any():
                pr, pc = rows[prev], cols[prev]
                d2 = ((r[:, None] - pr[None, :]) ** 2 + (c[:, None] - pc[None, :]) ** 2).min(axis=1).astype(float)
            else:
                d2 = np.zeros(r.size)
            uu = u[cells]
            order = np.lexsort((uu, d2))             # increasing distance, ties by the uniform draw
            seconds = base + np.sort(uu) * interval_s
            assigned = np.empty(r.size)
            assigned[order] = seconds
            out[s][r, c] = assigned
    fin = np.isfinite(out)
    if np.any(out[fin] < 0) or np.any(out[fin] >= horizon_s):
        raise ValueError("ignition second outside [0, horizon)")
    return out


def v2_settings(cell_duration_s, *, member_count, timing, selection, acceptance=None, trajectory_identity=None,
                timing_seed=DEFAULT_TIMING_SEED):
    B = kit.install()["bridge"]
    s = B.settings_for(cell_duration_s)
    acceptance = acceptance or {"rule": "all", "k": int(member_count), "m": int(member_count)}
    if acceptance["rule"] not in ("all", "k_of_m"):
        raise ValueError("acceptance rule must be all or k_of_m")
    s.update({
        "scenario_count": int(member_count),
        "seed": int(timing_seed),
        "dependence": "trajectory",
        "timing": timing,
        "timing_seed": int(timing_seed),
        "construction_version": CONSTRUCTION_VERSION,
        "member_selection": selection,
        "acceptance": acceptance,
        "trajectory_source": trajectory_identity,
        "member_law": ("member k is Monte Carlo trajectory selection.indices[k] of the export v3 rollout (coherent in space and "
                       "time); sub-hour ignition second by settings.timing; probabilities carry selection.weights"),
    })
    return s


@contextlib.contextmanager
def _v2_law(events_full, settings):
    """Supply trajectory ignitions where the frozen bridge would draw independent ones; restore on exit."""
    B = kit.install()["bridge"]
    original_draw, original_settings = B.draw_ignitions, B.settings_for
    calls = []

    def trajectory_draw(q, scenario_count, seed, horizon_s):
        q = np.asarray(q, dtype=float)
        if events_full.shape != (scenario_count,) + q.shape:
            raise ValueError("TRAJECTORY_EVENTS_SHAPE")
        if (scenario_count, seed, horizon_s) != (settings["scenario_count"], settings["seed"], settings["horizon_s"]):
            raise ValueError("DRAW_SETTINGS_DIFFER")
        if np.any(np.isfinite(events_full) & (q[None] <= 0)):
            raise ValueError("TRAJECTORY_IGNITION_WHERE_CONSTRUCTED_PROBABILITY_IS_ZERO")
        calls.append(1)
        return events_full.copy()

    B.draw_ignitions = trajectory_draw
    B.settings_for = lambda T: copy.deepcopy(settings) if float(T) == settings["burning_duration_s"] else original_settings(T)
    try:
        yield calls
    finally:
        B.draw_ignitions, B.settings_for = original_draw, original_settings


def load_export(npz_path, record_path):
    K = kit.install()
    record = json.loads(Path(record_path).read_text())
    if kit.sha256_file(npz_path) != record["npz_sha256"]:
        raise ValueError("FORECAST_EXPORT_HASH_MISMATCH")
    return K["bridge"].load_forecast(npz_path), record


def construct_v2(fc_full, record, *, cutoff_iso, event_id, epsg, events_full, settings, window=None):
    """In-memory v2 construction through the frozen regional path; returns (full, built) like packets.construct_regional."""
    K = kit.install()
    bound = K["contract"].verify_binding(fc_full, record, cutoff_iso, event_id, epsg)
    if float(bound["cell_duration_s"]) != settings["burning_duration_s"]:
        raise ValueError("CELL_DURATION_DIFFERS")
    with _v2_law(events_full, settings) as calls:
        full, built = K["packets"].construct_regional(fc_full, bound["cutoff_utc"], bound["epsg"], window, settings)
    if len(calls) != 1:
        raise ValueError("TRAJECTORY_DRAW_NOT_USED_EXACTLY_ONCE")
    return full, built


def hazard_arrays(built, ids, *, horizon_s=None):
    """Edge-grid members with NumPy rows (same values as bridge.to_edgegrid writes to HAZARD.json) for the checkers."""
    H, W = built["shape"]
    members = []
    for k, m in enumerate(built["members"]):
        n = len(m["breakpoints"]) - 1
        members.append({"id": ids[k], "breakpoints": [float(x) for x in m["breakpoints"]],
                        "flux": np.ascontiguousarray((m["flux_w_m2"] / 1000.0)[:, ::-1, :].reshape(n, -1)),
                        "flame": np.ascontiguousarray(m["flame"][:, ::-1, :].reshape(n, -1)),
                        "support": np.ones((n, H * W), dtype=bool)})
    horizon = float(built["settings"]["horizon_s"] if horizon_s is None else horizon_s)
    return {"schema": "wfg.routing.edgegrid/1", "dt": built["settings"]["routing_dt_s"], "valid_from": 0.0, "valid_until": horizon,
            "members": members, "version": 1}


def write_packet_v2(graph, graph_path, export_npz, record, record_sha256, cutoff_iso, epsg, out_dir, *, event_id, region_id,
                    window, events_full, settings):
    """Write a packet in the unchanged v1 layout with the v2 member law and records; returns (out_dir, hazard, summary)."""
    K = kit.install()
    P = K["packets"]
    with _v2_law(events_full, settings) as calls:
        out, hz, summary = P.write_regional_packet(graph, graph_path, export_npz, record, record_sha256, cutoff_iso, epsg, out_dir,
                                                   event_id=event_id, region_id=region_id, window=window)
    if len(calls) != 1:
        raise ValueError("TRAJECTORY_DRAW_NOT_USED_EXACTLY_ONCE")
    out = Path(out)
    interpretation = ("Exact-event research realizations: member k is Monte Carlo trajectory %s of the export v3 one-step-per-hour "
                      "rollout (dependence=trajectory, timing=%s), the latest documented coarse-cell duration T=%.6f s with fixed "
                      "phase energy, a scalar max-remaining enclosure of present fire and the inherited finite-cell radiation source "
                      "model; member weights in settings.member_selection; not a calibrated joint forecast or physical-safety evidence"
                      % (settings["member_selection"].get("indices"), settings["timing"], settings["burning_duration_s"]))
    hz["provenance"]["interpretation"] = interpretation
    hz["provenance"]["construction_version"] = CONSTRUCTION_VERSION
    (out / "HAZARD.json").write_text(json.dumps(hz, allow_nan=False, separators=(",", ":")) + "\n")
    for name in ("REPORT.json", "NATIVE_METADATA.json"):
        obj = json.loads((out / name).read_text())
        md = obj["native_metadata"] if name == "REPORT.json" else obj
        a = md["construction"]["assumptions"]
        a.update({"dependence": "trajectory", "timing": settings["timing"], "construction_version": CONSTRUCTION_VERSION,
                  "member_selection": settings["member_selection"], "acceptance": settings["acceptance"]})
        if name == "NATIVE_METADATA.json":
            md["construction"]["construction_version_v2"] = CONSTRUCTION_VERSION
        (out / name).write_text(json.dumps(obj, allow_nan=False, indent=1) + "\n")
    summary["files_sha256"] = {n: kit.sha256_file(out / n) for n in ("HAZARD.json", "REPORT.json", "NATIVE_METADATA.json",
                                                                      "constructed_arrays.npz")}
    summary.update(region=region_id, event_id=event_id, cutoff=cutoff_iso, construction_version=CONSTRUCTION_VERSION,
                   dependence="trajectory", timing=settings["timing"], member_selection=settings["member_selection"],
                   acceptance=settings["acceptance"], bridge_v2_sha256=kit.sha256_file(__file__), status="BUILT")
    with (out / "BUILD_SUMMARY.json").open("x") as f:
        json.dump(summary, f, indent=1, default=str)
        f.write("\n")
    return out, hz, summary


def frozen_window(packet_dir):
    md = json.loads((Path(packet_dir) / "NATIVE_METADATA.json").read_text())
    return (md.get("regional") or {}).get("window_rows_cols_north_up")


def rekey_request_k(request, ids, cutoff_iso):
    """Re-key a frozen request onto K member ids. Allowed only when the frozen per-member incurred dose and dose budgets
    are identical across members (true for all 20 frozen requests); refuses otherwise."""
    inc = set(request["incurred"].values())
    bud = set(request["budgets"]["dose"].values())
    if len(inc) != 1 or len(bud) != 1:
        raise ValueError("REKEY_K_NEEDS_IDENTICAL_MEMBER_VALUES")
    out = copy.deepcopy(request)
    out["incurred"] = {i: next(iter(inc)) for i in ids}
    out["budgets"] = {"peak": request["budgets"]["peak"], "dose": {i: next(iter(bud)) for i in ids}}
    out["as_of"] = cutoff_iso.replace("Z", "+00:00")
    return out


def member_ids(prefix, count):
    return ["%s:%d" % (prefix, k) for k in range(count)]


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
