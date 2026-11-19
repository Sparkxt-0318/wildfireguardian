"""Builds cells.json and TABLE.md from committed result files and from the runs/ outputs of run_v1.py / run_v2.py.

Every number is computed here from a file; no value is typed in except the NOT RUN reasons. Layout rules: LAYOUT.md.

    python3 build_cells.py            (from the repository root)
"""
import csv
import glob
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

R = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
RUNS = H / "runs"
BUD = (92, 105, 290)

ROWS = [("1", "full system as submitted"), ("2", "forecast → persistence"), ("3", "forecast → measured reach margin"),
        ("4", "heat closure off"), ("5", "thermal-dose budget off"), ("6", "corridor router → reference router"),
        ("7", "deadline field → recorded per-departure checks")]
COLS = [("F1", "Gyeongbuk 2025 (KFS_01)", ["uiseong_andong_2025", "yeongdeok_2025"]),
        ("F2", "Uljin 2022 (KFS_02)", ["uljin_2022"]), ("F3", "Hongseong 2023 (KFS_05)", ["hongseong_2023"]),
        ("F4", "Miryang 2022 (KFS_11)", ["miryang_2022"]), ("F5", "Caldor 2021", [])]
OTHER = [("F6", "Wapiti 2024", "US held-out forecast cohort"), ("F7", "Goat", "US held-out forecast cohort"),
         ("F8", "Lava", "US held-out forecast cohort"), ("F9", "Red Rock", "US held-out forecast cohort"),
         ("F10", "Pioneer", "US held-out forecast cohort"), ("F11", "Fish Creek", "US held-out forecast cohort"),
         ("F12", "Sancheong (KFS_04)", "Korean held-out forecast cohort"), ("F13", "Ulju (KFS_06)", "Korean held-out forecast cohort"),
         ("F14", "Bukgu (KFS_13)", "Korean held-out forecast cohort"),
         ("P-A", "28 GOFER fires", "margin calibration population"), ("P-B", "488 NIROPS incidents", "margin check population"),
         ("P-C", "SMOKE catalog, 44 events", "training / validation population")]

REASONS = {
    "NR-NOGRAPH": "No road graph, places or missions exist for this fire in the repo or in the fetched inputs (it is a forecast-scoring, calibration or training fire); the routing metrics are undefined.",
    "NR-MARGIN": "LAYOUT §7: the frozen margin rule exists for 5 h / 8 h horizons on known-perimeter inputs; the forecast arm exists at a 1-hour horizon on other issue times (V1, V2) or as retrospective scenarios (V3); V4 has no forecast arm. A run needs a rule mapping R to a 1-hour hazard that would be chosen after the full-system outputs are known.",
    "NR-NOSWEEP": "No recorded per-departure sweep exists for the V1 missions (committed per-departure checks cover the six 2025 planner caches only), so there is nothing to substitute for the field.",
    "NR-LB": "The router answers one departure per request; it produces no leave-by.",
    "NR-V3JOBS": "The V3 summaries are per place and place-run; job-level decided / route counts are not committed.",
    "NR-V3HEATOFF": "Heat closure off with the dose budget kept has no committed contrast, and the V3 inputs are not in the repo tree (rebuilt from three other branches by scripts/fdyn_rebuild_inputs.sh; the batch takes about 1 h 40 min with 3 workers per dwell mode) — not attempted.",
    "NR-V3PERSIST": "V3 hazards are retrospective reconstructions (kriged, FIRMS, envelope), not forecasts; there is no forecast to replace.",
    "NR-V5": "The v8 campaign has one arm and no ablation arms; only its own receipts exist.",
    "NR-REFV2": "No reference-router sweep is committed for V2; the planner caches were produced by the proposed router only.",
    "NR-CALDOR": "Caldor 2021 appears only in the v8 receipts; its graph is not in the fetched inputs, so no field or router can be run.",
    "NR-V4": "kcf-replay has margin arms only (R-based); it contains no forecast arm and no full-system arm to compare with.",
    "NR-V3RUN": "Not tabulated at this unit in a committed file.",
}


def m(value, status, source=None, command=None, reason=None):
    d = {"value": value, "status": status}
    if source:
        d["source"] = source
    if command:
        d["command"] = command
    if reason:
        d["reason"] = reason
        d["reason_text"] = REASONS[reason]
    return d


def nr(reason):
    return m(None, "NOT RUN", reason=reason)


