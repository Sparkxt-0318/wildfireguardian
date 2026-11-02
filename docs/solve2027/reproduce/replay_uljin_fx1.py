"""Linux reproduction with extended budget -- NOT the evaluated 30 s macOS benchmark.

Replays the recorded Uljin FX1 final-panel request (region uljin_2022, input time 2022-03-04T03:00:00Z) once through
``wfg_latest.api.route_and_check`` with an EXTENDED complete-request budget (default 300 s instead of the evaluated
30 s), then checks the outcome against the recorded campaign:

  * authoritative status CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN, runtime whole-road check CERTIFIED_ADMISSIBLE,
  * arrival 3,119 s, 512 road legs, 120 s required stay at the destination,
  * the route hash recorded for this mission in the final-input ablation (policy A4 = full policy),
  * the offline independent checker's verdict, with no contradiction.

Why an extended budget: the evaluated host is native macOS on an Apple M5 Pro. On slower Linux hosts the unchanged
30 s budget can end this mission as unresolved/TIMEOUT (api/reports/LINUX_VM_REPLAY_2026-10-17.md). That is correct
behaviour -- unresolved is never reported as safe -- but it does not show whether the same code reproduces the same
journey. A longer budget answers only that question. It is not a benchmark: its timings are not comparable with the
recorded 30 s campaign, and nothing in the frozen kit, the Route-Check API (api/config.py BUDGET_S = 30.0) or the
recorded results is changed. ``--also-evaluated-budget`` additionally runs the same request once with the evaluated
30 s budget and REPORTS (never asserts) what this host returns.

Expected values are read from the repository's recorded results and cross-checked against the documented numbers:
  research/routing/INDEPENDENT_ROWS.csv                   (state, arrival; arm RDA_CAND, both repetitions)
  research/routing/final-input-ablation/data/ROWS.csv     (n_legs, route_hash, authoritative_decision; policy A4)
  data/routing/latest_inputs_try02/requests/uljin_2022/20220304T030000Z_FX1.json   (required stay, "dwell")

Usage (repository root, Python 3.12, after ``python tools/fetch_routing_inputs.py``; Linux needs GNU /usr/bin/time):
  python docs/solve2027/reproduce/replay_uljin_fx1.py --out artifacts/solve2027/uljin-fx1
Exit status: 0 when every assertion holds, 1 when an assertion fails, 2 when a prerequisite is missing.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True     # importing the kit's controller/decision modules must not write into the frozen kit

REPO = Path(__file__).resolve().parents[3]
LABEL = "Linux reproduction with extended budget — not the evaluated 30 s macOS benchmark"
EVALUATED_BUDGET_S = 30.0          # api/config.py BUDGET_S and the route_and_check default; never changed here
REGION, CASE = "uljin_2022", "20220304T030000Z_FX1"
CUTOFF = CASE.split("_")[0]

# Documented numbers (README.md "Replay a recorded Korean routing case"; integration/README.md). The script also reads
# the recorded values from the result files below and requires both to agree, so a drifted document or file fails.
DOCUMENTED = {"authoritative_status": "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN", "arrival_s": 3119, "legs": 512, "dwell_s": 120}
INDEPENDENT_ROWS = REPO / "research" / "routing" / "INDEPENDENT_ROWS.csv"
ABLATION_ROWS = REPO / "research" / "routing" / "final-input-ablation" / "data" / "ROWS.csv"


class Prerequisite(Exception):
    """A missing input or tool: nothing was run."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(Path(path).read_text())


def single(values: set, what: str):
    if len(values) != 1:
        raise SystemExit("recorded repetitions disagree for %s: %s" % (what, sorted(map(str, values))))
    return next(iter(values))


