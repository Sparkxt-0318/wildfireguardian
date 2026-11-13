"""Multi-hour headline run on one (no-re-entry packet, reopening packet) pair of the same region/start/horizon/variant
(rule: MULTIHOUR_HEADLINE_RULE.md sections 1-2 and amendments (a)-(g), (1)-(3); committed before this runner).

SCENARIO, not what happened; roads limited to the recorded windows (graphs_interim). "Exact" means exact for the
time-dependent model's field, not for the fire.

Per packet pair:
  * no-re-entry (NR) fields per destination spec: CERT (router OR closed footprint), ROUTER-only, FREE (control);
    per (origin, destination) feasible set, and whether it is a prefix [0, x] (expected: always);
  * per origin: leave-by = latest feasible departure over its destinations, CERT and ROUTER;
  * every per-(origin, destination) NR CERT deadline witness is checked by the UNCHANGED full checker on BOTH packets
    (the NR packet and the as-built reopening packet), with the closed replay of each packet (acceptance 7, section 1);
  * amendment (d): reopening CERT field per destination; per (origin, destination, 30-min grid departure) count NR vs
    reopening verdicts that differ, feasible->infeasible and infeasible->feasible;
  * amendment (f): for every origin with no CERT route at t = 0, the ROAD-LIMITED split. The reachable set is an
    OVER-approximation of the nodes reachable from the origin at t = 0 in the NR CERT field (waiting allowed at every
    node, turn restrictions and wait-point blocks ignored; only edge-start blocks and the horizon apply). An origin is
    "fire-limited within the loaded graph" only if even this over-approximation contains no graph-boundary node
    (undirected degree 1, within one cell (375 m) of the recorded window edge); otherwise "possibly road-limited".
    Neither label claims that a real road out exists or does not exist.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import heapq
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
from deadline_field.core import backward, issue_set, witness_greedy  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402

STEP = 1800
ASSUMPTION = ("Assumes no fire outside mapped or forecast cells; no conservative unknown-support tier exists at "
              "multi-hour. The static final-footprint row shows whether the road crosses the eventual burn area, not "
              "when it was safe to leave.")
TRANSFORM_LABEL = {
    "no_reentry/1": "VARIANT (no_reentry/1), not the headline: no re-entry after the start; cells burned out before the "
                    "start stay open (NOREENTRY_RULE.md; MULTIHOUR_HEADLINE_RULE.md amendment 19:15 UTC)",
    "no_reentry/2": "HEADLINE arm (no_reentry/2): a cell that has burned is closed for the whole horizon, including cells "
                    "burned out before the start",
}
ROAD_LIMITED = "graph clipped to the recorded one-hour window; a road out may never have been loaded"


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def boundary_nodes(raw: dict, window: dict):
    """Undirected degree-1 nodes within one cell of the recorded (clipped) window edge."""
    nb = {}
    for e in raw["edges"]:
        if e["u"] != e["v"]:
            nb.setdefault(e["u"], set()).add(e["v"])
            nb.setdefault(e["v"], set()).add(e["u"])
    r = window["resolution"]
    x0, y0 = window["x0"], window["y0"]
    x1, y1 = x0 + window["width"] * r, y0 + window["height"] * r
    out = set()
    for n in raw["nodes"]:
        if len(nb.get(n["id"], ())) == 1:
            x, y = n["x"], n["y"]
            if min(x - x0, x1 - x, y - y0, y1 - y) <= r:
                out.add(n["id"])
    return out


def reach_over(inst, o: int, t: int):
    """Over-approximate forward reachable node set from node o at second t: earliest arrival, waiting allowed
    everywhere, turn restrictions and wait blocks ignored; an edge may start at s >= arrival if s is not in its
    blocked starts and s + D <= H."""
    H = inst.H
    best = {o: t}
    pq = [(t, o)]
    while pq:
        a, u = heapq.heappop(pq)
        if best.get(u) != a:
            continue
        for j in inst.out[u]:
            free = iv.subtract((a, H - inst.D[j]), inst.B[j]) if a <= H - inst.D[j] else []
            if not free:
                continue
            arr = free[0][0] + inst.D[j]
            v = inst.head[j]
            if arr < best.get(v, H + 1):
                best[v] = arr
                heapq.heappush(pq, (arr, v))
    return best


def codes_kind(codes):
    c = set(codes or [])
    budget = sorted(x for x in c if "PEAK" in x or "DOSE" in x)
    other = sorted(c - set(budget))
    return budget, other


def run(graph, nr_packet, re_packet, instance, window):
    t_all = time.perf_counter()
    tm = Counter()
    peak_l, dose_l = instance["limits"]["peak_kw_m2"], instance["limits"]["dose_kj_m2"]
    specs = {}
    for o in instance["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    # ---------------------------------------------------------------- no-re-entry packet
    pm = PacketModel(graph, nr_packet)
    H = pm.H
    window_iv = [0, H]
    offsets = list(range(0, H + 1, STEP))
    hz_nr = json.loads((Path(nr_packet) / "HAZARD.json").read_text())
    bs = Path(nr_packet) / "BUILD_SUMMARY.json"
    tr = ((json.loads(bs.read_text()).get("writer_identity") or {}).get("transform") if bs.exists() else None)
    ok_nr, pre_nr = pm.full_policy_reduces_to_contact(hz_nr, peak_limit=peak_l, dose_limit=dose_l, incurred=0.0)
    feas = {}
    nonprefix = Counter()
    witnesses = []
    for (dnode, dwell), origins in sorted(specs.items()):
        for var in ("cert", "router", "free"):
            t1 = time.perf_counter()
            fld = backward(pm.instance(var, [{"node": dnode, "dwell": dwell, "window": window_iv}], sorted(origins)))
            tm["nr_field_" + var] += time.perf_counter() - t1
            for o in origins:
                f = issue_set(fld, pm.nidx[o])
                feas[("nr_" + var, dnode, dwell, o)] = f
                if f and not (len(f) == 1 and f[0][0] == 0):
                    nonprefix[var] += 1
            if var == "cert":
                t2 = time.perf_counter()
                for o in sorted(origins):
                    f = feas[("nr_cert", dnode, dwell, o)]
                    if not f:
                        continue
                    ld = f[-1][1]
                    w = witness_greedy(fld, pm.nidx[o], ld)
                    legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), a, b) for k, x, a, b in w[1]]
                    dur = (w[0] + dwell) - ld
                    chk = full_check(pm, hz_nr, origin=o, legs=legs, dest=dnode, dwell=dwell, window=window_iv,
                                     departure=ld, incurred=0.0, peak=peak_l, dose=dose_l)
                    exact = bool(pre_nr["peak_cannot_bind_off_flame"] and pre_nr["max_exact_journey_duration_s"]
                                 is not None and dur <= pre_nr["max_exact_journey_duration_s"])
                    witnesses.append({"origin": o, "dest": dnode, "dwell": dwell, "deadline_s": ld, "arrival": w[0],
                                      "duration_s": dur, "exact_full_policy_nr": exact,
                                      "next_second_infeasible": not iv.contains(f, ld + 1), "legs": legs,
                                      "nr": chk})
                tm["nr_verify"] += time.perf_counter() - t2
            del fld
    # road-limited split, NR CERT field rules, t = 0
    bnodes = boundary_nodes(pm.raw, window)
    cert_inst = pm.instance("cert", [], sorted({o["entry_node"] for o in instance["origins"]}))
    no_route = {}
    for o in instance["origins"]:
        e = o["entry_node"]
        if any(iv.contains(feas[("nr_cert", d["node"], d["dwell_s"], e)], 0) for d in o["destinations"]):
            continue
        if iv.contains(cert_inst.IB[pm.nidx[e]], 0):
            no_route[o["origin_id"]] = {"entry_node": e, "split": "origin_point_in_flame_at_departure"}
            continue
        r = reach_over(cert_inst, pm.nidx[e], 0)
        hit = sorted(pm.node_ids[n] for n in r if pm.node_ids[n] in bnodes)
        no_route[o["origin_id"]] = {"entry_node": e, "reachable_nodes_over": len(r), "boundary_nodes_reached": len(hit),
                                    "split": "possibly_road_limited" if hit else "fire_limited_within_loaded_graph",
                                    "label": "ROAD-LIMITED: " + ROAD_LIMITED}
    del cert_inst, pm
    gc.collect()
    # ---------------------------------------------------------------- reopening (as-built) packet
    pm = PacketModel(graph, re_packet)
    if pm.H != H:
        raise SystemExit("horizon mismatch between packets")
    hz_re = json.loads((Path(re_packet) / "HAZARD.json").read_text())
    for (dnode, dwell), origins in sorted(specs.items()):
        t1 = time.perf_counter()
        fld = backward(pm.instance("cert", [{"node": dnode, "dwell": dwell, "window": window_iv}], sorted(origins)))
        tm["re_field_cert"] += time.perf_counter() - t1
        for o in origins:
            feas[("re_cert", dnode, dwell, o)] = issue_set(fld, pm.nidx[o])
        del fld
    t2 = time.perf_counter()
    for w in witnesses:
        w["reopening"] = full_check(pm, hz_re, origin=w["origin"], legs=w["legs"], dest=w["dest"], dwell=w["dwell"],
                                    window=window_iv, departure=w["deadline_s"], incurred=0.0, peak=peak_l,
                                    dose=dose_l)
        del w["legs"]
    tm["re_verify"] += time.perf_counter() - t2
    # ---------------------------------------------------------------- (d) verdict differences on the 30-min grid
    dd = Counter()
    for (dnode, dwell), origins in specs.items():
        for o in origins:
            a, b = feas[("nr_cert", dnode, dwell, o)], feas[("re_cert", dnode, dwell, o)]
            for t in offsets:
                x, y = iv.contains(a, t), iv.contains(b, t)
                dd["units"] += 1
                if x and not y:
                    dd["noreentry_feasible_clearing_infeasible"] += 1
                elif y and not x:
                    dd["noreentry_infeasible_clearing_feasible"] += 1
    # ---------------------------------------------------------------- (g) acceptance 7
    acc = Counter()
    for w in witnesses:
        bn, on = codes_kind(w["nr"]["codes"])
        br, orr = codes_kind(w["reopening"]["codes"])
        acc["requests"] += 1
        if bn != br:
            if not bn and br:
                acc["budget_codes_pass_on_noreentry_fail_on_reopening"] += 1
            elif bn and not br:
                acc["budget_codes_fail_on_noreentry_pass_on_reopening"] += 1
            else:
                acc["budget_codes_differ_both_failing"] += 1
        if on != orr:
            acc["non_budget_codes_differ (flame contact etc.)"] += 1
        if w["nr"]["closed_and_router_replay_clear"] != w["reopening"]["closed_and_router_replay_clear"]:
            acc["closed_replay_differs"] += 1
    wc = Counter()
    for w in witnesses:
        for k in ("nr", "reopening"):
            c = w[k]
            wc["%s:%s" % (k, "PASS" if (c["full_policy_ok"] and c["closed_and_router_replay_clear"])
                          else "FAIL:" + ",".join(c["codes"]))] += 1
        wc["exact_full_policy_nr:%s" % w["exact_full_policy_nr"]] += 1
        wc["next_second_infeasible:%s" % w["next_second_infeasible"]] += 1
    # ---------------------------------------------------------------- per origin
    origins_out = {}
    for o in instance["origins"]:
        e = o["entry_node"]
        row = {"entry_node": e, "type": o.get("origin_type")}
        for var in ("nr_cert", "nr_router", "nr_free", "re_cert"):
            u = iv.normalize([p for d in o["destinations"] for p in feas[(var, d["node"], d["dwell_s"], e)]])
            row["leave_by_" + var] = u[-1][1] if u and u[0][0] == 0 else None
            row["set_" + var] = u
        # horizon-censored: the fire never moves the leave-by inside the horizon (equals the fire-free control)
        row["censored_at_horizon"] = row["leave_by_nr_cert"] is not None and row["leave_by_nr_cert"] == row["leave_by_nr_free"]
        if o["origin_id"] in no_route:
            row["no_route"] = no_route[o["origin_id"]]
        origins_out[o["origin_id"]] = row
    split = Counter(v["split"] for v in no_route.values())
    return {"schema": "wfg.f31.headline/1", "H": H, "transform": tr, "label": "SCENARIO (F-DYN), not what happened; "
            "roads limited to the recorded windows; exact = exact for the time-dependent model's field, not for the fire; "
            + TRANSFORM_LABEL.get(tr, "UNKNOWN TRANSFORM %r: not reportable" % tr)
            + "; no re-entry contact field; witness checked against the as-built packet",
            "assumption": ASSUMPTION, "fields": "CERT = router OR closed footprint; ROUTER = router rule only; "
            "refusal-grade statements only from ROUTER", "precondition_noreentry": pre_nr,
            "precondition_noreentry_ok": ok_nr, "destinations": len(specs), "origins": len(origins_out),
            "nonprefix_feasible_sets": dict(nonprefix), "witness_checks": dict(wc), "acceptance7": dict(acc),
            "verdict_diff_noreentry_vs_clearing": dict(dd), "no_route_split": dict(split),
            "boundary_nodes": len(bnodes), "timing_s": {**dict(tm), "total": time.perf_counter() - t_all},
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
            "origins_detail": origins_out, "witnesses": witnesses}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--window-graph", type=Path, required=True, help="the recorded (clipped) graph: its grid = window")
    ap.add_argument("--nr-packet", type=Path, required=True)
    ap.add_argument("--re-packet", type=Path, required=True)
    ap.add_argument("--instance-json", type=Path, required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--horizon-s", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = json.loads(a.instance_json.read_text())
    inst = next((i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == a.horizon_s
                 and i["start_tag"] == a.start), None)
    if inst is None:
        raise SystemExit("no INSTANCE entry for region %s, start %s, horizon %s s" % (a.region, a.start, a.horizon_s))
    window = json.loads(a.window_graph.read_text())["grid"]
    out = run(a.graph, a.nr_packet, a.re_packet, inst, window)
    out["instance_entry"] = {"region": inst["region"], "start_tag": inst["start_tag"], "horizon_s": inst["horizon_s"]}
    out["window"] = window
    out["packets"] = {k: {"path": str(p), "HAZARD_sha256": sha(p / "HAZARD.json")}
                      for k, p in (("noreentry", a.nr_packet), ("reopening", a.re_packet))}
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("nonprefix_feasible_sets", "witness_checks", "acceptance7",
                                           "verdict_diff_noreentry_vs_clearing", "no_route_split", "timing_s")}))


if __name__ == "__main__":
    main()