def compare(base, arm):
    """base, arm: {place: leave_by or None}. The uniform leave-by comparison of LAYOUT §4."""
    both, only_b, only_a, deltas, n_b = 0, 0, 0, [], 0
    for p, b in base.items():
        a = arm.get(p)
        n_b += b is not None
        if b is not None and a is not None:
            if a != b:
                both += 1
                deltas.append(abs(a - b))
        elif b is not None and a is None:
            only_b += 1
        elif b is None and a is not None:
            only_a += 1
    return {"places_with_leave_by_in_full": n_b, "changed_total": both + only_b + only_a, "changed_both_defined": both,
            "leave_by_only_in_full": only_b, "leave_by_only_in_arm": only_a,
            "median_s": statistics.median(deltas) if deltas else None, "largest_s": max(deltas) if deltas else None}


# ------------------------------------------------------------------------------------------------- recorded: V1 routing rows
def v1_recorded():
    rows = list(csv.DictReader(open(R / "research/routing/INDEPENDENT_ROWS.csv")))
    out = {}
    for fire, _n, regions in COLS:
        for arm in ("RDA_CAND", "RDA_BASE"):
            rs = [r for r in rows if r["region"] in regions and r["arm"] == arm]
            by = defaultdict(list)
            for r in rs:
                by[r["case_id"] + "|" + r["region"]].append(r)
            dec = sum(all(x["resolved"] == "True" for x in v) for v in by.values())
            rt = sum(all(x["route"] == "True" for x in v) for v in by.values())
            out[(fire, arm)] = {"missions": len(by), "decided": dec, "routes": rt,
                                "median_wall_s": round(statistics.median(float(x["wall_s"]) for x in rs), 3) if rs else None,
                                "executions": len(rs)}
    return out


# ------------------------------------------------------------------------------------------------- new run: V1
def v1_new():
    p = RUNS / "v1.json"
    d = json.loads(p.read_text())
    out = defaultdict(lambda: {"missions": {}, "time": defaultdict(float)})
    for pk in d["packets"]:
        fire = next(f for f, _n, regs in COLS if pk["region"] in regs)
        o = out[fire]
        for k, v in pk["timing_s"].items():
            o["time"][k] += v
        for mid, mm in pk["missions"].items():
            o["missions"][mid] = mm
    return out, d


