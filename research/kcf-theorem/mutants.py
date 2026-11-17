"""A copy of deadline_field.core.backward / issue_core (F-3.1, unchanged logic when mutation is None) with five
switchable, realistic bugs, plus a greedy route extractor that follows the (possibly buggy) field with the SAME
(possibly buggy) transition rule, as a real implementation sharing one helper would.

Mutations (THEOREM.md section 6):
  shift_off_by_one   edge travel taken as D - 1 when shifting intervals back (and when emitting legs)
  ignore_turns       forbidden turns not removed from the predecessor lists (nor when emitting legs)
  block_at_arrival   closure tested at the arrival second t + D instead of the start second t
  wait_through_fire  waiting closure extends to second 0, ignoring wait-blocked seconds W_v
  scalar_deadline    each state keeps one number (latest time) and treats [0, latest] as feasible
"""
from __future__ import annotations

import heapq
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness-2026-11" / "F-3.1"))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import Field  # noqa: E402

MUTATIONS = ("shift_off_by_one", "ignore_turns", "block_at_arrival", "wait_through_fire", "scalar_deadline")


def _dur(inst, j, mut):
    return inst.D[j] - 1 if mut == "shift_off_by_one" else inst.D[j]


def _blocked_starts(inst, j, mut):
    if mut == "block_at_arrival":   # B tested at t + D: start t is blocked iff t + D in B
        return iv.normalize([(lo - inst.D[j], hi - inst.D[j]) for lo, hi in inst.B[j]])
    return inst.B[j]


def _wait_close(piece, Wv, mut):
    lo, hi = piece
    if mut == "wait_through_fire":
        return (0, hi)
    w = iv.max_below(Wv, lo)
    lo2 = 0 if w is None else max(w + 1, 0)
    return (min(lo, lo2), hi)


def backward(inst, mutation=None):
    E = len(inst.tail)
    R = [[] for _ in range(E)]
    pred = [[i for i in inst.inc[inst.tail[j]] if mutation == "ignore_turns" or (i, j) not in inst.forbidden]
            for j in range(E)]
    Bm = [_blocked_starts(inst, j, mutation) for j in range(E)]
    heap = [(-hi, j, lo, hi) for j in range(E) for lo, hi in inst.A[j]]
    heapq.heapify(heap)
    pushes = 0
    while heap:
        _, j, lo, hi = heapq.heappop(heap)
        d = _dur(inst, j, mutation)
        a, b = max(lo - d, 0), hi - d
        if a > b:
            continue
        cand = iv.subtract((a, b), Bm[j])
        for s in pred[j]:
            new = iv.subtract_all(cand, R[s])
            if not new:
                continue
            hv = inst.head[s]
            if inst.waitable[hv]:
                ext = []
                for p in new:
                    ext.extend(iv.subtract(_wait_close(p, inst.W[hv], mutation), R[s]))
                new = iv.subtract_all(iv.normalize(ext), R[s])
            if mutation == "scalar_deadline":
                top = max([p[1] for p in new] + [p[1] for p in R[s]])
                new = iv.subtract((0, top), R[s])
            for p in new:
                iv.add(R[s], p)
            for p in new:
                for q in iv.subtract(p, inst.A[s]):
                    heapq.heappush(heap, (-q[1], s, q[0], q[1]))
                    pushes += 1
            if pushes > 10 ** 6:
                raise RuntimeError("PIECES_CAP")
    G = [iv.normalize(R[j] + inst.A[j]) for j in range(E)]
    fld = Field(inst, R, G, {"pushes": pushes})
    fld.stats["mutation"] = mutation
    fld.stats["Bm"] = Bm
    return fld


def issue_set(fld, o, core_only=False):
    inst, mut = fld.inst, fld.stats["mutation"]
    X = []
    for j in inst.out[o]:
        d = _dur(inst, j, mut)
        for lo, hi in fld.G[j]:
            a, b = max(lo - d, 0), hi - d
            if a <= b:
                X.extend(iv.subtract((a, b), fld.stats["Bm"][j]))
    X = iv.normalize(X)
    if inst.waitable[o]:
        X = iv.normalize([_wait_close(p, inst.W[o], mut) for p in X])
    if core_only:                   # seconds from which the origin (after the issue, admission false) can complete
        return [(0, X[-1][1])] if mut == "scalar_deadline" and X else X
    X = iv.normalize(X + inst.AN.get(o, []))
    if mut == "scalar_deadline" and X:
        X = [(0, X[-1][1])]
    return iv.subtract_all(X, iv.normalize(inst.IB.get(o, [])))


def greedy_route(fld, o, t, max_legs=10 ** 4):
    """Follow the field from (o, t) with the field's own transition rule. Returns legs (list) or a string naming
    the dead end. Legs use the checker's format."""
    inst, mut = fld.inst, fld.stats["mutation"]
    if iv.contains(inst.AN.get(o, []), t):
        return []
    s, node, time, admitted, legs = None, o, t, False, []
    core = issue_set(fld, o, core_only=True)
    for _ in range(max_legs):
        if s is not None and admitted and iv.contains(inst.A[s], time):
            return legs
        best = None
        for j in inst.out[node]:
            if s is not None and mut != "ignore_turns" and (s, j) in inst.forbidden:
                continue
            arr = time + _dur(inst, j, mut)
            if arr > inst.H or iv.contains(fld.stats["Bm"][j], time) or not iv.contains(fld.G[j], arr):
                continue
            key = (0 if iv.contains(inst.A[j], arr) else 1, -arr, j)
            if best is None or key < best[0]:
                best = (key, j, arr)
        if best is not None:
            _, j, arr = best
            legs.append(["EDGE", j, time, arr])
            s, node, time, admitted = j, inst.head[j], arr, True
            continue
        nxt = core if s is None else fld.R[s]
        w_ok = mut == "wait_through_fire" or not iv.contains(inst.W[node], time)
        if inst.waitable[node] and time + 1 <= inst.H and w_ok and iv.contains(nxt, time + 1):
            legs.append(["WAIT", node, time, time + 1])
            time, admitted = time + 1, False
            continue
        return "dead end at node %d, time %d" % (node, time)
    return "no acceptance within %d legs" % max_legs
