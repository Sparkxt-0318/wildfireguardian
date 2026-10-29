"""Latest completion tally v2 (latest_forecast_routing_completion_20261015_v1), derived from the inherited native tally
(sha256 b27b5299...) by these changes only: one queue holds every region, so each row's region is the job's cohort and the
summary adds per-region blocks; "resolved in all repetitions" uses the queue's planned repetitions per mission (two here)
instead of a fixed three; rows add the receipt cleanup state. The decision call, independent checking (120 s cap, never
retried), witness rule and every class rule are unchanged. Revision 2.1 (reviewer producer-method findings on b9469702): an
interrupted checker or witness check (STARTED marker without a terminal record) is preserved as <label>.INTERRUPTED.json and
never retried; a malformed JOB or an exit-0 checker without valid JSON output is preserved as <label>.INVALID.json (never
renamed as final, never aborting the batch); missing RSS stays unavailable instead of zero; wall and RSS keep raw precision.
Inherited docstring follows.
Native-confirmation tally (routing_preparation_integration_20261014_v1), derived from the KLB regional_tally.py
(sha256 a50c7f36...) by asserted substitutions only (tools/derive_native_tally.py). Original docstring follows.
Regional classification for the separately declared Linux study. Derived from the frozen RDA1 phase_tally_v2.py
(sha256 48022d6f...). The decision call (journey_decision_v2_1), dispute rule and class rules are copied unchanged.
Changes:
  * the graph is loaded per job (job['graph_path']) instead of the fixed Uljin graph;
  * the frozen independent checker runs with the regional protocol's 120 s offline cap; a timeout leaves a
    <label>.TIMEOUT marker and a failure a <label>.FAILED.log; neither is retried; the row is INDEPENDENT_CHECK_MISSING
    (never resolved). Disputed-witness whole-road checks keep the RDA1 150 s;
  * the Uljin-only Phase C gate is removed; summaries are per region;
  * rows add region, cutoff, independent_state, successful_journey, receipt fields and the timed-command max RSS; a
    primary attempt whose GNU-time max RSS exceeds 3072 MiB gets regional_class MEMORY_GUARD_EXCEEDED (the regional
    protocol's guard would have stopped it); resolution uses regional_class.
  * amendment A3: the controller's enforced memory guard (memory_guard_triggered) also gives MEMORY_GUARD_EXCEEDED; a
    self-terminated exit 0 without an authoritative result is NO_PUBLICATION; descendant census counts are reported.
  * amendment A1: rows follow the queue (every planned slot appears): a slot with no folder is NOT_RUN and a folder without
    a complete receipt is INTERRUPTED (both unresolved, null measurements); a completed attempt that exited non-zero without
    deadline termination is WORKER_FAILED (exit code and last error line recorded) instead of the decision's LATE label.
Usage: regional_tally.py indep ROOT REGION [MAXSECONDS] | wroad ROOT REGION [MAXSECONDS] | tally ROOT REGION OUTDIR"""
import csv, json, os, pathlib, statistics as st, subprocess, sys, time, collections
mode, R, name = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
RAW = R / "raw" / name; IND = R / "raw" / (name + "_INDEPENDENT"); WR = R / "raw" / (name + "_WITNESS_WROAD")
PY = os.environ.get("WFG_CHECK_PYTHON", sys.executable); IND_CAP_S = 120.0; GUARD_MIB = 3072.0
DISPUTE_OPT = ("NOT_OPTIMAL_COUNTEREXAMPLE",); DISPUTE_REF = ("REFUSAL_CONTRADICTED", "FEASIBLE_ROUTE_EXISTS")
RESOLVED = ("VERIFIED_ROUTE", "VERIFIED_FULL_OPTIMUM", "CERTIFIED_REFUSAL")
def J(p): return json.loads(pathlib.Path(p).read_text())
TERMINAL = (".json", ".TIMEOUT", ".FAILED.log", ".INTERRUPTED.json", ".INVALID.json")
def terminal(base, name):
    return any((base / (name + suf)).exists() for suf in TERMINAL)