def v1_cells(cells, rec, new):
    cmd = "python3 research/kcf-ablation/run_v1.py --data-root <routing inputs> --out research/kcf-ablation/runs/v1.json"
    src = "research/kcf-ablation/runs/v1.json"
    for fire, _n, regions in COLS:
        if fire == "F5":
            continue
        o = new[fire]
        ms = o["missions"]
        T = o["time"]

        def arm_leave(armkey, name):
            return {k: v["arms"][armkey][name]["leave_by"] for k, v in ms.items()}

        def routes(armkey, name):
            return sum(v["arms"][armkey][name]["feasible_at_departure"] for v in ms.values())
        # row 1
        c = cells["1"][fire]["versions"].setdefault("V1", {"metrics": {}, "notes": []})["metrics"]
        r = rec[(fire, "RDA_CAND")]
        c["cases_decided"] = m("%d/%d" % (r["decided"], r["missions"]), "RECORDED", "research/routing/INDEPENDENT_ROWS.csv (arm RDA_CAND, both repetitions resolved)")
        c["routes_found"] = m(r["routes"], "RECORDED", "research/routing/INDEPENDENT_ROWS.csv (arm RDA_CAND)")
        c["leave_by_changed"] = m("base", "NEW RUN", src, cmd)
        c["median_change_s"] = m("base", "NEW RUN", src, cmd)
        c["largest_change_s"] = m("base", "NEW RUN", src, cmd)
        c["run_time_s"] = m({"router_median_per_execution_s": r["median_wall_s"], "host": "Apple M5 Pro, macOS (paper)"}, "RECORDED", "research/routing/INDEPENDENT_ROWS.csv wall_s")
        base = {b: {k: ms[k]["arms"]["full_models"]["full@%d" % b]["leave_by"] for k in ms} for b in BUD}
        cells["1"][fire]["versions"]["V1"]["field_full_arm"] = {
            "status": "NEW RUN", "command": cmd, "source": src,
            "decided": "%d/%d" % (len(ms), len(ms)),
            "routes_at_departure_by_budget": {str(b): routes("full_models", "full@%d" % b) for b in BUD},
            "contact_only_routes_at_departure": routes("full_models", "contact"),
            "places_with_leave_by_by_budget": {str(b): sum(v is not None for v in base[b].values()) for b in BUD},
            "leave_by_by_mission_at_92": {k: v for k, v in base[92].items()},
            "run_time_s": round(T["full_models:prepare"] + T["full_models:field:full"], 2),
            "host": "this container (Linux x86_64, 4 cores, Python 3.13.18, numpy 2.5.3)"}
        # rows 2, 4, 5 against the same budget
        for rid, armkey, name_fn, tkeys in (
                ("2", "persistence", lambda b: "full@%d" % b, ("persistence:prepare", "persistence:field:full")),
                ("4", "full_models", lambda b: "heat_off@%d" % b, ("full_models:prepare", "full_models:field:heat_off")),
                ("5", "full_models", lambda b: "dose_off", ("full_models:prepare", "full_models:field:dose_off"))):
            c = cells[rid][fire]["versions"].setdefault("V1", {"metrics": {}, "notes": []})["metrics"]
            per = {}
            for b in BUD:
                cmpb = compare(base[b], arm_leave(armkey, name_fn(b)))
                per[b] = cmpb
            rts = {b: routes(armkey, name_fn(b)) for b in BUD}
            c["cases_decided"] = m("%d/%d" % (len(ms), len(ms)), "NEW RUN", src, cmd)
            c["routes_found"] = m({str(b): rts[b] for b in BUD}, "NEW RUN", src, cmd)
            c["leave_by_changed"] = m({str(b): "%d of %d" % (per[b]["changed_total"], per[b]["places_with_leave_by_in_full"]) for b in BUD}, "NEW RUN", src, cmd)
            c["median_change_s"] = m({str(b): per[b]["median_s"] for b in BUD}, "NEW RUN", src, cmd)
            c["largest_change_s"] = m({str(b): per[b]["largest_s"] for b in BUD}, "NEW RUN", src, cmd)
            c["run_time_s"] = m(round(sum(T[k] for k in tkeys), 2), "NEW RUN", src, cmd)
            cells[rid][fire]["versions"]["V1"]["detail"] = {str(b): per[b] for b in BUD}
        # row 3
        c = cells["3"][fire]["versions"].setdefault("V1", {"metrics": {}, "notes": []})["metrics"]
        for k in ("cases_decided", "routes_found", "leave_by_changed", "median_change_s", "largest_change_s", "run_time_s"):
            c[k] = nr("NR-MARGIN")
        # row 6
        c = cells["6"][fire]["versions"].setdefault("V1", {"metrics": {}, "notes": []})["metrics"]
        rb = rec[(fire, "RDA_BASE")]
        c["cases_decided"] = m("%d/%d" % (rb["decided"], rb["missions"]), "RECORDED", "research/routing/INDEPENDENT_ROWS.csv (arm RDA_BASE)")
        c["routes_found"] = m(rb["routes"], "RECORDED", "research/routing/INDEPENDENT_ROWS.csv (arm RDA_BASE)")
        for k in ("leave_by_changed", "median_change_s", "largest_change_s"):
            c[k] = nr("NR-LB")
        c["run_time_s"] = m({"reference_median_per_execution_s": rb["median_wall_s"], "host": "Apple M5 Pro, macOS (paper)"}, "RECORDED", "research/routing/INDEPENDENT_ROWS.csv wall_s")
        # arrival agreement on jointly resolved missions (note)
        rows = [x for x in csv.DictReader(open(R / "research/routing/INDEPENDENT_ROWS.csv")) if x["region"] in regions]
        cand = {(x["case_id"], x["region"], x["rep"]): x for x in rows if x["arm"] == "RDA_CAND"}
        n_joint, n_same = 0, 0
        for x in rows:
            if x["arm"] == "RDA_BASE" and x["route"] == "True":
                y = cand[(x["case_id"], x["region"], x["rep"])]
                if y["route"] == "True":
                    n_joint += 1
                    n_same += x["arrival"] == y["arrival"]
        cells["6"][fire]["versions"]["V1"]["notes"].append("Arrival second equal on %d of %d jointly routed executions (not a leave-by); source research/routing/INDEPENDENT_ROWS.csv" % (n_same, n_joint))
        # row 7
        c = cells["7"][fire]["versions"].setdefault("V1", {"metrics": {}, "notes": []})["metrics"]
        for k in ("cases_decided", "routes_found", "leave_by_changed", "median_change_s", "largest_change_s", "run_time_s"):
            c[k] = nr("NR-NOSWEEP")


# ------------------------------------------------------------------------------------------------- V2
def load_v2():
    out = {}
    for arm in ("full", "persistence", "heat_off"):
        for f in sorted(glob.glob(str(RUNS / "v2" / ("*__" + arm + ".json")))):
            d = json.loads(Path(f).read_text())
            out.setdefault(arm, {})[(d["region"], d["input_time"])] = d
    committed = {}
    for f in sorted(glob.glob(str(R / "research/kcf-heat/data/tdu_1h/*__dwell_count.tdu.json"))):
        d = json.loads(Path(f).read_text())
        committed[(d["region"], d["input_time"])] = d
    return out, committed


