"""Return trips (rule: RETURN_TRIP_RULE.md, committed first). One F-DYN packet per run.

Outbound at t = 0 to the own destination with the earliest arrival (exact witness); return from that destination to
the place's entry node departing at arrival + dwell + delta. Contact field, cert rule. SCENARIO, not what happened.
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

DELTAS = (30 * 60, 60 * 60, 120 * 60)
CAP = 2 * 1024 ** 3


def _vmsize():
    for line in open("/proc/self/status"):
        if line.startswith("VmSize:"):
            return int(line.split()[1]) * 1024
    return 0


def run(graph, packet, instance):
    t0 = time.perf_counter()
    pm = PacketModel(graph, packet)
    H = pm.H
    dests = sorted({(d["node"], d["dwell_s"]) for o in instance["origins"] for d in o["destinations"]})
    entries = sorted({o["entry_node"] for o in instance["origins"]})
    # one destination field at a time (memory): earliest outbound arrival per (origin, own destination)
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (_vmsize() + CAP, hard))
    best, nc = {}, set()
    by_dest = {}
    for o in instance["origins"]:
        for d in o["destinations"]:
            by_dest.setdefault((d["node"], d["dwell_s"]), []).append(o)
    for (dn, dw), os_ in sorted(by_dest.items()):
        fld = backward(pm.instance("cert", [{"node": dn, "dwell": dw, "window": [0, H]}], entries))
        for o in sorted(os_, key=lambda o: o["origin_id"]):
            e = o["entry_node"]
            if not iv.contains(issue_set(fld, pm.nidx[e]), 0):
                continue
            try:
                w = witness(fld, pm.nidx[e], 0)
            except MemoryError:
                nc.add(o["origin_id"])
                continue
            if w is not None:
                cand = (w[0], dn, dw)
                cur = best.get(o["origin_id"])
                if cur is None or cand < cur:     # earliest arrival; ties -> lowest node id
                    best[o["origin_id"]] = cand
        del fld
    out_rows, need_return = {}, {}
    for o in instance["origins"]:
        e, oid = o["entry_node"], o["origin_id"]
        b = best.get(oid)
        r = {"entry_node": e, "outbound_checked": b is not None or oid in nc,
             "outbound_arrival_not_computed": b is None and oid in nc}
        if b:
            r.update(outbound_dest=b[1], arrival=b[0], dwell=b[2])
            need_return.setdefault(e, set()).add(b[1])
        out_rows[oid] = r
    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    t_out = time.perf_counter() - t0
    ret = {}
    for e, srcs in sorted(need_return.items()):
        fld = backward(pm.instance("cert", [{"node": e, "dwell": 0, "window": [0, H]}], sorted(srcs)))
        for s in srcs:
            ret[(e, s)] = issue_set(fld, pm.nidx[s])
    res = {}
    for dl in DELTAS:
        cnt = Counter()
        for oid, r in out_rows.items():
            if not r["outbound_checked"]:
                cnt["outbound_not_checked"] += 1
                continue
            if r["outbound_arrival_not_computed"]:
                cnt["outbound_arrival_not_computed"] += 1
                continue
            t = r["arrival"] + r["dwell"] + dl
            if t > H:
                c = "beyond_horizon"
            else:
                c = "return_checked" if iv.contains(ret[(r["entry_node"], r["outbound_dest"])], t) else "return_not_checked"
            cnt[c] += 1
            r.setdefault("return", {})[str(dl // 60)] = {"depart": t, "class": c}
        res[str(dl // 60)] = dict(cnt)
    return {"schema": "wfg.f31.return/1", "packet": str(packet), "H": H,
            "label": "model statement on a SCENARIO (F-DYN), not what happened; contact field",
            "counts": res, "origins": out_rows,
            "timing_s": {"outbound": t_out, "total": time.perf_counter() - t0},
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
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.summary_from:
        rows = []
        for f in a.summary_from:
            d = json.loads(f.read_text())
            e = d.get("manifest_entry", {})
            rows.append({"packet": "%s %s h%s %s" % (e.get("region"), e.get("start"), e.get("horizon_h"), e.get("variant")),
                         "soundness": e.get("soundness"), "counts_by_delay_min": d["counts"],
                         "return_not_checked": {dl: sorted(o for o, r in d["origins"].items()
                                                           if r.get("return", {}).get(dl, {}).get("class") == "return_not_checked")
                                                for dl in d["counts"]}})
        a.out.write_text(json.dumps({"what": "return trips (RETURN_TRIP_RULE.md): outbound at the start checked, return "
                                             "after arrival + dwell + delay; model statements on scenarios",
                                     "packets": rows}, indent=1))
        return
    doc = json.loads(a.instance_json.read_text())
    cand = [i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == a.horizon_s]
    inst = next((i for i in cand if i["start_tag"] == a.start), cand[0])
    out = run(a.graph, a.packet, inst)
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out["counts"]), json.dumps(out["timing_s"]))


if __name__ == "__main__":
    main()
