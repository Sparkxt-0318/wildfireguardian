"""The benchmark harness: run a method on a frozen split set at a fixed wall-clock budget, check
every plan with :mod:`evacplan.oracle`, write ``results/<method>.csv`` and regenerate
``evacplan/LEADERBOARD.md``.

Result rows (one per instance, seed, budget and set; :data:`COLUMNS`)
--------------------------------------------------------------------
* ``delivered_checked``, ``unresolved``, ``model_no_route``: residents, from the oracle's
  :class:`~evacplan.oracle.PlanResult` (``delivered_total``, ``unresolved_total``,
  ``model_no_route_total``). Residents no itinerary boards are "not planned" (the rest).
* ``makespan_s``, ``min_slack_s``: from the PlanResult (empty when undefined, e.g. no delivery).
* ``runtime_s``: wall-clock seconds of ``method.solve`` only (loading and the oracle excluded).
* ``best_bound``: the method's proven upper bound on delivered residents (empty: none);
  ``gap = (best_bound - delivered_checked) / best_bound`` (0 if the bound is 0; empty without one).
* ``commit`` (git HEAD, ``+dirty`` if ``evacplan/`` has uncommitted changes besides the
  leaderboard), ``seed`` (the method's seed), ``config`` (compact JSON: set, budget, method
  config, instance generator config and fingerprint, label, oracle and contract versions), ``host``.

Per-facility rows (``results/<method>.facilities.csv``; :data:`FACILITY_COLUMNS`), one per
instance, seed, budget, set, facility and mobility class with residents
-------------------------------------------------------------------------------------------
* the facility's deadlines and servability (method-independent, :mod:`evacplan.deadlines`, every
  state declared by the oracle): ``deadline_state``/``deadline_cause``, ``arrive_by_s`` (the latest
  time the first vehicle can arrive and still serve someone of the class), ``leave_by_s`` (the
  latest time the last vehicle can leave with one), ``deadline_shelter`` and ``unservable``
  (residents no plan can serve: scoped ``model_no_route``, never hidden);
* this plan's outcome for them, from the oracle: ``delivered_checked``, ``unresolved``,
  ``model_no_route`` (trips, plus residents left on board), ``not_planned``; ``first_board_s`` and
  ``last_leave_s`` (first boarding start and last departure after boarding of the class);
* ``commit``, ``config`` (as the result row), ``host``.

Final states come only from the oracle; methods' own claims are never scored. Timed runs hold
the shared bench lock (``program/benchlock.py``); ``test`` is refused unless explicitly allowed
(only at milestones, after Siyeong approves).
"""
from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import json
import math
import os
import platform
import re
import socket
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

import hazard_contract as hc

from .deadlines import class_deadlines
from .instances import CACHE_DIR, EVACPLAN_ROOT, SPLIT_PATH, Split, SplitEntry, load_entry, load_split
from .methods import get_method
from .oracle import ORACLE_VERSION, ClassDeadline, Oracle, PlanResult
from .schema import CLASSES, Board, Drive, Instance, Solution
from .validate import validate_solution

COLUMNS = ("instance", "method", "seed", "delivered_checked", "unresolved", "model_no_route", "makespan_s",
           "min_slack_s", "runtime_s", "best_bound", "gap", "commit", "config", "host")
FACILITY_COLUMNS = ("instance", "method", "seed", "facility", "mobility_class", "residents", "release_s",
                    "deadline_state", "deadline_cause", "arrive_by_s", "leave_by_s", "deadline_shelter", "unservable",
                    "delivered_checked", "unresolved", "model_no_route", "not_planned", "first_board_s", "last_leave_s",
                    "commit", "config", "host")
FACILITY_SUFFIX = ".facilities.csv"
RESULTS_DIR = EVACPLAN_ROOT / "results"
LEADERBOARD_PATH = EVACPLAN_ROOT / "LEADERBOARD.md"


class TestSetRefused(PermissionError):
    """The test set is touched only at milestones, after Siyeong approves (program rule 5)."""

    __test__ = False      # not a pytest test class