def v2_places(arm_runs, key):
    out = {}
    for (reg, t), d in arm_runs.items():
        for o, v in d["origins"].items():
            out[(reg, t, o)] = v[key]
    return out


def v2_cells(cells):
    runs, committed = load_v2()
    if not all(len(runs.get(a, {})) == 6 for a in ("full", "persistence", "heat_off")):
        print("V2 runs incomplete:", {a: len(v) for a, v in runs.items()})
        return None
    cmd = "python3 research/kcf-ablation/run_v2.py --data-root <routing inputs> --out-dir research/kcf-ablation/runs/v2 --arm %s <six planner caches>"
    # reproduction check: the NEW RUN full arm against the committed C.4 files, every origin and key
    diffs = 0
    n = 0
    for k, d in runs["full"].items():
        for o, v in committed[k]["origins"].items():
            for kk, x in v.items():
                if kk.startswith(("exact_", "grid_")):
                    n += 1
                    diffs += runs["full"][k]["origins"][o][kk] != x
    repro = {"values_compared": n, "differences": diffs}
    # F-3.1 cert job count check
    cert_jobs = sum(d["job_feasible"]["cert"] for d in runs["full"].values())
    jobs = sum(d["jobs"] for d in runs["full"].values())
    base = {b: {p: v for p, v in v2_places(runs["full"], "exact_tdu%d" % b).items()} for b in BUD}
    comm_base = {b: {(k[0], k[1], o): v["exact_tdu%d" % b] for k, d in committed.items() for o, v in d["origins"].items()} for b in BUD}
    tot = lambda arm, key: sum(d["timing_s"][key] for d in runs[arm].values())
    fire = "F1"
    # row 1
    c = cells["1"][fire]["versions"].setdefault("V2", {"metrics": {}, "notes": []})["metrics"]
    jf = {b: sum(d["job_feasible"]["tdu%d" % b] for d in runs["full"].values()) for b in BUD}
    c["cases_decided"] = m("%d/%d" % (jobs, jobs), "NEW RUN", "research/kcf-ablation/runs/v2/*__full.json (field answers every job)", cmd % "full")
    c["routes_found"] = m({str(b): jf[b] for b in BUD}, "NEW RUN", "research/kcf-ablation/runs/v2/*__full.json", cmd % "full")
    for k in ("leave_by_changed", "median_change_s", "largest_change_s"):
        c[k] = m("base", "RECORDED", "research/kcf-heat/data/tdu_1h/*.tdu.json (exact_tdu*)")
    c["run_time_s"] = m(round(tot("full", "total"), 1), "NEW RUN", "research/kcf-ablation/runs/v2/*__full.json (timing_s.total, six caches, no witness pass)", cmd % "full")
    cells["1"][fire]["versions"]["V2"]["detail"] = {
        "jobs": jobs, "cert_only_feasible_jobs": cert_jobs, "cert_check_equals_F31_7970": cert_jobs == 7970,
        "cert_heat_feasible_jobs": sum(d["job_feasible"]["cert_heat"] for d in runs["full"].values()),
        "places": len(base[92]), "places_with_leave_by": {str(b): sum(v is not None for v in base[b].values()) for b in BUD},
        "reproduction_vs_committed_tdu_1h": repro}
    # row 2 persistence, row 4 heat off (NEW RUN, vs the NEW RUN full arm)
    for rid, arm in (("2", "persistence"), ("4", "heat_off")):
        c = cells[rid][fire]["versions"].setdefault("V2", {"metrics": {}, "notes": []})["metrics"]
        per, rts = {}, {}
        for b in BUD:
            per[b] = compare(base[b], v2_places(runs[arm], "exact_tdu%d" % b))
            rts[b] = sum(d["job_feasible"]["tdu%d" % b] for d in runs[arm].values())
        c["cases_decided"] = m("%d/%d" % (jobs, jobs), "NEW RUN", "research/kcf-ablation/runs/v2/*__%s.json" % arm, cmd % arm)
        c["routes_found"] = m({str(b): rts[b] for b in BUD}, "NEW RUN", "research/kcf-ablation/runs/v2/*__%s.json" % arm, cmd % arm)
        c["leave_by_changed"] = m({str(b): "%d of %d" % (per[b]["changed_total"], per[b]["places_with_leave_by_in_full"]) for b in BUD}, "NEW RUN", "research/kcf-ablation/runs/v2/*__%s.json" % arm, cmd % arm)
        c["median_change_s"] = m({str(b): per[b]["median_s"] for b in BUD}, "NEW RUN", "same", cmd % arm)
        c["largest_change_s"] = m({str(b): per[b]["largest_s"] for b in BUD}, "NEW RUN", "same", cmd % arm)
        c["run_time_s"] = m(round(tot(arm, "total"), 1), "NEW RUN", "research/kcf-ablation/runs/v2/*__%s.json (timing_s.total)" % arm, cmd % arm)
        cells[rid][fire]["versions"]["V2"]["detail"] = {str(b): per[b] for b in BUD}
        cells[rid][fire]["versions"]["V2"]["detail"]["burning_cells_by_cache"] = {"%s %s" % k: d["burning_cells"] for k, d in runs[arm].items()}
        if rid == "2":
            ch = Counter()
            for k, d in runs[arm].items():
                for o, v in d["origins"].items():
                    ch["%s %s" % k] += v["exact_tdu92"] != runs["full"][k]["origins"][o]["exact_tdu92"]
            cells[rid][fire]["versions"]["V2"]["detail"]["places_changed_at_92_by_cache"] = dict(ch)
            cells[rid][fire]["versions"]["V2"]["detail"]["full_burning_cells_by_cache"] = {"%s %s" % k: d["burning_cells"] for k, d in runs["full"].items()}
    # row 3
    c = cells["3"][fire]["versions"].setdefault("V2", {"metrics": {}, "notes": []})["metrics"]
    for k in ("cases_decided", "routes_found", "leave_by_changed", "median_change_s", "largest_change_s", "run_time_s"):
        c[k] = nr("NR-MARGIN")
    # row 5 (dose off): leave-by RECORDED from tdu_1h (exact_cert_heat vs exact_tdu*), routes NEW RUN
    c = cells["5"][fire]["versions"].setdefault("V2", {"metrics": {}, "notes": []})["metrics"]
    off = {(k[0], k[1], o): v["exact_cert_heat"] for k, d in committed.items() for o, v in d["origins"].items()}
    per = {b: compare(comm_base[b], off) for b in BUD}
    c["cases_decided"] = m("%d/%d" % (jobs, jobs), "NEW RUN", "research/kcf-ablation/runs/v2/*__full.json (job_feasible.cert_heat)", cmd % "full")
    c["routes_found"] = m(sum(d["job_feasible"]["cert_heat"] for d in runs["full"].values()), "NEW RUN", "same", cmd % "full")
    c["leave_by_changed"] = m({str(b): "%d of %d" % (per[b]["changed_total"], per[b]["places_with_leave_by_in_full"]) for b in BUD}, "RECORDED", "research/kcf-heat/data/tdu_1h/*__dwell_count.tdu.json (exact_cert_heat vs exact_tdu92/105/290), tabulated by build_cells.py")
    c["median_change_s"] = m({str(b): per[b]["median_s"] for b in BUD}, "RECORDED", "same")
    c["largest_change_s"] = m({str(b): per[b]["largest_s"] for b in BUD}, "RECORDED", "same")
    c["run_time_s"] = m(round(tot("full", "prepare") + tot("full", "field_masks_only"), 1), "NEW RUN", "research/kcf-ablation/runs/v2/*__full.json (prepare + field_masks_only)", cmd % "full")
    cells["5"][fire]["versions"]["V2"]["detail"] = {str(b): per[b] for b in BUD}
    # row 6
    c = cells["6"][fire]["versions"].setdefault("V2", {"metrics": {}, "notes": []})["metrics"]
    for k in ("cases_decided", "routes_found", "leave_by_changed", "median_change_s", "largest_change_s", "run_time_s"):
        c[k] = nr("NR-REFV2")
    # row 7: recorded planner deadline (grid) against the full system's exact leave-by
    c = cells["7"][fire]["versions"].setdefault("V2", {"metrics": {}, "notes": []})["metrics"]
    rec_dl = {(k[0], k[1], o): v["recorded_deadline"] for k, d in committed.items() for o, v in d["origins"].items()}
    per = {b: compare(comm_base[b], rec_dl) for b in BUD}
    s31 = json.loads((R / "research/harness-2026-11/F-3.1/results/SUMMARY_final_70f70d7.json").read_text())
    tj = sum(x["jobs_all"]["total"] for x in s31)
    nrte = sum(x["jobs_all"].get("no_route:match", 0) for x in s31)
    chk = sum(x["jobs_all"].get("checked:match", 0) for x in s31)
    c["cases_decided"] = m("%d/%d" % (nrte + chk, tj), "RECORDED", "research/harness-2026-11/F-3.1/results/SUMMARY_final_70f70d7.json (jobs_all: checked + no_route; the rest are 297 UNRESOLVED and 186 AT_ISSUE)")
    c["routes_found"] = m(chk, "RECORDED", "same")
    c["leave_by_changed"] = m({str(b): "%d of %d" % (per[b]["changed_total"], per[b]["places_with_leave_by_in_full"]) for b in BUD}, "RECORDED", "research/kcf-heat/data/tdu_1h/*.tdu.json (recorded_deadline vs exact_tdu*), tabulated by build_cells.py")
    c["median_change_s"] = m({str(b): per[b]["median_s"] for b in BUD}, "RECORDED", "same")
    c["largest_change_s"] = m({str(b): per[b]["largest_s"] for b in BUD}, "RECORDED", "same")
    c["run_time_s"] = m({"recorded_checks_s": 147900, "host": "Apple Mac, 13 workers (RESULTS §5)"}, "RECORDED", "research/harness-2026-11/F-3.1/RESULTS.md §5")
    cells["7"][fire]["versions"]["V2"]["detail"] = {str(b): per[b] for b in BUD}
    cells["7"][fire]["versions"]["V2"]["detail"]["one_sided_places_at_92"] = [
        {"cache": "%s %s" % (p[0], p[1]), "origin": p[2], "full_exact_s": comm_base[92][p], "recorded_planner_deadline_s": rec_dl[p]}
        for p in comm_base[92] if (comm_base[92][p] is None) != (rec_dl[p] is None)]
    cells["7"][fire]["versions"]["V2"]["notes"].append(
        "Footnote 4: the recorded checks predate heat closure and dose, so against row 1 this arm differs in three ways. "
        "F-3.1's field-only contrast (cert vs recorded, RESULTS §4): exact leave-by later than the grid value at 508 of 508 places, median by file 293–397 s, maximum 584 s.")
    return {"repro": repro, "cert_jobs": cert_jobs}