def preserve_interrupted(base, name, what):
    """A STARTED marker without a terminal record = an interrupted earlier check: record it once, never retry it."""
    st = base / (name + ".STARTED")
    if st.exists() and not terminal(base, name):
        tmp = base / (name + ".tmp")
        (base / (name + ".INTERRUPTED.json")).write_text(json.dumps({"status": what + "_INTERRUPTED", "started": st.read_text(),
            "partial_output_bytes": tmp.stat().st_size if tmp.exists() else None, "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rule": "interrupted checks are preserved and never retried"}))
        return True
    return False
if mode == "indep":
    IND.mkdir(parents=True, exist_ok=True); end = time.time() + float(sys.argv[4] if len(sys.argv) > 4 else 40)
    for d in sorted(RAW.iterdir()):
        if time.time() > end: break
        if preserve_interrupted(IND, d.name, "INDEPENDENT_CHECK"): print(d.name, "INTERRUPTED (preserved, not retried)"); continue
        if terminal(IND, d.name): continue
        if not (d / "COMPLETE_PROCESS_RECEIPT.json").exists() or not (d / "RESULT.json").exists(): continue
        tmp = IND / (d.name + ".tmp")
        try:
            job = J(d / "JOB.json")
            cmd = [PY, "-I", "-B", str(R / "runner/ffi_independent_checker.py"), "--graph", str(R / job["graph_path"]), "--packet-dir", str(R / job["source_directory"]),
                   "--request", str(R / job["request_path"]), "--result", str(d / "RESULT.json"), "--out", str(tmp)]
        except Exception as exc:
            (IND / (d.name + ".INVALID.json")).write_text(json.dumps({"status": "INDEPENDENT_CHECK_INPUT_INVALID", "error": repr(exc)})); print(d.name, "INVALID_JOB"); continue
        (IND / (d.name + ".STARTED")).write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        t0 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=IND_CAP_S)
        except subprocess.TimeoutExpired:
            (IND / (d.name + ".TIMEOUT")).write_text(json.dumps({"status": "INDEPENDENT_CHECK_TIMEOUT", "cap_s": IND_CAP_S, "elapsed_s": time.time() - t0}))
            print(d.name, "TIMEOUT"); continue
        if p.returncode == 0:
            try:
                obj = json.loads(tmp.read_text()); assert isinstance(obj, dict)
            except Exception as exc:
                (IND / (d.name + ".INVALID.json")).write_text(json.dumps({"status": "INDEPENDENT_CHECK_OUTPUT_INVALID", "error": repr(exc), "exit_code": 0,
                                                                          "elapsed_s": time.time() - t0, "stdout_tail": p.stdout[-400:]}))
                print(d.name, "INVALID_OUTPUT"); continue
            tmp.rename(IND / (d.name + ".json")); print(d.name, "ok", round(time.time() - t0, 1))
        else: (IND / (d.name + ".FAILED.log")).write_text(p.stdout + p.stderr); print(d.name, "FAILED")
    print(len(list(IND.glob("*.json"))), "independent records (outputs plus interrupted/invalid records);", len(list(IND.glob("*.TIMEOUT"))), "timeouts;", len(list(IND.glob("*.FAILED.log"))), "failed"); sys.exit(0)
sys.path.insert(0, str(R / "decision")); import journey_decision_v2_1 as JD
_cache = {}
def C(k):
    if k not in _cache: _cache[k] = J(R / k)
    return _cache[k]
def decide(d):
    rc = J(d / "COMPLETE_PROCESS_RECEIPT.json"); job = J(d / "JOB.json")
    res = J(d / "RESULT.json") if (d / "RESULT.json").exists() else {}
    dec = JD.decision_from_worker_record(res, rc, job, graph=C(job["graph_path"]), request=C(job["request_path"]), hazard=C(job["hazard_path"]),
                                         optimality_certificate=res.get("optimality_certificate"), refusal_certificate=res.get("refusal_certificate"))
    return rc, job, res, dec