# ------------------------------------------------------------------------- provenance
def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def git_commit(evacplan_root: Path = EVACPLAN_ROOT) -> str:
    """HEAD of this checkout, with ``+dirty`` when ``evacplan/`` has uncommitted changes (the
    generated leaderboard excepted)."""
    try:
        sha = _git(["rev-parse", "HEAD"], evacplan_root).strip()
        status = _git(["status", "--porcelain", "--", ".", ":(exclude)LEADERBOARD.md"], evacplan_root)
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return sha + ("+dirty" if status.strip() else "")


def host_string() -> str:
    return (f"{socket.gethostname()} ({platform.system()} {platform.machine()}, {os.cpu_count()} cpu, "
            f"python {platform.python_version()})")


# ---------------------------------------------------------------------------- bench lock
def repo_root(start: Path = EVACPLAN_ROOT) -> Path | None:
    try:
        return Path(_git(["rev-parse", "--show-toplevel"], start).strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def load_benchlock(repo: Path | None = None):
    """``program/benchlock.py`` of this checkout, loaded by path (its documented Python use)."""
    repo = repo or repo_root()
    path = None if repo is None else repo / "program" / "benchlock.py"
    if path is None or not path.is_file():
        raise FileNotFoundError("program/benchlock.py not found; timed runs need the shared bench lock "
                                "(pass --lock no only if you hold it yourself)")
    spec = importlib.util.spec_from_file_location("wfg_program_benchlock", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ancestor_pids() -> set[int]:
    out: set[int] = set()
    pid = os.getpid()
    for _ in range(64):
        try:
            ppid = int(subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True,
                                      check=True).stdout.strip())
        except (OSError, ValueError, subprocess.CalledProcessError):
            break
        if ppid <= 1 or ppid in out:
            break
        out.add(ppid)
        pid = ppid
    return out


def lock_held_by_ancestor(benchlock) -> bool:
    """True if the bench lock's recorded holder is a parent process of this one on this host
    (``benchlock.py -- evacplan run ...``): acquiring it again would deadlock."""
    try:
        text = Path(benchlock.lock_path()).read_text()
    except OSError:
        return False
    pid = re.search(r"\bpid=(\d+)\b", text)
    host = re.search(r"\bhost=(\S+)", text)
    if pid is None or (host is not None and host.group(1) != socket.gethostname()):
        return False
    return int(pid.group(1)) in _ancestor_pids()


@contextlib.contextmanager
def bench_guard(mode: str, label: str, log: Callable[[str], None] = print):
    """Hold the shared bench lock around timed work. ``mode``: ``auto`` (acquire unless a parent
    process already holds it), ``yes`` (always acquire), ``no`` (do not lock)."""
    if mode not in ("auto", "yes", "no"):
        raise ValueError("lock mode must be auto, yes or no")
    if mode == "no":
        yield "not locked"
        return
    bl = load_benchlock()
    if mode == "auto" and lock_held_by_ancestor(bl):
        yield "held by a parent process"
        return
    with bl.bench_lock(label) as waited:
        log(f"[evacplan] bench lock acquired after {waited:.1f}s")
        yield f"acquired after {waited:.1f}s"


# --------------------------------------------------------------------------------- rows
def _num(x: float | None, nd: int) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return ""
    return f"{float(x):.{nd}f}"


def make_row(*, entry: SplitEntry, set_name: str, method_name: str, method_config: dict, seed: int,
             budget_s: float, plan, runtime_s: float, best_bound: float | None, commit: str, host: str) -> dict:
    delivered = int(plan.delivered_total)
    if best_bound is None:
        gap = None
    elif best_bound > 0:
        gap = (float(best_bound) - delivered) / float(best_bound)
    else:
        gap = 0.0
    config = {
        "set": set_name, "budget_s": float(budget_s), "method": method_config,
        "instance": {"generator": entry.generator, "generator_version": entry.generator_version,
                     "config": entry.config, "fingerprint": entry.fingerprint},
        "label": entry.label, "oracle": ORACLE_VERSION, "hazard_contract": hc.CONTRACT_VERSION,
    }
    return {
        "instance": entry.id, "method": method_name, "seed": str(int(seed)), "delivered_checked": str(delivered),
        "unresolved": str(int(plan.unresolved_total)), "model_no_route": str(int(plan.model_no_route_total)),
        "makespan_s": _num(plan.makespan_s, 1), "min_slack_s": _num(plan.min_slack_s, 1),
        "runtime_s": _num(runtime_s, 4), "best_bound": _num(best_bound, 3), "gap": _num(gap, 6),
        "commit": commit, "config": json.dumps(config, sort_keys=True, separators=(",", ":")), "host": host,
    }


def row_config(row: dict) -> dict:
    return json.loads(row["config"])


def _key(row: dict) -> tuple:
    cfg = row_config(row)
    key = (cfg["set"], float(cfg["budget_s"]), row["instance"], row["method"], int(row["seed"]))
    if "facility" in row:
        key += (row["facility"], CLASSES.index(row["mobility_class"]))
    return key


def _columns(path: Path) -> tuple[str, ...]:
    return FACILITY_COLUMNS if Path(path).name.endswith(FACILITY_SUFFIX) else COLUMNS


def read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    cols = _columns(path)
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != cols:
            raise ValueError(f"{path}: columns {reader.fieldnames} are not the harness columns {list(cols)}")
        return list(reader)


def write_rows(path: Path, rows: Iterable[dict]) -> Path:
    rows = sorted(rows, key=_key)
    cols = _columns(path)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r[c] for c in cols})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(buf.getvalue())
    tmp.replace(path)
    return path


