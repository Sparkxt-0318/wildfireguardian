"""Property test: backward interval field == exhaustive forward oracle, at every departure second, on random small
networks with non-waitable nodes, forbidden turns, cycles, blocked edges/waits/issue points, opening windows and
dwell-blocked acceptance."""
from __future__ import annotations

import random

from hypothesis import HealthCheck, given, settings, strategies as st

from deadline_field import intervals as iv
from deadline_field.bruteforce import Oracle
from deadline_field.core import Instance, backward, issue_set, witness


def random_instance(seed: int, *, max_nodes=7, H=None):
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
    A = [[] for _ in range(m)]
    for j in range(m):
        if head[j] in dests:
            # opening window [open, close - dwell] with dwell-blocked sub-intervals removed
            dwell = rnd.randint(0, 4)
            op = rnd.randint(0, H // 2); cl = rnd.randint(op, H + 2)
            hi_ = min(cl, H) - dwell
            base = [(op, hi_)] if op <= hi_ else []
            block = rand_ivs(1)
            A[j] = iv.subtract_all(iv.normalize(base), iv.normalize(block))
    origins = list(range(n))
    IB = {o: (rand_ivs(1) if rnd.random() < 0.3 else []) for o in origins}
    raw = dict(H=H, n_nodes=n, tail=tail, head=head, D=D, waitable=waitable, forbidden=forbidden,
               B=B, W=W, A=A, IB=IB)
    return raw


def check_seed(seed: int):
    raw = random_instance(seed)
    inst = Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()})
    fld = backward(inst)
    orc = Oracle(raw)
    for o in range(raw["n_nodes"]):
        S = iv.to_set(issue_set(fld, o))
        for t in range(0, raw["H"] + 1):
            ea = orc.earliest(o, t)
            assert (t in S) == (ea is not None), (seed, o, t, ea)
            w = witness(fld, o, t)
            if ea is None:
                assert w is None
            else:
                assert w is not None and w[0] == ea, (seed, o, t, ea, w)
                replay_witness(raw, o, t, w)


def replay_witness(raw, o, t, w):
    """The witness is a legal journey under the raw rules (independent of the field)."""
    arr, legs = w
    B = [iv.to_set(iv.normalize(b)) for b in raw["B"]]
    W = [iv.to_set(iv.normalize(x)) for x in raw["W"]]
    A = [iv.to_set(iv.normalize(x)) for x in raw["A"]]
    assert t not in iv.to_set(iv.normalize(raw["IB"].get(o, [])))
    node, inc, now, admitted = o, None, t, False
    for kind, x, a, b in legs:
        assert a == now
        if kind == "EDGE":
            assert raw["tail"][x] == node and (inc is None or (inc, x) not in raw["forbidden"])
            assert b == a + raw["D"][x] and a not in B[x] and b <= raw["H"]
            node, inc, now, admitted = raw["head"][x], x, b, True
        else:
            assert x == node and raw["waitable"][node] and a not in W[node] and b == a + 1 <= raw["H"]
            now, admitted = b, False
    assert admitted and inc is not None and now == arr and arr in A[inc]


@settings(max_examples=3000, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(min_value=0, max_value=10**9))
def test_field_equals_oracle(seed):
    check_seed(seed)


def test_dense_seeds():
    for seed in range(1500):
        check_seed(seed)


def test_fixed_point_certificate_and_mutation():
    """check_fixed_point accepts every computed field and rejects a field with one second added or removed."""
    from deadline_field.core import check_fixed_point
    rejected = 0
    for seed in range(400):
        raw = random_instance(seed)
        inst = Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()})
        fld = backward(inst)
        check_fixed_point(fld)
        rnd = random.Random(seed)
        s = rnd.randrange(len(inst.tail))
        t = rnd.randint(0, inst.H)
        S = iv.to_set(fld.R[s]) ^ {t}           # flip one second
        fld.R[s] = iv.from_set(S)
        fld.G[s] = iv.normalize(fld.R[s] + inst.A[s])
        try:
            check_fixed_point(fld)
        except AssertionError:
            rejected += 1
    # flipping a second must always break the unique fixed point
    assert rejected == 400


def test_export_cert_roundtrip():
    """Exported certificate re-loads into a field that passes the closure check."""
    from deadline_field.core import Field, check_fixed_point
    from deadline_field.export import export_cert
    for seed in range(50):
        raw = random_instance(seed)
        inst = Instance(**{k: (list(v) if isinstance(v, list) else v) for k, v in raw.items()})
        fld = backward(inst)
        cert, ci = export_cert(fld, origins=range(inst.n_nodes))
        R = [[] for _ in inst.tail]
        for k, v in cert["states"].items():
            if not k.startswith("issue:"):
                R[int(k)] = [tuple(p) for p in v["R"]]
        G = [iv.normalize(R[j] + inst.A[j]) for j in range(len(R))]
        check_fixed_point(Field(inst, R, G, {}))
        for o in range(inst.n_nodes):
            assert [tuple(p) for p in cert["states"]["issue:%d" % o]["R"]] == __import__("deadline_field.core", fromlist=["x"]).issue_core(fld, o)
