"""Gate part 2 (PROTOCOL §2.1.2): exact issue sets, fast solver vs deadline_field.core, on 4 base jobs (all places)
and 40 seeded delayed instances; plus pruning check (pruned gains == unpruned fast gains, all places). -> gate2.json"""
import json, random, sys, time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import fastfield as FF, defend as DF
from deadline_field import core, intervals as iv


def core_sets(R, b, H, places):
    """Union over shelters of core.issue_set, as replay.run_one builds the instance."""
    RR = R.R
    close_s = {int(c): int(v) for c, v in enumerate(b) if v >= 0}
    inst = RR.instance(close_s, H)
    E = len(inst.tail)
    need = sorted({s for p in places for s in R.pl_sh[p]})
    out = {p: [] for p in places}
    for s in need:
        sn = int(R.sh_node[s])
        acc = RR.accept(close_s, sn, H)
        inst.A = [[] for _ in range(E)]
        for j in RR.inc_by_node.get(sn, []):
            inst.A[j] = list(acc)
        inst.AN = {}
        fld = core.backward(inst)
        for p in places:
            if s not in R.pl_sh[p]:
                continue
            on = int(R.pl_node[p])
            bo = close_s.get(RR.node_cell[on])
            inst.IB = {on: [(bo, H)] if bo is not None else []}
            out[p].extend(core.issue_set(fld, on))
    return {p: iv.normalize(v) for p, v in out.items()}


def fast_sets(R, b, H, places):
    lo, fields = DF.solve_all(R, b, H, shelters=sorted({s for p in places for s in R.pl_sh[p]}))
    vals = DF.place_values(R, b, lo, fields, places)
    return {p: ([(0, v[0])] if v[0] >= 0 else []) for p, v in vals.items()}


def setup(region, arm, hz, hour):
    R = DF.REG[region]; H = FF.HORIZONS[hz]; T = datetime(2025, 3, 25, hour, tzinfo=timezone.utc)
    d, f, info, cs, b = DF.base_state(R, arm, T, H)
    return R, H, T, d, f, b


def base_check(a):
    R, H, T, d, f, b = setup(*a)
    pl = list(range(len(R.places)))
    t = time.time(); cs = core_sets(R, b, H, pl); tc = time.time() - t
    fs = fast_sets(R, b, H, pl)
    bad = [R.places[p] for p in pl if cs[p] != fs[p]]
    return {"job": a, "places": len(pl), "mismatch": bad, "core_s": round(tc, 1),
            "nonempty": sum(1 for p in pl if cs[p]), "pieces_gt1": sum(1 for p in pl if len(cs[p]) > 1)}


def delayed_check(a):
    (region, arm, hz, hour, D, kind, seed) = a
    R, H, T, d, f, b = setup(region, arm, hz, hour)
    cands = [(k, cid, ch) for k, cid, meta, DD, ch in DF.candidate_changes(R, T, d, f, b, H) if DD == D and k == kind]
    rng = random.Random(seed)
    if not cands:
        return {"inst": a, "skipped": "no candidate of this kind"}
    k, cid, ch = rng.choice(cands)
    # pruned (production path) vs unpruned fast, all places
    lo, fields = DF.solve_all(R, b, H)
    base = DF.place_values(R, b, lo, fields)
    DF.prepare(R, b, lo, fields)
    pr = DF.evaluate(R, b, H, lo, fields, base, ch)
    b2 = b.copy()
    for c, v in ch.items():
        b2[c] = v
    lo2, f2 = DF.solve_all(R, b2, H)
    full = DF.place_values(R, b2, lo2, f2)
    unpr = {p: full[p][0] - base[p][0] for p in full if full[p][0] > base[p][0]}
    # core on: every gaining place + up to 6 seeded others
    others = [p for p in range(len(R.places)) if p not in unpr]
    rng.shuffle(others)
    pl = sorted(set(unpr) | set(others[:6]))
    t = time.time(); cs = core_sets(R, b2, H, pl); tc = time.time() - t
    fs = {p: ([(0, full[p][0])] if full[p][0] >= 0 else []) for p in pl}
    bad = [R.places[p] for p in pl if cs[p] != fs[p]]
    return {"inst": a, "candidate": cid, "cells_changed": len(ch), "gaining_places": len(unpr),
            "pruned_equals_unpruned": pr == unpr, "core_checked_places": len(pl), "mismatch": bad, "core_s": round(tc, 1)}


def main():
    rng = random.Random(20261118)
    base_jobs = [(r, "MEASURED", "8h", 10) for r in FF.REGIONS] + [(r, "WORST", "5h", 6) for r in FF.REGIONS]
    delayed = []
    for kind in ["ROAD"] * 20 + ["FRONT"] * 20:
        delayed.append((rng.choice(FF.REGIONS), rng.choice(FF.ARMS), rng.choice(list(FF.HORIZONS)), rng.randrange(3, 16),
                        rng.choice(DF.DELAYS), kind, rng.randrange(1 << 30)))
    out = {"base": [], "delayed": []}
    with ProcessPoolExecutor(4, initializer=DF.init, initargs=(FF.REGIONS,)) as ex:
        fb = [ex.submit(base_check, j) for j in base_jobs]
        fd = [ex.submit(delayed_check, j) for j in delayed]
        for x in fb:
            out["base"].append(x.result()); print(out["base"][-1], flush=True)
        for x in fd:
            out["delayed"].append(x.result()); print(out["delayed"][-1], flush=True)
    out["summary"] = {"base_mismatch_places": sum(len(x["mismatch"]) for x in out["base"]),
                      "delayed_instances": len([x for x in out["delayed"] if "skipped" not in x]),
                      "delayed_skipped": len([x for x in out["delayed"] if "skipped" in x]),
                      "delayed_mismatch_places": sum(len(x.get("mismatch", [])) for x in out["delayed"]),
                      "pruning_failures": sum(1 for x in out["delayed"] if x.get("pruned_equals_unpruned") is False),
                      "delayed_with_gain": sum(1 for x in out["delayed"] if x.get("gaining_places"))}
    Path("gate2.json").write_text(json.dumps(out, indent=1, default=str))
    print(out["summary"])


if __name__ == "__main__":
    main()