def facility_outcomes(instance: Instance, solution: Solution, plan: PlanResult) -> dict[tuple[str, int], dict]:
    """Per (facility, class): this plan's delivered / unresolved / model_no_route / not planned
    residents (from the oracle's trips; residents left on board count as model_no_route, as in the
    plan totals) and the first boarding start and last departure after boarding (instance clock)."""
    out: dict[tuple[str, int], dict] = {}

    def get(fid: str, c: int) -> dict:
        return out.setdefault((fid, c), {"delivered_checked": 0, "unresolved": 0, "model_no_route": 0, "not_planned": 0,
                                         "first_board_s": None, "last_leave_s": None})
    for f in instance.facilities:
        for c in range(3):
            if f.residents.vector()[c]:
                get(f.id, c)
    for v in plan.vehicles:
        for t in v.trips:
            col = {"checked": "delivered_checked", "unresolved": "unresolved"}.get(t.state.value, "model_no_route")
            for fid, cc in t.by_facility.items():
                for c in range(3):
                    if cc.vector()[c]:
                        get(fid, c)[col] += cc.vector()[c]
    for sch in validate_solution(instance, solution).schedules:
        for fid, vec in sch.onboard_end.items():
            for c in range(3):
                if vec[c]:
                    get(fid, c)["model_no_route"] += vec[c]
    for fid, cc in plan.not_planned.items():
        for c in range(3):
            if cc.vector()[c]:
                get(fid, c)["not_planned"] += cc.vector()[c]
    for it, res in zip(solution.itineraries, plan.vehicles):
        acts = it.actions
        for j, a in enumerate(acts):
            if not isinstance(a, Board):
                continue
            ar = res.actions[j] if j < len(res.actions) else None
            nxt = next((b for b in acts[j + 1:] if isinstance(b, Drive)), None)
            for c in range(3):
                if not a.counts.vector()[c]:
                    continue
                d = get(a.facility, c)
                if ar is not None and ar.t_start is not None:
                    d["first_board_s"] = ar.t_start if d["first_board_s"] is None else min(d["first_board_s"], ar.t_start)
                if nxt is not None:
                    d["last_leave_s"] = nxt.depart_s if d["last_leave_s"] is None else max(d["last_leave_s"], nxt.depart_s)
    return out