def recorded_expectations(request: dict) -> dict:
    """The recorded outcome of this mission, read from the repository's result files (never typed in)."""
    rows = [r for r in csv.DictReader(INDEPENDENT_ROWS.open())
            if r["region"] == REGION and r["case_id"] == CASE and r["arm"] == "RDA_CAND"]
    abl = [r for r in csv.DictReader(ABLATION_ROWS.open())
           if r["cohort"] == REGION and r["case_id"] == CASE and r["policy"] == "A4"]
    if len(rows) != 2 or len(abl) != 2:
        raise SystemExit("expected two recorded repetitions in each result file, found %d and %d" % (len(rows), len(abl)))
    rec = {
        "state": single({r["state"] for r in rows}, "INDEPENDENT_ROWS state"),
        "arrival_s": int(single({r["arrival"] for r in rows}, "INDEPENDENT_ROWS arrival")),
        "recorded_wall_s_m5_pro": [float(r["wall_s"]) for r in rows],
        "authoritative_status": single({r["authoritative_decision"] for r in abl}, "ablation authoritative_decision"),
        "legs": int(single({r["n_legs"] for r in abl}, "ablation n_legs")),
        "route_hash": single({r["route_hash"] for r in abl}, "ablation route_hash"),
        "ablation_arrival_s": int(single({r["arrival"] for r in abl}, "ablation arrival")),
        "dwell_s": int(request["destinations"][0]["dwell"]),
        "sources": {"state_arrival_wall": str(INDEPENDENT_ROWS.relative_to(REPO)),
                    "legs_route_hash_status": str(ABLATION_ROWS.relative_to(REPO)),
                    "dwell": "data/routing/latest_inputs_try02/requests/%s/%s.json" % (REGION, CASE)},
    }
    agree = {"authoritative_status": rec["authoritative_status"], "arrival_s": rec["arrival_s"], "legs": rec["legs"],
             "dwell_s": rec["dwell_s"]}
    if agree != DOCUMENTED or rec["ablation_arrival_s"] != rec["arrival_s"] or rec["state"] != "CHECKED_CENTRE_OPTIMUM":
        raise SystemExit("recorded results %s disagree with the documented values %s" % (agree, DOCUMENTED))
    return rec


def gnu_time_version() -> str | None:
    try:
        p = subprocess.run(["/usr/bin/time", "--version"], capture_output=True, text=True, timeout=10)
        return (p.stdout + p.stderr).strip().splitlines()[0] if (p.stdout + p.stderr).strip() else None
    except Exception:
        return None


def preflight(inputs: Path, kit: Path) -> dict:
    missing = [t for t in ("/usr/bin/time", "/bin/ps") if not os.access(t, os.X_OK)]
    if missing:
        raise Prerequisite("%s missing: the kit controller launches and measures every request with GNU /usr/bin/time "
                           "and /bin/ps (Debian/Ubuntu: sudo apt-get install time procps)" % ", ".join(missing))
    if platform.system() == "Linux" and "GNU" not in (gnu_time_version() or ""):
        raise Prerequisite("/usr/bin/time is not GNU time (the kit runs `/usr/bin/time -v` on Linux); install the `time` package")
    paths = {"graph": inputs / "graphs" / REGION / "graph.json",
             "packet": inputs / "latest_inputs_try02" / "packets" / REGION / CUTOFF,
             "request": inputs / "latest_inputs_try02" / "requests" / REGION / (CASE + ".json")}
    for p in (paths["graph"], paths["packet"] / "HAZARD.json", paths["request"], kit / "CANDIDATE_MANIFEST.json"):
        if not p.is_file():
            raise Prerequisite("missing %s; first run: python tools/fetch_routing_inputs.py" % p)
    return paths


def package_identity() -> dict:
    """The imported wfg_latest must be the reviewed 1.0.0 copy that the repository carries in integration/src."""
    import wfg_latest
    from wfg_latest import api as wapi
    installed = Path(wapi.__file__).resolve()
    repo_copy = REPO / "integration" / "src" / "wfg_latest" / "api.py"
    ident = {"version": wfg_latest.__version__, "api_py": str(installed), "api_py_sha256": sha256(installed),
             "repository_api_py_sha256": sha256(repo_copy)}
    if ident["version"] != "1.0.0" or ident["api_py_sha256"] != ident["repository_api_py_sha256"]:
        raise Prerequisite("imported wfg_latest is not the reviewed 1.0.0 copy in integration/src: %s" % ident)
    return ident


