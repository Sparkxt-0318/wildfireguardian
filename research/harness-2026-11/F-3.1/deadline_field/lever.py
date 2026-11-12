"""Timing lever vs destination lever (rule: LEVER_RULE.md, committed first). One F-DYN packet per run.

Cert contact field per destination of the region; every origin read off every destination field.
Model statements on scenarios (SCENARIO, not what happened); free-flow only (no traffic in this model).
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402

T_REF = 150 * 60
SHIFTS = (30 * 60, 60 * 60, 120 * 60)
CAP = 2 * 1024 ** 3


def _vmsize():
    for line in open("/proc/self/status"):
        if line.startswith("VmSize:"):
            return int(line.split()[1]) * 1024
    return 0


def classify(base, a, b):
    if base:
        return "checked_at_ref"
    return {(True, True): "both", (True, False): "A_only", (False, True): "B_only", (False, False): "neither"}[(a, b)]


def run(graph, packet, instance, *, arrivals=True):
    t0 = time.perf_counter()
    pm = PacketModel(graph, packet)
    H = pm.H
    dests = sorted({(d["node"], d["dwell_s"]) for o in instance["origins"] for d in o["destinations"]})
    entries = sorted({o["entry_node"] for o in instance["origins"]})
    feas = {}
    for dn, dw in dests:     # keep only the issue sets (memory); a field is rebuilt only if an arrival is needed
        fld = backward(pm.instance("cert", [{"node": dn, "dwell": dw, "window": [0, H]}], entries))
        for e in entries:
            feas[(dn, dw, e)] = issue_set(fld, pm.nidx[e])
        del fld
    t_field = time.perf_counter() - t0
    _fc = {}

    def field(k):
        if k not in _fc:
            _fc.clear()
            _fc[k] = backward(pm.instance("cert", [{"node": k[0], "dwell": k[1], "window": [0, H]}], entries))
        return _fc[k]
    if arrivals:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (_vmsize() + CAP, hard))

    def earliest(e, dset, t):
        best, nc = None, False
        for k in dset:
            if not iv.contains(feas[k + (e,)], t):
                continue
            try:
                w = witness(field(k), pm.nidx[e], t)
            except MemoryError:
                nc = True
                continue
            if w is not None and (best is None or w[0] < best):
                best = w[0]
        return best, nc

    def tab(t_ref, shifts, with_arrivals):
        out = {}
        for s in shifts:
            cnt, gains, rows = Counter(), [], {}
            for o in instance["origins"]:
                e = o["entry_node"]
                own = [(d["node"], d["dwell_s"]) for d in o["destinations"]]
                U_own = iv.normalize([p for k in own for p in feas[k + (e,)]])
                U_all = iv.normalize([p for k in dests for p in feas[k + (e,)]])
                base = iv.contains(U_own, t_ref)
                a = t_ref - s >= 0 and iv.contains(U_own, t_ref - s)
                b = iv.contains(U_all, t_ref)
                c = classify(base, a, b)
                cnt[c] += 1
                r = {"class": c}
                if c == "both" and with_arrivals:
                    arrA, ncA = earliest(e, own, t_ref - s)
                    arrB, ncB = earliest(e, dests, t_ref)
                    r.update(arrival_A=arrA, arrival_B=arrB)
                    if arrA is None or arrB is None:
                        cnt["arrival_not_computed"] += 1
                    else:
                        gains.append(arrB - arrA)
                        r["gain_B_minus_A_s"] = arrB - arrA
                rows[o["origin_id"]] = r
            gains.sort()
            out[str(s // 60)] = {"counts": dict(cnt), "rows": rows,
                                 "gain_B_minus_A_s": {"n": len(gains), "median": gains[len(gains) // 2] if gains else None,
                                                      "min": gains[0] if gains else None, "max": gains[-1] if gains else None}}
        return out

    primary = tab(T_REF, SHIFTS, arrivals)
    sens = {}
    for t in range(120 * 60, H + 1, 1800):
        res = tab(t, SHIFTS, False)
        sens[str(t)] = {k: v["counts"] for k, v in res.items()}
    return {"schema": "wfg.f31.lever/1", "packet": str(packet), "H": H, "t_ref_s": T_REF,
            "label": "model statement on a SCENARIO (F-DYN), not what happened; free-flow only (no traffic modelled)",
            "destinations": len(dests), "origins": len(instance["origins"]), "primary": primary,
            "sensitivity_all_grid_departures_ge_120min": sens,
            "timing_s": {"fields": t_field, "total": time.perf_counter() - t0},
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-from", nargs="+", type=Path)
    ap.add_argument("--graph", type=Path)
    ap.add_argument("--packet", type=Path)
    ap.add_argument("--instance-json", type=Path)
    ap.add_argument("--region")
    ap.add_argument("--start")
    ap.add_argument("--horizon-s", type=int)
    ap.add_argument("--no-arrivals", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.summary_from:
        rows = []
        for f in a.summary_from:
            d = json.loads(f.read_text())
            e = d.get("manifest_entry", {})
            rows.append({"packet": "%s %s h%s %s" % (e.get("region"), e.get("start"), e.get("horizon_h"), e.get("variant")),
                         "soundness": e.get("soundness"),
                         "primary_t_ref_150min": {s: {"counts": v["counts"], "gain_B_minus_A_s": v["gain_B_minus_A_s"]}
                                                  for s, v in d["primary"].items()},
                         "sensitivity_all_grid_departures_ge_120min": d["sensitivity_all_grid_departures_ge_120min"]})
        a.out.write_text(json.dumps({"what": "timing lever (A: depart 30/60/120 min earlier, same destinations) vs "
                                             "destination lever (B: same departure, any candidate destination); rule "
                                             "LEVER_RULE.md; model statements on scenarios; free-flow only",
                                     "packets": rows}, indent=1))
        return
    doc = json.loads(a.instance_json.read_text())
    cand = [i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == a.horizon_s]
    inst = next((i for i in cand if i["start_tag"] == a.start), None)
    if inst is None:
        raise SystemExit("no INSTANCE entry for region %s, start %s, horizon %s s" % (a.region, a.start, a.horizon_s))
    out = run(a.graph, a.packet, inst, arrivals=not a.no_arrivals)
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({s: v["counts"] for s, v in out["primary"].items()}), json.dumps(out["timing_s"]))


if __name__ == "__main__":
    main()
