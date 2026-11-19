#!/usr/bin/env python3
"""Re-verify wfg-roadlayer village certificates WITHOUT the tool. Standard library only. It imports one module:
checker.py, the independent route checker of research/kcf-theorem (copied byte for byte next to this file).

    python3 verify_certificate.py CERT_DIR            # every certificates/villages/*.json
    python3 verify_certificate.py CERT_DIR/villages/X.json [...]

What is checked, for every village (THEOREM.md is research/kcf-theorem/THEOREM.md):

 1. instance.json.gz has the SHA-256 the certificate names (of its uncompressed bytes).
 2. The masks follow from the fire input: every edge closure B, wait closure W, shelter acceptance A and origin
    closure IB is re-derived here from the per-cell closure seconds and the road geometry (exact fractions) and must
    equal the stored masks. With the heat option the per-piece and per-node closure seconds stored in the instance
    take the cell's place (the radiant-heat rule that produced them is research/kcf-radiation; run.json records it).
 3. Hypotheses M1-M4 of Theorem 2 hold (closures permanent, shelters accept from second 0, origin closure
    permanent). Then every feasible departure set is a prefix [0, L] (Theorem 2(a)).
 4. For every candidate shelter, L is recomputed by the scalar recursion of Theorem 2(b), written here from the
    theorem (not from the tool), and must equal the claimed latest departure. This proves both "a route exists for
    every departure up to L" and "no route exists at L + 1".
 5. Every witness journey (at the latest departure and at the issue time) is accepted by checker.check_route.
 6. The road-cut claim: "fire" needs the latest witness to arrive before H - dwell (so the horizon does not bind,
    and the cut at L + 1 is caused by a closure); "horizon" needs a shelter attaining L whose latest departure falls
    below L when its acceptance ends one second earlier (so the earliest journey from L arrives exactly at H - dwell);
    "at_issue" needs every set to be empty.
 7. Fire arrival at the village equals the closure second of its entry cell; the stage and the flag follow from the
    stated thresholds.

Not checked here: how the fire-arrival raster was resampled to the 375 m road cells (run.json names the raster's
SHA-256 and the rule), and whether the model fits reality. Exit status 0 only if every certificate passes.
"""
from __future__ import annotations

import gzip
import hashlib
import heapq
import json
import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checker  # noqa: E402  (research/kcf-theorem/checker.py, verbatim)


