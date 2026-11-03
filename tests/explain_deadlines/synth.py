"""Synthetic worlds for the explain_deadlines tests (tiny grids, graphs, packets and cache documents).

Everything here is invented test data on a 100 m toy lattice; nothing describes a real place or result.
The packet writer below follows the bridge's construction rules (wfg_latest/bridge.py ``construct``/``to_edgegrid``):
breakpoints {0, H} + births + rounded-up extinctions + R, flame[i] = active set at bp[i], router rows reversed from the
native north-up npz rows.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from tools.explain_deadlines.packet import round_up_sum
from tools.explain_deadlines.plans import canonical_sha256

GRID = {"x0": 0.0, "y0": 0.0, "resolution": 100.0, "width": 4, "height": 3}


def router_to_native(cell: int, W: int, H: int) -> tuple:
    r, c = divmod(cell, W)
    return H - 1 - r, c


def write_packet(d: Path, *, grid=GRID, members=4, T=4000.0, R=0.0, horizon=3600.0, current=(), ignitions=None,
                 set_id="synthetic:set", time_origin="2025-01-01T00:00:00+00:00") -> list:
    """``current``: router cells burning at t=0 (phase [0, R)); ``ignitions``: {member: {router_cell: birth}}.
    Returns the member ids."""
    d.mkdir(parents=True, exist_ok=True)
    W, H = grid["width"], grid["height"]
    ids = ["%s:%d" % (set_id, i) for i in range(members)]
    ev = np.full((members, H, W), np.inf)
    for s, cells in (ignitions or {}).items():
        for cell, b in cells.items():
            r, c = router_to_native(cell, W, H)
            ev[s, r, c] = float(b)
    cur = np.zeros((H, W), dtype=bool)
    for cell in current:
        r, c = router_to_native(cell, W, H)
        cur[r, c] = True
    np.savez(d / "constructed_arrays.npz", ignition_time_s=ev, current_active=cur, support=np.ones((H, W), dtype=bool))
    res = grid["resolution"]
    report = {"native_metadata": {
        "affine_transform": [res, 0.0, grid["x0"], 0.0, -res, grid["y0"] + H * res], "crs": "EPSG:5179",
        "time_origin": time_origin,
        "construction": {"parent_forecast": {"cutoff_utc": time_origin}, "assumptions": {
            "version": "wfg.hazard.construction/1", "burning_duration_s": T, "initial_remaining_s": R, "horizon_s": horizon,
            "fuel_load_kg_m2": 10.0, "consumed_fraction": 0.1, "heat_of_combustion_j_kg": 18608000.0,
            "radiative_fraction": 0.3, "atmospheric_transmissivity": 1.0, "emission_height_m": 5.0, "receiver_height_m": 0.0}}},
        "rows": [{"request": {"incurred": {m: 0 for m in ids}}}]}
    (d / "REPORT.json").write_text(json.dumps(report))
    (d / "NATIVE_METADATA.json").write_text(json.dumps(report["native_metadata"]))
    out = []
    for s in range(members):
        births = {}
        for cell, b in (ignitions or {}).get(s, {}).items():
            births[cell] = float(b)
        knots = {0.0, horizon}
        for b in births.values():
            if 0 < b < horizon:
                knots.add(b)
            e = round_up_sum(b, T)
            if 0 < e < horizon:
                knots.add(e)
        if current and 0 < R < horizon:
            knots.add(float(R))
        bp = sorted(knots)
        flame = []
        for left in bp[:-1]:
            row = [False] * (W * H)
            for cell, b in births.items():
                if b <= left < round_up_sum(b, T):
                    row[cell] = True
            if left < R:
                for cell in current:
                    row[cell] = True
            flame.append(row)
        out.append({"id": ids[s], "breakpoints": bp, "flame": flame, "flux": [[0.0] * (W * H) for _ in flame],
                    "support": [[True] * (W * H) for _ in flame]})
    hz = {"schema": "wfg.routing.edgegrid/1", "version": 1, "graph_revision": "synthetic", "crs": "EPSG:5179", "grid": dict(grid),
          "dt": 1, "time_origin": time_origin, "issued_at": time_origin, "available_at": time_origin, "valid_from": 0.0,
          "valid_until": horizon, "members": out}
    (d / "HAZARD.json").write_text(json.dumps(hz))
    return ids


def graph(nodes: dict, edges: list, *, waitable=(), forbidden=()) -> dict:
    """nodes: {id: (x, y)}; edges: [(id, u, v, ticks)] (each edge also needs no reverse here)."""
    return {"revision": "synthetic", "crs": "EPSG:5179", "grid": dict(GRID),
            "nodes": [{"id": k, "x": float(x), "y": float(y), "waitable": k in waitable} for k, (x, y) in nodes.items()],
            "edges": [{"id": e, "u": u, "v": v, "travel_ticks": t, "reverse_edge": None, "segments": [], "source_way": 1000 + i,
                       "direction_evidence": "synthetic"} for i, (e, u, v, t) in enumerate(edges)],
            "forbidden_turns": [list(p) for p in forbidden], "mid_edge_reversal": False}


def route_job(job_id, *, start, dest, depart, legs_edges, raw_graph, dwell=120, window=(0, 3600), waits=()):
    """A cached checked route-check job whose route is the given edge sequence driven without waits (or with
    ``waits`` = [(index_before_edge, seconds)])."""
    edges = {e["id"]: e for e in raw_graph["edges"]}
    t = depart
    times, nodes, eids, wlist, legs = [t], [start], [], [], []
    node = start
    wait_at = dict(waits)
    for i, eid in enumerate(legs_edges):
        if i in wait_at:
            for s in range(t, t + wait_at[i]):
                legs.append({"kind": "WAIT", "node": node, "start": s, "end": s + 1})
            wlist.append({"node_id": node, "from_s": t, "to_s": t + wait_at[i]})
            t += wait_at[i]
            times.append(t)
            nodes.append(node)
        e = edges[eid]
        assert e["u"] == node
        legs.append({"kind": "EDGE", "edge": eid, "start": t, "end": t + e["travel_ticks"], "from_fraction": 0, "to_fraction": 1})
        t += e["travel_ticks"]
        node = e["v"]
        times.append(t)
        nodes.append(node)
        eids.append(eid)
    assert node == dest
    sha = canonical_sha256({"legs": legs, "destination": dest, "arrival": t})
    return {"job_id": job_id, "kind": "route_check", "status": "done",
            "request": {"start": {"node_id": start}, "destination": {"node_id": dest}, "depart_offset_s": depart, "dwell_s": dwell,
                        "destination_window": list(window), "policy": "full"},
            "snap": {}, "error": None,
            "result": {"verdict": "checked_route", "reason_code": None, "raw_status": "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN",
                       "departure_s": depart, "arrival_s": t, "route": {"type": "Feature", "geometry": {"type": "LineString", "coordinates": []},
                                                                      "properties": {"times_s": times, "node_ids": nodes, "edge_ids": eids,
                                                                                     "waits": wlist, "route_sha256": sha}}}}


def refusal_job(job_id, *, start, dest, depart, verdict="model_no_route", reason=None, dwell=120, window=(0, 3600)):
    return {"job_id": job_id, "kind": "route_check", "status": "done",
            "request": {"start": {"node_id": start}, "destination": {"node_id": dest}, "depart_offset_s": depart, "dwell_s": dwell,
                        "destination_window": list(window), "policy": "full"},
            "snap": {}, "error": None,
            "result": {"verdict": verdict, "reason_code": reason, "raw_status": "FULL_MODEL_REFUSAL_PROVEN" if verdict == "model_no_route" else "UNRESOLVED",
                       "departure_s": depart, "arrival_s": None, "route": None}}


def cache_doc(plans: list, route_checks: dict, research_checks=(), offsets=(0, 600, 1200, 1800, 2400, 3000)) -> dict:
    """plans: [{origin_id: [attempt dicts]}] grouped in one dispatch job."""
    plan_list = []
    for origin_id, attempts in plans:
        plan_list.append({"origin_id": origin_id, "attempts": attempts})
    job = {"job_id": "dp_synthetic", "kind": "dispatch_plan", "status": "done", "request": {"depart_offsets_s": list(offsets)},
           "result": {"plans": plan_list, "rejected_origins": []}}
    return {"schema": "wfg.planner.cache/1", "region_id": "synthetic", "plans": [job], "requests": [{"depart_offsets_s": list(offsets)}],
            "route_checks": route_checks, "research_checks": list(research_checks), "rejected_requests": [], "travel_only": {}}


def attempt(dest, off, verdict, job_id, arrival=None, reason=None):
    return {"destination_id": dest, "depart_offset_s": off, "verdict": verdict, "reason_code": reason, "arrival_s": arrival,
            "route_check_job_id": job_id}


def travel_only_job(job_id, *, contact, status, raw_graph, member_ids, **route_kw):
    """A cached travel-only route check (router policy travel_only) with the API's recorded full-policy assessment:
    ``contact`` = per-member contact flags in member order, ``status`` = its whole_road_contact."""
    job = route_job(job_id, raw_graph=raw_graph, **route_kw)
    job["request"]["policy"] = "travel_only"
    job["result"]["policy"] = "travel_only"
    job["result"]["full_policy_assessment"] = {
        "whole_road_contact": status, "grammar_ok": True,
        "per_scenario": {m: {"peak_kw_m2": 0.0, "dose_kj_m2": 0.0, "contact": bool(c)} for m, c in zip(member_ids, contact)}}
    return job


def with_provenance(job: dict, *, graph_sha, packet_sha: dict, set_id, region, input_time, member_ids, policy="full") -> dict:
    """Attach the result provenance the API records (input hashes of the graph and the packet files)."""
    job.setdefault("result", {})["provenance"] = {
        "input_hashes": {"graph": graph_sha, "hazard": packet_sha["HAZARD.json"],
                         "packet/REPORT.json": packet_sha["REPORT.json"], "packet/NATIVE_METADATA.json": packet_sha["NATIVE_METADATA.json"],
                         "packet/constructed_arrays.npz": packet_sha["constructed_arrays.npz"]},
        "scenario_set_id": set_id, "region": region, "input_time": input_time, "scenario_ids": list(member_ids),
        "fire_input_type": "recorded", "policy": policy}
    return job


def lonlat_identity(x, y):
    return (float(x), float(y))
