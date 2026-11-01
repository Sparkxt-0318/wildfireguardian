#!/usr/bin/env python3
"""E3 scenario robustness (Track C, Phase 1 batch 1), compute step: how often does a plan whose trips are
checked in all K members fail in FRESH members of the same SYNTHETIC hazard model, how does that depend on K,
and which default safety margin keeps the out-of-sample violation of delivered residents below 5 % / 1 %?

Pre-registration: README.md in this folder (committed before the main run). Run from the worktree root inside
the shared bench lock (program rule 6); the analysis is ``e3_analyze.py``:

    .venv/bin/python program/benchlock.py --label E3-compute -- \\
        .venv/bin/python evacplan/experiments/E3-scenario-robustness/e3_compute.py compute

``compute`` regenerates every dev instance's hazard model with 8 + 32 + 256 members (the first 8 must equal
the instance's members bit for bit), makes the plans of ``config.yaml`` (B1 on blocks of instance members and
of fresh planning members, B2 on the instance members), computes support sets by greedy removal, and checks
every plan against fresh check members one member at a time, tier by tier, until the time budget is used.
Raw records go to ``evacplan/runs/E3-scenario-robustness/`` (git-ignored; the B1 plans and checks regenerate,
the B2 plans do not, because B2's time-limited search depends on machine load; a copy of the batch-1 records is
committed under ``raw/``, batch-1 review E3-D8). ``selftest`` checks a
finished run directory (used after the smoke run, ``config_smoke.yaml``, before the main run starts).

Data and rules. The frozen dev split only, regenerated through ``evacplan.instances`` (fingerprints verified);
refused when ``EVACPLAN_MILESTONE`` is set (rule 5). Fresh members are further draws of each instance's own
SYNTHETIC hazard model: ``hazard_contract.synthetic`` with the instance's seed, ignition, rate, direction, grid
and horizon, and the generator's post-processing (ignitions floored to whole seconds, persistent burning); the
generator and the frozen instances are untouched. Every verdict comes from ``evacplan.oracle`` (rule 3): a plan
is checked against each fresh member with ``Oracle.check_plan`` on a one-member scenario set built from that
member; this file only reads (compares) states. Unresolved is never delivered (rule 4): a trip that is not
``checked`` in a fresh member is a violation there, whatever its cause.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

import hazard_contract as hc
from evacplan.generators import synthetic as syn
from evacplan.harness import MARGINS_MIN, delivered_by_margin, delivered_slacks, host_string
from evacplan.instances import load_entry, load_split
from evacplan.methods import get_method
from evacplan.oracle import Oracle, State
from evacplan.schema import Solution

EXP_DIR = Path(__file__).resolve().parent
EVACPLAN_DIR = EXP_DIR.parents[1]
REPO_DIR = EVACPLAN_DIR.parent
CONFIG_PATH = EXP_DIR / "config.yaml"
RUNS_DIR = EVACPLAN_DIR / "runs" / "E3-scenario-robustness"
FIG_DIR = EXP_DIR / "figures"
LABEL = "SYNTHETIC"
DATA: dict = {}        # instance id -> (entry, instance, scenario set, ig, ex, sup); inherited by forked workers


# ----------------------------------------------------------------------------------- basics
def load_config(path: Path | str | None = None) -> dict:
    return yaml.safe_load(Path(path or CONFIG_PATH).read_text())


def guard_rule5() -> None:
    if os.environ.get("EVACPLAN_MILESTONE"):
        raise SystemExit("refused: EVACPLAN_MILESTONE is set; E3 uses the dev set only (program rule 5)")


COMPUTE_PATHS = ("evacplan/src", "evacplan/instances", "hazard_contract/src",
                 "evacplan/experiments/E3-scenario-robustness/e3_compute.py",
                 "evacplan/experiments/E3-scenario-robustness/config.yaml",
                 "evacplan/experiments/E3-scenario-robustness/config_smoke.yaml")


def git_head() -> str:
    """HEAD, plus ``+dirty`` if any file that affects this step's output (``COMPUTE_PATHS``) is uncommitted
    (the analysis script and the README do not affect the raw records)."""
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True, check=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *COMPUTE_PATHS],
                           cwd=REPO_DIR, capture_output=True, text=True, check=True).stdout
    return out.stdout.strip() + ("+dirty" if dirty.strip() else "")


def boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


def size_of(iid: str) -> str:
    return iid.split("-")[1]


def state_code(state) -> str:
    if state == State.CHECKED:
        return "0"
    if state == State.UNRESOLVED:
        return "1"
    return "2"


# ---------------------------------------------------------------------------------- members
def extended_members(entry, ss, k_total: int, k_instance: int):
    """The instance's SYNTHETIC hazard model with ``k_total`` members (same seed, ignition, rate, direction,
    grid and horizon; ignitions floored to whole seconds; persistent burning). The first ``k_instance`` draws
    must equal the instance's members bit for bit (``hazard_contract.synthetic`` draws members one after the
    other from one generator), else the instance is refused."""
    cfg = syn.SyntheticConfig.model_validate(entry.config)
    fire = syn._Fire(cfg, syn.SIZES[cfg.size], np.zeros(2))
    pv = ss.meta.provenance
    if int(fire.seed) != int(pv["seed"]):
        raise RuntimeError(f"{entry.id}: hazard seed {fire.seed} != provenance {pv['seed']}")
    raw = hc.synthetic(K=k_total, height=fire.height, width=fire.width, cell_m=syn.CELL_M, x0=fire.x0, y0=fire.y0,
                       crs_epsg=syn.CRS_EPSG, ignition_xy=(float(pv["ignition_xy"][0]), float(pv["ignition_xy"][1])),
                       t_ignition_s=syn.T_IGNITION_S, ros_m_s=float(pv["ros_m_s"]),
                       spread_dir_deg=float(pv["spread_dir_deg"]), horizon_s=fire.horizon,
                       burn_duration_s=syn.PERSIST_S, issue_time_utc=syn.ISSUE_TIME_UTC, heat=fire.heat,
                       seed=fire.seed)
    ig = np.floor(raw.ignite_s)
    ex = np.where(np.isfinite(ig), ig + syn.PERSIST_S, np.inf)
    sup = np.array(raw.supported, dtype=bool)
    k = k_instance
    same = (ig[:k].tobytes() == np.ascontiguousarray(ss.ignite_s, dtype=np.float64).tobytes()
            and ex[:k].tobytes() == np.ascontiguousarray(ss.extinguish_s, dtype=np.float64).tobytes()
            and sup[:k].tobytes() == np.ascontiguousarray(ss.supported, dtype=bool).tobytes())
    if not same:
        raise RuntimeError(f"{entry.id}: the first {k} regenerated members differ from the instance's members")
    return ig, ex, sup


def member_set(ss, ig, ex, sup, ks, role: str) -> hc.ScenarioSet:
    """A scenario set of the listed members (SYNTHETIC, the instance's meta with K replaced)."""
    ks = [int(k) for k in ks]
    meta = hc.ScenarioMeta(**{**ss.meta.model_dump(), "K": len(ks), "provenance": {
        **ss.meta.provenance, "e3_role": role, "e3_members": ks,
        "e3_note": "SYNTHETIC: members of the instance's hazard model regenerated with more draws (E3)"}})
    return hc.ScenarioSet(ig[ks], ex[ks], sup[ks], meta)


# ------------------------------------------------------------------------------------ plans
def plan_specs(cfg: dict) -> dict[str, dict]:
    """Plan id -> arm, K, planning members (absolute indices) and method, in config order."""
    k_inst, p = cfg["members"]["instance"], cfg["members"]["fresh_plan"]
    out: dict[str, dict] = {}
    for K in cfg["plans"]["armA_K"]:
        for g in range(k_inst // K):
            out[f"A{K}-g{g}"] = {"arm": "A", "K": K, "members": list(range(g * K, g * K + K)), "method": "b1_greedy"}
    for K in cfg["plans"]["armB_K"]:
        for g in range(p // K):
            out[f"B{K}-g{g}"] = {"arm": "B", "K": K, "members": list(range(k_inst + g * K, k_inst + g * K + K)),
                                 "method": "b1_greedy"}
    if cfg["plans"].get("b2"):
        out["B2-A8"] = {"arm": "B2", "K": k_inst, "members": list(range(k_inst)), "method": "b2_vrptw"}
    return out


def planning_set(iid: str, spec: dict, k_inst: int) -> hc.ScenarioSet:
    e, inst, ss, ig, ex, sup = DATA[iid]
    if spec["members"] == list(range(k_inst)):
        return ss                                # the instance's own scenario set (what the harness uses)
    return member_set(ss, ig, ex, sup, spec["members"], "plan")


def trip_records(plan) -> list[dict]:
    """Per trip in plan order: vehicle and trip index, residents, state code, cause and the delivered
    residents' safety slack (ASSUMPTIONS #91, the prefix rule; None unless checked with residents)."""
    out = []
    for vi, v in enumerate(plan.vehicles):
        for ti, t in enumerate(v.trips):
            n = int(t.counts.total)
            slack = None
            if t.state == State.CHECKED and n:
                prefix = [lg.slack_s for lg in v.legs if lg.action <= t.action]
                slack = float(min(prefix))
            out.append({"v": vi, "t": ti, "n": n, "state": state_code(t.state), "cause": t.cause, "slack_s": slack})
    return out


def in_sample(plan) -> dict:
    trips = trip_records(plan)
    mine = sorted((r["slack_s"], r["n"]) for r in trips if r["slack_s"] is not None)
    if mine != sorted(delivered_slacks(plan)):
        raise AssertionError("per-trip slacks disagree with evacplan.harness.delivered_slacks")
    return {"delivered": int(plan.delivered_total), "unresolved": int(plan.unresolved_total),
            "model_no_route": int(plan.model_no_route_total), "not_planned": int(plan.not_planned_total),
            "min_slack_s": plan.min_slack_s, "by_margin_min": {str(k): v for k, v in delivered_by_margin(plan).items()},
            "trips": trips}


def _plan_task(iid: str, pid: str, spec: dict, k_inst: int, budget_s: float, seed: int,
               want_support: bool = False, prev_solution: str | None = None) -> dict:
    """Make one plan (or reuse ``prev_solution``), check it in-sample with the oracle, and optionally find its
    support set (greedy removal)."""
    e, inst, ss, ig, ex, sup = DATA[iid]
    pset = planning_set(iid, spec, k_inst)
    t0 = time.monotonic()
    if prev_solution is None:
        res = get_method(spec["method"]).solve(inst, pset, budget_s=budget_s, seed=seed, deadline=t0 + budget_s)
        solution, info, diag = res.solution, res.info, res.diagnostics
    else:
        solution, info, diag = Solution.model_validate_json(prev_solution), {"reused": True}, {}
    runtime = time.monotonic() - t0
    t1 = time.monotonic()
    rec = in_sample(Oracle(inst, pset).check_plan(solution))
    out = {"instance": iid, "plan": pid, "arm": spec["arm"], "K": spec["K"], "members": spec["members"],
           "method": spec["method"], "runtime_s": round(runtime, 3), "oracle_s": round(time.monotonic() - t1, 3),
           "stopped_at_budget": bool(info.get("stopped_at_budget", False)),
           "diagnostics": diag, "solution": solution.model_dump_json(), **rec}
    if want_support:
        out["support_record"] = _support_task(iid, pid, spec, out["solution"], budget_s, seed)
    return out


def _same_plan(a: Solution, b: Solution) -> bool:
    return ([it.model_dump(mode="json") for it in a.itineraries] == [it.model_dump(mode="json") for it in b.itineraries])


def _support_task(iid: str, pid: str, spec: dict, solution_json: str, budget_s: float, seed: int) -> dict:
    """Greedy removal in member order: drop a planning member if B1 without it returns the identical plan.
    The rest is a compression (support) set of the plan (Campi, Garatti & Ramponi 2018)."""
    e, inst, ss, ig, ex, sup = DATA[iid]
    target = Solution.model_validate_json(solution_json)
    keep = list(spec["members"])
    runs = 0
    t0 = time.monotonic()
    for k in list(spec["members"]):
        trial = [m for m in keep if m != k]
        if not trial:
            continue
        pset = member_set(ss, ig, ex, sup, trial, "support")
        res = get_method(spec["method"]).solve(inst, pset, budget_s=budget_s, seed=seed,
                                               deadline=time.monotonic() + budget_s)
        runs += 1
        if res.info.get("stopped_at_budget"):
            raise RuntimeError(f"{iid}/{pid}: B1 stopped at its budget during the support search")
        if _same_plan(res.solution, target):
            keep = trial
    return {"instance": iid, "plan": pid, "K": spec["K"], "support": keep, "s": len(keep), "runs": runs,
            "seconds": round(time.monotonic() - t0, 2)}


def _check_task(iid: str, solutions: dict[str, str], members: list[int], check0: int) -> dict:
    """Check every plan against each listed fresh member alone (one-member scenario set, the oracle)."""
    e, inst, ss, ig, ex, sup = DATA[iid]
    sols = {pid: Solution.model_validate_json(js) for pid, js in solutions.items()}
    recs = []
    t0 = time.monotonic()
    for j in members:
        oracle = Oracle(inst, member_set(ss, ig, ex, sup, [j], "check"))
        for pid, sol in sols.items():
            plan = oracle.check_plan(sol)
            states, causes = [], {}
            n = 0
            for v in plan.vehicles:
                for t in v.trips:
                    c = state_code(t.state)
                    if c != "0":
                        causes[str(n)] = t.cause
                    states.append(c)
                    n += 1
            recs.append({"instance": iid, "plan": pid, "c": int(j - check0), "member": int(j),
                         "states": "".join(states), "causes": causes, "delivered": int(plan.delivered_total)})
    return {"records": recs, "seconds": time.monotonic() - t0, "instance": iid, "plans": sorted(sols),
            "members": [int(j) for j in members]}


# ---------------------------------------------------------------------------------- compute
def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _append(path: Path, rec: dict) -> None:
    with open(path, "a") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")


def cmd_compute(args) -> int:
    guard_rule5()
    cfg = load_config(args.config)
    runs_dir = Path(args.runs_dir) if args.runs_dir else RUNS_DIR
    t_start = time.monotonic()
    budget_s = 60.0 * float(args.budget_min if args.budget_min is not None else cfg["budget"]["compute_minutes"])
    workers = int(args.workers or cfg["budget"]["workers"])
    runs_dir.mkdir(parents=True, exist_ok=True)
    host, boot, commit = host_string(), boot_id(), git_head()
    want = cfg.get("host_boot_prefix")
    if want and not boot.startswith(want) and not args.any_host:
        raise SystemExit(f"refused: boot id {boot} does not start with {want} (another container session: the "
                         "baselines must be re-run first; ASSUMPTIONS #92)")
    k_inst, p, n_check = cfg["members"]["instance"], cfg["members"]["fresh_plan"], cfg["members"]["fresh_check"]
    check0 = k_inst + p
    k_total = check0 + n_check
    sizes = set(args.sizes.split(",")) if args.sizes else {"S", "M", "L"}
    entries = [e for e in load_split().entries("dev") if size_of(e.id) in sizes]
    if args.instances:
        entries = [e for e in entries if e.id in set(args.instances.split(","))]
    log = print
    log(f"[E3] compute: {len(entries)} dev instances; commit {commit}; host {host}; boot {boot}; "
        f"budget {budget_s / 60:.0f} min; {workers} workers", flush=True)

    # phase 0: instances (fingerprints verified) and extended members (bit-identity verified)
    members_info = {}
    for e in entries:
        t0 = time.monotonic()
        inst, ss = load_entry(e)
        ig, ex, sup = extended_members(e, ss, k_total, k_inst)
        DATA[e.id] = (e, inst, ss, ig, ex, sup)
        members_info[e.id] = {"k_total": k_total, "first_bit_identical": k_inst, "seconds": round(time.monotonic() - t0, 3),
                              "fingerprint": e.fingerprint}
    (runs_dir / "members.json").write_text(json.dumps(members_info, indent=1) + "\n")
    log(f"[E3] phase 0 done: members regenerated, first {k_inst} bit-identical on all {len(entries)} instances "
        f"({time.monotonic() - t_start:.0f} s)", flush=True)

    specs = plan_specs(cfg)
    b1 = cfg["planner"]["b1"]
    b2 = cfg["planner"].get("b2") or {}
    plans_path, support_path, checks_path = runs_dir / "plans.jsonl", runs_dir / "support.jsonl", runs_dir / "checks.jsonl"
    plans = {(r["instance"], r["plan"]): r for r in _jsonl(plans_path)}

    # phases 1-3: B1 plans with their in-sample checks and (where listed) support sets in the worker pool;
    # meanwhile B2 plans in the main process (B2 is load-sensitive: its plans are treated as given)
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
        done_sup = {(r["instance"], r["plan"]) for r in _jsonl(support_path)}
        want_plans = [(e.id, pid) for e in entries for pid, sp in specs.items()
                      if sp["method"] == "b1_greedy" and pid in cfg["plans_by_size"][size_of(e.id)]
                      and ((e.id, pid) not in plans or (pid in cfg["support"]["plans_by_size"][size_of(e.id)]
                                                         and (e.id, pid) not in done_sup))]
        jobs = []
        for iid, pid in want_plans:
            sup_wanted = pid in cfg["support"]["plans_by_size"][size_of(iid)] and (iid, pid) not in done_sup
            prev = plans.get((iid, pid))
            jobs.append(pool.apply_async(_plan_task, (iid, pid, specs[pid], k_inst, float(b1["budget_s"]),
                                                      int(b1["seed"]), sup_wanted, prev["solution"] if prev else None)))
        if "B2-A8" in specs and not args.skip_b2:
            for e in entries:
                if size_of(e.id) not in b2.get("sizes", []) or (e.id, "B2-A8") in plans:
                    continue
                rec = _plan_task(e.id, "B2-A8", specs["B2-A8"], k_inst, float(b2["budget_s"]), int(b2["seed"]),
                                 False, None)
                rec.update(commit=commit, host=host)
                _append(plans_path, rec)
                plans[(e.id, "B2-A8")] = rec
                log(f"  B2 {e.id}: delivered {rec['delivered']} unresolved {rec['unresolved']} "
                    f"runtime {rec['runtime_s']} s diagnostics {rec['diagnostics']}", flush=True)
        n_sup = 0
        for (iid, pid), job in zip(want_plans, jobs):
            try:
                rec = job.get()
            except Exception as exc:  # noqa: BLE001 - one failed plan must not end the lock hold; it is logged
                log(f"  ERROR planning {iid}/{pid}: {type(exc).__name__}: {exc}", flush=True)
                _append(runs_dir / "errors.jsonl", {"phase": "plan", "instance": iid, "plan": pid,
                                                     "error": f"{type(exc).__name__}: {exc}", "commit": commit})
                continue
            sup_rec = rec.pop("support_record", None)
            if (rec["instance"], rec["plan"]) not in plans:
                rec.update(commit=commit, host=host)
                _append(plans_path, rec)
                plans[(rec["instance"], rec["plan"])] = rec
            if sup_rec is not None:
                sup_rec.update(commit=commit, host=host)
                _append(support_path, sup_rec)
                n_sup += 1
            if rec["stopped_at_budget"]:
                log(f"  WARNING {rec['instance']}/{rec['plan']}: B1 stopped at its budget", flush=True)
        log(f"[E3] phases 1-3 done: {len(want_plans)} B1 plan tasks, {n_sup} support sets "
            f"({time.monotonic() - t_start:.0f} s)", flush=True)

        # phase 4: out-of-sample checks, tier by tier, until the budget is used
        done = {(r["instance"], r["plan"], r["c"]) for r in _jsonl(checks_path)}
        order = {"S": 0, "M": 1, "L": 2}
        tasks = []
        for tier in cfg["tiers"]:
            for e in sorted(entries, key=lambda x: order[size_of(x.id)]):
                if size_of(e.id) not in tier["sizes"]:
                    continue
                pids = [pid for pid in tier["plans"] if (e.id, pid) in plans]
                if not pids:
                    continue
                chunk = int(cfg["chunk_members"][size_of(e.id)])
                lo, hi = tier["check"]
                for a in range(lo, min(hi, n_check), chunk):
                    cs = list(range(a, min(a + chunk, hi, n_check)))
                    todo = [pid for pid in pids if any((e.id, pid, c) not in done for c in cs)]
                    if todo:
                        tasks.append((tier["name"], e.id, todo, [check0 + c for c in cs]))
        log(f"[E3] phase 4: {len(tasks)} check tasks queued by tier; budget ends at {budget_s / 60:.0f} min", flush=True)
        stop_at = t_start + budget_s
        inflight: list = []
        tier_done: dict[str, int] = defaultdict(int)
        tier_all: dict[str, int] = defaultdict(int)
        for t in tasks:
            tier_all[t[0]] += 1
        i = 0
        stopped = False
        while i < len(tasks) or inflight:
            while i < len(tasks) and len(inflight) < workers and not stopped:
                if time.monotonic() > stop_at:
                    stopped = True
                    break
                name, iid, pids, js = tasks[i]
                sols = {pid: plans[(iid, pid)]["solution"] for pid in pids}
                inflight.append((name, pool.apply_async(_check_task, (iid, sols, js, check0))))
                i += 1
            if stopped and i < len(tasks):
                i = len(tasks)
            still = []
            for name, job in inflight:
                if job.ready():
                    try:
                        out = job.get()
                    except Exception as exc:  # noqa: BLE001 - logged; the task's members stay unchecked
                        log(f"  ERROR {name} check task: {type(exc).__name__}: {exc}", flush=True)
                        _append(runs_dir / "errors.jsonl", {"phase": "check", "tier": name,
                                                             "error": f"{type(exc).__name__}: {exc}", "commit": commit})
                        tier_done[name] += 1
                        continue
                    for r in out["records"]:
                        if (r["instance"], r["plan"], r["c"]) in done:
                            continue
                        r.update(commit=commit, host=host)
                        _append(checks_path, r)
                        done.add((r["instance"], r["plan"], r["c"]))
                    tier_done[name] += 1
                    log(f"  {name} {out['instance']} members {out['members'][0]}-{out['members'][-1]} plans "
                        f"{len(out['plans'])}: {out['seconds']:.1f} s (elapsed {(time.monotonic() - t_start) / 60:.1f} min)",
                        flush=True)
                else:
                    still.append((name, job))
            inflight = still
            time.sleep(0.2)
    run = {"commit": commit, "host": host, "boot_id": boot, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "elapsed_s": round(time.monotonic() - t_start, 1), "budget_s": budget_s, "workers": workers,
           "stopped_at_budget": stopped, "tiers": {k: f"{tier_done[k]}/{tier_all[k]} tasks" for k in tier_all},
           "instances": [e.id for e in entries], "config": str(args.config or CONFIG_PATH)}
    runs = _jsonl(runs_dir / "runs.jsonl")
    _append(runs_dir / "runs.jsonl", {**run, "n": len(runs) + 1})
    log(f"[E3] compute done: {json.dumps(run)}", flush=True)
    return 0


# --------------------------------------------------------------------------------- selftest
def cmd_selftest(args) -> int:
    """Invariants of a finished run directory (the smoke run before the main run): every instance's first 8
    regenerated members were bit-identical; every plan has its in-sample record; the B1 plan with the instance's
    own 8 members reproduces the committed harness row (B1 is deterministic); every check record has one state per
    trip; a plan's trips that are checked in the in-sample members of a K=8 plan are the delivered ones."""
    cfg = load_config(args.config)
    runs_dir = Path(args.runs_dir) if args.runs_dir else RUNS_DIR
    members = json.loads((runs_dir / "members.json").read_text())
    k_inst = cfg["members"]["instance"]
    assert members and all(m["first_bit_identical"] == k_inst for m in members.values()), members
    plans = {(r["instance"], r["plan"]): r for r in _jsonl(runs_dir / "plans.jsonl")}
    checks = _jsonl(runs_dir / "checks.jsonl")
    support = _jsonl(runs_dir / "support.jsonl")
    assert plans, "no plans"
    rows = list(csv.DictReader(open(EVACPLAN_DIR / "results" / "b1_greedy.csv")))
    for (iid, pid), r in plans.items():
        assert r["delivered"] == sum(t["n"] for t in r["trips"] if t["slack_s"] is not None), (iid, pid)
        assert not r["stopped_at_budget"], (iid, pid)
        if pid == "A8-g0":
            ref = [x for x in rows if x["instance"] == iid and json.loads(x["config"])["budget_s"] == 60.0]
            assert ref, f"no committed B1 row for {iid}"
            for x in ref:
                assert int(x["delivered_checked"]) == r["delivered"], (iid, x["delivered_checked"], r["delivered"])
                if x["min_slack_s"]:
                    assert abs(float(x["min_slack_s"]) - r["min_slack_s"]) < 0.051, (iid, x["min_slack_s"], r["min_slack_s"])
    for c in checks:
        pl = plans[(c["instance"], c["plan"])]
        assert len(c["states"]) == len(pl["trips"]), (c["instance"], c["plan"], c["c"])
        assert set(c["states"]) <= set("012")
        assert c["delivered"] == sum(t["n"] for t, s in zip(pl["trips"], c["states"]) if s == "0"), c
    for s_ in support:
        assert 0 < s_["s"] <= s_["K"] and set(s_["support"]) <= set(plans[(s_["instance"], s_["plan"])]["members"])
    print(f"[E3] selftest ok: {len(members)} instances, {len(plans)} plans, {len(checks)} check records, "
          f"{len(support)} support sets ({runs_dir})", flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compute")
    c.add_argument("--config", default=None, help="config file (default: config.yaml next to this file)")
    c.add_argument("--runs-dir", default=None, help="raw output folder (default: evacplan/runs/E3-scenario-robustness)")
    c.add_argument("--budget-min", type=float, default=None)
    c.add_argument("--workers", type=int, default=None)
    c.add_argument("--sizes", default=None, help="comma-separated subset of S,M,L")
    c.add_argument("--instances", default=None, help="comma-separated instance ids (dev)")
    c.add_argument("--skip-b2", action="store_true")
    c.add_argument("--any-host", action="store_true", help="do not refuse another boot session (tests only)")
    t = sub.add_parser("selftest")
    t.add_argument("--config", default=None)
    t.add_argument("--runs-dir", default=None)
    args = ap.parse_args(argv)
    return cmd_compute(args) if args.cmd == "compute" else cmd_selftest(args)


if __name__ == "__main__":
    sys.exit(main())
