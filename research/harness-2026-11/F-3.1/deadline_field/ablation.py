"""Forecast ablation at the 1-hour horizon (step 1; orchestrator, adopted from Iris).

Fields with the recorded c651 members ('c651') vs present fire only ('present': every forecast-drawn new ignition
removed; present fire and burned state kept). Rule variant 'cert' (router OR closed whole-road rule); contact field.

(a) Six planner packets: per (place, input time), exact (1 s) latest departure over the place's recorded candidate
    shelters, and the planner-grid deadline; deadline(c651) - deadline(present) and status changes.
(b) The 20 research missions on the 15 routing windows (data/routing/latest_inputs_try02/requests): latest departure
    and earliest arrival at the recorded departure under each. These missions carry small dose budgets (incurred dose),
    so the contact field is not the full policy for them; each witness is run through the unchanged full checker and
    its verdict reported.
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

from tools.explain_deadlines.plans import CacheModel  # noqa: E402

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402

MODES = ("c651", "present")


def planner(cache_path: Path, data_root: Path):
    doc = json.loads(cache_path.read_text())
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    gp = data_root / "graphs" / region / "graph.json"
    pd = data_root / "latest_inputs_try02" / "packets" / region / compact
    model = CacheModel(doc)
    pms = {m: PacketModel(gp, pd, present_only=(m == "present")) for m in MODES}
    origin_specs = defaultdict(set)
    origin_offsets = {}
    for oid, plan in model.plans.items():
        origin_offsets[oid] = sorted({c.offset_s for c in plan.sweep})
        for c in plan.sweep:
            for a in c.attempts:
                job = model.job(a.job_id)
                if job:
                    q = job["request"]
                    origin_specs[oid].add((q["start"]["node_id"], q["destination"]["node_id"], q["dwell_s"],
                                           tuple(q["destination_window"])))
    specs = defaultdict(set)
    for oid, ss in origin_specs.items():
        for st, d, dw, w in ss:
            specs[(d, dw, w)].add(st)
    feas = {}
    t = Counter()
    for m, pm in pms.items():
        t0 = time.perf_counter()
        for (d, dw, w), starts in sorted(specs.items(), key=str):
            fld = backward(pm.instance("cert", [{"node": d, "dwell": dw, "window": list(w)}], sorted(starts)))
            for st in starts:
                feas[(m, d, dw, w, st)] = issue_set(fld, pm.nidx[st])
        t[m] = time.perf_counter() - t0
    rows = {}
    cnt = Counter()
    for oid, ss in origin_specs.items():
        r = {"origin_id": oid}
        offs = origin_offsets[oid]
        for m in MODES:
            union = iv.normalize([p for (st, d, dw, w) in ss for p in feas[(m, d, dw, w, st)]])
            r["exact_" + m] = union[-1][1] if union else None
            g = [o for o in offs if iv.contains(union, o)]
            r["grid_" + m] = g[-1] if g else None
            r["status_" + m] = "checked" if union else "no_route"
        r["exact_diff_s"] = None if None in (r["exact_c651"], r["exact_present"]) else r["exact_c651"] - r["exact_present"]
        r["grid_diff_s"] = None if None in (r["grid_c651"], r["grid_present"]) else r["grid_c651"] - r["grid_present"]
        if r["status_c651"] != r["status_present"]:
            cnt["status_change:%s->%s(present->c651)" % (r["status_present"], r["status_c651"])] += 1
        elif r["exact_diff_s"] == 0:
            cnt["exact_equal"] += 1
        elif r["exact_diff_s"] is not None:
            cnt["exact_differs"] += 1
        else:
            cnt["both_no_route"] += 1
        if r["grid_diff_s"] not in (0, None):
            cnt["grid_differs"] += 1
        rows[oid] = r
    ign = {s: sum(1 for c, ph in pms["c651"].pk.phases[s].items() if ph[3] == "FUTURE") for s in range(pms["c651"].pk.S)}
    return {"cache_file": str(cache_path.relative_to(ROOT)), "new_ignitions_per_member": ign, "counts": dict(cnt),
            "timing_s": dict(t), "origins": rows}


def missions(data_root: Path):
    out = []
    for f in sorted((data_root / "latest_inputs_try02" / "requests").glob("*/*.json")):
        q = json.loads(f.read_text())
        region, tag = f.parent.name, f.stem
        compact = tag.split("_")[0]
        gp = data_root / "graphs" / region / "graph.json"
        pd = data_root / "latest_inputs_try02" / "packets" / region / compact
        hazard = json.loads((pd / "HAZARD.json").read_text())
        o = q["position"]["node"]
        d = q["destinations"][0]
        win = d["open_intervals"][0]
        dep = int(q["departure"])
        row = {"mission": "%s/%s" % (region, tag), "departure": dep}
        for m in MODES:
            pm = PacketModel(gp, pd, present_only=(m == "present"))
            inst = pm.instance("cert", [{"node": d["node"], "dwell": d["dwell"], "window": list(win)}], [o])
            fld = backward(inst)
            f_ = issue_set(fld, pm.nidx[o])
            w = witness(fld, pm.nidx[o], dep) if iv.contains(f_, dep) else None
            row["latest_" + m] = f_[-1][1] if f_ else None
            row["arrival_at_dep_" + m] = None if w is None else w[0]
            if w is not None:
                legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), a, b) for k, x, a, b in w[1]]
                inc = max(q["incurred"].values())
                dose = min(q["budgets"]["dose"].values())
                chk = full_check(pm, hazard, origin=o, legs=legs, dest=d["node"], dwell=d["dwell"], window=win,
                                 departure=dep, incurred=inc, peak=q["budgets"]["peak"], dose=dose)
                row["witness_full_check_" + m] = {k: chk[k] for k in ("full_policy_ok", "full_status", "codes", "max_dose")}
        out.append(row)
    return out


def summarize(res: dict) -> dict:
    """Committed summary (results/FORECAST_ABLATION_1h.json): per cache the ignition counts, the count block and
    every origin whose exact deadline or status differs; plus all missions. Present-only deadlines are contact-field
    counterfactuals (their witnesses are not checked against a present-only full policy)."""
    return {"what": "forecast ablation at 1 h: c651 members as recorded vs present fire only (cert contact field); diff = c651 - present",
            "planner": [{"cache_file": p["cache_file"], "new_ignitions_per_member": p["new_ignitions_per_member"],
                         "counts": p["counts"],
                         "differing": [r for r in p["origins"].values()
                                       if r["exact_diff_s"] not in (0, None) or r["status_c651"] != r["status_present"]]}
                        for p in res["planner"]],
            "missions": res.get("missions", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caches", nargs="*", type=Path)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "routing")
    ap.add_argument("--missions", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--summary-from", nargs=2, type=Path, metavar=("PLANNER_JSON", "MISSIONS_JSON"),
                    help="only write the committed summary from two earlier raw outputs")
    a = ap.parse_args()
    if a.summary_from:
        pl = json.loads(a.summary_from[0].read_text())
        mi = json.loads(a.summary_from[1].read_text())
        a.out.write_text(json.dumps(summarize({"planner": pl["planner"], "missions": mi.get("missions", [])}), indent=1, default=str))
        return
    res = {"planner": [planner(c.resolve(), a.data_root) for c in a.caches]}
    if a.missions:
        res["missions"] = missions(a.data_root)
    res["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    a.out.write_text(json.dumps(res, indent=1, default=str))
    for p in res["planner"]:
        print(p["cache_file"], p["new_ignitions_per_member"], json.dumps(p["counts"]), p["timing_s"])
    for m in res.get("missions", []):
        print(json.dumps({k: v for k, v in m.items() if not k.startswith("witness")}),
              {k: v["full_policy_ok"] for k, v in m.items() if k.startswith("witness")})


if __name__ == "__main__":
    main()