def disputed(dec, ind):
    v = ((ind or {}).get("optimality_or_refusal") or {}).get("verdict"); a = dec["authoritative_status"]
    return (a == "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN" and v in DISPUTE_OPT) or (a == "FULL_MODEL_REFUSAL_PROVEN" and v in DISPUTE_REF)
if mode == "wroad":
    WR.mkdir(parents=True, exist_ok=True); end = time.time() + float(sys.argv[4] if len(sys.argv) > 4 else 20); n = 0
    for d in sorted(RAW.iterdir()):
        if time.time() > end: break
        if not (d / "COMPLETE_PROCESS_RECEIPT.json").exists() or not (IND / (d.name + ".json")).exists(): continue
        if preserve_interrupted(WR, d.name, "WITNESS_WHOLEROAD"): print(d.name, "WITNESS INTERRUPTED (preserved)"); continue
        out = WR / (d.name + ".json")
        if terminal(WR, d.name): continue
        rc, job, res, dec = decide(d); ind = J(IND / (d.name + ".json"))
        if not disputed(dec, ind): continue
        (WR / (d.name + ".STARTED")).write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        n += 1; p = subprocess.run([PY, "-I", "-B", str(R / "runner/witness_wholeroad.py"), str(R), str(d), str(IND / (d.name + ".json")), str(out), "150"], capture_output=True, text=True)
        if not out.exists():
            (WR / (d.name + ".FAILED.log")).write_text(p.stdout + p.stderr)
        print(p.stdout.strip() or p.stderr[-400:])
    print(n, "disputed witnesses checked;", len(list(WR.glob("*.json"))), "total"); sys.exit(0)
OUT = pathlib.Path(sys.argv[4]); OUT.mkdir(parents=True, exist_ok=True); rows = []
def stage_costs(res):
    stg = res.get("rda_stages") or []; tot = collections.Counter(); per = []
    for s in stg if isinstance(stg, list) else []:
        es = s.get("exposure_stats") or {}
        per.append({k: s.get(k) for k in ("stage", "status", "reason", "elapsed_s", "wall_cap_s", "arrival", "labels", "expansions", "occupancy_evaluations")} | {"boxes_computed": es.get("boxes_computed"), "coef_s": es.get("coef_s")})
        for k in ("labels", "expansions", "occupancy_evaluations"): tot[k] += s.get(k) or 0
    m = ((res.get("result") or {}).get("metrics") or {})
    for k in ("labels", "expansions"):
        if not per and isinstance(m.get(k), (int, float)): tot[k] += m[k]
    return per, tot
QJOBS = J(R / "queues" / (name + ".json"))["jobs"]
PLANNED = collections.Counter(j["case_id"] for j in QJOBS if j.get("arm") == "RDA_CAND")
def stub(job, state):
    return {"label": pathlib.Path(job["output_path"]).name, "region": job["cohort"], "case_id": job["case_id"], "cutoff": job["case_id"].split("_")[0],
            "mission_type": job["case_id"].split("_")[1], "arm": job["arm"], "rep": job["rep"], "class": state, "regional_class": state, "resolved": False,
            "successful_journey": False, "slot_state": state, "reporting_class": state}
def worker_error(d):
    for fn in ("PROCESS.time", "stdout.log"):
        f = d / fn
        if f.exists():
            lines = [l.strip() for l in f.read_text(errors="replace").splitlines() if l.strip() and not l.startswith(("\t", "Command being timed"))]
            errs = [l for l in lines if "Error" in l or "Exception" in l or "Unsupported" in l or "terminated by signal" in l or "Killed" in l]
            if errs: return errs[-1][:300]
    return None