def route_hash_of(result: dict):
    """Hash of the published route, read exactly as the Route-Check API reads it (api/runner.py)."""
    stage = (result.get("result") or {}).get("published_stage")
    hashes = [s.get("route_sha256") for s in result.get("rda_stages") or []
              if isinstance(s, dict) and s.get("stage") == stage and s.get("route_sha256")]
    return (hashes[-1] if hashes else None), stage


def attempt(paths: dict, kit: Path, out: Path, budget_s: float, python: str, label: str) -> dict:
    """One controlled attempt through wfg_latest.api.route_and_check plus the authoritative journey it published."""
    from wfg_latest import api as wapi
    t0 = time.perf_counter()
    summary = wapi.route_and_check(kit_root=kit, packet_dir=paths["packet"], graph=paths["graph"], request=paths["request"],
                                   out_dir=out, arm="RDA_CAND", python=python, budget_s=budget_s, check=True, label=label)
    call_wall_s = time.perf_counter() - t0
    # Recompute the authoritative decision from the frozen worker records, exactly as route_and_check and the
    # Route-Check API do (api/runner.py), to read the journey legs it does not return.
    import journey_decision_v2_1 as JD   # route_and_check put the kit's decision/ and runner/ folders on sys.path
    result = read_json(out / "RESULT.json") if (out / "RESULT.json").exists() else {}
    receipt = read_json(out / "COMPLETE_PROCESS_RECEIPT.json") if (out / "COMPLETE_PROCESS_RECEIPT.json").exists() else {}
    decision = JD.decision_from_worker_record(result, receipt, read_json(out / "JOB.json"), graph=read_json(paths["graph"]),
                                              request=read_json(paths["request"]),
                                              hazard=read_json(paths["packet"] / "HAZARD.json"),
                                              optimality_certificate=result.get("optimality_certificate"),
                                              refusal_certificate=result.get("refusal_certificate"))
    journey = decision.get("journey") or {}
    legs = journey.get("legs") or []
    rhash, stage = route_hash_of(result)
    # route_and_check writes the offline independent checker's full report next to the attempt folder.
    ind_path = out.parent / (out.name + "_INDEPENDENT.json")
    ind = read_json(ind_path) if ind_path.is_file() else {}
    grammar = ind.get("grammar") or {}
    return {"budget_s": budget_s, "label": label, "route_and_check": summary,
            "call_wall_s_including_independent_check": call_wall_s,
            "recomputed_authoritative_status": decision.get("authoritative_status"),
            "journey": {"arrival_s": journey.get("arrival"), "legs_total": len(legs),
                        "edge_legs": sum(1 for g in legs if g.get("kind") == "EDGE"),
                        "wait_legs": sum(1 for g in legs if g.get("kind") == "WAIT"),
                        "destination": journey.get("destination")},
            "independent_report": str(ind_path) if ind else None,
            "independent_grammar": {k: grammar.get(k) for k in ("ok", "arrival", "mission_end", "legs")} if ind else None,
            "independent_whole_road_contact": (ind.get("whole_road_contact") or {}).get("status") if ind else None,
            "route_sha256": rhash, "published_stage": stage,
            "receipt": {k: receipt.get(k) for k in ("on_time_complete_publication", "exit_code", "cleanup_state",
                                                     "deadline_termination_requested", "memory_guard_triggered",
                                                     "external_launch_to_completion_wall_s", "raw_primary_status")}}