def ceil_q(x: F) -> int:
    return -((-x.numerator) // x.denominator)


class Inst:
    def __init__(self, path: Path):
        raw = gzip.decompress(path.read_bytes())
        self.sha256 = hashlib.sha256(raw).hexdigest()
        d = json.loads(raw)
        self.d = d
        self.H = int(d["H"])
        self.dwell = int(d["dwell_s"])
        self.tail = [e[0] for e in d["edges"]]
        self.head = [e[1] for e in d["edges"]]
        self.D = [e[2] for e in d["edges"]]
        self.n = int(d["n_nodes"])
        self.waitable = set(d["waitable"])
        self.forbidden = {(a, b) for a, b in d["forbidden"]}
        self.B = {int(k): [tuple(x) for x in v] for k, v in d["B"].items()}
        self.W = {int(k): [tuple(x) for x in v] for k, v in d["W"].items()}
        self.close = {int(k): int(v) for k, v in d["cell_closure_s"].items()}
        self.node_cell = d["node_cell"]
        # heat option (research/kcf-radiation): per-piece and per-node closure seconds replace the cell's
        self.heat = "heat_piece_closure_s" in d
        self.piece_close = {(int(j), int(k)): int(b) for j, v in d.get("heat_piece_closure_s", {}).items() for k, b in v}
        self.node_close = {int(v): int(b) for v, b in d.get("heat_node_closure_s", {}).items()}
        self.inc, self.out = {}, {}
        for j, (u, v) in enumerate(zip(self.tail, self.head)):
            self.out.setdefault(u, []).append(j)
            self.inc.setdefault(v, []).append(j)
        self._cache = {}

    # -- check 2: masks from cell closures (research/kcf-replay/replay.py rules, re-implemented) ---------------
    def derive_masks(self):
        bad = []
        H = self.H
        for j, segs in enumerate(self.d["segments"]):
            lo = None
            for k, (c, end) in enumerate(segs):
                b = self.piece_close.get((j, k)) if self.heat else self.close.get(int(c))
                if b is None:
                    continue
                z = F(end) if isinstance(end, int) else F(end).limit_denominator(10 ** 9)
                s = max(ceil_q(F(b) - F(self.D[j]) * z), 0)
                lo = s if lo is None else min(lo, s)
            want = [(lo, H)] if lo is not None and lo <= H else []
            if self.B.get(j, []) != want:
                bad.append("edge %d: stored B %r, derived %r" % (j, self.B.get(j), want))
        for v in range(self.n):
            b = self.node_b(v)
            want = [(max(b - 1, 0), H)] if (v in self.waitable and b is not None and b - 1 <= H) else []
            if self.W.get(v, []) != want:
                bad.append("node %d: stored W %r, derived %r" % (v, self.W.get(v), want))
        return bad

    def node_b(self, node):
        return self.node_close.get(node) if self.heat else self.close.get(self.node_cell[node])

    def accept(self, node):
        b = self.node_b(node)
        hi = self.H - self.dwell
        if b is not None:
            hi = min(hi, b - self.dwell - 1)
        return [(0, hi)] if hi >= 0 else []

    def origin_closure(self, node):
        b = self.node_b(node)
        return [(b, self.H)] if b is not None else []

    # -- check 3: M1, M2 (M3, M4 are checked per certificate) ---------------------------------------------------
    def m1_m2(self):
        bad = []
        for j, ivs in self.B.items():
            cut = [(lo, min(hi, self.H - self.D[j])) for lo, hi in ivs if lo <= self.H - self.D[j]]
            if len(cut) > 1 or (cut and cut[0][1] != self.H - self.D[j]):
                bad.append("M1 fails on edge %d: %r" % (j, ivs))
        for v, ivs in self.W.items():
            cut = [(lo, min(hi, self.H - 1)) for lo, hi in ivs if lo <= self.H - 1]
            if len(cut) > 1 or (cut and cut[0][1] != self.H - 1):
                bad.append("M2 fails on node %d: %r" % (v, ivs))
        return bad

    # -- check 4: Theorem 2(b) ---------------------------------------------------------------------------------
    def c(self, j):
        lim = self.H - self.D[j]
        for lo, hi in self.B.get(j, []):
            if lo <= lim:
                return lo
        return lim + 1

    def ell(self, shelter, a_end):
        """l_s = max(a_s, max over allowed successors j of tau_j(l_j)), tau_j(x) = min(c_j - 1, x - D_j); -1 = empty."""
        key = (shelter, a_end)
        if key in self._cache:
            return self._cache[key]
        E = len(self.D)
        ell = [-1] * E
        heap = []
        if a_end is not None and a_end >= 0:
            for s in self.inc.get(shelter, []):
                ell[s] = a_end
                heap.append((-a_end, s))
        heapq.heapify(heap)
        while heap:
            nv, j = heapq.heappop(heap)
            v = -nv
            if v != ell[j]:
                continue
            x = min(self.c(j) - 1, v - self.D[j])
            if x < 0:
                continue
            for s in self.inc.get(self.tail[j], []):
                if (s, j) not in self.forbidden and x > ell[s]:
                    ell[s] = x
                    heapq.heappush(heap, (-x, s))
        self._cache[key] = ell
        return ell

    def latest(self, origin, shelter, a_end, ib):
        ell = self.ell(shelter, a_end)
        L0 = -1
        for j in self.out.get(origin, []):
            if ell[j] >= 0:
                L0 = max(L0, min(self.c(j) - 1, ell[j] - self.D[j]))
        i_o = min((lo for lo, hi in ib if lo <= self.H), default=self.H + 1)
        L = min(L0, i_o - 1)
        return L if L >= 0 else None

    # -- check 5: a checker.py instance restricted to the witness ---------------------------------------------
    def sub_instance(self, legs, origin, shelter, acc, ib):
        edges = list(dict.fromkeys(l[1] for l in legs if l[0] == "EDGE"))
        nodes = list(dict.fromkeys([origin] + [self.tail[j] for j in edges] + [self.head[j] for j in edges] +
                                   [l[1] for l in legs if l[0] == "WAIT"]))
        ei, ni = {j: i for i, j in enumerate(edges)}, {v: i for i, v in enumerate(nodes)}
        d = {"H": self.H, "edges": [[ni[self.tail[j]], ni[self.head[j]], self.D[j]] for j in edges],
             "waitable": [ni[v] for v in nodes if v in self.waitable],
             "forbidden": [[ei[a], ei[b]] for a in edges for b in edges if (a, b) in self.forbidden],
             "B": {ei[j]: [list(x) for x in self.B.get(j, [])] for j in edges},
             "W": {ni[v]: [list(x) for x in self.W.get(v, [])] for v in nodes if v in self.waitable},
             "A": {ei[j]: [list(x) for x in acc] for j in edges if self.head[j] == shelter},
             "IB": {ni[origin]: [list(x) for x in ib]}, "AN": {}}
        route = [[l[0], ei[l[1]] if l[0] == "EDGE" else ni[l[1]], l[2], l[3]] for l in legs]
        return d, ni[origin], route


def stage(remaining, horizon_left, st):
    imm, sb = st["immediate_hours"] * 3600, st["standby_hours"] * 3600
    if remaining is not None:
        return "즉시 실행" if remaining <= imm else ("실행대기" if remaining <= sb else "준비")
    return "준비" if horizon_left >= sb else None


def verify(cert_path: Path, insts: dict):
    c = json.loads(cert_path.read_text(encoding="utf-8"))
    fails = []
    ipath = (cert_path.parent / c["instance"]["file"]).resolve()
    if ipath not in insts:
        inst = Inst(ipath)
        insts[ipath] = inst
        inst.mask_problems = inst.derive_masks() + inst.m1_m2()
    inst = insts[ipath]
    if inst.sha256 != c["instance"]["sha256_uncompressed"]:
        return ["instance SHA-256 %s differs from the certificate's %s" % (inst.sha256, c["instance"]["sha256_uncompressed"])]
    if inst.mask_problems:
        fails += inst.mask_problems[:5]
    H, o = inst.H, c["origin_node"]
    if c["horizon_s"] != H or c["dwell_s"] != inst.dwell:
        fails.append("horizon/dwell differ from the instance")
    ib = inst.origin_closure(o)
    if [tuple(x) for x in c["origin_IB"]] != ib:
        fails.append("origin closure %r, derived %r" % (c["origin_IB"], ib))
    if len(ib) > 1 or (ib and ib[0][1] != H):
        fails.append("M4 fails at the origin: %r" % ib)
    A = inst.close.get(inst.node_cell[o])
    if c["fire_arrival_at_village_s"] != A:
        fails.append("fire arrival at the village %r, entry-cell closure %r" % (c["fire_arrival_at_village_s"], A))
    Ls = []
    for sh in c["shelters"]:
        acc = inst.accept(sh["node"])
        if [tuple(x) for x in sh["A"]] != acc:
            fails.append("shelter %s acceptance %r, derived %r" % (sh["id"], sh["A"], acc))
        if acc and acc[0][0] != 0:
            fails.append("M3 fails at shelter %s" % sh["id"])
        L = inst.latest(o, sh["node"], acc[0][1] if acc else None, ib)
        want = [[0, L]] if L is not None else []
        if sh["claimed_feasible"] != want or sh["claimed_latest"] != L:
            fails.append("shelter %s: claimed %r, Theorem 2(b) gives %r" % (sh["id"], sh["claimed_feasible"], want))
        Ls.append((L, sh, acc))
    allL = [L for L, _, _ in Ls if L is not None]
    Lmax = max(allL) if allL else None
    cl = c["claims"]
    if cl["latest_departure_s"] != Lmax:
        fails.append("latest departure claimed %r, recomputed %r" % (cl["latest_departure_s"], Lmax))
    if cl["windows"] != ([[0, Lmax]] if Lmax is not None else []):
        fails.append("windows claimed %r, recomputed %r" % (cl["windows"], [[0, Lmax]] if Lmax is not None else []))
    for w in c["witnesses"]:
        L, sh, acc = next((x for x in Ls if x[1]["rank"] == w["shelter_rank"]), (None, None, None))
        if sh is None:
            fails.append("witness names an unknown shelter")
            continue
        d, oi, route = inst.sub_instance(w["legs"], o, sh["node"], acc, ib)
        ok, why = checker.check_route(d, oi, w["departure"], route)
        if not ok:
            fails.append("witness %s rejected by checker.py: %s" % (w["what"], why))
        end = w["legs"][-1][3] if w["legs"] else w["departure"]
        if end != w["arrival"]:
            fails.append("witness %s arrival %r, legs end at %r" % (w["what"], w["arrival"], end))
    kind = cl["cut_kind"]
    lw = next((w for w in c["witnesses"] if w["what"] == "latest"), None)
    if kind == "at_issue":
        if Lmax is not None or cl["road_cut_s"] != 0:
            fails.append("cut at the issue time claimed, but a departure is feasible")
    elif kind == "fire":
        if Lmax is None or lw is None or cl["road_cut_s"] != Lmax + 1:
            fails.append("fire cut claimed without a latest departure and witness")
        elif not lw["arrival"] < H - inst.dwell:
            fails.append("fire cut claimed but the latest witness arrives at H - dwell (the horizon binds)")
    elif kind == "horizon":
        good = False
        for L, sh, acc in Ls:
            if L == Lmax and acc and acc[0][1] == H - inst.dwell:
                L2 = inst.latest(o, sh["node"], acc[0][1] - 1, ib)
                if L2 is None or L2 < Lmax:
                    good = True
        if not good or cl["road_cut_s"] is not None:
            fails.append("'not cut within the horizon' claimed, but no shelter attaining L is horizon-bound")
    else:
        fails.append("unknown cut kind %r" % kind)
    st = c["stage"]
    cut = cl["road_cut_s"]
    if st["now"] != stage(A, H, st["thresholds"]):
        fails.append("stage now %r, recomputed %r" % (st["now"], stage(A, H, st["thresholds"])))
    if cut is None:
        want_flag = False
    elif A is not None:
        want_flag = (A - cut) > st["thresholds"]["immediate_hours"] * 3600
    else:
        want_flag = True if (H - cut) >= st["thresholds"]["immediate_hours"] * 3600 else None
    if st["flag"] != want_flag:
        fails.append("flag %r, recomputed %r" % (st["flag"], want_flag))
    return fails


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    paths = []
    for a in argv:
        p = Path(a)
        if p.is_dir():
            paths += sorted((p / "villages").glob("*.json")) if (p / "villages").is_dir() else sorted(p.glob("*.json"))
        else:
            paths.append(p)
    insts, n_fail = {}, 0
    for p in paths:
        fails = verify(p, insts)
        print(("PASS  " if not fails else "FAIL  ") + p.name)
        for f in fails:
            print("      " + f)
        n_fail += bool(fails)
    print("%d certificate(s): %d pass, %d fail" % (len(paths), len(paths) - n_fail, n_fail))
    return 0 if n_fail == 0 and paths else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
