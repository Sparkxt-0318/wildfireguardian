"""Equality tests E1, E2, E3 and E5 on one recorded cache (PROTOCOL.md 3). Untimed.

    python3 eq_real.py CACHE_NAME OUT_JSON

For every destination spec of the cache (all its jobs, as run_b.py groups them), the baseline field
(``core.backward``, unchanged) is compared with each fast variant:

E1  Feas(o) of every origin of the spec, as normalized interval lists (equal lists = equal sets, second by second).
E2  every state's R and G (variants without pruning: whole sets; with pruning: the baseline sets cut to
    [alpha_s, H]); and the windowed fixed-point certificate ``fastfield.check_fixed_point`` on the fast field.
E3  every job: verdict, arrival second and leg sequence of the witness, identical to the baseline's.
E5  pruned variants: three nodes that are not origins of the spec (seeded choice) must be refused, and the fallback
    (pruning off for them) must return the baseline Feas.
Also reports, per variant, how many states took the scalar path (the fast-path share).
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research" / "kcf-bench-mac"))
from common import DATA_ROOT, load_cache  # noqa: E402

sys.path.insert(0, str(ROOT / "research" / "harness-2026-11" / "F-3.1"))
sys.path.insert(0, str(HERE))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
import fastfield as ff  # noqa: E402

VARIANTS = [("scalar", True, False, True), ("prune", False, True, True), ("both", True, True, True),
            ("scalar_plain", True, False, False), ("both_plain", True, True, False)]


def clip(ivs, lo, H):
    return [(max(a, lo), min(b, H)) for a, b in ivs if b >= lo and a <= H]


def main():
    name, out = sys.argv[1], Path(sys.argv[2])
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    doc = load_cache(name)
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    pm = PacketModel(DATA_ROOT / "graphs" / region / "graph.json",
                     DATA_ROOT / "latest_inputs_try02" / "packets" / region / compact)
    by_spec = defaultdict(list)
    for key, job in sorted(doc["route_checks"].items()):
        q = job["request"]
        by_spec[(q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))].append(
            (key, q["start"]["node_id"], int(q["depart_offset_s"])))
    rng = random.Random("20261123:%s" % name)
    tally = {v[0]: Counter() for v in VARIANTS}
    kinds = {v[0]: Counter() for v in VARIANTS}
    fails = []
    for si, spec in enumerate(sorted(by_spec, key=str)):
        if only is not None and str(si) not in only:
            continue
        dnode, dwell, window = spec
        origins = sorted({s for _, s, _ in by_spec[spec]})
        oidx = [pm.nidx[o] for o in origins]
        inst = pm.instance("cert", [{"node": dnode, "dwell": dwell, "window": list(window)}], origins)
        ref = backward(inst)
        E, H = len(inst.tail), inst.H
        ref_feas = {o: issue_set(ref, o) for o in oidx}
        ref_w = {}
        for key, s, t in by_spec[spec]:
            o = pm.nidx[s]
            ref_w[key] = witness(ref, o, t) if iv.contains(ref_feas[o], t) else None
        non_sources = rng.sample([v for v in range(inst.n_nodes) if v not in set(oidx)], 3)
        for vname, sc, pr, wd in VARIANTS:
            T = tally[vname]
            try:
                f = ff.solve(inst, scalar=sc, prune_origins=oidx if pr else None, windows=wd)
                kinds[vname].update(f.stats["kinds"])
                T["specs"] += 1
                # E1
                for o in oidx:
                    T["E1_origin_sets"] += 1
                    T["E1_seconds_compared"] += H + 1
                    if ff.issue_set(f, o) != ref_feas[o]:
                        fails.append((vname, str(spec), "E1", o))
                # E2
                for s in range(E):
                    lo = f.lo[s]
                    wr = clip(ref.R[s], lo, H) if pr else ref.R[s]
                    wg = clip(ref.G[s], lo, H) if pr else ref.G[s]
                    T["E2_states"] += 1
                    if f.R[s] != wr or f.G[s] != wg:
                        fails.append((vname, str(spec), "E2", s))
                ff.check_fixed_point(f)
                T["E2_fixed_point_fields"] += 1
                # E3
                for key, s, t in by_spec[spec]:
                    o = pm.nidx[s]
                    w = ff.witness(f, o, t) if iv.contains(ff.issue_set(f, o), t) else None
                    T["E3_jobs"] += 1
                    if w != ref_w[key]:
                        fails.append((vname, str(spec), "E3", key))
                    elif w is not None:
                        T["E3_routes"] += 1
                # E5
                if pr:
                    for v in non_sources:
                        T["E5_guard_checks"] += 1
                        try:
                            ff.issue_set(f, v)
                            fails.append((vname, str(spec), "E5_no_refusal", v))
                        except ValueError:
                            pass
                        if ff.issue_set(f, v, fallback=True) != issue_set(ref, v):
                            fails.append((vname, str(spec), "E5_fallback", v))
            except Exception as exc:
                fails.append((vname, str(spec), "crash", type(exc).__name__, str(exc)[:300]))
        print(name, si, len(by_spec), "failures so far", len(fails), flush=True)
    share = {}
    for v, k in kinds.items():
        st = k.get("states", 0)
        share[v] = {kk: (vv / st if st else None) for kk, vv in k.items() if kk != "states"}
    res = {"cache": name, "edges": len(pm.g.u), "specs": len(by_spec), "tally": {k: dict(v) for k, v in tally.items()},
           "state_kinds_summed_over_specs": {k: dict(v) for k, v in kinds.items()}, "state_kind_shares": share,
           "failures": len(fails), "failure_list": [repr(x) for x in fails[:200]]}
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps({"cache": name, "failures": len(fails), "share": share}, indent=1))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
