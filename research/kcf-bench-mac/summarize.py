"""Build results/RESULTS.json and the tables in RESULTS.md from runs/ (PLAN.md 8). Reads only files under runs/.

    python3 research/kcf-bench-mac/summarize.py
"""
from __future__ import annotations

import json
import random
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHES, FULL_A_CACHE, SAMPLE_SEED  # noqa: E402

HERE = Path(__file__).resolve().parent
R = HERE / "runs"


def jl(p):
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def j(p):
    return json.loads(p.read_text()) if p.exists() else None


def boot(xs, f, n=10000):
    if len(xs) < 2:
        return None
    rnd = random.Random(SAMPLE_SEED)
    vals = sorted(f([xs[rnd.randrange(len(xs))] for _ in xs]) for _ in range(n))
    return [vals[int(0.025 * n)], vals[int(0.975 * n) - 1]]


def mrange(xs):
    xs = [x for x in xs if x is not None]
    return {"median": st.median(xs), "min": min(xs), "max": max(xs), "n": len(xs)} if xs else None


def b_runs(c, kind):
    ms = [j(R / "b" / ("%s.%s.r%d.measure.json" % (c, kind, r))) for r in (1, 2, 3)]
    outs = [j(R / "b" / ("%s.%s.r%d.json" % (c, kind, r))) for r in (1, 2, 3)]
    ok = [(m, o) for m, o in zip(ms, outs) if m and o and m["exit_code"] == 0]
    if not ok:
        return None
    return {"repeats": len(ok), "jobs": ok[0][1]["jobs"], "destination_specs": ok[0][1]["destination_specs"],
            "edges": ok[0][1]["edges"], "wall_s": mrange([m["wall_s"] for m, _ in ok]),
            "cpu_s": mrange([m["cpu_s"] for m, _ in ok]), "peak_rss_mib": mrange([m["peak_rss_mib"] for m, _ in ok]),
            "fields_s": mrange([o["timing_s"]["fields"] for _, o in ok]),
            "loadavg_before": [m["loadavg_before"][0] for m, _ in ok]}