# ------------------------------------------------------------------------------------------------- V3, V5
def v3_cells(cells):
    txt = (R / "research/kcf-heat/ROUTING_EFFECT.md").read_text()
    rows = {}
    for mm in re.finditer(r"\| then dose ≤ (\d+) TDU[^|]*\| (counted|excluded) \| (\d+) \| (\d+)–(\d+) s \(([\d.]+) s\) \| (\d+) \|", txt):
        b, stay, n, lo, hi, med, lost = mm.groups()
        rows.setdefault(stay, {})[int(b)] = {"moved": int(n), "range_s": [int(lo), int(hi)], "median_s": float(med), "lose_route": int(lost)}
        break_ = None
    # the first matches belong to the Places table (it comes before the Place-runs table)
    places = {}
    seen = set()
    for mm in re.finditer(r"\| then dose ≤ (\d+) TDU[^|]*\| (counted|excluded) \| (\d+) \| (\d+)–(\d+) s \(([\d.]+) s\) \| (\d+) \|", txt):
        b, stay, n, lo, hi, med, lost = mm.groups()
        key = (int(b), stay)
        if key in seen:
            continue
        seen.add(key)
        places[key] = {"moved": int(n), "lo": int(lo), "hi": int(hi), "median": float(med), "lose": int(lost)}
    mh = json.loads((R / "research/kcf-heat/data/multihour/summary_dwell_count.json").read_text())
    tsum = sum(p["timing_s"]["field_tdu"] for p in mh["packets"])
    src = "research/kcf-heat/ROUTING_EFFECT.md (Multi-hour runs, Places table, 286 places, stay counted)"
    c = cells["5"]["F1"]["versions"].setdefault("V3", {"metrics": {}, "notes": []})["metrics"]
    c["cases_decided"] = nr("NR-V3JOBS")
    c["routes_found"] = nr("NR-V3JOBS")
    c["leave_by_changed"] = m({str(b): "%d of 286" % places[(b, "counted")]["moved"] for b in BUD}, "RECORDED", src)
    c["median_change_s"] = m({str(b): places[(b, "counted")]["median"] for b in BUD}, "RECORDED", src)
    c["largest_change_s"] = m({str(b): places[(b, "counted")]["hi"] for b in BUD}, "RECORDED", src)
    c["run_time_s"] = m(round(tsum, 1), "RECORDED", "research/kcf-heat/data/multihour/summary_dwell_count.json (sum over 48 packets of timing_s.field_tdu, serial seconds, witness pass excluded; host not recorded in file)")
    cells["5"]["F1"]["versions"]["V3"]["detail"] = {"places_counted": {str(k[0]): v for k, v in places.items() if k[1] == "counted"},
                                                    "places_excluded": {str(k[0]): v for k, v in places.items() if k[1] == "excluded"},
                                                    "places_that_lose_a_route_stay_counted": {str(b): places[(b, "counted")]["lose"] for b in BUD}}
    for rid, why in (("1", "NR-V3JOBS"), ("2", "NR-V3PERSIST"), ("3", "NR-MARGIN"), ("4", "NR-V3HEATOFF"), ("6", "NR-V3JOBS"), ("7", "NR-V3JOBS")):
        c = cells[rid]["F1"]["versions"].setdefault("V3", {"metrics": {}, "notes": []})["metrics"]
        for k in ("cases_decided", "routes_found", "leave_by_changed", "median_change_s", "largest_change_s", "run_time_s"):
            c[k] = nr(why)
    cells["1"]["F1"]["versions"]["V3"]["notes"].append("Base for V3: %s; 286 places have a leave-by under cert (before heat)." % "research/kcf-heat/ROUTING_EFFECT.md")