def assertions(run: dict, rec: dict, request: dict) -> list:
    s = run["route_and_check"]
    ind = s.get("independent") or {}
    classification = ind.get("classification")
    overall = classification.get("overall") if isinstance(classification, dict) else classification
    gram = run.get("independent_grammar") or {}
    stay = None
    if gram.get("arrival") is not None and gram.get("mission_end") is not None:
        stay = gram["mission_end"] - gram["arrival"]
    checks = [
        ("on-time complete publication within the extended budget", s.get("on_time") is True, s.get("on_time")),
        ("process cleanup CLEAN", s.get("cleanup_state") == "CLEAN", s.get("cleanup_state")),
        ("authoritative status equals the recorded status", s.get("authoritative_status") == rec["authoritative_status"],
         s.get("authoritative_status")),
        ("recomputed decision equals route_and_check's decision",
         run["recomputed_authoritative_status"] == s.get("authoritative_status"), run["recomputed_authoritative_status"]),
        ("successful journey (publication authority)", s.get("successful_journey") is True, s.get("successful_journey")),
        ("runtime whole-road check CERTIFIED_ADMISSIBLE", s.get("runtime_whole_road") == "CERTIFIED_ADMISSIBLE",
         s.get("runtime_whole_road")),
        ("arrival equals the recorded arrival", s.get("arrival_s") == rec["arrival_s"] == run["journey"]["arrival_s"],
         s.get("arrival_s")),
        ("journey legs equal the recorded legs", run["journey"]["legs_total"] == rec["legs"], run["journey"]["legs_total"]),
        ("every leg is a road leg (no waiting), as recorded",
         run["journey"]["edge_legs"] == rec["legs"] and run["journey"]["wait_legs"] == 0,
         {"edge": run["journey"]["edge_legs"], "wait": run["journey"]["wait_legs"]}),
        ("journey ends at the request's destination", run["journey"]["destination"] == request["destinations"][0]["node"],
         run["journey"]["destination"]),
        ("required destination stay equals the recorded stay (exposure checked including the stay)",
         rec["dwell_s"] == DOCUMENTED["dwell_s"] and request.get("exposure_scope") == "including_dwell",
         {"dwell_s": rec["dwell_s"], "exposure_scope": request.get("exposure_scope")}),
        ("route hash equals the recorded full-policy route hash", run["route_sha256"] == rec["route_hash"], run["route_sha256"]),
        # route_and_check reports status "FAILED" only when the offline checker did not finish; success carries no status.
        ("offline independent checker completed", ind.get("status") != "FAILED" and run.get("independent_report") is not None,
         ind.get("status") or "completed"),
        ("independent trajectory check: valid, same arrival and legs, mission ends one required stay after arrival",
         gram.get("ok") is True and gram.get("arrival") == rec["arrival_s"] and gram.get("legs") == rec["legs"]
         and stay == rec["dwell_s"], dict(gram, stay_s=stay)),
        ("independent whole-road contact CLEAR (road, waits and stay)", run.get("independent_whole_road_contact") == "CLEAR",
         run.get("independent_whole_road_contact")),
        ("independent checker certifies the optimum",
         overall == "INDEPENDENTLY_CERTIFIED_OPTIMAL" and ind.get("verdict") == "INDEPENDENTLY_CERTIFIED_OPTIMAL",
         {"classification": overall, "verdict": ind.get("verdict")}),
        ("independent checker reports no contradiction", not ind.get("contradictions"), ind.get("contradictions")),
    ]
    return [{"check": name, "passed": bool(ok), "observed": observed} for name, ok, observed in checks]


def load_average():
    """Host load (1, 5, 15 min) - other work on a shared host inflates every timing reported here."""
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        return None