def make_facility_rows(*, entry: SplitEntry, method_name: str, seed: int, row: dict, instance: Instance,
                       deadlines: list[ClassDeadline], outcomes: dict) -> list[dict]:
    """Per-facility rows (one per facility and class with residents) for one result row."""
    rows = []
    for d in deadlines:
        c = CLASSES.index(d.mobility_class)
        o = outcomes.get((d.facility, c), {})
        rows.append({
            "instance": entry.id, "method": method_name, "seed": str(int(seed)), "facility": d.facility,
            "mobility_class": d.mobility_class, "residents": str(d.residents), "release_s": _num(d.release_s, 1),
            "deadline_state": d.state.value, "deadline_cause": d.cause or "", "arrive_by_s": _num(d.arrive_by_s, 1),
            "leave_by_s": _num(d.leave_by_s, 1), "deadline_shelter": d.shelter or "", "unservable": str(d.unservable),
            "delivered_checked": str(o.get("delivered_checked", 0)), "unresolved": str(o.get("unresolved", 0)),
            "model_no_route": str(o.get("model_no_route", 0)), "not_planned": str(o.get("not_planned", 0)),
            "first_board_s": _num(o.get("first_board_s"), 1), "last_leave_s": _num(o.get("last_leave_s"), 1),
            "commit": row["commit"], "config": row["config"], "host": row["host"],
        })
    return rows


def upsert_rows(path: Path, new: Iterable[dict]) -> list[dict]:
    """Replace rows with the same (set, budget, instance, method, seed[, facility, class]); keep all others."""
    merged = {_key(r): r for r in read_rows(path)}
    for r in new:
        merged[_key(r)] = r
    write_rows(path, merged.values())
    return list(merged.values())


# ----------------------------------------------------------------------------------- run
def run(method: str, set_name: str, budget_s: float, *, seeds: Iterable[int] = (0,), instances: Iterable[str] | None = None,
        method_config: dict | None = None, allow_test: bool = False, lock: str = "auto",
        split_path: Path = SPLIT_PATH, cache_dir: Path = CACHE_DIR, results_dir: Path = RESULTS_DIR,
        leaderboard_path: Path | None = LEADERBOARD_PATH, save_plans: bool = True,
        log: Callable[[str], None] = print) -> list[dict]:
    """Run ``method`` on every instance of ``set_name`` (or the listed ``instances``) and seed at
    ``budget_s`` seconds each; returns the result rows (also upserted into the CSV)."""
    if not (isinstance(budget_s, (int, float)) and math.isfinite(budget_s) and budget_s > 0):
        raise ValueError("budget_s must be a positive number of seconds")
    seeds = [int(s) for s in seeds]
    if not seeds:
        raise ValueError("give at least one seed")
    split = load_split(split_path)
    if set_name == "test" and not allow_test:
        raise TestSetRefused("the test set is run only at milestones, after Siyeong approves (--allow-test)")
    entries = split.entries(set_name)
    if instances:
        wanted = list(dict.fromkeys(instances))
        known = {e.id: e for e in entries}
        missing = [i for i in wanted if i not in known]
        if missing:
            raise KeyError(f"not in set {set_name!r}: {missing}")
        entries = [known[i] for i in wanted]
    m = get_method(method, **(method_config or {}))
    commit, host = git_commit(), host_string()
    log(f"[evacplan] {method} on {set_name} ({len(entries)} instances x {len(seeds)} seeds) at {budget_s:g} s; "
        f"commit {commit}")
    loaded = [(e, *load_entry(e, cache_dir)) for e in entries]          # regenerate before timing
    csv_path = Path(results_dir) / f"{method}.csv"
    fac_path = Path(results_dir) / f"{method}{FACILITY_SUFFIX}"
    rows: list[dict] = []
    with bench_guard(lock, f"evacplan run {method} {set_name} {budget_s:g}s", log) as lock_state:
        for e, inst, ss in loaded:
            oracle = Oracle(inst, ss)
            deadlines = class_deadlines(inst, ss, oracle=oracle)          # per facility; not timed
            for seed in seeds:
                t0 = time.monotonic()
                res = m.solve(inst, ss, budget_s=float(budget_s), seed=seed, deadline=t0 + float(budget_s))
                runtime = time.monotonic() - t0
                plan = oracle.check_plan(res.solution)
                row = make_row(entry=e, set_name=set_name, method_name=method, method_config=m.config(), seed=seed,
                               budget_s=budget_s, plan=plan, runtime_s=runtime, best_bound=res.best_bound,
                               commit=commit, host=host)
                upsert_rows(csv_path, [row])
                upsert_rows(fac_path, make_facility_rows(
                    entry=e, method_name=method, seed=seed, row=row, instance=inst, deadlines=deadlines,
                    outcomes=facility_outcomes(inst, res.solution, plan)))
                rows.append(row)
                if save_plans:
                    d = Path(results_dir) / "runs" / method / f"{set_name}-b{budget_s:g}"
                    d.mkdir(parents=True, exist_ok=True)
                    sol = res.solution.model_copy(update={"provenance": {
                        **res.solution.provenance, "commit": commit, "seed": seed, "host": host,
                        "config": row_config(row)}})
                    (d / f"{e.id}-s{seed}.solution.json").write_text(sol.model_dump_json(indent=1) + "\n")
                    (d / f"{e.id}-s{seed}.result.json").write_text(plan.model_dump_json(indent=1) + "\n")
                    (d / f"{e.id}.deadlines.json").write_text(
                        "[\n" + ",\n".join(x.model_dump_json() for x in deadlines) + "\n]\n")
                log(f"  {e.id} seed {seed}: delivered {row['delivered_checked']}/{inst.residents_total} "
                    f"unresolved {row['unresolved']} model_no_route {row['model_no_route']} "
                    f"unservable {sum(d.unservable for d in deadlines)} "
                    f"runtime {row['runtime_s']} s [{e.label or 'real'}]")
    log(f"[evacplan] bench lock: {lock_state}; rows -> {csv_path}, per facility -> {fac_path}")
    if leaderboard_path is not None:
        write_leaderboard(results_dir, split, leaderboard_path)
        log(f"[evacplan] leaderboard -> {leaderboard_path}")
    return rows