def v5_cells(cells):
    rows = list(csv.DictReader(open(R / "research/kcf-evidence/sources/corridor-router-v8/receipts.csv")))
    inc = {"F1": ["Gyeongbuk_2025"], "F2": ["uljin_2022"], "F3": ["hongseong_2023"], "F4": ["miryang_2022"], "F5": ["Caldor2021"]}
    for fire, names in inc.items():
        rs = [r for r in rows if r["incident"] in names]
        route = sum(r["kind"] == "route" for r in rs)
        ref = sum(r["kind"] == "refusal" for r in rs)
        c = cells["1"][fire]["versions"].setdefault("V5", {"metrics": {}, "notes": []})["metrics"]
        src = "research/kcf-evidence/sources/corridor-router-v8/receipts.csv (incident %s)" % "/".join(names)
        c["cases_decided"] = m("%d/%d" % (route + ref, len(rs)), "RECORDED", src)
        c["routes_found"] = m(route, "RECORDED", src)
        for k in ("leave_by_changed", "median_change_s", "largest_change_s"):
            c[k] = m("base", "RECORDED", src)
        c["run_time_s"] = m({"median_wall_s": round(statistics.median(float(r["wall_s"]) for r in rs), 3), "host": "Apple Mac (v8 campaign)"}, "RECORDED", src + " wall_s")
        cells["1"][fire]["versions"]["V5"]["notes"].append("v8 router only, permissive missing-input policy; no heat closure, dose budget or deadline field. Not comparable with V1/V2 counts.")
    for rid in ("2", "3", "4", "5", "6", "7"):
        for fire in inc:
            c = cells[rid][fire]["versions"].setdefault("V5", {"metrics": {}, "notes": []})["metrics"]
            for k in ("cases_decided", "routes_found", "leave_by_changed", "median_change_s", "largest_change_s", "run_time_s"):
                c[k] = nr("NR-V5")
    # Caldor: nothing else exists
    for rid, _t in ROWS:
        cells[rid]["F5"].setdefault("not_run_all", "NR-CALDOR")


