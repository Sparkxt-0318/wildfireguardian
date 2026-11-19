"""Closures → F-3.1 deadline field → per-village answers. No new science: the instance is built exactly as
research/kcf-replay/replay.py (Region.instance, Region.accept, run_one) builds it, and the field is the unchanged
research/harness-2026-11/F-3.1/deadline_field/core.py (vendored byte-for-byte in vendor/deadline_field).
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F

from .vendor.deadline_field import core
from .vendor.deadline_field import intervals as iv

STAGES = ("즉시 실행", "실행대기", "준비")  # immediate, standby, prepare
STAGE_EN = {"즉시 실행": "Execute now", "실행대기": "Standby", "준비": "Prepare"}


def ceil_q(x: F) -> int:
    return -((-x.numerator) // x.denominator)


def build_instance(road, close_s: dict, H: int) -> core.Instance:
    """replay.py Region.instance: edge j is closed for start t when its occupancy meets a closed cell along its
    chord (phase [b, beyond H)); a wait [t, t+1] at a waitable node is closed from b - 1."""
    B = []
    for j, segs in enumerate(road.seg):
        Dq = F(road.D[j])
        lo = None
        for c, zb in segs:
            b = close_s.get(c)
            if b is None:
                continue
            s = max(ceil_q(F(b) - Dq * zb), 0)
            lo = s if lo is None else min(lo, s)
        B.append([(lo, H)] if lo is not None and lo <= H else [])
    W = []
    for v, c in enumerate(road.node_cell):
        b = close_s.get(c)
        W.append([(max(b - 1, 0), H)] if (road.waitable[v] and b is not None and b - 1 <= H) else [])
    return core.Instance(H=H, n_nodes=len(road.node_ids), tail=road.tail, head=road.head, D=road.D,
                         waitable=road.waitable, forbidden=road.forbidden, B=B, W=W)


def accept(road, close_s: dict, node: int, H: int, dwell: int, nodeb=None):
    """replay.py Region.accept: arrival a is accepted if a <= H - dwell and the shelter cell is not closed during
    the stay [a, a + dwell]. ``nodeb`` (heat option): per-node closure second in place of the cell's."""
    b = nodeb(node) if nodeb else close_s.get(road.node_cell[node])
    acc = (0, H - dwell)
    if acc[1] < 0:
        return []
    if b is not None:
        return iv.subtract(acc, [(max(b - dwell, 0), H)])
    return [acc]


def origin_closure(road, close_s: dict, node: int, H: int, nodeb=None):
    b = nodeb(node) if nodeb else close_s.get(road.node_cell[node])
    return [(b, H)] if b is not None else []


# ------------------------------------------------------------------------------------------------ workers
_W = {}


def _init(inst_args, inc_by_node):
    _W["inst"] = core.Instance(**inst_args)
    _W["inc"] = inc_by_node


def _legs(w):
    if w is None:
        return None
    arr, legs = w
    return {"arrival": arr, "legs": [list(l) for l in legs]}


def _shelter_job(job):
    """One backward pass for one shelter; issue sets and witnesses for the origins that list it."""
    snode, acc, origins = job
    inst = _W["inst"]
    E = len(inst.tail)
    inst.A = [[] for _ in range(E)]
    for j in _W["inc"].get(snode, []):
        inst.A[j] = list(acc)
    inst.AN = {}
    inst.IB = {}
    fld = core.backward(inst)
    out = {}
    for on, ib in origins:
        inst.IB = {on: ib}
        S = core.issue_set(fld, on)
        res = {"set": [list(p) for p in S], "w_last": None, "w_first": None}
        if S:
            res["w_last"] = _legs(core.witness(fld, on, S[-1][1]))
            if S[0][0] == 0:
                res["w_first"] = _legs(core.witness(fld, on, 0))
        out[on] = res
    inst.IB = {}
    return snode, out, fld.stats["pushes"]


def run_passes(road, inst, jobs, workers: int):
    args = {"H": inst.H, "n_nodes": inst.n_nodes, "tail": inst.tail, "head": inst.head, "D": inst.D,
            "waitable": inst.waitable, "forbidden": inst.forbidden, "B": inst.B, "W": inst.W}
    if workers <= 1:
        _init(args, road.inc_by_node)
        return [_shelter_job(j) for j in jobs]
    with ProcessPoolExecutor(workers, initializer=_init, initargs=(args, road.inc_by_node)) as ex:
        return list(ex.map(_shelter_job, jobs, chunksize=1))


def default_workers(setting: int) -> int:
    if setting and setting > 0:
        return setting
    return max(1, min(8, os.cpu_count() or 1))


# ------------------------------------------------------------------------------------------------ stages
def stage_of(remaining_s, horizon_left_s, st):
    """Stage from the time left until fire arrival. remaining_s None = not reached before the horizon, which is
    horizon_left_s away. Returns a stage name or None when the horizon is too short to tell."""
    imm, sb = st["immediate_hours"] * 3600, st["standby_hours"] * 3600
    if remaining_s is not None:
        if remaining_s <= imm:
            return "즉시 실행"
        if remaining_s <= sb:
            return "실행대기"
        return "준비"
    # arrival is later than the horizon: remaining > horizon_left_s
    if horizon_left_s >= sb:
        return "준비"
    return None


