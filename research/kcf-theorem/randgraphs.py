"""Random small instances for the property and mutation tests, emitted in two forms: the repository's
``deadline_field.core.Instance`` and the independent checker's plain dict. Families:

  general  closures anywhere: roads close and REOPEN, origins burn and clear, shelters open late
  closure  hypotheses M1-M4 of THEOREM.md: every closure is permanent ([c, H]), every acceptance set is [0, a]
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness-2026-11" / "F-3.1"))
from deadline_field.core import Instance  # noqa: E402


def _random_ivs(rng, H, k_max=2):
    out = []
    for _ in range(rng.randint(0, k_max)):
        a = rng.randint(0, H)
        out.append([a, min(H, a + rng.randint(0, H // 2))])
    return out


def _suffix(rng, H, p_none=0.5):
    return [] if rng.random() < p_none else [[rng.randint(0, H), H]]


def _prefix(rng, H, p_none=0.2):
    return [] if rng.random() < p_none else [[0, rng.randint(0, H)]]


def generate(rng: random.Random, family: str):
    n = rng.randint(2, 6)
    H = rng.randint(4, 20)
    E = rng.randint(1, 10)
    edges = []
    for _ in range(E):
        u = rng.randrange(n)
        v = rng.randrange(n - 1)
        v = v + 1 if v >= u else v                     # no self-loops (the road graph has none)
        edges.append([u, v, rng.randint(1, 4)])
    shelters = set(rng.sample(range(n), rng.randint(1, min(2, n))))
    waitable = [v for v in range(n) if rng.random() < 0.4]
    inc = {}
    for j, (u, v, _) in enumerate(edges):
        inc.setdefault(v, []).append(j)
    forbidden = [[i, j] for j, (u, _, _) in enumerate(edges) for i in inc.get(u, []) if rng.random() < 0.2]
    B, W, A, IB, AN = {}, {}, {}, {}, {}
    acc = {}
    for d in shelters:
        acc[d] = _random_ivs(rng, H, 2) if family == "general" else _prefix(rng, H)
    for j, (u, v, _) in enumerate(edges):
        B[j] = _random_ivs(rng, H) if family == "general" else _suffix(rng, H)
        if v in shelters:
            A[j] = acc[v]
    for v in waitable:
        W[v] = _random_ivs(rng, H) if family == "general" else _suffix(rng, H)
    for o in range(n):
        if rng.random() < 0.3:
            IB[o] = _random_ivs(rng, H, 1) if family == "general" else _suffix(rng, H, 0)
        if o in shelters and rng.random() < 0.3:
            AN[o] = acc[o]
    chk = {"H": H, "edges": edges, "waitable": waitable, "forbidden": forbidden,
           "B": B, "W": W, "A": A, "IB": IB, "AN": AN, "n_nodes": n}
    return to_instance(chk), chk


def to_instance(chk):
    n, E = chk["n_nodes"], len(chk["edges"])
    tup = lambda L: [tuple(x) for x in L]  # noqa: E731
    return Instance(H=chk["H"], n_nodes=n, tail=[e[0] for e in chk["edges"]], head=[e[1] for e in chk["edges"]],
                    D=[e[2] for e in chk["edges"]], waitable=[v in set(chk.get("waitable", ())) for v in range(n)],
                    forbidden={tuple(f) for f in chk.get("forbidden", ())},
                    B=[tup(chk.get("B", {}).get(j, [])) for j in range(E)],
                    W=[tup(chk.get("W", {}).get(v, [])) for v in range(n)],
                    A=[tup(chk.get("A", {}).get(j, [])) for j in range(E)],
                    IB={o: tup(x) for o, x in chk.get("IB", {}).items()},
                    AN={o: tup(x) for o, x in chk.get("AN", {}).items()})


def monotone_hull(chk):
    """THEOREM.md Corollary 3 transform: every closure made permanent from its first second, every acceptance set cut
    to its initial segment [0, a]. Returns a new checker dict."""
    H = chk["H"]

    def up(ivs):
        s = [lo for lo, hi in ivs if lo <= hi]
        return [[max(min(s), 0), H]] if s else []

    def down(ivs):
        pts = set()
        for lo, hi in ivs:
            pts.update(range(lo, hi + 1))
        a = -1
        while a + 1 in pts:
            a += 1
        return [[0, a]] if a >= 0 else []

    out = dict(chk)
    out["B"] = {j: up(v) for j, v in chk.get("B", {}).items()}
    out["W"] = {j: up(v) for j, v in chk.get("W", {}).items()}
    out["IB"] = {j: up(v) for j, v in chk.get("IB", {}).items()}
    out["A"] = {j: down(v) for j, v in chk.get("A", {}).items()}
    out["AN"] = {j: down(v) for j, v in chk.get("AN", {}).items()}
    return out
