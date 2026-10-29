"""Test-only adapter: journey thermal check with ``radiation_law="v1" | "v2"`` (evaluation, not production).

v1: the byte-identical copy of the frozen centre-model checker (``frozen_copy/routing/independent.py``,
``check_route``) on the packet's HAZARD.json, exactly the path that produced the recorded per-member exposures.

v2: contact is still decided by that unchanged v1 check (FLAME_CONTACT code). Radiation is evaluated with
``wfg.radiation.law/2-flamefront`` on the continuous trajectory: the issue point at departure, every EDGE leg with
linear motion between its fraction endpoints, every WAIT, and the destination stay [arrival, arrival + dwell] when
``exposure_scope == "including_dwell"`` (as v1). Two results are produced per member:

* sampled (point law): samples at most ``max_dt_s`` seconds and ``max_ds_m`` metres apart, plus every leg endpoint;
  peak = largest sample (an exact point value of the law, so a sampled exceedance is a definite violation of the
  model); dose = incurred + trapezoid integral (linear kJ/m2 and TDU), an estimate between samples;
* certified upper bounds: the same sub-intervals, each enclosed by ``flux_enclosure_many`` over the bounding box of its
  path piece and its closed time interval; peak upper = max, dose upper = incurred + sum(upper x duration).

Decision per member: ``PASS_CERTIFIED`` (upper peak and upper dose within budget), ``FAIL_PEAK_DEFINITE`` (a sample
exceeds the peak limit), ``FAIL_DOSE_SAMPLED`` (the sampled dose exceeds the budget; not certified because no
nontrivial dose lower bound exists outside the flame), ``UNRESOLVED`` (sampled values pass, bounds cannot certify).
Model-relative only; no physical-safety claim.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE / "frozen_copy"))

import wfg_flamefront as W  # noqa: E402
from routing import core as frozen_core  # noqa: E402,F401  (byte-identical copy, recorded in SOURCE_SHA256.json)
from routing import independent as frozen_independent  # noqa: E402

FUEL_SETTINGS = {
    "E100": {"label": "E = 100 kW/m2 (specified default)", "fuel": {}},
    "E23": {"label": "E = 22.6 kW/m2 panels, 100 in flame (measurement-consistent)",
            "fuel": {"emissive_power_kw_m2": W.constants.EMISSIVE_POWER_MEASURED_DECAY_KW_M2,
                     "inflame_emissive_power_kw_m2": W.constants.EMISSIVE_POWER_SURFACE_KW_M2}},
}


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Case:
    """Graph, packet (hazard and member arrays) and request of one mission, loaded once."""

    def __init__(self, inputs_root, cohort, case_id):
        inputs_root = Path(inputs_root)
        cutoff = case_id.split("_")[0]
        self.cohort, self.case_id, self.cutoff = cohort, case_id, cutoff
        self.graph_path = inputs_root / "graphs" / cohort / "graph.json"
        self.packet_dir = inputs_root / "latest_inputs_try02/packets" / cohort / cutoff
        self.request_path = inputs_root / "latest_inputs_try02/requests" / cohort / (case_id + ".json")
        self.graph = json.loads(self.graph_path.read_text())
        self.hazard = json.loads((self.packet_dir / "HAZARD.json").read_text())
        self.request = json.loads(self.request_path.read_text())
        self.members, self.grid, self.info = W.load_packet_members(self.packet_dir)
        self.member_ids = [m["id"] for m in self.hazard["members"]]
        assert self.member_ids == self.info["member_ids"]
        self.fields = [W.prepare(m, self.grid) for m in self.members]
        self.nodes = {n["id"]: n for n in self.graph["nodes"]}
        self.edges = {e["id"]: e for e in self.graph["edges"]}
        self.hashes = {"graph": sha256_file(self.graph_path), "hazard": sha256_file(self.packet_dir / "HAZARD.json"),
                       "request": sha256_file(self.request_path),
                       "constructed_arrays": sha256_file(self.packet_dir / "constructed_arrays.npz"),
                       "report": sha256_file(self.packet_dir / "REPORT.json")}


def trajectory_pieces(case, legs, destination):
    """List of motion pieces (t0, t1, x0, y0, x1, y1, kind) covering issue, legs and the destination stay."""
    req = case.request
    pieces = []
    pos = case.nodes[req["position"]["node"]]
    dep = float(req["departure"])
    pieces.append((dep, dep, float(pos["x"]), float(pos["y"]), float(pos["x"]), float(pos["y"]), "ISSUE"))
    arrival = dep
    for leg in legs:
        t0, t1 = float(leg["start"]), float(leg["end"])
        if leg["kind"] == "WAIT":
            n = case.nodes[leg["node"]]
            pieces.append((t0, t1, float(n["x"]), float(n["y"]), float(n["x"]), float(n["y"]), "WAIT"))
        else:
            e = case.edges[leg["edge"]]
            u, v = case.nodes[e["u"]], case.nodes[e["v"]]
            f, qf = float(leg["from_fraction"]), float(leg["to_fraction"])
            ux, uy, vx, vy = float(u["x"]), float(u["y"]), float(v["x"]), float(v["y"])
            pieces.append((t0, t1, ux + f * (vx - ux), uy + f * (vy - uy), ux + qf * (vx - ux), uy + qf * (vy - uy), "EDGE"))
        arrival = t1
    dest = {d["node"]: d for d in req["destinations"]}[destination]
    n = case.nodes[destination]
    if req.get("exposure_scope") == "including_dwell":
        pieces.append((arrival, arrival + float(dest["dwell"]), float(n["x"]), float(n["y"]), float(n["x"]),
                       float(n["y"]), "DWELL"))
    return pieces, arrival


def sample_track(pieces, max_dt_s=0.5, max_ds_m=5.0):
    """Sample times/positions and the sub-interval boxes used for enclosures."""
    T, X, Y, kinds = [], [], [], []
    boxes, intervals = [], []
    for (t0, t1, x0, y0, x1, y1, kind) in pieces:
        if t1 == t0:
            T.append(t0); X.append(x0); Y.append(y0); kinds.append(kind)
            boxes.append((x0, x0, y0, y0)); intervals.append((t0, t0))
            continue
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil((t1 - t0) / max_dt_s)), int(math.ceil(L / max_ds_m)))
        s = np.linspace(0.0, 1.0, n + 1)
        ts = t0 + s * (t1 - t0); xs = x0 + s * (x1 - x0); ys = y0 + s * (y1 - y0)
        for k in range(n + 1):
            T.append(ts[k]); X.append(xs[k]); Y.append(ys[k]); kinds.append(kind)
        for k in range(n):
            boxes.append((min(xs[k], xs[k + 1]), max(xs[k], xs[k + 1]), min(ys[k], ys[k + 1]), max(ys[k], ys[k + 1])))
            intervals.append((ts[k], ts[k + 1]))
    return np.array(T), np.array(X), np.array(Y), kinds, np.array(boxes), np.array(intervals)


def _dose_piecewise(T, q, form):
    """Trapezoid over consecutive samples with positive duration (zero-duration duplicates contribute nothing)."""
    total = 0.0
    f = q if form == "linear" else q ** W.constants.TDU_EXPONENT
    dt = np.diff(T)
    m = dt > 0
    total = float(np.sum(0.5 * (f[:-1] + f[1:])[m] * dt[m]))
    return total


def check_v1(case, legs, destination):
    return frozen_independent.check_route(case.graph, case.hazard, case.request, legs, destination)


def check_v2(case, legs, destination, *, fuel=None, max_dt_s=0.5, max_ds_m=5.0, certify=True, contact=None):
    """v2 thermal check of one journey for every member (see module docstring)."""
    fuel = W.FuelParameters.coerce(fuel)
    req = case.request
    if contact is None:
        contact = check_v1(case, legs, destination)
    contact_ok = "FLAME_CONTACT" not in contact["codes"]
    pieces, arrival = trajectory_pieces(case, legs, destination)
    T, X, Y, kinds, boxes, intervals = sample_track(pieces, max_dt_s, max_ds_m)
    pts = np.column_stack([X, Y])
    peak_limit = float(req["budgets"]["peak"])
    out = {"contact_ok": contact_ok, "v1_codes": contact["codes"], "arrival": arrival, "samples": int(T.size),
           "boxes": int(len(boxes)), "per_member": {}}
    for k, mid in enumerate(case.member_ids):
        ff = case.fields[k]
        q, eng = W.flux_at_events(pts, T, ff, case.grid, fuel)
        inc = float(req["incurred"][mid]); budget = float(req["budgets"]["dose"][mid])
        dose_lin = inc + _dose_piecewise(T, q, "linear")
        dose_tdu = _dose_piecewise(T, q, "tdu")
        ip = int(np.argmax(q))
        rec = {"peak_kw_m2": float(q[ip]), "peak_time_s": float(T[ip]), "peak_x": float(X[ip]), "peak_y": float(Y[ip]),
               "peak_phase": kinds[ip], "peak_band": W.as3959_band(q[ip]), "dose_kj_m2": dose_lin,
               "dose_added_kj_m2": dose_lin - inc, "incurred_kj_m2": inc, "dose_budget_kj_m2": budget,
               "dose_tdu": dose_tdu, "engulfed_samples": int(eng.sum()), "peak_limit_kw_m2": peak_limit,
               "exposed_seconds_over_1kw": float(np.sum(np.diff(T)[(q[:-1] > 1.0) & (np.diff(T) > 0)])),
               "probit_lethality": W.probit_lethality(dose_tdu)["probability"]}
        if certify:
            lo, up = W.flux_enclosure_many(boxes, intervals, ff, case.grid, fuel)
            dur = intervals[:, 1] - intervals[:, 0]
            rec["peak_upper_kw_m2"] = float(up.max())
            rec["dose_upper_kj_m2"] = inc + float(np.sum(up * dur))
            rec["dose_lower_kj_m2"] = inc + float(np.sum(lo * dur))
        peak_fail = rec["peak_kw_m2"] > peak_limit
        dose_fail = dose_lin > budget
        if peak_fail:
            status = "FAIL_PEAK_DEFINITE"
        elif dose_fail:
            status = "FAIL_DOSE_SAMPLED"
        elif certify and rec["peak_upper_kw_m2"] <= peak_limit and rec["dose_upper_kj_m2"] <= budget:
            status = "PASS_CERTIFIED"
        else:
            status = "UNRESOLVED"
        rec["status"] = status
        rec["peak_margin_kw_m2"] = peak_limit - rec["peak_kw_m2"]
        rec["dose_margin_kj_m2"] = budget - dose_lin
        out["per_member"][mid] = rec
    sts = [r["status"] for r in out["per_member"].values()]
    if not contact_ok:
        out["journey_status"] = "FAIL_CONTACT"
    elif any(s.startswith("FAIL") for s in sts):
        out["journey_status"] = "FAIL_PEAK_DEFINITE" if "FAIL_PEAK_DEFINITE" in sts else "FAIL_DOSE_SAMPLED"
    elif all(s == "PASS_CERTIFIED" for s in sts):
        out["journey_status"] = "PASS_CERTIFIED"
    else:
        out["journey_status"] = "UNRESOLVED"
    return out


def check_journey(case, legs, destination, radiation_law="v1", **kw):
    """Switch between the frozen v1 check and the v2 check (contact unchanged)."""
    if radiation_law == "v1":
        return check_v1(case, legs, destination)
    if radiation_law == "v2":
        return check_v2(case, legs, destination, **kw)
    raise ValueError("radiation_law must be 'v1' or 'v2'")
