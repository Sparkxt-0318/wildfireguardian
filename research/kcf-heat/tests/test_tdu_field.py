"""TDU field against an exhaustive forward oracle on random small networks.

The oracle is a plain Dijkstra on dose over the time-expanded graph from one (origin, departure second), with the
router's rules spelled out directly (as F-3.1's bruteforce.Oracle) and move doses read from dense dicts. It shares no
code with the interval/run machinery. The random networks reuse F-3.1's generator design (non-waitable nodes,
forbidden turns, cycles, blocked edges/waits/issue points, opening windows, dwell-blocked acceptance)."""
import heapq
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat.closure import iv  # noqa: E402
from kcf_heat.dose import RLE, rle_from_dense  # noqa: E402
from kcf_heat.tdu_field import INF, Costs, feasible_set, issue_values, tdu_backward, witness_tdu  # noqa: E402

from deadline_field.core import Instance, backward, issue_set  # noqa: E402


def random_instance(seed, *, max_nodes=7, H=None):
    """Same construction as F-3.1 tests/test_field_vs_oracle.random_instance (copied: that module needs hypothesis)."""
    rnd = random.Random(seed)
    n = rnd.randint(2, max_nodes)
    H = H if H is not None else rnd.randint(5, 40)
    m = rnd.randint(1, 3 * n)
    tail, head, D = [], [], []
    for _ in range(m):
        u, v = rnd.randrange(n), rnd.randrange(n)
        if u == v and rnd.random() < 0.7:
            v = (u + 1) % n
        tail.append(u); head.append(v); D.append(rnd.randint(1, max(1, H // 4)))
    waitable = [rnd.random() < 0.4 for _ in range(n)]

    def rand_ivs(k, lo=-3, hi=None):
        hi = H + 3 if hi is None else hi
        out = []
        for _ in range(rnd.randint(0, k)):
            a = rnd.randint(lo, hi); b = a + rnd.randint(0, max(1, H // 3))
            out.append((a, b))
        return out

    B = [rand_ivs(2) if rnd.random() < 0.5 else [] for _ in range(m)]
    W = [rand_ivs(2) if rnd.random() < 0.5 else [] for _ in range(n)]
    forbidden = set()
    for i in range(m):
        for j in range(m):
            if head[i] == tail[j] and rnd.random() < 0.25:
                forbidden.add((i, j))
    dests = rnd.sample(range(n), rnd.randint(1, min(3, n)))
    AN = {}
    for dnode in dests:
        dwell = rnd.randint(0, 4)
        op = rnd.randint(0, H // 2); cl = rnd.randint(op, H + 2)
        hi_ = min(cl, H) - dwell
        base = [(op, hi_)] if op <= hi_ else []
        AN[dnode] = iv.subtract_all(iv.normalize(base), iv.normalize(rand_ivs(1)))
    A = [list(AN.get(head[j], [])) for j in range(m)]
    IB = {o: (rand_ivs(1) if rnd.random() < 0.3 else []) for o in range(n)}
    return dict(H=H, n_nodes=n, tail=tail, head=head, D=D, waitable=waitable, forbidden=forbidden,
                B=B, W=W, A=A, IB=IB, AN=AN), rnd


def random_costs(raw, rnd, zero=False):
    """Dense random doses (most moves 0, some runs, some per-second noise) -> (dense dicts, Costs)."""
    H = raw["H"]

    def dense():
        a = [0] * (H + 1)
        if zero or rnd.random() < 0.4:
            return a
        for _ in range(rnd.randint(1, 3)):
            lo = rnd.randint(0, H); hi = min(H, lo + rnd.randint(0, H // 2)); c = rnd.randint(1, 9)
            for t in range(lo, hi + 1):
                a[t] = c if rnd.random() < 0.7 else rnd.randint(1, 9)
        return a

    E = [dense() for _ in raw["tail"]]
    Wd = [dense() for _ in range(raw["n_nodes"])]
    Ad = {n: dense() for n in raw["AN"]}
    costs = Costs(edge={j: RLE(rle_from_dense(a)) for j, a in enumerate(E)},
                  wait={n: RLE(rle_from_dense(a)) for n, a in enumerate(Wd)},
                  dwell={n: RLE(rle_from_dense(a)) for n, a in Ad.items()})
    return (E, Wd, Ad), costs


def oracle_min_dose(raw, dense, o, t):
    """Minimum dose of an accepted journey departing o at t; None if no journey exists."""
    E, Wd, Ad = dense
    H = raw["H"]
    S = lambda x: iv.to_set(iv.normalize(x))  # noqa: E731
    B = [S(b) for b in raw["B"]]; Wb = [S(w) for w in raw["W"]]; A = [S(a) for a in raw["A"]]
    if t in S(raw["IB"].get(o, [])):
        return None
    best = None
    if t in S(raw["AN"].get(o, [])):
        best = Ad[o][t]
    out = {}
    for j, u in enumerate(raw["tail"]):
        out.setdefault(u, []).append(j)
    start = ("issue", -1, t, False)
    dist = {start: 0}
    heap = [(0, 0, start)]
    k = 1
    while heap:
        d, _, st = heapq.heappop(heap)
        if dist.get(st) != d:
            continue
        kind, s, time, admitted = st
        if kind == "edge" and admitted and time in A[s]:
            c = d + Ad[raw["head"][s]][time]
            best = c if best is None else min(best, c)
        node = o if kind == "issue" else raw["head"][s]
        for j in out.get(node, []):
            if kind != "issue" and (s, j) in raw["forbidden"]:
                continue
            arr = time + raw["D"][j]
            if arr > H or time in B[j]:
                continue
            ns = ("edge", j, arr, True); nd = d + E[j][time]
            if nd < dist.get(ns, INF):
                dist[ns] = nd; heapq.heappush(heap, (nd, k, ns)); k += 1
        if raw["waitable"][node] and time + 1 <= H and time not in Wb[node]:
            ns = (kind, s, time + 1, False); nd = d + Wd[node][time]
            if nd < dist.get(ns, INF):
                dist[ns] = nd; heapq.heappush(heap, (nd, k, ns)); k += 1
    return best


def replay(raw, dense, o, t, w):
    """The witness is a legal journey and its dose (summed independently) equals the reported minimum."""
    E, Wd, Ad = dense
    V, arr, legs = w
    S = lambda x: iv.to_set(iv.normalize(x))  # noqa: E731
    assert t not in S(raw["IB"].get(o, []))
    if not legs:
        assert arr == t and t in S(raw["AN"].get(o, [])) and Ad[o][t] == V
        return
    node, inc, now, admitted, dose = o, None, t, False, 0
    for kind, x, a, b in legs:
        assert a == now
        if kind == "EDGE":
            assert raw["tail"][x] == node and (inc is None or (inc, x) not in raw["forbidden"])
            assert b == a + raw["D"][x] and a not in S(raw["B"][x]) and b <= raw["H"]
            dose += E[x][a]
            node, inc, now, admitted = raw["head"][x], x, b, True
        else:
            assert x == node and raw["waitable"][node] and a not in S(raw["W"][node]) and b == a + 1 <= raw["H"]
            dose += Wd[node][a]
            now, admitted = b, False
    assert admitted and now == arr and arr in S(raw["A"][inc])
    assert dose + Ad[node][arr] == V


def check_seed(seed, budget=None):
    raw, rnd = random_instance(seed)
    dense, costs = random_costs(raw, rnd)
    budget = rnd.choice([0, 3, 10, 30, 10 ** 6]) if budget is None else budget
    inst = Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()})
    fld = tdu_backward(inst, costs, budget)
    for o in range(raw["n_nodes"]):
        vals = issue_values(fld, o)
        for t in range(raw["H"] + 1):
            m = oracle_min_dose(raw, dense, o, t)
            want = m if (m is not None and m <= budget) else INF
            assert int(vals[t]) == want, (seed, o, t, int(vals[t]), m, budget)
            if want < INF:
                replay(raw, dense, o, t, witness_tdu(fld, o, t, values=vals))


def test_tdu_field_equals_oracle_dense_seeds():
    for seed in range(1200):
        check_seed(seed)


def test_tdu_field_large_budget_and_larger_networks():
    for seed in range(5000, 5150):
        check_seed(seed, budget=10 ** 6)


def test_zero_dose_equals_f31_field():
    """With every dose 0 the TDU field's feasible departures are exactly F-3.1's issue sets."""
    for seed in range(800):
        raw, rnd = random_instance(seed)
        _, costs = random_costs(raw, rnd, zero=True)
        inst = Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()})
        fld = tdu_backward(inst, costs, 0)
        ref = backward(Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()}))
        for o in range(raw["n_nodes"]):
            assert feasible_set(issue_values(fld, o), 0) == issue_set(ref, o), (seed, o)


def test_budget_monotone():
    """A larger budget never removes a feasible departure."""
    for seed in range(300):
        raw, rnd = random_instance(seed)
        _, costs = random_costs(raw, rnd)
        inst = Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()})
        lo, hi = tdu_backward(inst, costs, 5), tdu_backward(inst, costs, 25)
        for o in range(raw["n_nodes"]):
            a, b = feasible_set(issue_values(lo, o), 5), feasible_set(issue_values(hi, o), 25)
            assert not iv.subtract_all(a, b), (seed, o)