def git_commit() -> str | None:
    """HEAD of this checkout; in a copy without git metadata (e.g. the Docker image) the WFG_API_GIT_COMMIT fallback."""
    try:
        p = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:
        pass
    return os.environ.get("WFG_API_GIT_COMMIT")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="fresh directory; existing outputs are never overwritten")
    ap.add_argument("--budget-s", type=float, default=300.0,
                    help="EXTENDED complete-request budget for this non-benchmark reproduction (default 300)")
    ap.add_argument("--also-evaluated-budget", action="store_true",
                    help="also run once with the evaluated 30 s budget and report (never assert) the outcome")
    ap.add_argument("--markdown-summary", type=Path, default=None,
                    help="also append a short Markdown summary to this file (e.g. $GITHUB_STEP_SUMMARY)")
    ap.add_argument("--inputs", type=Path, default=REPO / "data" / "routing")
    ap.add_argument("--kit", type=Path, default=REPO / "integration" / "kit")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args(argv)
    out = a.out.resolve()
    if out.exists():
        print("Output exists: %s (choose a fresh --out)" % out, file=sys.stderr)
        return 2
    if a.budget_s < EVALUATED_BUDGET_S:
        print("--budget-s must be at least the evaluated %.0f s" % EVALUATED_BUDGET_S, file=sys.stderr)
        return 2
    print("=" * 100)
    print(LABEL.upper())
    print("Recorded Uljin FX1 request, extended budget %.0f s (the evaluated benchmark is 30 s on native macOS, Apple M5 Pro)."
          % a.budget_s)
    print("=" * 100, flush=True)
    try:
        paths = preflight(a.inputs.resolve(), a.kit.resolve())
        request = read_json(paths["request"])
        rec = recorded_expectations(request)
        ident = package_identity()
    except Prerequisite as exc:
        print("PREREQUISITE MISSING: %s" % exc, file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    load_at_start = load_average()
    runs = {"extended": attempt(paths, a.kit.resolve(), out / "extended_budget", a.budget_s, a.python,
                                "SOLVE2027_LINUX_REPRO_EXTENDED_%ds" % int(a.budget_s))}
    checks = assertions(runs["extended"], rec, request)
    if a.also_evaluated_budget:
        ev = attempt(paths, a.kit.resolve(), out / "evaluated_budget_report_only", EVALUATED_BUDGET_S, a.python,
                     "SOLVE2027_LINUX_REPORT_ONLY_30s")
        ev["note"] = ("Report only, never asserted. The evaluated campaign ran on native macOS (Apple M5 Pro); on a slower "
                      "host the unchanged 30 s budget can end this mission unresolved/TIMEOUT, which is never reported as safe.")
        runs["evaluated_budget_report_only"] = ev
    ext = runs["extended"]["route_and_check"]
    report = {
        "label": LABEL, "benchmark": False, "evaluated_configuration": False,
        "why": "The evaluated host is native macOS (Apple M5 Pro) with a fixed 30 s budget. This run only checks that the "
               "same code reproduces the recorded journey on this host; its timings are not benchmark results.",
        "mission": {"region": REGION, "case_id": CASE, "arm": "RDA_CAND"},
        "budgets_s": {"this_run": a.budget_s, "evaluated": EVALUATED_BUDGET_S},
        "within_evaluated_30s_budget": bool(ext.get("wall_s") is not None and ext["wall_s"] <= EVALUATED_BUDGET_S),
        "host": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
                 "cpu_count": os.cpu_count(), "gnu_time": gnu_time_version(), "evaluated_host": False,
                 "load_average_1_5_15_min": {"start": load_at_start, "end": load_average()}},
        "git_commit": git_commit(), "started_at": started, "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "wfg_latest": ident,
        "input_sha256": {"graph": sha256(paths["graph"]), "hazard": sha256(paths["packet"] / "HAZARD.json"),
                         "request": sha256(paths["request"])},
        "recorded": rec, "documented": DOCUMENTED, "runs": runs, "assertions": checks,
        "passed": all(c["passed"] for c in checks),
    }
    (out / "REPRODUCTION_SUMMARY.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print()
    for c in checks:
        print("  [%s] %s: %s" % ("PASS" if c["passed"] else "FAIL", c["check"], json.dumps(c["observed"], default=str)))
    print()
    print("extended budget %.0f s: request wall_s %.2f s (%s the evaluated 30 s budget); call incl. independent check %.2f s"
          % (a.budget_s, ext.get("wall_s") or float("nan"), "within" if report["within_evaluated_30s_budget"] else "OVER",
             runs["extended"]["call_wall_s_including_independent_check"]))
    print("recorded M5 Pro wall_s for this mission (both repetitions, 30 s budget): %s"
          % ", ".join("%.2f" % w for w in rec["recorded_wall_s_m5_pro"]))
    if "evaluated_budget_report_only" in runs:
        e = runs["evaluated_budget_report_only"]["route_and_check"]
        print("report-only 30 s attempt on this host: %s%s, wall_s %s (not asserted)"
              % (e.get("authoritative_status"), " / " + str(e.get("unresolved_reason")) if e.get("unresolved_reason") else "",
                 "%.2f" % e["wall_s"] if e.get("wall_s") is not None else "n/a"))
    print("summary: %s" % (out / "REPRODUCTION_SUMMARY.json"))
    print(("REPRODUCED: " if report["passed"] else "NOT REPRODUCED: ") + LABEL)
    if a.markdown_summary is not None:
        with open(a.markdown_summary, "a", encoding="utf-8") as md:
            md.write(markdown(report))
    return 0 if report["passed"] else 1


def markdown(report: dict) -> str:
    ext = report["runs"]["extended"]
    s = ext["route_and_check"]
    gram = ext.get("independent_grammar") or {}
    stay = "n/a"
    if gram.get("mission_end") is not None and gram.get("arrival") is not None:
        stay = "%g" % (gram["mission_end"] - gram["arrival"])
    lines = ["### %s" % report["label"], "",
             "Recorded Uljin FX1 request replayed through `wfg_latest.api.route_and_check` with an extended %.0f s budget "
             "(evaluated benchmark: 30 s on native macOS, Apple M5 Pro). Timings below are not benchmark results." %
             report["budgets_s"]["this_run"], "",
             "| | this host | recorded |", "|---|---|---|",
             "| authoritative status | `%s` | `%s` |" % (s.get("authoritative_status"),
                                                          report["recorded"]["authoritative_status"]),
             "| arrival | %s s | %s s |" % (s.get("arrival_s"), report["recorded"]["arrival_s"]),
             "| road legs | %s | %s |" % (ext["journey"]["legs_total"], report["recorded"]["legs"]),
             "| required stay (independent checker) | %s s | %s s |" % (stay, report["recorded"]["dwell_s"]),
             "| route hash | `%s…` | `%s…` |" % (str(ext.get("route_sha256"))[:16], report["recorded"]["route_hash"][:16]),
             "| independent checker | `%s` | |" % ((s.get("independent") or {}).get("verdict")),
             "| request wall time | %.2f s (extended budget) | %s s (M5 Pro, 30 s budget) |" % (
                 s.get("wall_s") or float("nan"), " / ".join("%.2f" % w for w in report["recorded"]["recorded_wall_s_m5_pro"])),
             ""]
    ev = report["runs"].get("evaluated_budget_report_only")
    if ev:
        e = ev["route_and_check"]
        lines += ["Report only (never asserted): the same request with the evaluated 30 s budget on this host returned `%s`%s "
                  "after %s s. Unresolved is never reported as safe." % (
                      e.get("authoritative_status"), " (`%s`)" % e["unresolved_reason"] if e.get("unresolved_reason") else "",
                      "%.2f" % e["wall_s"] if e.get("wall_s") is not None else "n/a"), ""]
    lines += ["Host: %s, %s CPUs, Python %s, load average at start %s. Assertions: %d/%d passed." % (
        report["host"]["platform"], report["host"]["cpu_count"], report["host"]["python"],
        report["host"]["load_average_1_5_15_min"]["start"],
        sum(c["passed"] for c in report["assertions"]), len(report["assertions"])), ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