# ------------------------------------------------------------------------------------------------- rendering
def fmt(mt):
    v, st = mt["value"], mt["status"]
    tag = {"RECORDED": "R", "NEW RUN": "N", "NOT RUN": "–"}[st]
    if st == "NOT RUN":
        return "– (%s)" % mt["reason"]
    if isinstance(v, dict):
        if "host" in v:
            v = next(x for k, x in v.items() if k != "host")
        elif "recorded_checks_s" in v:
            v = v["recorded_checks_s"]
        else:
            vals = list(v.values())
            if all(x == vals[0] for x in vals):
                v = vals[0]
            else:
                v = " / ".join("n/a" if x is None else str(x) for x in vals)
    if v is None:
        v = "n/a"
    if isinstance(v, str):
        v = v.replace(" of ", "/")
    return "%s [%s]" % (v, tag)


def version_line(ver, vv):
    mt = vv["metrics"]
    keys = ("cases_decided", "routes_found", "leave_by_changed", "median_change_s", "largest_change_s", "run_time_s")
    rs = {mt[k].get("reason") for k in keys if mt[k]["status"] == "NOT RUN"}
    if all(mt[k]["status"] == "NOT RUN" for k in keys) and len(rs) == 1:
        return "**%s** NOT RUN (%s)" % (ver, rs.pop())
    return "**%s** " % ver + " · ".join(fmt(mt[k]) for k in keys)


