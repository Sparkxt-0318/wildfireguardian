"""Summarize reproduce.py outputs: attempt-level agreement, deadline agreement, exact-vs-grid deadlines, compute."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(d: dict) -> dict:
    att = Counter()
    mism = []
    rec_compute = 0.0
    n_jobs = 0
    for r in d["attempts"]:
        if r.get("job") is None:
            att["no_job"] += 1
            continue
        if "field" not in r:
            att["not_evaluated(limit_dests)"] += 1
            continue
        n_jobs += 1
        rec_compute += r.get("recorded_compute_s") or 0.0
        f = r["field"]
        rt, ce = f["router"], f["cert"]
        v = r["verdict"]
        raw = r.get("raw_status")
        if v == "checked_route":
            ok = rt["feasible"] and ce["feasible"] and rt["arrival"] == r["arrival"] and ce["arrival"] == r["arrival"]
            att["checked:" + ("match" if ok else "MISMATCH")] += 1
            if not ok:
                mism.append(r)
        elif v == "model_no_route":
            ok = (not rt["feasible"]) and (not ce["feasible"])
            att["no_route:" + ("match" if ok else "MISMATCH")] += 1
            if not ok:
                mism.append(r)
        else:
            if rt["issue_blocked"]:
                cls = "issue_blocked(router)"
            elif not rt["feasible"]:
                cls = "router_infeasible"
            elif ce["feasible"]:
                cls = "cert_feasible"
            else:
                cls = "router_feasible_cert_infeasible"
            att["unresolved[%s]:%s" % (raw, cls)] += 1
            if raw == "AT_ISSUE_FAILURE" and not rt["issue_blocked"]:
                mism.append(r)
                att["AT_ISSUE_not_issue_blocked:MISMATCH"] += 1
    jobs = Counter()
    jm = []
    for r in d.get("jobs", []):
        if "field" not in r:
            jobs["not_evaluated(limit_dests)"] += 1
            continue
        f = r["field"]
        rt, ce = f["router"], f["cert"]
        v = r["verdict"]
        tag = "recheck" if r.get("recheck_of") else "original"
        if v == "checked_route":
            ok = rt["feasible"] and ce["feasible"] and rt["arrival"] == r["arrival"] and ce["arrival"] == r["arrival"]
            jobs["checked:" + ("match" if ok else "MISMATCH")] += 1
            same = isinstance(r.get("recorded_legs"), list) and [tuple(x) for x in r["recorded_legs"]] == [tuple(x) for x in (ce["legs"] or [])]
            jobs["checked:identical_route_cert" if same else "checked:different_route_same_arrival_cert"] += ok
            if not ok:
                jm.append(r)
        elif v == "model_no_route":
            ok = (not rt["feasible"]) and (not ce["feasible"])
            jobs["no_route:" + ("match" if ok else "MISMATCH")] += 1
            if not ok:
                jm.append(r)
        else:
            if rt["issue_blocked"]:
                cls = "issue_blocked(router)"
            elif not rt["feasible"]:
                cls = "router_infeasible"
            elif ce["feasible"]:
                cls = "cert_feasible"
            else:
                cls = "router_feasible_cert_infeasible"
            jobs["unresolved[%s]:%s" % (r.get("raw_status"), cls)] += 1
        jobs["total"] += 1
    dl = Counter()
    exact_vs_grid = Counter()
    deadline_rows = []
    gain = []
    for oid, o in d["origins"].items():
        rec = o["recorded_deadline"]
        ex_u = o.get("field_deadline_exact_uncapped_cert")
        gr = o.get("field_deadline_grid_cert")
        if gr is not None and ex_u is not None:
            gain.append(ex_u - gr)
        for var in ("router", "cert"):
            g = o.get("field_deadline_grid_" + var)
            key = "equal" if g == rec else ("field_later" if (g is not None and (rec is None or g > rec)) else "field_earlier")
            dl[var + ":" + key] += 1
        ex, gr = o.get("field_deadline_exact_cert"), o.get("field_deadline_grid_cert")
        if gr is not None or ex is not None:
            exact_vs_grid["differs" if ex != gr else "same"] += 1
        deadline_rows.append({"origin": oid, "kind": o["kind"], "recorded": rec, **{k: v for k, v in o.items() if k.startswith("field_")}})
    # ---- Iris split: deadline classes against the fire-free control field (grid answers)
    cls = Counter()
    cls_match = Counter()
    holes = Counter()
    for oid, o in d["origins"].items():
        rec = o["recorded_deadline"]
        plan_last = max([r["offset"] for r in d["attempts"] if r["origin_id"] == oid], default=None)
        ce, fr = o.get("field_deadline_grid_cert"), o.get("field_deadline_grid_free")
        if rec is None and ce is None:
            c = "no_checked_departure"
        elif rec is not None and rec == plan_last and ce == plan_last:
            c = "censored_at_last_offset"
        elif ce == fr:
            c = "window_set(same_as_fire_free)"
        else:
            c = "fire_set(differs_from_fire_free)"
        cls[c] += 1
        cls_match[c + (":match" if (ce == rec and o.get("field_deadline_grid_router") == rec) else ":MISMATCH")] += 1
        holes["holes_cert" if o.get("holes_cert") else "no_holes_cert"] += 1
    # ---- attempt cells changed by fire (cert vs free) and their agreement
    fire_cells = Counter()
    for r in d.get("jobs", []):
        f = r.get("field")
        if not f or "free" not in f:
            continue
        if f["free"]["feasible"] != f["cert"]["feasible"] or (f["cert"]["feasible"] and f["free"]["arrival"] != f["cert"]["arrival"]):
            key = "fire_affected"
        else:
            key = "fire_free_identical"
        v = r["verdict"]
        ok = ((v == "checked_route" and f["cert"]["feasible"] and f["cert"]["arrival"] == r["arrival"]) or
              (v == "model_no_route" and not f["router"]["feasible"]))
        fire_cells[key + ":" + (v or "none") + (":match" if ok else (":unresolved_cell" if v not in ("checked_route", "model_no_route") else ":MISMATCH"))] += 1
    # ---- witness checks
    wc = Counter()
    for v in d.get("deadline_witness_checks", []):
        wc["deadline_witness:" + ("PASS" if v["full_policy_ok"] and v["closed_and_router_replay_clear"] else "FAIL")] += 1
        wc["deadline_next_second_infeasible:" + str(v["next_second_infeasible"])] += 1
    for r in d.get("jobs", []):
        fc = (r.get("field") or {}).get("cert", {}).get("full_check")
        if fc:
            wc["job_witness:" + ("PASS" if fc["full_policy_ok"] and fc["closed_and_router_replay_clear"] else "FAIL")] += 1
    t = d["timing_s"]
    ours = t["prepare_packet_model"] + sum(t["fields"].values()) + sum(t["issue_and_witness"].values())
    ours_cert_only = t["prepare_packet_model"] + t["fields"].get("cert", 0) + t["issue_and_witness"].get("cert", 0)
    return {"cache_file": d["cache_file"], "destination_specs": d["destination_specs"], "jobs": n_jobs,
            "attempts": dict(att), "jobs_all": dict(jobs), "job_mismatches": [{k: r.get(k) for k in ("job", "offset", "verdict", "raw_status", "arrival", "field")} for r in jm][:20], "deadlines": dict(dl), "deadline_classes": dict(cls), "deadline_class_match": dict(cls_match),
            "feasible_set_holes": dict(holes), "fire_cells": dict(fire_cells), "witness_checks": dict(wc),
            "piece_stats": d.get("piece_stats"), "peak_rss_mib": d.get("peak_rss_mib"), "timing_s": d["timing_s"], "exact_vs_grid_cert": dict(exact_vs_grid),
            "exact_uncapped_minus_grid_cert_s": {"n": len(gain), "n_positive": sum(g > 0 for g in gain),
                                                 "median": sorted(gain)[len(gain) // 2] if gain else None,
                                                 "max": max(gain) if gain else None},
            "recorded_compute_s_sum": rec_compute, "field_compute_s_both_variants": ours,
            "field_compute_s_cert_only": ours_cert_only, "precondition_ok": all(v["ok"] for v in d["precondition"].values()),
            "mismatches": [{k: r.get(k) for k in ("origin_id", "offset", "dest_id", "verdict", "raw_status", "arrival", "field")}
                           for r in mism][:20],
            "deadline_rows": deadline_rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    outs = [summarize(json.loads(p.read_text())) for p in a.runs]
    for s in outs:
        print(json.dumps({k: v for k, v in s.items() if k not in ("deadline_rows", "mismatches")}, indent=1))
        if s["mismatches"]:
            print("MISMATCHES:", json.dumps(s["mismatches"], indent=1)[:3000])
    if a.out:
        a.out.write_text(json.dumps(outs, indent=1))


if __name__ == "__main__":
    main()