for job in QJOBS:
    d = R / job["output_path"]
    if not d.is_dir(): rows.append(stub(job, "NOT_RUN")); continue
    if not (d / "COMPLETE_PROCESS_RECEIPT.json").exists(): rows.append(stub(job, "INTERRUPTED")); continue
    rc, job, res, dec = decide(d)
    ind = J(IND / (d.name + ".json")) if (IND / (d.name + ".json")).exists() else None
    istate = "OK" if ind is not None else ("TIMEOUT_120S" if (IND / (d.name + ".TIMEOUT")).exists() else ("FAILED" if (IND / (d.name + ".FAILED.log")).exists() else (
        "INTERRUPTED" if (IND / (d.name + ".INTERRUPTED.json")).exists() else ("INVALID_OUTPUT" if (IND / (d.name + ".INVALID.json")).exists() else ("NO_RESULT" if not res else "NOT_RUN")))))
    wr = J(WR / (d.name + ".json")) if (WR / (d.name + ".json")).exists() else None
    a = dec["authoritative_status"]; ci = (ind or {}).get("classification") or {}; opt = (ind or {}).get("optimality_or_refusal") or {}
    contra = list((ind or {}).get("contradictions") or []); note = ""
    dispute = disputed(dec, ind); cleared = dispute and (wr or {}).get("status") == "DEFINITE_REJECT"
    if dispute: note = "independent centre-model counterexample at %s; offline whole-road check: %s" % ((wr or {}).get("witness_arrival"), (wr or {}).get("status", "NOT_RUN"))
    if ind is None and res: klass = "INDEPENDENT_CHECK_MISSING"
    elif contra: klass = "CONTRADICTION"
    elif dec["is_successful_journey"]:
        base_ok = ci.get("trajectory") == "VALID" and ci.get("whole_road_contact") == "CLEAR" and (res.get("whole_road_check") or {}).get("status") == "CERTIFIED_ADMISSIBLE"
        if not base_ok: klass = "CONTRADICTION"
        elif dispute and not cleared: klass = "CONTRADICTION"
        elif ci.get("centre_model") != "FEASIBLE": klass = "ROAD_ONLY_ROUTE"
        elif a == "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN": klass = "VERIFIED_FULL_OPTIMUM"
        else: klass = "VERIFIED_ROUTE"
    elif a == "FULL_MODEL_REFUSAL_PROVEN":
        v = opt.get("verdict")
        if v == "INDEPENDENTLY_CERTIFIED_REFUSAL": klass = "CERTIFIED_REFUSAL"
        elif dispute and not cleared: klass = "CONTRADICTION"
        else: klass = "UNSUPPORTED_REFUSAL_CLAIM"
    elif a == "CENTRE_MODEL_REFUSAL_ONLY": klass = "CENTRE_REFUSAL_ONLY"
    else:
        r = dec.get("unresolved_reason")
        klass = {"CANDIDATE_REJECTED_BY_WHOLE_ROAD": "REJECTED_CANDIDATE", "SEARCH_TIMEOUT": "TIMEOUT", "LATE_RESULT": "LATE"}.get(r, "UNKNOWN_CHECK" if r and "CHECK" in r else (a if a != "UNRESOLVED" else str(r)))
    per, tot = stage_costs(res); tv = rc.get("time_v") or {}
    rss = None if tv.get("timed_command_RSS_bytes") is None else tv["timed_command_RSS_bytes"] / 2**20   # missing stays unavailable (not zero)
    over = None if rss is None else rss > GUARD_MIB
    failed = (not rc.get("deadline_termination_requested")) and rc.get("exit_code") not in (0, None)
    rk = "MEMORY_GUARD_EXCEEDED" if (over or rc.get("memory_guard_triggered")) else ("WORKER_FAILED" if failed else klass)
    if rk in ("LATE", "LATE_RESULT") and not rc.get("termination_requested", rc.get("deadline_termination_requested")) and not (res or {}).get("authority_final"):
        rk = "NO_PUBLICATION"  # amendment A3: exited 0 by itself without an authoritative result
    rej = res.get("rejected_witnesses") or []; jr = dec.get("journey") or {}
    rows.append({"label": d.name, "region": job["cohort"], "case_id": job["case_id"], "cutoff": job["case_id"].split("_")[0], "mission_type": job["case_id"].split("_")[1],
        "arm": job["arm"], "rep": job["rep"], "class": klass, "regional_class": rk, "resolved": rk in RESOLVED, "slot_state": "COMPLETED",
        "reporting_class": ("DEADLINE_STOP" if rc.get("deadline_termination_requested") and rk not in RESOLVED else rk),
        "preparation_mode": (res.get("preparation") or {}).get("mode"), "preparation_declared": job.get("preparation_mode"),
        "preparation_cache_hit": (res.get("preparation") or {}).get("cache_hit"), "preparation_s": (res.get("preparation") or {}).get("prepare_s"),
        "worker_error": worker_error(d) if failed else None,
        "successful_journey": bool(dec.get("is_successful_journey")), "authoritative_status": a, "unresolved_reason": dec.get("unresolved_reason"), "arrival": jr.get("arrival"),
        "primary_status": res.get("primary_status"), "result_reason": (res.get("result") or {}).get("reason"), "runtime_whole_road": (res.get("whole_road_check") or {}).get("status"),
        "independent_state": istate, "independent_verdict": opt.get("verdict"), "independent_overall": ci.get("overall"), "independent_centre": ci.get("centre_model"),
        "independent_contact": ci.get("whole_road_contact"), "contradictions": ";".join(contra), "dispute_note": note,
        "rejected_witnesses": ";".join("%s:%s:%s" % (w.get("stage"), (w.get("check") or {}).get("status") if isinstance(w.get("check"), dict) else w.get("check_status"), "prefilter" if "prefilter" in str(w.get("check_kind")) else "checker") for w in rej if isinstance(w, dict)),
        "on_time": rc.get("on_time_complete_publication"), "exit_code": rc.get("exit_code"), "deadline_termination_requested": rc.get("deadline_termination_requested"),
        "forced_kill": rc.get("forced_kill"), "started_utc": rc.get("started_utc"), "ended_utc": rc.get("ended_utc"),
        "wall_s": rc.get("external_launch_to_completion_wall_s"), "cpu_s": tv.get("CPU_s"), "rss_mib": rss, "rss_over_3072_mib": over,
        "cleanup_state": rc.get("cleanup_state"), "cleanup_ok": rc.get("cleanup_ok"), "rss_sample_errors": rc.get("rss_sample_errors"),
        "memory_guard_triggered": rc.get("memory_guard_triggered"), "sampled_family_peak_rss_mib": None if rc.get("sampled_family_peak_rss_bytes") is None else rc["sampled_family_peak_rss_bytes"] / 2**20,
        "descendants_after_exit": None if rc.get("descendants_after_exit") is None else len(rc["descendants_after_exit"]), "descendants_remaining": None if rc.get("descendants_remaining_after_cleanup") is None else len(rc["descendants_remaining_after_cleanup"]),
        "labels_total": tot["labels"], "expansions_total": tot["expansions"], "occupancy_evaluations_total": tot["occupancy_evaluations"],
        "boxes_computed": max([p["boxes_computed"] or 0 for p in per] or [0]), "bound_model_cache": json.dumps(res.get("bound_model_cache"), default=str)[:300],
        "worker_stages_json": json.dumps(res.get("stages"), default=str), "rda_stages_json": json.dumps(per, default=str)})