# --------------------------------------------------------------------------- leaderboard
def all_rows(results_dir: Path = RESULTS_DIR) -> list[dict]:
    out: list[dict] = []
    for f in sorted(Path(results_dir).glob("*.csv")):
        if not f.name.endswith(FACILITY_SUFFIX):
            out.extend(read_rows(f))
    return out


def all_facility_rows(results_dir: Path = RESULTS_DIR) -> list[dict]:
    out: list[dict] = []
    for f in sorted(Path(results_dir).glob(f"*{FACILITY_SUFFIX}")):
        out.extend(read_rows(f))
    return out


def _fmt(x: float | None, nd: int = 1) -> str:
    return "–" if x is None else f"{x:.{nd}f}"


def _unservable(facility_rows: list[dict]) -> dict[tuple, float]:
    """(set, budget, method, instance) -> residents no plan can serve (mean over seeds)."""
    per: dict[tuple, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for r in facility_rows:
        cfg = row_config(r)
        per[(cfg["set"], float(cfg["budget_s"]), r["method"], r["instance"])][int(r["seed"])] += float(r["unservable"])
    return {k: sum(v.values()) / len(v) for k, v in per.items()}


def render_leaderboard(rows: list[dict], split: Split | None = None, facility_rows: list[dict] | None = None) -> str:
    unserv = _unservable(facility_rows or [])
    residents: dict[str, int] = {}
    order: dict[str, int] = {}
    if split is not None:
        for entries in split.sets.values():
            for e in entries:
                order.setdefault(e.id, len(order))
                if "residents" in e.stats:
                    residents[e.id] = int(e.stats["residents"])
    lines = [
        "# evacplan leaderboard (Track C)",
        "",
        "Regenerated by `evacplan run` and `evacplan leaderboard` from `evacplan/results/*.csv` (git-ignored). "
        "Do not edit by hand.",
        "",
        "* Every number comes from `evacplan.oracle`. **delivered** = residents whose trip is `checked` in all K "
        "members; `unresolved` is never safe and never delivered; `model_no_route` is scoped to the hazard model, its "
        "members and horizon; **not planned** = residents no itinerary boards.",
        "* **unservable** = residents that no plan can serve within the model, fleet and horizon: a scoped "
        "`model_no_route` per facility and mobility class, declared by the oracle (`results/<method>.facilities.csv`, "
        "which also holds each facility's latest first-arrival and last-departure times). They are counted again "
        "inside not planned (or model_no_route / unresolved if a plan tries them).",
        "* Methods are compared only at **equal wall-clock budgets**: one table per set and budget. Runtime is the "
        "method's own wall clock; rows over budget are counted.",
        "* **SYNTHETIC** rows are SYNTHETIC instances (`evacplan/instances/SPLIT.json`), not real-world results.",
        "",
    ]
    if not rows:
        lines += ["No results yet.", ""]
        return "\n".join(lines)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        cfg = row_config(r)
        groups[(cfg["set"], float(cfg["budget_s"]))].append(r)
    for (set_name, budget) in sorted(groups, key=lambda k: (k[0] != "dev", k[0], k[1])):
        g = groups[(set_name, budget)]
        lines += [f"## {set_name}, budget {budget:g} s", ""]
        lines += ["| method | label | instances | seeds | delivered | unresolved | model_no_route | not planned | "
                  "unservable | residents | min slack (s) | mean runtime (s) | over budget | mean gap | commit |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        by_method: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in g:
            by_method[(r["method"], row_config(r)["label"] or "real")].append(r)
        for (meth, label), rs in sorted(by_method.items()):
            per_inst: dict[str, list[dict]] = defaultdict(list)
            for r in rs:
                per_inst[r["instance"]].append(r)

            def tot(col: str) -> float:
                return sum(sum(float(x[col]) for x in v) / len(v) for v in per_inst.values())
            n_res = sum(residents.get(i, 0) for i in per_inst) if all(i in residents for i in per_inst) else None
            dl, un, mn = tot("delivered_checked"), tot("unresolved"), tot("model_no_route")
            slacks = [float(r["min_slack_s"]) for r in rs if r["min_slack_s"]]
            gaps = [float(r["gap"]) for r in rs if r["gap"]]
            seeds = sorted({int(r["seed"]) for r in rs})
            over = sum(float(r["runtime_s"]) > budget for r in rs)
            commits = sorted({r["commit"][:12] for r in rs})
            share = f" ({100 * dl / n_res:.1f}%)" if n_res else ""
            us = [unserv.get((set_name, budget, meth, i)) for i in per_inst]
            us_txt = "–" if any(u is None for u in us) else f"{sum(us):g}"
            lines.append(
                f"| {meth} | {label} | {len(per_inst)} | {len(seeds)} | {dl:g}{share} | {un:g} | {mn:g} | "
                f"{'–' if n_res is None else f'{n_res - dl - un - mn:g}'} | {us_txt} | {'–' if n_res is None else n_res} | "
                f"{_fmt(min(slacks) if slacks else None)} | {_fmt(sum(float(r['runtime_s']) for r in rs) / len(rs), 3)} | "
                f"{over} | {_fmt(sum(gaps) / len(gaps) if gaps else None, 3)} | {', '.join(commits)} |")
        methods = sorted({r["method"] for r in g})
        inst_ids = sorted({r["instance"] for r in g}, key=lambda i: (order.get(i, len(order)), i))
        labels = {r["instance"]: row_config(r)["label"] or "real" for r in g}
        lines += ["", "Delivered (checked) per instance, mean over seeds:", "",
                  "| instance | label | residents | unservable | " + " | ".join(methods) + " |",
                  "|---|---|---|---|" + "---|" * len(methods)]
        for i in inst_ids:
            cells = []
            for meth in methods:
                v = [float(r["delivered_checked"]) for r in g if r["instance"] == i and r["method"] == meth]
                cells.append(f"{sum(v) / len(v):g}" if v else "–")
            u = [x for (st, bd, _m, ii), x in unserv.items() if st == set_name and bd == budget and ii == i]
            lines.append(f"| {i} | {labels[i]} | {residents.get(i, '–')} | {f'{max(u):g}' if u else '–'} | "
                         + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def write_leaderboard(results_dir: Path = RESULTS_DIR, split: Split | None = None,
                      path: Path = LEADERBOARD_PATH) -> Path:
    if split is None:
        split = load_split(SPLIT_PATH)
    path = Path(path)
    path.write_text(render_leaderboard(all_rows(results_dir), split, all_facility_rows(results_dir)))
    return path