def main():
    out = {"caches": {}, "synthetic": [], "host": j(R / "HOST.json"),
           "commits": (R / "COMMITS.txt").read_text() if (R / "COMMITS.txt").exists() else None}
    for c, path in CACHES:
        row = {"cache": path}
        row["B_full"] = b_runs(c, "full")
        row["B_pass1_set"] = b_runs(c, "pass1") if c != FULL_A_CACHE else row["B_full"]
        row["B_repeat_set"] = b_runs(c, "repeat")
        planned = len(j(R / "jobs" / ("%s.pass1.json" % c)) or [])
        a = jl(R / "a" / ("%s.pass1.jsonl" % c))
        seen, arows = set(), []
        for x in a:
            if x["job"] not in seen:
                seen.add(x["job"]); arows.append(x)
        mfiles = [R / "a" / n for n in (["UA0324.head.measure.json", "UA0324.tail.measure.json"] if c == FULL_A_CACHE
                                        else ["%s.pass1.measure.json" % c] + (["%s.pass1_resume.measure.json" % c, "%s.pass1_resume2.measure.json" % c] if c == "YD0326" else []))]
        ms = [j(p) for p in mfiles if p.exists()]
        procs = []
        for n in (["UA0324.pass1.jsonl.proc.json"] if c == FULL_A_CACHE else ["%s.pass1.jsonl.proc.json" % c]):
            procs += jl(R / "a" / n)
        walls = [x["wall_s"] for x in arows]
        cpus = [x["cpu_s"] for x in arows]
        row["A_pass1"] = None if not arows else {
            "jobs_planned": planned, "jobs_run": len(arows), "complete": len(arows) == planned,
            "per_job_wall_s": {"median": st.median(walls), "median_95ci": boot(walls, st.median),
                               "mean": st.mean(walls), "mean_95ci": boot(walls, st.mean), "min": min(walls), "max": max(walls)},
            "per_job_cpu_s": {"median": st.median(cpus), "median_95ci": boot(cpus, st.median),
                              "mean": st.mean(cpus), "mean_95ci": boot(cpus, st.mean)},
            "per_job_kit_compute_s_median": st.median([x["compute_s"] for x in arows if x["compute_s"] is not None] or [0]),
            "sum_per_job_wall_s": sum(walls), "sum_per_job_cpu_s": sum(cpus),
            "process_wall_s": sum(m["wall_s"] for m in ms) if ms else None,
            "process_cpu_s": sum(m["cpu_s"] for m in ms) if ms else None,
            "peak_rss_mib_largest_process": max(m["peak_rss_mib"] for m in ms) if ms else None,
            "peak_rss_mib_worker_plus_kit_upper_bound": (max(p["worker_peak_rss_mib"] for p in procs)
                                                         + max(p["largest_kit_child_peak_rss_mib"] for p in procs)) if procs else None,
            "verdicts": {v: sum(1 for x in arows if x["verdict"] == v) for v in sorted({x["verdict"] for x in arows}, key=str)},
            "failed_status": sum(1 for x in arows if x["status"] != "done"),
            "loadavg_1min_median": st.median([x["loadavg"][0] for x in arows]),
            "loadavg_1min_max": max(x["loadavg"][0] for x in arows)}
        # repeats: pass-1 values for the repeat set + r2 + r3
        rep_ids = j(R / "jobs" / ("%s.repeat.json" % c)) or []
        by = {x["job"]: x for x in arows}
        reps = [{i: by[i] for i in rep_ids if i in by}]
        rep_ms = [None]
        for r in (2, 3):
            reps.append({x["job"]: x for x in jl(R / "a" / ("%s.repeat.r%d.jsonl" % (c, r)))})
            rep_ms.append(j(R / "a" / ("%s.repeat.r%d.measure.json" % (c, r))))
        complete = [k for k, d in enumerate(reps) if len(d) == len(rep_ids) and rep_ids]
        row["A_repeat_set"] = None if len(complete) < 1 else {
            "repeats_complete": len(complete), "jobs": len(rep_ids),
            "sum_wall_s_per_repeat": [sum(reps[k][i]["wall_s"] for i in rep_ids) for k in complete],
            "sum_cpu_s_per_repeat": [sum(reps[k][i]["cpu_s"] for i in rep_ids) for k in complete],
            "per_job_median_of_repeats_wall_s_median": st.median([st.median([reps[k][i]["wall_s"] for k in complete]) for i in rep_ids]),
            "per_job_range_over_repeats_wall_s_max": max(max(reps[k][i]["wall_s"] for k in complete) - min(reps[k][i]["wall_s"] for k in complete) for i in rep_ids),
            "process_wall_s_r2_r3": [m["wall_s"] for m in rep_ms[1:] if m],
            "process_cpu_s_r2_r3": [m["cpu_s"] for m in rep_ms[1:] if m],
            "peak_rss_mib_r2_r3": [m["peak_rss_mib"] for m in rep_ms[1:] if m]}
        # ratios only on identical job sets
        ratio = {}
        A1, Bm = row["A_pass1"], row["B_pass1_set"]
        process_complete = len(ms) == len(mfiles) and all(m["exit_code"] == 0 for m in ms)
        if A1 and Bm and A1["complete"] and process_complete and c != "YD0326":
            ratio["pass1_set_wall"] = A1["process_wall_s"] / Bm["wall_s"]["median"]
            ratio["pass1_set_cpu"] = A1["process_cpu_s"] / Bm["cpu_s"]["median"]
            ratio["pass1_set_jobs"] = A1["jobs_run"]
            ratio["pass1_set_basis"] = "A measured process wall/CPU"
        elif A1 and Bm and A1["complete"]:          # Amendment 2: YD0326's first process never wrote its measure file
            ratio["pass1_set_wall"] = A1["sum_per_job_wall_s"] / Bm["wall_s"]["median"]
            ratio["pass1_set_cpu"] = A1["sum_per_job_cpu_s"] / Bm["cpu_s"]["median"]
            ratio["pass1_set_jobs"] = A1["jobs_run"]
            ratio["pass1_set_basis"] = "sum of A per-job wall/CPU (Amendment 2)"
        Ar, Br = row["A_repeat_set"], row["B_repeat_set"]
        if Ar and Br and Ar["process_wall_s_r2_r3"]:
            ratio["repeat_set_wall_median"] = st.median(Ar["process_wall_s_r2_r3"]) / Br["wall_s"]["median"]
            ratio["repeat_set_cpu_median"] = st.median(Ar["process_cpu_s_r2_r3"]) / Br["cpu_s"]["median"]
        row["ratio_A_over_B"] = ratio
        # accuracy
        cmp_ = j(R / "compare" / ("%s.json" % c))
        if cmp_:
            rows = cmp_["rows"]
            dis = []
            for r in rows:
                why = []
                if not r["same_verdict"]:
                    why.append("verdict")
                if not r["same_departure_s"]:
                    why.append("departure")
                if r["same_arrival_s"] is False:
                    why.append("arrival")
                if r["same_legs"] is False:
                    why.append("legs")
                if r["a_route_valid"] is False or r["a_route_rebuild_error"]:
                    why.append("A route invalid")
                if r["b_route_valid"] is False:
                    why.append("B route invalid")
                if why:
                    dis.append({"job": r["job"], "why": why, **{k: r[k] for k in (
                        "offset", "recorded_verdict", "a_verdict", "a_raw_status", "a_reason_code", "b_verdict",
                        "b_issue_blocked", "a_departure_s", "b_departure_s", "a_arrival_s", "b_arrival_s",
                        "a_route_valid", "b_route_valid", "a_route_rebuild_error")},
                        "a_codes": (r["a_full_check"] or {}).get("codes"), "b_codes": (r["b_full_check"] or {}).get("codes")})
            chk = [r for r in rows if r["a_verdict"] == r["b_verdict"] == "checked_route"]
            row["accuracy"] = {
                "jobs_both": len(rows), "same_verdict": sum(r["same_verdict"] for r in rows),
                "same_departure_s": sum(bool(r["same_departure_s"]) for r in rows),
                "both_checked": len(chk), "same_arrival_s": sum(bool(r["same_arrival_s"]) for r in chk),
                "same_legs": sum(bool(r["same_legs"]) for r in chk),
                "a_routes": sum(1 for r in rows if r["a_verdict"] == "checked_route"),
                "a_routes_valid": sum(1 for r in rows if r["a_route_valid"]),
                "b_routes": sum(1 for r in rows if r["b_verdict"] == "checked_route"),
                "b_routes_valid": sum(1 for r in rows if r["b_route_valid"]),
                "a_unresolved_b_decided": sum(1 for r in rows if r["a_verdict"] == "unresolved"),
                "a_matches_recorded_verdict": sum(1 for r in rows if r["a_verdict"] == r["recorded_verdict"]),
                "disagreements": len(dis), "disagreement_list": dis}
        out["caches"][c] = row
    for s in (250, 354, 500):
        d, m = j(R / "synth" / ("side%d.json" % s)), j(R / "synth" / ("side%d.measure.json" % s))
        if d or m:
            out["synthetic"].append({"side": s, "result": d, "measure": m})
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "RESULTS.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({c: {"A": (r["A_pass1"] or {}).get("jobs_run"), "ratio": r["ratio_A_over_B"],
                          "acc": {k: v for k, v in (r.get("accuracy") or {}).items() if k != "disagreement_list"}}
                      for c, r in out["caches"].items()}, indent=1))


if __name__ == "__main__":
    main()