def assemble(region, fire, settings, inst, results, close_s, nodeb=None):
    """Per-village rows (dicts with seconds after issue; formatting is done by the writers)."""
    H = fire.horizon_s
    dwell = settings["routing"]["dwell_s"]
    st = settings["stage"]
    road = region.road
    by_shelter = {snode: out for snode, out, _ in results}
    rows = []
    for o in region.origins:
        row = {"origin": o, "refusal": None, "candidates": region.cands.get(o["id"], [])}
        rows.append(row)
        if o["node"] is None or not o["checkable"]:
            row["refusal"] = ("ENTRY_TOO_FAR", "도로망 2 km 밖 — 점검 불가", "more than 2 km from the road network — not checkable")
            continue
        cands = row["candidates"]
        if not cands:
            row["refusal"] = ("NO_SHELTER", "후보 대피소 없음", "no candidate shelter")
            continue
        on = o["node"]
        cell = road.node_cell[on]
        if cell in fire.uncovered_set:
            row["refusal"] = ("FIRE_INPUT_UNCOVERED", "진입 지점 셀에 화재 도달 자료 없음", "no fire-arrival data at the entry cell")
            continue
        A = close_s.get(cell)  # fire arrival at the village's entry cell, None = not within H
        fast = road.fastest_ticks(on, {s["node"] for s in cands}, max_ticks=H)
        per = []
        for k, s in enumerate(cands):
            res = by_shelter[s["node"]][on]
            S = [tuple(p) for p in res["set"]]
            ft = fast.get(s["node"])
            free = H - dwell - ft if ft is not None and H - dwell - ft >= 0 else None
            per.append({"k": k, "shelter": s, "set": S, "L": S[-1][1] if S else None, "fire_free_latest": free,
                        "fastest_s": ft, "w_last": res["w_last"], "w_first": res["w_first"],
                        "accept": accept(road, close_s, s["node"], H, dwell, nodeb)})
        row["per_shelter"] = per
        if all(p["fire_free_latest"] is None for p in per):
            row["refusal"] = ("NO_ROAD_PATH", "화재와 무관하게 도로망으로 후보 대피소에 갈 수 없음",
                              "no road path to any candidate shelter even without fire")
            continue
        windows = iv.normalize([p for x in per for p in x["set"]])
        Ls = [p["L"] for p in per if p["L"] is not None]
        L = max(Ls) if Ls else None
        free_max = max(p["fire_free_latest"] for p in per if p["fire_free_latest"] is not None)
        # The last road out is cut at L + 1 unless the latest departure is set by the horizon: some shelter attaining
        # L is reached, by the earliest journey departing at L, exactly at H - dwell (replay.py: cut_within_H is
        # false when the witness arrives at H - DWELL). Closures are permanent, so a journey from L + 1 can never
        # arrive earlier than one from L; the horizon then binds and nothing is known beyond it.
        horizon_bound = L is not None and any(p["L"] == L and p["w_last"] is not None and p["w_last"]["arrival"] == H - dwell
                                              for p in per)
        if L is None:
            cut = 0
        elif horizon_bound:
            cut = None
        else:
            cut = L + 1
        row.update(windows=windows, L=L, leave_by=(windows[0][1] if windows and windows[0][0] == 0 else None),
                   fire_free_latest=free_max, cut=cut, A=A, horizon=H, origin_ib=origin_closure(road, close_s, on, H, nodeb))
        # route at the latest departure (the last road out) and at the issue time (leave now)
        best = None
        for p in per:
            if L is not None and p["L"] == L and p["w_last"] is not None:
                key = (p["w_last"]["arrival"], p["k"])
                if best is None or key < best[0]:
                    best = (key, p)
        row["last"] = best[1] if best else None
        first = None
        for p in per:
            if p["w_first"] is not None:
                key = (p["w_first"]["arrival"], p["k"])
                if first is None or key < first[0]:
                    first = (key, p)
        row["now"] = first[1] if first else None
        # stages
        row["stage_now"] = stage_of(A, H, st)
        row["stage_immediate_at"] = (A - st["immediate_hours"] * 3600) if (A is not None and A > st["immediate_hours"] * 3600) else None
        if cut is None:
            row["stage_at_cut"] = None
            row["flag"] = False
            row["gap"] = None
        else:
            if A is not None:
                row["gap"] = A - cut
                row["stage_at_cut"] = stage_of(A - cut, None, st)
                row["flag"] = (A - cut) > st["immediate_hours"] * 3600
            else:
                row["gap"] = None  # more than H - cut
                row["stage_at_cut"] = stage_of(None, H - cut, st)
                row["flag"] = True if (H - cut) >= st["immediate_hours"] * 3600 else None
    return rows


def sort_key(row):
    """Earliest road cut first; villages with no cut inside the horizon after, by fire arrival; refusals last."""
    if row["refusal"]:
        return (3, 0, 0, row["origin"]["name"], row["origin"]["id"])
    if row["cut"] is not None:
        return (0, row["cut"], row["A"] if row["A"] is not None else 1 << 40, row["origin"]["name"], row["origin"]["id"])
    return (1, row["A"] if row["A"] is not None else 1 << 40, 0, row["origin"]["name"], row["origin"]["id"])