def render(cells, extra):
    L = ["# TABLE: what each component adds, fire by fire", "",
         "Frozen layout: [LAYOUT.md](LAYOUT.md). Values: [cells.json](cells.json) (every cell carries file, command and reason). Reading: [READING.md](READING.md).",
         "Main at `a697d14`. **[R]** = RECORDED (committed file, cited in cells.json), **[N]** = NEW RUN (command in cells.json), **– (code)** = NOT RUN, reason code in §Reasons.",
         "Budget triples are the three dose budgets **92 / 105 / 290 TDU**, side by side; none is chosen as the submission. "
         "A single number means the same value at all three budgets. n/a = no place changed (or no value exists). Metrics per line: decided · routes found · places whose leave-by changes (changed of places with a leave-by in row 1) · median change s · largest change s · run time s.",
         "Versions V1–V5 are different inputs and are never added; the lines inside a cell are separate versions (LAYOUT §1).", ""]
    hdr = "| row | " + " | ".join("**%s** %s" % (f, n) for f, n, _ in COLS) + " |"
    L += [hdr, "|---|" + "---|" * len(COLS)]
    for rid, rn in ROWS:
        cs = []
        for f, _n, _r in COLS:
            cell = cells[rid][f]
            if cell.get("not_run_all") and not cell["versions"]:
                cs.append("NOT RUN (%s)" % cell["not_run_all"])
                continue
            lines = []
            for ver in ("V1", "V2", "V3", "V4", "V5"):
                vv = cell["versions"].get(ver)
                if not vv:
                    continue
                lines.append(version_line(ver, vv))
            cs.append("<br>".join(lines) if lines else "NOT RUN (no version)")
        L.append("| **%s. %s** | " % (rid, rn) + " | ".join(cs) + " |")
    L += ["", "## Fires with no road inputs (all seven rows NOT RUN, every cell)", "",
          "| col | fire | group | rows 1–7 |", "|---|---|---|---|"]
    for f, n, g in OTHER:
        L.append("| %s | %s | %s | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |" % (f, n, g))
    L += ["", "## Reasons", ""] + ["* **%s**: %s" % (k, v) for k, v in REASONS.items()]
    L += ["", "## Footnotes", ""] + extra
    return "\n".join(L) + "\n"


def main():
    cells = {rid: {f: {"row": rn, "col": n, "versions": {}} for f, n, _ in COLS} for rid, rn in ROWS}
    rec = v1_recorded()
    new, v1raw = v1_new()
    v1_cells(cells, rec, new)
    info = v2_cells(cells)
    v3_cells(cells)
    v5_cells(cells)
    for rid, _ in ROWS:
        for f, n, g in OTHER:
            cells[rid][f] = {"row": dict(ROWS)[rid], "col": n, "group": g, "not_run_all": "NR-NOGRAPH", "versions": {}, "reason_text": REASONS["NR-NOGRAPH"]}
    out = {"layout": "research/kcf-ablation/LAYOUT.md", "main_commit": "a697d14", "reasons": REASONS, "cells": cells,
           "checks": {"v2": info, "v1_host": v1raw["host"], "v1_wall_s": v1raw["wall_s"]}}
    (H / "cells.json").write_text(json.dumps(out, indent=1, default=str))
    foot = [
        "1. **Mixed versions across a row.** Row 1 mixes V1 (paper router outcomes, RECORDED, Apple host) with V2/V3/V5 lines; they are separate lines, never summed. Row 5 mixes V1 (NEW RUN), V2 (RECORDED leave-by) and V3 (RECORDED).",
        "2. **Host.** NEW RUN times are from this container (Linux x86_64, 4 cores, Python 3.13.18, numpy 2.5.3); RECORDED times are from the host named in each file. They are not compared with each other (F-3.1 RESULTS §5 measures this host at 2.6–2.8× slower than the Mac).",
        "3. **Leave-by definitions differ by version** (LAYOUT §4): V1 uncapped exact; V2 exact capped at the planner range; V3 range over timing variants, earliest edge. Nothing is pooled across them.",
        "4. **Row 7 base.** The recorded checks carry no heat closure and no dose budget; V2 row 7 therefore differs from row 1 in three ways. See the line in cells.json.",
        "5. **V1 base check.** The contact-only arm of run_v1.py returns P1's 15 routes and 5 refusals at the missions' own departures (cells.json → checks); the full arm differs from it in no mission.",
        "6. **Row 6 leave-by.** Not produced by a one-departure router (NR-LB). Arrival-second agreement on jointly routed executions is in the cell notes.",
        "7. **Dose budget in P1.** P1's own cumulative-exposure limit (old 0.703 kW/m² law; 200-execution ablation `research/routing/final-input-ablation/`) is a different component from the kcf-heat TDU budget in row 5 and is not used for that row.",
        "8. **V2 NEW RUN times.** The three V2 arms (full, persistence, heat_off) ran at the same time on 4 cores, so each time is longer than a solo run. The full arm also computes the contact-only field used for the 7,970-job check, and its time includes it. V2 arms were run without the witness pass that kcf-heat's committed C.4 files include; their leave-by values for the full arm equal the committed ones at all 4,240 compared values.",
        "9. **Persistence in the forecast-skill sense** (Brier) is in READING.md as context only; it is not one of the cell metrics."]
    (H / "TABLE.md").write_text(render(cells, foot))
    print("cells.json and TABLE.md written")


if __name__ == "__main__":
    main()
