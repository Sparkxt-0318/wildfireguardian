"""N1 (LAYOUT.md section 6): the 20 V1 missions under the four field arms that need a re-run.

For each mission (graph, packet, origin, destination spec, departure, window) of the frozen try02 inputs:

  full         cert_heat masks AND dose <= budget (kcf_heat.tdu_field, shelter stay counted, q0 = 1.42), budgets 92/105/290
  dose_off     cert_heat masks only                                   (row 5)
  heat_off     cert masks (no heat closure) AND dose <= budget          (row 4)
  persistence  full, with the packet reduced to fire already burning     (row 2; PacketModel present_only=True)
  contact      cert masks only (no heat, no dose): reproduces P1's verdicts (sanity, not a row)

Per mission and arm: feasible departure set (integer-second intervals), the verdict at the mission's own departure,
and the leave-by = latest feasible second (V1 definition, LAYOUT section 4). Timings are per packet.

    python run_v1.py --data-root DATA/routing --out runs/v1.json [--only REGION]
"""
import argparse
import json
import platform
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KH = ROOT / "research" / "kcf-heat"
sys.path.insert(0, str(KH))
from kcf_heat.closure import HeatPacketModel, HeatRule, iv  # noqa: E402  (puts F-3.1 on sys.path)
from kcf_heat.dose import Q0_KW_M2, DoseModel  # noqa: E402
from kcf_heat.tdu_field import ModelCosts, feasible_set, issue_core_values, issue_values, tdu_backward  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402

BUDGETS = (92.0, 105.0, 290.0)


def missions(data_root: Path, only=None):
    out = defaultdict(list)
    for p in sorted((data_root / "latest_inputs_try02" / "requests").glob("*/*.json")):
        region = p.parent.name
        if only and region != only:
            continue
        stamp = p.stem.split("_")[0]
        d = json.loads(p.read_text())
        assert d["incoming_edge"] is None and len(d["destinations"]) == 1 and d["destinations"][0]["open_intervals"].__len__() == 1
        dd = d["destinations"][0]
        out[(region, stamp)].append({"id": region + "/" + p.stem, "origin": d["position"]["node"], "departure": int(d["departure"]),
                                     "dest": dd["node"], "dwell": int(dd["dwell"]), "window": list(dd["open_intervals"][0]),
                                     "horizon": float(d["horizon"])})
    return out


def leave_by(feas):
    return feas[-1][1] if feas else None


def run_packet(data_root, region, stamp, ms, rule):
    rec = {"region": region, "packet": stamp, "missions": {}, "timing_s": {}, "arms": {}}
    t_all = time.perf_counter()
    graph = data_root / "graphs" / region / "graph.json"
    packet = data_root / "latest_inputs_try02" / "packets" / region / stamp
    for arm in ("full_models", "persistence"):
        t0 = time.perf_counter()
        pm = HeatPacketModel(graph, packet, heat=rule, present_only=(arm == "persistence"))
        dm = DoseModel(pm, rule, q0=Q0_KW_M2)
        bq = {b: dm.quanta(b) for b in BUDGETS}
        bmax = max(bq.values())
        rec["timing_s"][arm + ":prepare"] = time.perf_counter() - t0
        rec["arms"][arm] = {"burning_cells": len(pm.burning), "members": pm.pk.S, "H": pm.H}
        tf = {"contact": 0.0, "dose_off": 0.0, "full": 0.0, "heat_off": 0.0}
        for m in ms:
            spec = [{"node": m["dest"], "dwell": m["dwell"], "window": m["window"]}]
            oi = pm.nidx[m["origin"]]
            costs = ModelCosts(dm, {pm.nidx[m["dest"]]: m["dwell"]})
            res = {}
            t = time.perf_counter()
            res["contact"] = issue_set(backward(pm.instance("cert", spec, [m["origin"]])), oi)
            tf["contact"] += time.perf_counter() - t
            t = time.perf_counter()
            inst_h = pm.instance("cert_heat", spec, [m["origin"]])
            res["dose_off"] = issue_set(backward(inst_h), oi)
            tf["dose_off"] += time.perf_counter() - t
            t = time.perf_counter()
            fld = tdu_backward(inst_h, costs, bmax)
            vals = issue_values(fld, oi, issue_core_values(fld, oi))
            for b in BUDGETS:
                res["full@%g" % b] = feasible_set(vals, bq[b])
            tf["full"] += time.perf_counter() - t
            t = time.perf_counter()
            inst_c = pm.instance("cert", spec, [m["origin"]])
            fld = tdu_backward(inst_c, costs, bmax)
            vals = issue_values(fld, oi, issue_core_values(fld, oi))
            for b in BUDGETS:
                res["heat_off@%g" % b] = feasible_set(vals, bq[b])
            tf["heat_off"] += time.perf_counter() - t
            for k in sorted(res):
                if k.startswith("full@") and iv.subtract_all(res[k], res["dose_off"]):
                    raise SystemExit("subset violated: " + k + " " + m["id"])
            dep = m["departure"]
            out = {}
            for k, feas in res.items():
                out[k] = {"feasible_at_departure": bool(iv.contains(feas, dep)), "leave_by": leave_by(feas),
                          "n_intervals": len(feas), "set": [list(map(int, x)) for x in feas]}
            rec["missions"].setdefault(m["id"], {"departure": dep, "origin": m["origin"], "dest": m["dest"],
                                                 "window": m["window"], "arms": {}})["arms"][arm] = out
        for k, v in tf.items():
            rec["timing_s"][arm + ":field:" + k] = v
        del pm, dm
    rec["timing_s"]["packet_total"] = time.perf_counter() - t_all
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only")
    a = ap.parse_args()
    rule = HeatRule()
    out = {"schema": "kcf-ablation.v1/1", "host": {"platform": platform.platform(), "python": platform.python_version()},
           "heat_rule": rule.describe(), "budgets_tdu": list(BUDGETS), "q0": Q0_KW_M2, "packets": []}
    t0 = time.perf_counter()
    for (region, stamp), ms in missions(a.data_root, a.only).items():
        r = run_packet(a.data_root, region, stamp, ms, rule)
        out["packets"].append(r)
        print(region, stamp, round(r["timing_s"]["packet_total"], 1), "s", flush=True)
    out["wall_s"] = time.perf_counter() - t0
    out["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0 / (1024.0 if sys.platform != "darwin" else 1024.0)
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
