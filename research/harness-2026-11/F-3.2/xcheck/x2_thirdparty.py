"""X2 (PASS_RULES.md): earliest arrival on small random instances by four methods that must agree.

M1 wfg_sipp.sipp.solve; M2 generate.certify accepted by BOTH checkers with the same claim/T; M3 networkx 3.4.2 on a
time-expanded graph; M4 an exhaustive time sweep. M3 and M4 below are written from CERTIFICATE_SPEC.md §1 only
(the instance is plain data here; they never call the router or the checkers):
  points (s, t, a); init (s0, dep, 1);
  EDGE (s,t,*) -> (j, t+D_j, 1) iff tail[j] = hd(s), (s,j) not forbidden, t not in EB_j, t+D_j <= H;
  WAIT (s,t,*) -> (s, t+1, 0) iff waitable[hd(s)], t not in WB_hd(s), t+1 <= H;
  goal (s,t,1) with t in AC_hd(s); hd(s) = head[s], or origin for the issue sentinel s = E.
Usage: python x2_thirdparty.py --n 2000 --seed 20261112 --c-checker PATH --out FILE [--control none|perturb|wait_admits|ignore_eb]
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import networkx as nx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


# ---------------------------------------------------------------- instance data (plain dicts) and generator
def _ivls(rng, lo, hi, k):
    """k random closed integer intervals inside [lo, hi], merged (sorted, disjoint, non-adjacent)."""
    raw = []
    for _ in range(k):
        a = rng.randint(lo, hi); b = min(hi, a + rng.randint(0, max(1, (hi - lo) // 3)))
        raw.append((a, b))
    raw.sort(); out = []
    for a, b in raw:
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def random_instance(rng):
    V = rng.randint(3, 8); E = rng.randint(V, 3 * V); H = rng.randint(8, 48); dep = rng.randint(0, 3)
    tail = [rng.randrange(V) for _ in range(E)]
    head = [rng.choice([n for n in range(V) if n != tail[j]]) for j in range(E)]
    D = [rng.randint(1, 6) for _ in range(E)]
    origin = rng.randrange(V)
    into = [j for j in range(E) if head[j] == origin]
    s0 = rng.choice(into) if into and rng.random() < 0.2 else E
    forbidden = sorted({(s, j) for s in range(E + 1) for j in range(E) if rng.random() < 0.1})
    waitable = [rng.random() < 0.6 for _ in range(V)]
    EB = {j: iv for j in range(E) if (iv := _ivls(rng, 0, H, rng.randint(0, 3)))}
    WB = {n: iv for n in range(V) if (iv := _ivls(rng, 0, H, rng.randint(0, 3)))}
    dests = rng.sample(range(V), rng.randint(1, 2))
    AC = {n: iv for n in dests if (iv := _ivls(rng, 0, H, rng.randint(1, 2)))}
    return dict(V=V, tail=tail, head=head, D=D, origin=origin, s0=s0, forbidden=forbidden, waitable=waitable,
                EB=EB, WB=WB, AC=AC, dep=dep, H=H)


def edge_cases():
    base = dict(V=3, tail=[0, 1, 0], head=[1, 2, 2], D=[2, 3, 6], origin=0, s0=3, forbidden=[], waitable=[True, True, True],
                EB={}, WB={}, AC={2: [(0, 20)]}, dep=0, H=20)
    out = [dict(base, name="plain")]
    out.append(dict(base, name="dep_eq_H", dep=20))
    out.append(dict(base, name="no_acceptance", AC={}))
    out.append(dict(base, name="origin_is_destination", AC={0: [(0, 20)], 2: [(0, 20)]}))
    out.append(dict(base, name="origin_destination_later_window", AC={0: [(5, 20)]}))
    out.append(dict(base, name="nothing_waitable", waitable=[False, False, False], AC={2: [(9, 9)]}))
    out.append(dict(base, name="all_edges_blocked", EB={0: [(0, 20)], 1: [(0, 20)], 2: [(0, 20)]}))
    out.append(dict(base, name="wait_needed_at_unwaitable", waitable=[True, False, True], EB={1: [(0, 4)]}, AC={2: [(0, 20)]}))
    out.append(dict(base, name="forbidden_turn", forbidden=[(0, 1)], AC={2: [(0, 5)]}))
    return out


def hd(I, s):
    return I["origin"] if s == len(I["D"]) else I["head"][s]


def inside(t, ivs):
    return any(a <= t <= b for a, b in ivs)


# ---------------------------------------------------------------- M3: networkx time-expanded graph (third party)
def m3_networkx(I, control="none"):
    E, H, dep = len(I["D"]), I["H"], I["dep"]
    if dep > H:
        return None
    forb = set(map(tuple, I["forbidden"]))
    G = nx.DiGraph()
    init = (I["s0"], dep, 1)
    G.add_node(init)
    for s in range(E + 1):
        n = hd(I, s)
        for t in range(dep, H + 1):
            for a in (0, 1):
                p = (s, t, a)
                for j in range(E):
                    if I["tail"][j] != n or (s, j) in forb:
                        continue
                    if control != "ignore_eb" and inside(t, I["EB"].get(j, [])):
                        continue
                    if t + I["D"][j] <= H:
                        G.add_edge(p, (j, t + I["D"][j], 1))
                if I["waitable"][n] and not inside(t, I["WB"].get(n, [])) and t + 1 <= H:
                    G.add_edge(p, (s, t + 1, 1 if control == "wait_admits" else 0))
    reach = nx.descendants(G, init) | {init}
    goals = [t for (s, t, a) in reach if a == 1 and inside(t, I["AC"].get(hd(I, s), []))]
    return min(goals) if goals else None


# ---------------------------------------------------------------- M4: exhaustive time sweep (brute force)
def m4_sweep(I):
    E, H, dep = len(I["D"]), I["H"], I["dep"]
    if dep > H:
        return None
    forb = set(map(tuple, I["forbidden"]))
    at = {t: set() for t in range(dep, H + 1)}
    at[dep].add((I["s0"], 1))
    for t in range(dep, H + 1):
        for (s, a) in sorted(at[t]):
            if a == 1 and inside(t, I["AC"].get(hd(I, s), [])):
                return t                                   # times are swept in increasing order: first goal is earliest
            n = hd(I, s)
            for j in range(E):
                if I["tail"][j] == n and (s, j) not in forb and not inside(t, I["EB"].get(j, [])) and t + I["D"][j] <= H:
                    at[t + I["D"][j]].add((j, 1))
            if I["waitable"][n] and not inside(t, I["WB"].get(n, [])) and t + 1 <= H:
                at[t + 1].add((s, 0))
    return None


# ---------------------------------------------------------------- M1 / M2: the router and our certificate pipeline
def to_instance(I):
    from wfg_sipp.sipp import Instance
    return Instance(n_nodes=I["V"], tail=list(I["tail"]), head=list(I["head"]), D=list(I["D"]), origin=I["origin"],
                    start_state=I["s0"], forbidden=set(map(tuple, I["forbidden"])), waitable=list(I["waitable"]),
                    edge_block={j: list(v) for j, v in I["EB"].items()}, wait_block={n: list(v) for n, v in I["WB"].items()},
                    accept={n: list(v) for n, v in I["AC"].items()}, departure=I["dep"], horizon=I["H"])


def m1_solve(I):
    from wfg_sipp.sipp import solve
    r = solve(to_instance(I))
    if r["status"] not in ("FOUND", "EXHAUSTED"):
        raise RuntimeError("M1 status " + r["status"])
    return int(r["arrival"]) if r["status"] == "FOUND" else None


def m2_certify(I, c_checker, tmp):
    import generate as G
    claim, T, text, _, _ = G.certify(to_instance(I))
    p = Path(tmp) / "x.wfgc"; p.write_text(text)
    py = subprocess.run([sys.executable, str(HERE.parent / "check_py.py"), str(p)], capture_output=True, text=True).stdout.strip()
    cc = subprocess.run([c_checker, str(p)], capture_output=True, text=True).stdout.strip()
    want = "ACCEPT %s %s" % (claim, T)
    if not (py == cc == want):
        return "CHECKER_DISAGREE py=%r c=%r want=%r" % (py, cc, want)
    return T if claim == "ROUTE" else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--c-checker", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--control", choices=["none", "perturb", "wait_admits", "ignore_eb"], default="none")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    insts = [dict(random_instance(rng), name="r%04d" % i) for i in range(a.n)] + edge_cases()
    rows, bad = [], []
    stats = dict(route=0, no_route=0)
    with tempfile.TemporaryDirectory() as tmp:
        for k, I in enumerate(insts):
            m1 = m1_solve(I)
            if a.control == "perturb" and k < 50 and m1 is not None:
                m1 += 1
            if a.control in ("none", "perturb"):
                m2 = m2_certify(I, a.c_checker, tmp)
                m3 = m3_networkx(I)
            else:
                m2 = m1                                   # controls (ii)/(iii) test the M3 encoder against M1
                m3 = m3_networkx(I, a.control)
            m4 = m4_sweep(I)
            agree = m1 == m2 == m3 == m4
            stats["route" if m4 is not None else "no_route"] += 1
            if not agree:
                bad.append(dict(name=I["name"], M1=m1, M2=m2, M3=m3, M4=m4, instance=I))
    rep = dict(control=a.control, seed=a.seed, instances=len(insts), random=a.n, edge_cases=len(insts) - a.n,
               networkx=nx.__version__, disagreements=len(bad), **stats,
               PASS=(len(bad) == 0) if a.control == "none" else None, DETECTED=(len(bad) > 0) if a.control != "none" else None,
               disagreement_examples=[{k: v for k, v in b.items() if k != "instance"} for b in bad[:10]],
               disagreement_instances=[b["instance"] for b in bad[:5]])
    Path(a.out).write_text(json.dumps(rep, indent=1, default=list) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if not k.startswith("disagreement_")}), flush=True)
    return 0 if (rep["PASS"] if a.control == "none" else rep["DETECTED"]) else 1


if __name__ == "__main__":
    sys.exit(main())