with (OUT / "EXECUTIONS.csv").open("w", newline="") as f:
    FN = []
    for r in rows:
        for k in r:
            if k not in FN: FN.append(k)
    w = csv.DictWriter(f, fieldnames=FN, restval=None); w.writeheader(); w.writerows(rows)
(OUT / "EXECUTIONS.json").write_text(json.dumps(rows, indent=1))
med = lambda xs: st.median(xs) if xs else None
summ = {"queue": name, "scope": "one host per run root (see ENVIRONMENT.json); never pooled across hosts or workloads; model-relative resolution, not physical safety",
        "planned_repetitions_per_mission": sorted(set(PLANNED.values()))}
def block(X):
    out = {}
    for arm in sorted({r["arm"] for r in X}):
        A = [r for r in X if r["arm"] == arm]; per = collections.defaultdict(list)
        for r in A: per[r["case_id"]].append(r["regional_class"])
        out[arm] = {"executions": len(A), "classes": dict(collections.Counter(r["regional_class"] for r in A)), "resolved_executions": sum(r["resolved"] for r in A),
                    "reporting_classes": dict(collections.Counter(r.get("reporting_class") for r in A)),
                    "preparation_modes": dict(collections.Counter(str(r.get("preparation_mode")) for r in A)),
                    "missions": len(per), "missions_resolved_all_reps": sum(1 for c, v in per.items() if len(v) == PLANNED[c] and all(k in RESOLVED for k in v)),
                    "missions_resolved_any_rep": sum(1 for v in per.values() if any(k in RESOLVED for k in v)),
                    "per_mission": {c: v for c, v in sorted(per.items())}, "contradictions": sum(r["class"] == "CONTRADICTION" for r in A),
                    "independent_states": dict(collections.Counter(r.get("independent_state") for r in A)),
                    "slot_states": dict(collections.Counter(r["slot_state"] for r in A)),
                    "cleanup_states": dict(collections.Counter(str(r.get("cleanup_state")) for r in A)),
                    "on_time": sum(bool(r.get("on_time")) for r in A), "wall_median_s": med([r["wall_s"] for r in A if r.get("wall_s") is not None]),
                    "wall_sum_s": round(sum(r.get("wall_s") or 0 for r in A), 2), "cpu_sum_s": round(sum(r.get("cpu_s") or 0 for r in A), 2),
                    "rss_max_mib": max([r["rss_mib"] for r in A if r.get("rss_mib") is not None] or [None], key=lambda v: -1 if v is None else v),
                    "rss_over_3072": sum(bool(r.get("rss_over_3072_mib")) for r in A)}
    return out
