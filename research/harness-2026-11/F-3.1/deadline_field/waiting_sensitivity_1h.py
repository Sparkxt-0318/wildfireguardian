"""Waiting-location sensitivity on the 1-h panel (rule: WAITING_SENSITIVITY_RULE.md, committed first).

Per planner cache: the optimistic (frozen packet) field under the supplied waiting rule (graph dead ends only) and
under the sensitivity arm (waiting allowed at every node; the full checker reads the same modified graph), CERT and
ROUTER. Per job: feasible at the recorded departure, both arms. Per origin: latest feasible departure over its
specs, both arms. Every job that becomes feasible only with waiting everywhere gets a witness checked by the unchanged
full checker on the modified graph. Any job feasible under the supplied rule but not with waiting everywhere is a
FAULT and is listed.
    python3 -m deadline_field.waiting_sensitivity_1h CACHE --out OUT
    python3 -m deadline_field.waiting_sensitivity_1h --summary-from OUT... --out SUMMARY
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness_greedy  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402

LABEL = "SENSITIVITY: waiting allowed at every node (not the supplied graph rule)"
SUPPLIED = "waiting is allowed only at graph dead-end nodes (as supplied in graph.json; rule undocumented)"


def run(cache_path: Path, data_root: Path):
    t0 = time.perf_counter()
    doc = json.loads(cache_path.read_text())
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    gp = data_root / "graphs" / region / "graph.json"
    pd = data_root / "latest_inputs_try02" / "packets" / region / compact
    jobs = []
    for key, job in sorted(doc["route_checks"].items()):
        q = job["request"]
        jobs.append({"job": key, "start": q["start"]["node_id"], "dest": q["destination"]["node_id"],
                     "dwell": q["dwell_s"], "window": tuple(q["destination_window"]), "offset": int(q["depart_offset_s"])})
    specs = defaultdict(set)
    for j in jobs:
        specs[(j["dest"], j["dwell"], j["window"])].add(j["start"])
    arms = {"supplied": PacketModel(gp, pd), "wait_all": PacketModel(gp, pd, waitable_all=True)}
    hazard = json.loads((pd / "HAZARD.json").read_text())
    feas, fields = {}, {}
    for arm, pm in arms.items():
        for var in ("cert", "router"):
            for spec in sorted(specs, key=str):
                fld = backward(pm.instance(var, [{"node": spec[0], "dwell": spec[1], "window": list(spec[2])}],
                                           sorted(specs[spec])))
                for o in specs[spec]:
                    feas[(arm, var, spec, o)] = issue_set(fld, pm.nidx[o])
                if arm == "wait_all" and var == "cert":
                    fields[spec] = fld          # kept for witnesses of flipped jobs
                else:
                    del fld
    trans, faults, flips = Counter(), [], []
    for j in jobs:
        spec = (j["dest"], j["dwell"], j["window"])
        for var in ("cert", "router"):
            a = iv.contains(feas[("supplied", var, spec, j["start"])], j["offset"])
            b = iv.contains(feas[("wait_all", var, spec, j["start"])], j["offset"])
            la, lb = ("feasible" if a else "no_route"), ("feasible" if b else "no_route")
            trans["%s|%s->%s" % (var, la, lb)] += 1
            if a and not b:
                faults.append({"job": j["job"], "field": var})
            if var == "cert" and b and not a:
                flips.append(j)
    pm = arms["wait_all"]
    wc = Counter()
    wrows = []
    for j in flips:
        spec = (j["dest"], j["dwell"], j["window"])
        w = witness_greedy(fields[spec], pm.nidx[j["start"]], j["offset"])
        legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), a, b) for k, x, a, b in w[1]]
        chk = full_check(pm, hazard, origin=j["start"], legs=legs, dest=j["dest"], dwell=j["dwell"], window=list(j["window"]),
                         departure=j["offset"], incurred=0.0)
        waits = sum(1 for k, *_ in legs if k == "WAIT")
        wc["PASS" if chk["full_policy_ok"] and chk["closed_and_router_replay_clear"] else "FAIL:" + ",".join(chk["codes"])] += 1
        wrows.append({"job": j["job"], "wait_legs": waits, **chk})
    del fields
    origins = defaultdict(set)
    for j in jobs:
        origins[j["start"]].add((j["dest"], j["dwell"], j["window"]))
    od = {}
    for o, sp in origins.items():
        d = {}
        for arm in arms:
            for var in ("cert", "router"):
                m = [feas[(arm, var, s, o)][-1][1] for s in sp if feas[(arm, var, s, o)]]
                d["%s_%s" % (arm, var)] = max(m) if m else None
        od[o] = d
    return {"label": LABEL, "supplied_rule": SUPPLIED, "cache_file": str(cache_path.relative_to(ROOT)),
            "waitable_nodes_supplied": sum(1 for n in arms["supplied"].raw["nodes"] if n.get("waitable")),
            "nodes": len(arms["supplied"].raw["nodes"]), "jobs": len(jobs), "transitions": dict(trans),
            "faults": faults, "flip_witness_checks": dict(wc), "flip_witnesses": wrows, "origin_deadlines": od,
            "wall_s": time.perf_counter() - t0,
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0}


def summarize(outs):
    tot = Counter()
    per = []
    for d in outs:
        sh = {"cert": [], "router": []}
        ch = Counter()
        for o, x in d["origin_deadlines"].items():
            for var in ("cert", "router"):
                a, b = x["supplied_" + var], x["wait_all_" + var]
                if a != b:
                    ch[var + ":changed"] += 1
                    if a is None:
                        ch[var + ":none->deadline"] += 1
                    elif b is None:
                        ch[var + ":deadline->none (FAULT)"] += 1
                    else:
                        sh[var].append(b - a)
        for v in sh.values():
            v.sort()
        row = {"cache": d["cache_file"], "jobs": d["jobs"], "transitions": d["transitions"], "faults": len(d["faults"]),
               "flip_witness_checks": d["flip_witness_checks"], "origins": len(d["origin_deadlines"]),
               "origin_deadline_changes": dict(ch),
               "origin_deadline_shift_s": {v: {"n": len(s), "median_upper": s[len(s) // 2] if s else None,
                                               "max": s[-1] if s else None} for v, s in sh.items()}}
        per.append(row)
        for k, v in d["transitions"].items():
            tot[k] += v
        tot["faults"] += len(d["faults"])
    return {"what": "waiting-location sensitivity, 1-h panel (WAITING_SENSITIVITY_RULE.md); optimistic field; " + LABEL,
            "supplied_rule": SUPPLIED, "totals": dict(tot), "caches": per}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cache", type=Path, nargs="?")
    ap.add_argument("--summary-from", nargs="+", type=Path)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "routing")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.summary_from:
        s = summarize([json.loads(f.read_text()) for f in a.summary_from])
        a.out.write_text(json.dumps(s, indent=1))
        print(json.dumps(s["totals"], indent=1))
        return
    out = run(a.cache.resolve(), a.data_root)
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("cache_file", "jobs", "transitions", "flip_witness_checks", "wall_s",
                                           "peak_rss_mib")}))
    if out["faults"]:
        print("FAULTS", len(out["faults"]))


if __name__ == "__main__":
    main()