summ["all_regions"] = block(rows)
summ["by_region"] = {g: block([r for r in rows if r["region"] == g]) for g in sorted({r["region"] for r in rows})}
both = [(a, b) for a in rows for b in rows if a["arm"] == "RDA_CAND" and b["arm"] == "RDA_BASE" and a["case_id"] == b["case_id"] and a["region"] == b["region"] and a["rep"] == b["rep"]]
P = [(a, b) for a, b in both if a["resolved"] and b["resolved"]]
mc = med([a["wall_s"] for a, b in P]); mb = med([b["wall_s"] for a, b in P])
summ["paired"] = {"pairs": len(both), "both_resolved": len(P), "median_wall_cand_s": mc, "median_wall_base_s": mb,
                  "ratio_of_medians": (mc / mb) if P else None, "median_of_ratios": med([a["wall_s"] / b["wall_s"] for a, b in P]),
                  "same_arrival_when_both_resolved_routes": sum(1 for a, b in P if a.get("arrival") is not None and a.get("arrival") == b.get("arrival")),
                  "base_resolved_cand_not": [(b["region"], b["case_id"], b["rep"]) for a, b in both if b["resolved"] and not a["resolved"]],
                  "cand_resolved_base_not": [(a["region"], a["case_id"], a["rep"]) for a, b in both if a["resolved"] and not b["resolved"]]}
(OUT / "SUMMARY.json").write_text(json.dumps(summ, indent=1))
print(json.dumps({"queue": name, "all_regions": {a: {k: v for k, v in b.items() if k != "per_mission"} for a, b in summ["all_regions"].items()}, "paired": summ["paired"]}, indent=1))
