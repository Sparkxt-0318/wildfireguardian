"""The benchmark harness: run a method on a frozen split set at a fixed wall-clock budget, check
every plan with :mod:`evacplan.oracle`, write ``results/<method>.csv`` and regenerate
``evacplan/LEADERBOARD.md`` with one safety-margin figure per table (``evacplan/figures/``).

Result rows (one per instance, seed, budget, set and host; :data:`COLUMNS`)
--------------------------------------------------------------------------
* ``delivered_checked``, ``unresolved``, ``model_no_route``: residents, from the oracle's
  :class:`~evacplan.oracle.PlanResult` (``delivered_total``, ``unresolved_total``,
  ``model_no_route_total``). Residents no itinerary boards are "not planned" (the rest).
* ``makespan_s``, ``min_slack_s``: from the PlanResult (empty when undefined, e.g. no delivery).
* ``delivered_slack_ge_0m``, ``_5m``, ``_15m``, ``_30m``: residents delivered with a safety slack of at
  least 0, 5, 15 and 30 minutes (:func:`delivered_slacks`: the smallest oracle leg slack over their
  vehicle's legs from the start of its itinerary through the unloading that delivers them).
  ``delivered_slack_ge_0m`` equals ``delivered_checked``. A report, not a change of the problem: delivered
  still counts every checked trip.
* ``runtime_s``: wall-clock seconds of ``method.solve`` only (loading and the oracle excluded).
* ``best_bound``: the method's proven upper bound on delivered residents (empty: none);
  ``gap = (best_bound - delivered_checked) / best_bound`` (0 if the bound is 0; empty without one).
* ``commit`` (git HEAD, ``+dirty`` if ``evacplan/``, ``hazard_contract/`` or ``program/`` has
  uncommitted changes besides the generated leaderboard), ``seed`` (the method's seed), ``config``
  (compact JSON: set, budget, method config, instance generator config and fingerprint, label, the
  oracle version, the hazard_contract format ``CONTRACT_VERSION``, ``versions``: the installed
  hazard_contract (``__version__``), numpy, ortools and highspy, ``delivered_by_margin_min``: residents
  delivered with slack >= m minutes for every m in :data:`MARGINS_MIN`, and, when the method reports
  them, ``diagnostics``: how far its own search got, e.g. B2's solutions found and final objective; never
  scored), ``host`` (:func:`host_string`: host name, OS, machine, CPU model, CPU count, Python version).

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

The leaderboard (``program/DECISIONS.md``, 2026-11-01)
------------------------------------------------------
One table per (set, budget, host): rows of different hosts are never pooled or compared. Per-instance
cells show the median over seeds and [min-max]; method totals the median and [min-max] of the per-seed
totals. Under each table, the bar for beating B2 (:func:`compare_to_b2`): max(B2 best observed, the
best-of-baselines total); a method beats B2 only if its worst of at least 5 repeats, each covering every
instance of the set, exceeds the bar. Recorded observations outside the rows (e.g. the Phase 0 review's
B2 run) come from ``evacplan/docs/recorded_observations.json``.

Final states come only from the oracle; methods' own claims are never scored. Timed runs hold
the shared bench lock (``program/benchlock.py``); ``test`` is refused unless explicitly allowed
(only at milestones, after Siyeong approves).
"""
from __future__ import annotations

import contextlib
import csv
import functools
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
import platform
import re
import socket
import statistics
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Callable, Iterable, Mapping

import hazard_contract as hc

from .deadlines import class_deadlines
from .instances import CACHE_DIR, EVACPLAN_ROOT, SPLIT_PATH, Split, SplitEntry, load_entry, load_split
from .methods import canonical, get_method
from .oracle import ORACLE_VERSION, ClassDeadline, Oracle, PlanResult, State
from .schema import CLASSES, Board, Drive, Instance, Solution
from .validate import TIME_TOL_S, validate_solution

MARGINS_MIN = (0, 1, 2, 5, 10, 15, 20, 30, 45, 60)     # required safety margins (min): the curve in each row's config
ROW_MARGINS_MIN = (0, 5, 15, 30)                       # ... and the ones with their own column
LEADERBOARD_MARGINS_MIN = (5, 15, 30)                  # ... and the ones in the leaderboard tables


def margin_column(minutes: int) -> str:
    """Result column of residents delivered with a safety slack of at least ``minutes``."""
    return f"delivered_slack_ge_{int(minutes)}m"


COLUMNS = ("instance", "method", "seed", "delivered_checked", "unresolved", "model_no_route", "makespan_s",
           "min_slack_s", "delivered_slack_ge_0m", "delivered_slack_ge_5m", "delivered_slack_ge_15m",
           "delivered_slack_ge_30m", "runtime_s", "best_bound", "gap", "commit", "config", "host")
LEGACY_COLUMNS = tuple(c for c in COLUMNS if not c.startswith("delivered_slack_ge_"))   # rows before 2026-11-01
FACILITY_COLUMNS = ("instance", "method", "seed", "facility", "mobility_class", "residents", "release_s",
                    "deadline_state", "deadline_cause", "arrive_by_s", "leave_by_s", "deadline_shelter", "unservable",
                    "delivered_checked", "unresolved", "model_no_route", "not_planned", "first_board_s", "last_leave_s",
                    "commit", "config", "host")
FACILITY_SUFFIX = ".facilities.csv"
RESULTS_DIR = EVACPLAN_ROOT / "results"
LEADERBOARD_PATH = EVACPLAN_ROOT / "LEADERBOARD.md"
RECORDED_OBSERVATIONS_PATH = EVACPLAN_ROOT / "docs" / "recorded_observations.json"
RECORDED_OBSERVATIONS_SCHEMA = "evacplan.recorded_observations/1"
BASELINES = ("b0_independent", "b1_greedy", "b2_vrptw", "b3_mip")     # B0-B3 (not noop)
B2 = "b2_vrptw"
NOT_JUDGED = ("noop",)                                                # plumbing: no verdict, not drawn
MIN_REPEATS = 5                                                       # repeats a method needs for a verdict


class TestSetRefused(PermissionError):
    """The test set is touched only at milestones, after Siyeong approves (program rule 5)."""

    __test__ = False      # not a pytest test class


# ------------------------------------------------------------------------- provenance
def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


DIRTY_SIBLINGS = ("hazard_contract", "program")      # beside evacplan/: their changes can change results too
GENERATED = ("LEADERBOARD.md", "figures", "results")  # evacplan/ outputs the harness writes: never "dirty"
VERSIONED = ("numpy", "ortools", "highspy")


def git_commit(evacplan_root: Path = EVACPLAN_ROOT) -> str:
    """HEAD of this checkout, with ``+dirty`` when ``evacplan/``, ``hazard_contract/`` or ``program/``
    has uncommitted changes, untracked files included (the generated ``evacplan/LEADERBOARD.md``, its
    margin figures under ``evacplan/figures/`` and the result rows under ``evacplan/results/`` excepted:
    they are outputs, not code)."""
    try:
        sha = _git(["rev-parse", "HEAD"], evacplan_root).strip()
        top = Path(_git(["rev-parse", "--show-toplevel"], evacplan_root).strip()).resolve()
        rel = Path(evacplan_root).resolve().relative_to(top).as_posix()
        specs = [f":(top){p}" for p in (rel, *DIRTY_SIBLINGS)] + [f":(top,exclude){rel}/{out}" for out in GENERATED]
        status = _git(["status", "--porcelain", "--", *specs], evacplan_root)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return "unknown"
    return sha + ("+dirty" if status.strip() else "")


@functools.lru_cache(maxsize=1)
def package_versions() -> dict[str, str | None]:
    """Versions that can change results: the installed hazard_contract (``__version__``; its format,
    ``CONTRACT_VERSION``, is recorded separately) and numpy, ortools and highspy, read from the installed
    distributions without importing them (importing highspy here would load its libhighs before OR-Tools'
    bundled one; ``methods.highs_worker``). ``None``: not installed."""
    out: dict[str, str | None] = {"hazard_contract": hc.__version__}
    for name in VERSIONED:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def cpu_model(system: str | None = None, *, cpuinfo: Path = Path("/proc/cpuinfo"), runner: Callable = subprocess.run,
              processor: str | None = None) -> str:
    """The CPU model: Linux ``/proc/cpuinfo`` "model name", macOS ``sysctl -n machdep.cpu.brand_string``,
    else ``platform.processor()``, else ``"unknown cpu"`` (``system``, ``cpuinfo``, ``runner`` and
    ``processor`` stand in for the machine in tests)."""
    system = platform.system() if system is None else system
    if system == "Linux":
        try:
            for line in Path(cpuinfo).read_text(errors="replace").splitlines():
                key, sep, value = line.partition(":")
                if sep and key.strip().lower() == "model name" and value.strip():
                    return " ".join(value.split())
        except OSError:
            pass
    elif system == "Darwin":
        try:
            out = runner(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=10,
                         check=True)
            name = " ".join(str(out.stdout or "").split())
            if name:
                return name
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    proc = platform.processor() if processor is None else processor
    return " ".join(str(proc or "").split()) or "unknown cpu"


def machine_session(system: str | None = None, *, cpuinfo: Path = Path("/proc/cpuinfo"),
                    boot_id: Path = Path("/proc/sys/kernel/random/boot_id"), runner: Callable = subprocess.run) -> str:
    """The boot session of a virtual machine, ``""`` on bare metal. On a VM the CPU label does not name the
    hardware behind it: two cloud containers with the same host string ran B0/B1 1.7-2.4x apart
    (``program/DECISIONS.md``, 2026-11-01), so each boot of a VM is its own host. Linux: a VM has the
    ``hypervisor`` CPU flag; the session is the first 8 characters of ``/proc/sys/kernel/random/boot_id``
    (``"unknown"`` if unreadable). macOS: ``sysctl kern.hv_vmm_present`` = 1, session from
    ``kern.bootsessionuuid``. Other systems: ``""`` (``system``, ``cpuinfo``, ``boot_id``, ``runner`` stand in for
    the machine in tests)."""
    system = platform.system() if system is None else system
    if system == "Linux":
        try:
            flags = [ln for ln in Path(cpuinfo).read_text(errors="replace").splitlines()
                     if ln.partition(":")[0].strip().lower() == "flags"]
        except OSError:
            return ""
        if not any("hypervisor" in ln.partition(":")[2].split() for ln in flags):
            return ""
        try:
            return Path(boot_id).read_text().strip().lower()[:8] or "unknown"
        except OSError:
            return "unknown"
    if system == "Darwin":
        def sysctl(name: str) -> str:
            out = runner(["sysctl", "-n", name], capture_output=True, text=True, timeout=10, check=True)
            return str(out.stdout or "").strip()
        try:
            if sysctl("kern.hv_vmm_present") != "1":
                return ""
        except (OSError, ValueError, subprocess.SubprocessError):
            return ""
        try:
            return sysctl("kern.bootsessionuuid").lower()[:8] or "unknown"
        except (OSError, ValueError, subprocess.SubprocessError):
            return "unknown"
    return ""


_SESSION_RE = re.compile(r", vm boot [^,()]+\)$")


def host_string(*, session: str | None = None) -> str:
    """The machine a row ran on: host name (OS and machine, CPU model, CPU count, Python version[, VM boot
    session]), e.g. ``vm (Linux x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu, python 3.12.3, vm boot
    ff671362)``. Rows are compared, and times read, only between rows with the same host string. On a virtual
    machine the string ends with its boot session (:func:`machine_session`), so each container session is its own
    host; ``session`` stands in for the machine's in tests."""
    session = machine_session() if session is None else session
    tail = f", vm boot {session}" if session else ""
    return (f"{socket.gethostname()} ({platform.system()} {platform.machine()}, {cpu_model()}, {os.cpu_count()} cpu, "
            f"python {platform.python_version()}{tail})")


def host_class(host: str) -> str:
    """A host string without its VM boot session: the class every session of that virtual machine belongs to."""
    return _SESSION_RE.sub(")", host)


def host_slug(host: str) -> str:
    """A file-name-safe name for a host string: its lower-case words joined by ``-``, plus 8 hex digits of its
    SHA-256 (two host strings never share a slug)."""
    words = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")[:80].strip("-") or "host"
    return f"{words}-{hashlib.sha256(host.encode()).hexdigest()[:8]}"


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


def delivered_slacks(plan: PlanResult) -> list[tuple[float, int]]:
    """``(safety slack in s, residents)`` for every checked trip that delivers residents, in plan order.

    A delivered resident's safety slack is the smallest oracle :attr:`~evacplan.oracle.LegResult.slack_s` over
    the legs of their vehicle, moving and stationary, from the start of its itinerary up to and including the
    last leg of the trip that unloads them: the prefix rule of the plan's ``min_slack_s`` (ASSUMPTIONS #27).
    Each leg's slack is capped by the oracle at horizon - leg end, so a late delivery keeps at most the time
    left before the horizon. Read from the oracle's result objects only; no state is declared here (rule 3)."""
    out: list[tuple[float, int]] = []
    for v in plan.vehicles:
        for t in v.trips:
            if t.state != State.CHECKED or not t.counts.total:
                continue
            prefix = [lg.slack_s for lg in v.legs if lg.action <= t.action]
            if not prefix or any(s is None for s in prefix):        # pragma: no cover - the oracle's own invariant
                raise AssertionError(f"vehicle {v.vehicle}: a checked trip includes a leg without a slack")
            out.append((float(min(prefix)), int(t.counts.total)))
    return out


def delivered_by_margin(plan: PlanResult, margins_min: Iterable[int] = MARGINS_MIN) -> dict[int, int]:
    """Residents delivered with a safety slack of at least m minutes (:func:`delivered_slacks`), for each m in
    ``margins_min``. Slacks of checked legs are never negative, so m = 0 gives ``plan.delivered_total``; times
    compare with the oracle's 1 µs tolerance (ASSUMPTIONS #3)."""
    pairs = delivered_slacks(plan)
    return {int(m): sum(n for s, n in pairs if s >= 60.0 * float(m) - TIME_TOL_S) for m in margins_min}


def _margin_curve(margins: Mapping[int, int], delivered: int) -> dict[int, int]:
    curve = {int(k): int(v) for k, v in dict(margins).items()}
    if sorted(curve) != sorted(MARGINS_MIN):
        raise ValueError(f"the margin curve needs exactly the margins {MARGINS_MIN} (minutes), not {sorted(curve)}")
    if curve[0] != delivered:
        raise ValueError(f"residents delivered with slack >= 0 ({curve[0]}) must equal delivered_checked ({delivered})")
    if any(curve[a] < curve[b] for a, b in zip(MARGINS_MIN, MARGINS_MIN[1:])):
        raise ValueError(f"residents delivered with slack >= m cannot grow with m: {curve}")
    return curve


def make_row(*, entry: SplitEntry, set_name: str, method_name: str, method_config: dict, seed: int,
             budget_s: float, plan, runtime_s: float, best_bound: float | None, commit: str, host: str,
             versions: dict | None = None, diagnostics: dict | None = None,
             margins: Mapping[int, int] | None = None, bound_only: bool = False) -> dict:
    """One result row. ``margins`` (minutes -> residents, every m in :data:`MARGINS_MIN`) defaults to
    :func:`delivered_by_margin` of ``plan``; slack >= 0 must equal ``plan.delivered_total``. ``bound_only``: the
    method plans nothing and only proves ``best_bound`` (:attr:`evacplan.methods.Method.bound_only`); the row's
    config says so and its ``gap`` is empty (it has no plan to measure)."""
    delivered = int(plan.delivered_total)
    curve = _margin_curve(delivered_by_margin(plan) if margins is None else margins, delivered)
    if best_bound is None or bound_only:
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
        "versions": dict(package_versions() if versions is None else versions),
        "delivered_by_margin_min": {str(m): curve[m] for m in MARGINS_MIN},
    }
    if diagnostics:
        config["diagnostics"] = dict(diagnostics)
    if bound_only:
        config["bound_only"] = True
    return {
        "instance": entry.id, "method": method_name, "seed": str(int(seed)), "delivered_checked": str(delivered),
        "unresolved": str(int(plan.unresolved_total)), "model_no_route": str(int(plan.model_no_route_total)),
        "makespan_s": _num(plan.makespan_s, 1), "min_slack_s": _num(plan.min_slack_s, 1),
        **{margin_column(m): str(curve[m]) for m in ROW_MARGINS_MIN},
        "runtime_s": _num(runtime_s, 4), "best_bound": _num(best_bound, 3), "gap": _num(gap, 6),
        "commit": commit, "config": json.dumps(config, sort_keys=True, separators=(",", ":")), "host": host,
    }


def row_config(row: dict) -> dict:
    return json.loads(row["config"])


def is_bound_only(row: dict) -> bool:
    """A row of a bound-only method (it plans nothing; only its ``best_bound`` counts)."""
    return row_config(row).get("bound_only") is True


def _key(row: dict) -> tuple:
    """Upsert key: (set, budget, instance, method, seed, host[, facility, class])."""
    cfg = row_config(row)
    key = (cfg["set"], float(cfg["budget_s"]), row["instance"], row["method"], int(row["seed"]), row["host"])
    if "facility" in row:
        key += (row["facility"], CLASSES.index(row["mobility_class"]))
    return key


def _columns(path: Path) -> tuple[str, ...]:
    return FACILITY_COLUMNS if Path(path).name.endswith(FACILITY_SUFFIX) else COLUMNS


def read_rows(path: Path) -> list[dict]:
    """Rows of a result or per-facility CSV. Result files written before 2026-11-01 (:data:`LEGACY_COLUMNS`,
    no margin columns) are read with the new columns empty; the next upsert rewrites them with all columns."""
    if not path.is_file():
        return []
    cols = _columns(path)
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        header = tuple(reader.fieldnames or ())
        if header == cols:
            return list(reader)
        if cols == COLUMNS and header == LEGACY_COLUMNS:
            return [{c: r.get(c) or "" for c in COLUMNS} for r in reader]
        raise ValueError(f"{path}: columns {reader.fieldnames} are not the harness columns {list(cols)}")


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
    """Replace rows with the same (set, budget, instance, method, seed, host[, facility, class]); keep all others
    (the same run on another host is another row)."""
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
    ``budget_s`` seconds each; returns the result rows (also upserted into the CSV). ``method`` may be an
    alias (``B2``); rows and files use the registered name. Instances the method does not apply to
    (:meth:`~evacplan.methods.Method.applicable`, e.g. B3 beyond S) are skipped and get no row."""
    method = canonical(method)
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
    commit, host, versions = git_commit(), host_string(), package_versions()
    log(f"[evacplan] {method} on {set_name} ({len(entries)} instances x {len(seeds)} seeds) at {budget_s:g} s; "
        f"commit {commit}; host {host}")
    loaded = [(e, *load_entry(e, cache_dir)) for e in entries]          # regenerate before timing
    csv_path = Path(results_dir) / f"{method}.csv"
    fac_path = Path(results_dir) / f"{method}{FACILITY_SUFFIX}"
    rows: list[dict] = []
    with bench_guard(lock, f"evacplan run {method} {set_name} {budget_s:g}s", log) as lock_state:
        for e, inst, ss in loaded:
            if not m.applicable(inst):
                log(f"  {e.id}: skipped ({method} does not apply to this instance)")
                continue
            oracle = Oracle(inst, ss)
            deadlines = class_deadlines(inst, ss, oracle=oracle)          # per facility; not timed
            for seed in seeds:
                t0 = time.monotonic()
                res = m.solve(inst, ss, budget_s=float(budget_s), seed=seed, deadline=t0 + float(budget_s))
                runtime = time.monotonic() - t0
                plan = oracle.check_plan(res.solution)
                row = make_row(entry=e, set_name=set_name, method_name=method, method_config=m.config(), seed=seed,
                               budget_s=budget_s, plan=plan, runtime_s=runtime, best_bound=res.best_bound,
                               commit=commit, host=host, versions=versions, diagnostics=res.diagnostics,
                               bound_only=bool(getattr(m, "bound_only", False)))
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


def table_key(row: dict) -> tuple[str, float, str]:
    """(set, budget, host): rows are compared only with rows of the same key."""
    cfg = row_config(row)
    return cfg["set"], float(cfg["budget_s"]), row["host"]


def _tables(rows: Iterable[dict]) -> dict[tuple[str, float, str], list[dict]]:
    """Rows per table (set, budget, host). A bound-only method's rows join every table of their set and host,
    whatever budget they were computed with (a proven bound does not depend on the time it took); with no such
    table they get one of their own (at their smallest budget)."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    bounds: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if is_bound_only(r):
            s, _, h = table_key(r)
            bounds[(s, h)].append(r)
        else:
            groups[table_key(r)].append(r)
    for (s, h), rs in bounds.items():
        keys = [k for k in groups if (k[0], k[2]) == (s, h)] or [(s, min(table_key(r)[1] for r in rs), h)]
        for k in keys:
            groups[k].extend(rs)
    return {k: groups[k] for k in sorted(groups, key=lambda k: (k[0] != "dev", k[0], k[1], k[2]))}


def _fmt(x: float | None, nd: int = 1) -> str:
    return "–" if x is None else f"{x:.{nd}f}"


def _count(x: float) -> str:
    """A count or a median of counts: whole numbers plain, others to one decimal."""
    x = round(float(x), 6)                     # sums of medians of whole counts: no float noise in the text
    return f"{x:.0f}" if x.is_integer() else f"{x:.1f}"


def _stat(values: list[float], residents: int | None = None) -> str:
    """The median of repeated values, then (share of ``residents``), then [min–max] when they differ; ``–`` for
    none."""
    if not values:
        return "–"
    med, lo, hi = statistics.median(values), min(values), max(values)
    share = f" ({100 * med / residents:.1f}%)" if residents else ""
    return f"{_count(med)}{share}" + (f" [{_count(lo)}–{_count(hi)}]" if lo != hi else "")


def _value(row: dict, col: str) -> float | None:
    v = row.get(col)
    return None if v in (None, "") else float(v)


def seed_totals(rows: Iterable[dict], col: str, instances: Iterable[str] | None = None) -> dict[int, float]:
    """Per-seed totals of ``col`` over ``instances`` (default: every instance of ``rows``), for the seeds whose rows
    cover all of them with a value (other seeds have no total)."""
    rows = list(rows)
    need = set(instances) if instances is not None else {r["instance"] for r in rows}
    by: dict[int, dict[str, float | None]] = defaultdict(dict)
    for r in rows:
        by[int(r["seed"])][r["instance"]] = _value(r, col)
    return {s: sum(v[i] for i in need) for s, v in sorted(by.items())
            if need <= set(v) and all(v[i] is not None for i in need)}


def _total(rows: list[dict], col: str, residents: int | None = None) -> str:
    """A method's total of ``col`` in a table: median and [min–max] of the per-seed totals; when the seeds differ
    by instance, the sum of the per-instance medians; ``–`` when a row lacks the column (rows from before it)."""
    if any(_value(r, col) is None for r in rows):
        return "–"
    seeds = {int(r["seed"]) for r in rows}
    totals = seed_totals(rows, col)
    if len(totals) == len(seeds):
        return _stat(list(totals.values()), residents)
    per_inst: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        per_inst[r["instance"]].append(float(r[col]))
    med = sum(statistics.median(v) for v in per_inst.values())
    share = f" ({100 * med / residents:.1f}%)" if residents else ""
    return f"{_count(med)}{share} [seeds differ by instance]"


def _unservable(facility_rows: list[dict]) -> dict[tuple, float]:
    """(set, budget, host, method, instance) -> residents no plan can serve (median over seeds)."""
    per: dict[tuple, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for r in facility_rows:
        per[(*table_key(r), r["method"], r["instance"])][int(r["seed"])] += float(r["unservable"])
    return {k: statistics.median(v.values()) for k, v in per.items()}


# ----------------------------------------------------------------- recorded observations and the B2 bar
@dataclass(frozen=True)
class RecordedObservation:
    """A total observed outside the result rows (e.g. a review's run whose rows were not kept), keyed by set,
    budget, method and host. Only B2's enter the leaderboard, as B2's best observed total. An observation keyed by
    a host class (a VM host string without its boot session, :func:`host_class`) applies to every session of that
    class: it can only raise the bar, never lower it. One keyed by a full host string applies to that host only."""

    set: str
    budget_s: float
    method: str
    host: str
    delivered_checked: int
    source: str
    unresolved: int | None = None
    commit: str | None = None
    recorded: str | None = None
    note: str = ""

    @classmethod
    def of(cls, obj) -> "RecordedObservation":
        if isinstance(obj, cls):
            return obj
        d = dict(obj)
        names = {f.name for f in fields(cls)}
        missing = {"set", "budget_s", "method", "host", "delivered_checked", "source"} - set(d)
        if missing or set(d) - names:
            raise ValueError(f"recorded observation {d}: missing {sorted(missing)}, unknown {sorted(set(d) - names)}")
        return cls(set=str(d["set"]), budget_s=float(d["budget_s"]), method=canonical(str(d["method"])),
                   host=str(d["host"]), delivered_checked=int(d["delivered_checked"]), source=str(d["source"]),
                   unresolved=None if d.get("unresolved") is None else int(d["unresolved"]),
                   commit=d.get("commit"), recorded=d.get("recorded"), note=str(d.get("note") or ""))


def load_recorded_observations(path: Path = RECORDED_OBSERVATIONS_PATH) -> list[RecordedObservation]:
    """The version-controlled table of recorded observations (``evacplan/docs/recorded_observations.json``)."""
    path = Path(path)
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    if data.get("schema") != RECORDED_OBSERVATIONS_SCHEMA:
        raise ValueError(f"{path}: schema {data.get('schema')!r} is not {RECORDED_OBSERVATIONS_SCHEMA!r}")
    return [RecordedObservation.of(o) for o in data.get("observations", [])]


@dataclass(frozen=True)
class B2Comparison:
    """The bar for beating B2 and the verdicts of one table (one set, budget and host)."""

    set_name: str
    budget: float
    host: str
    instances: tuple[str, ...]                    # the set's instances
    best_of_baselines: dict[str, float]           # per instance with a baseline row: best delivered by any baseline
    best_of_baselines_total: float | None         # their sum; None unless every instance has a baseline row
    b2_best_observed: float | None                # best complete B2 per-seed total or recorded B2 observation
    b2_source: str
    recorded: tuple[RecordedObservation, ...]     # recorded B2 observations of this set, budget and host
    bar: float | None                             # max(b2_best_observed, best_of_baselines_total); None if either is
    verdicts: dict[str, str]                      # method -> verdict

    def bar_line(self) -> str:
        if self.bar is not None:
            return (f"Bar for beating B2 on this host: max(B2 best observed {_count(self.b2_best_observed)} "
                    f"[{self.b2_source}], best-of-baselines total {_count(self.best_of_baselines_total)}) = "
                    f"{_count(self.bar)}; a method beats B2 only if its worst of ≥{MIN_REPEATS} repeats exceeds "
                    f"{_count(self.bar)}.")
        n = len(self.instances)
        why = [f"B2 best observed {_count(self.b2_best_observed)} [{self.b2_source}]" if self.b2_best_observed is not None
               else f"no B2 total covering all {n} instances and no recorded B2 observation for this set, budget and host"]
        missing = [i for i in self.instances if i not in self.best_of_baselines]
        why.append(f"best-of-baselines total {_count(self.best_of_baselines_total)}"
                   if self.best_of_baselines_total is not None else f"no baseline row for {len(missing)} of {n} instances")
        return f"Bar for beating B2 on this host: undefined ({'; '.join(why)}); no method is judged against B2 here."


def _verdict(method: str, rows: list[dict], instances: tuple[str, ...], bar: float | None) -> str:
    if method in BASELINES:
        return "baseline"
    if method in NOT_JUDGED:
        return "–"
    seeds = {int(r["seed"]) for r in rows}
    totals = seed_totals(rows, "delivered_checked", instances)
    if len(totals) < MIN_REPEATS or len(totals) < len(seeds):         # every repeat must cover every instance
        return f"n/a (fewer than {MIN_REPEATS} repeats or not all instances)"
    if bar is None:
        return "n/a (no bar on this host)"
    worst = min(totals.values())
    return "beats B2" if worst > bar else f"no (worst {_count(worst)} ≤ bar {_count(bar)})"


def compare_to_b2(rows: Iterable[dict], instances: Iterable[str], *, set_name: str, budget: float, host: str,
                  observations: Iterable = ()) -> B2Comparison:
    """The 2026-11-01 rule (``program/DECISIONS.md``) for one table, from that set's, budget's and host's rows only:

    * best-of-baselines total = sum over ``instances`` (the set's) of the most residents any baseline row (B0-B3,
      any seed) delivered on that instance;
    * B2 best observed = the largest of B2's per-seed totals over the seeds that cover every instance and of the
      recorded observations (``observations``) of B2 for this set, budget and host, or for its host class (a VM
      host without its boot session: an observation of the class applies to every session, which can only raise
      the bar);
    * bar = max of the two; a method other than the baselines and noop "beats B2" only if it has at least
      :data:`MIN_REPEATS` seeds, each covering every instance, and its worst per-seed total exceeds the bar.
    """
    budget = float(budget)
    rows = [r for r in rows if table_key(r) == (set_name, budget, host) and not is_bound_only(r)]   # plans only
    instances = tuple(dict.fromkeys(instances)) or tuple(sorted({r["instance"] for r in rows}))
    best: dict[str, float] = {}
    for r in rows:
        if r["method"] in BASELINES:
            v = float(r["delivered_checked"])
            best[r["instance"]] = max(best.get(r["instance"], v), v)
    y = sum(best[i] for i in instances) if all(i in best for i in instances) else None
    b2_totals = seed_totals([r for r in rows if r["method"] == B2], "delivered_checked", instances)
    hosts = {host, host_class(host)}
    recorded = tuple(o for o in map(RecordedObservation.of, observations)
                     if (o.set, o.budget_s, o.method) == (set_name, budget, B2) and o.host in hosts)
    values = list(b2_totals.values()) + [float(o.delivered_checked) for o in recorded]
    x = max(values) if values else None
    source = ""
    if x is not None:
        seeds = [s for s, t in b2_totals.items() if t == x]
        parts = [f"B2 rows on this host, seed{'s' if len(seeds) > 1 else ''} {', '.join(map(str, seeds))}"] if seeds else []
        source = "; ".join(parts + [f"recorded: {o.source}" for o in recorded if o.delivered_checked == x])
    bar = max(x, y) if x is not None and y is not None else None
    by_method: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_method[r["method"]].append(r)
    verdicts = {m: _verdict(m, rs, instances, bar) for m, rs in sorted(by_method.items())}
    return B2Comparison(set_name=set_name, budget=budget, host=host, instances=instances,
                        best_of_baselines={i: v for i, v in best.items() if i in instances},
                        best_of_baselines_total=y, b2_best_observed=x, b2_source=source, recorded=recorded, bar=bar,
                        verdicts=verdicts)


# ----------------------------------------------------------------------------- margin figure
SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SERIES_MARKERS = ("o", "s", "^", "D", "v", "P", "X", "h")
_INK, _INK_2, _MUTED, _GRID, _AXIS, _SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def _row_curve(row: dict) -> list[int] | None:
    raw = row_config(row).get("delivered_by_margin_min")
    if not isinstance(raw, dict):
        return None
    try:
        return [int(raw[str(m)]) for m in MARGINS_MIN]
    except (KeyError, TypeError, ValueError):
        return None


def margin_curves(rows: Iterable[dict]) -> dict[str, dict]:
    """Per method of one table (noop and bound-only methods left out; methods with a row lacking the curve left
    out): residents delivered with slack >= m for every m in :data:`MARGINS_MIN`, summed over the method's
    instances: ``median`` over seeds
    and ``lo``/``hi`` (min/max) of the per-seed totals; when the seeds differ by instance, the sum of the
    per-instance medians without a band (``per_seed_totals`` False)."""
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["method"] not in NOT_JUDGED and not is_bound_only(r):
            by[r["method"]].append(r)
    out: dict[str, dict] = {}
    for method, rs in sorted(by.items()):
        curves = [_row_curve(r) for r in rs]
        if any(c is None for c in curves):
            continue
        per_seed: dict[int, dict[str, list[int]]] = defaultdict(dict)
        for r, c in zip(rs, curves):
            per_seed[int(r["seed"])][r["instance"]] = c
        instances = sorted({r["instance"] for r in rs})
        k = range(len(MARGINS_MIN))
        if all(set(v) == set(instances) for v in per_seed.values()):
            cols = list(zip(*[[sum(v[i][j] for i in instances) for j in k] for _, v in sorted(per_seed.items())]))
            med, lo, hi, exact = [statistics.median(c) for c in cols], [min(c) for c in cols], [max(c) for c in cols], True
        else:
            per_inst: dict[str, list[list[int]]] = defaultdict(list)
            for r, c in zip(rs, curves):
                per_inst[r["instance"]].append(c)
            med = [sum(statistics.median(c[j] for c in cs) for cs in per_inst.values()) for j in k]
            lo, hi, exact = list(med), list(med), False
        out[method] = {"margins_min": list(MARGINS_MIN), "median": med, "lo": lo, "hi": hi,
                       "instances": len(instances), "seeds": len(per_seed), "per_seed_totals": exact}
    return out


def figure_name(set_name: str, budget: float, host: str) -> str:
    """``margin_<set>_<budget>s_<host-slug>.png``."""
    return f"margin_{re.sub(r'[^A-Za-z0-9]+', '-', set_name)}_{float(budget):g}s_{host_slug(host)}.png"


def _series_style(methods: Iterable[str]) -> dict[str, tuple[str, str, str]]:
    """(colour, marker, line style) per method. Colour follows the method, not its rank: B0-B3 keep the first four
    categorical slots, other methods take the next four in name order; any beyond eight are drawn in muted grey,
    dashed, each with its own marker (the legend names every line)."""
    slots = {m: i for i, m in enumerate(BASELINES)}
    rest = [m for m in sorted(methods) if m not in slots]
    out = {}
    for m in methods:
        i = slots[m] if m in slots else len(BASELINES) + rest.index(m)
        colour, style = (SERIES_COLORS[i], "-") if i < len(SERIES_COLORS) else (_MUTED, "--")
        out[m] = (colour, SERIES_MARKERS[i % len(SERIES_MARKERS)], style)
    return out


def write_margin_figure(rows: Iterable[dict], path: Path, *, set_name: str, budget: float, host: str) -> str:
    """Residents delivered vs required safety margin (0-60 min) for one table (one set, budget and host): one line
    per method (median over seeds, :func:`margin_curves`) with a min-max band. The title says SYNTHETIC when any
    row is SYNTHETIC and names the host. Agg canvas at a fixed size and dpi, matplotlib's default style whatever
    the local configuration, no software stamp: the same rows give the same bytes. Returns the title (also the
    PNG's ``Title`` text)."""
    import matplotlib.style
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import MaxNLocator

    rows = list(rows)
    curves = margin_curves(rows)
    synthetic = any(row_config(r).get("label") == "SYNTHETIC" for r in rows)
    title = (f"{'SYNTHETIC - ' if synthetic else ''}residents delivered vs required safety margin\n"
             f"{set_name}, budget {float(budget):g} s, host {host}")
    style = _series_style(curves)
    x = list(MARGINS_MIN)
    with matplotlib.style.context("default"), rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        fig = Figure(figsize=(8.0, 4.4), dpi=100, facecolor=_SURFACE)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot()
        ax.set_facecolor(_SURFACE)
        for method, c in curves.items():
            colour, marker, line = style[method]
            if c["per_seed_totals"] and c["lo"] != c["hi"]:
                ax.fill_between(x, c["lo"], c["hi"], color=colour, alpha=0.10, linewidth=0)
            seeds = f"{c['seeds']} seed{'s' if c['seeds'] != 1 else ''}"
            note = "" if c["per_seed_totals"] else ", seeds differ by instance"
            ax.plot(x, c["median"], color=colour, linestyle=line, linewidth=1.5, marker=marker, markersize=6,
                    markeredgecolor=_SURFACE, markeredgewidth=1.2, solid_joinstyle="round", solid_capstyle="round",
                    label=f"{method} ({c['instances']} instances, {seeds}{note})")
        if not curves:
            ax.text(0.5, 0.5, "no rows with margin columns", transform=ax.transAxes, ha="center", va="center",
                    color=_INK_2)
        ax.set_xlim(0, 60)
        ax.set_xticks([0, 5, 10, 15, 20, 30, 45, 60])
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel("required safety margin (min): residents count when their slack is at least this", color=_INK_2)
        ax.set_ylabel("residents delivered (sum over instances)", color=_INK_2)
        ax.tick_params(colors=_MUTED, labelcolor=_INK_2)
        ax.grid(True, color=_GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(_AXIS)
        ax.set_title(title, loc="left", fontsize=10, color=_INK)
        if curves:
            ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=8, labelcolor=_INK,
                      title="line: median over seeds\nband: min-max over seeds", title_fontsize=8)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=100, facecolor=_SURFACE, bbox_inches="tight", metadata={"Software": None, "Title": title})
    return title


# --------------------------------------------------------------------------------- render
def _bounds_table(plans: list[dict], bound_rows: list[dict], inst_ids: list[str], labels: Mapping[str, str],
                  residents: Mapping[str, int], size_of: Mapping[str, str]) -> list[str]:
    """The table of a leaderboard section for bound-only methods: per instance their proven bound, its gap to the
    best plan of the section, (bound - best delivered) / bound with best delivered = the most residents any method
    delivered on the instance in this section (any seed), and their runtime; then the mean gap by size. A bound
    below a delivered plan would be a bug: it is flagged INVALID."""
    best: dict[str, float] = {}
    for r in plans:
        v = float(r["delivered_checked"])
        best[r["instance"]] = max(best.get(r["instance"], v), v)
    methods = sorted({r["method"] for r in bound_rows})
    out = ["Proven upper bounds of bound-only methods (they plan nothing: not in the method table, no verdict, not "
           "in the figure; their rows join every table of this set and host, whatever budget computed them); "
           "**gap** = (bound - best delivered) / bound, **best delivered** = the most residents any method delivered "
           "on the instance in this table (any seed):", "",
           "| instance | label | residents | best delivered | " + " | ".join(f"{m} | gap | runtime (s)" for m in methods)
           + " |", "|---|---|---|---|" + "---|---|---|" * len(methods)]
    gaps: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    invalid: list[str] = []
    for i in inst_ids:
        cells = []
        for m in methods:
            rs = [r for r in bound_rows if r["instance"] == i and r["method"] == m and r["best_bound"]]
            if not rs:
                cells += ["–", "–", "–"]
                continue
            b = min(float(r["best_bound"]) for r in rs)
            rt = statistics.median(float(r["runtime_s"]) for r in rs)
            gap = None if i not in best else ((b - best[i]) / b if b > 0 else 0.0)
            if gap is not None:
                gaps[m][size_of.get(i, "other")].append(gap)
                gaps[m]["all"].append(gap)
                if b < best[i]:
                    invalid.append(f"{m} on {i}: bound {b:g} < delivered {_count(best[i])}")
            cells += [f"{b:g}", "–" if gap is None else f"{100 * gap:.1f}%", f"{rt:.1f}"]
        out.append(f"| {i} | {labels.get(i, 'real')} | {residents.get(i, '–')} | "
                   f"{'–' if i not in best else _count(best[i])} | " + " | ".join(cells) + " |")
    order = {z: n for n, z in enumerate(("S", "M", "L"))}
    for m in methods:
        parts = [f"{z} {100 * statistics.mean(v):.1f}% ({len(v)})"
                 for z, v in sorted(gaps[m].items(), key=lambda kv: (kv[0] == "all", order.get(kv[0], 3), kv[0]))]
        rs = [r for r in bound_rows if r["method"] == m]
        budgets = ", ".join(f"{b:g} s" for b in sorted({float(row_config(r)["budget_s"]) for r in rs}))
        commits = ", ".join(sorted({r["commit"][:12] for r in rs}))
        out += ["", f"Mean gap of {m} by size (instances): {', '.join(parts) or '–'}; computed at budget {budgets}, "
                    f"commit {commits}."]
    if invalid:
        out += ["", "**INVALID BOUND** (a proven bound below a delivered plan is a bug): " + "; ".join(invalid) + "."]
    return out


def render_leaderboard(rows: list[dict], split: Split | None = None, facility_rows: list[dict] | None = None, *,
                       observations: Iterable | None = None, figure_links: Mapping[tuple, str] | None = None) -> str:
    """LEADERBOARD.md text: one section per (set, budget, host). ``observations``: recorded observations (default:
    ``docs/recorded_observations.json``); ``figure_links``: (set, budget, host) -> the margin figure's path relative
    to the leaderboard."""
    observations = load_recorded_observations() if observations is None else [RecordedObservation.of(o)
                                                                              for o in observations]
    unserv = _unservable(facility_rows or [])
    residents: dict[str, int] = {}
    order: dict[str, int] = {}
    size_of: dict[str, str] = {}
    set_ids: dict[str, list[str]] = {}
    if split is not None:
        for name, entries in split.sets.items():
            set_ids[name] = [e.id for e in entries]
            for e in entries:
                order.setdefault(e.id, len(order))
                size_of[e.id] = str(e.config.get("size", "other"))
                if "residents" in e.stats:
                    residents[e.id] = int(e.stats["residents"])
    lines = [
        "# evacplan leaderboard (Track C)",
        "",
        "Regenerated by `evacplan run` and `evacplan leaderboard` from `evacplan/results/*.csv` (committed; the plans and "
        "oracle results under `results/runs/` are not), with one safety-margin figure per table in `figures/`. "
        "Do not edit by hand.",
        "",
        "* **delivered**, **unresolved**, **model_no_route**, **not planned** and **unservable** come from "
        "`evacplan.oracle`: delivered = residents whose trip is `checked` in all K members; `unresolved` is never safe "
        "and never delivered; `model_no_route` is scoped to the hazard model, its members and horizon; not planned = "
        "residents no itinerary boards. **best bound** and **gap** come from the methods' own proofs (e.g. B3's "
        "relaxed MIP), not from the oracle. **runtime** is the harness's wall clock around the method's solve (the "
        "oracle check is not timed).",
        "* **unservable** = residents that no plan can serve within the model, fleet and horizon: a scoped "
        "`model_no_route` per facility and mobility class, declared by the oracle (`results/<method>.facilities.csv`, "
        "which also holds each facility's latest first-arrival and last-departure times). They are counted again "
        "inside not planned (or model_no_route / unresolved if a plan tries them).",
        "* **One table per set, budget and host.** Methods are compared only at **equal wall-clock budgets** and on "
        "**the same host**: everything in a table (totals, best bounds, best of baselines, the bar for beating B2, the "
        "verdicts and the margin figure) uses only that host's rows. Rows from different hosts are never pooled or "
        "compared, and times are never compared across hosts: when the work moves to another machine, the baselines "
        "are re-run there (`program/DECISIONS.md`, 2026-11-01). The host string names the machine, its OS, CPU model "
        "and CPU count, and the Python version. Rows over budget are counted.",
        "* **Repeats**: every method runs 5 repeats (seeds 0-4, `--repeats 5`) at the same budget on a quiet machine. "
        "A per-instance cell is the median over seeds, followed by [min–max] when the seeds differ; in the method "
        "table, a total is the median of the per-seed totals, followed by their [min–max] when they differ. "
        "Time-limited methods differ between repeats even when they ignore the seed: B2's OR-Tools search is seedless, "
        "so its repeats differ only through machine load (how far the search gets within the budget), and its outcome "
        "is not monotone in that depth (`docs/ASSUMPTIONS.md` #84; each B2 row records the solutions found and the "
        "final objective).",
        "* **Beating B2** (`program/DECISIONS.md`, 2026-11-01): the **best-of-baselines total** is the sum over the "
        "set's instances of the most residents any baseline (B0, B1, B2, B3; any seed) delivered on that instance; "
        "**B2 best observed** is the largest B2 per-seed total over the seeds that cover every instance of the set, or "
        "a recorded observation of B2 for the same set, budget and host (`docs/recorded_observations.json`, printed "
        "with its source), whichever is larger; the **bar** is the larger of the two. A method other than the "
        "baselines and noop beats B2 only if its worst of 5 repeats exceeds the bar: it needs at least 5 repeats, each "
        "covering every instance of the set, and its lowest per-seed total must be above the bar. Otherwise the "
        "verdict is no (worst ≤ bar) or n/a (fewer than 5 repeats, a repeat missing an instance, or no bar on this "
        "host).",
        "* **slack ≥ m min** = residents delivered with a safety slack of at least m minutes: the smallest oracle leg "
        "slack over their vehicle's legs from the start of its itinerary through the unloading that delivers them, "
        "each leg's slack capped at the time left before the hazard horizon (`docs/ASSUMPTIONS.md` #91). slack ≥ 0 "
        "equals delivered. The problem definition is unchanged: delivered counts every checked trip whatever its "
        "margin. Each table's figure plots residents delivered against the required margin (0-60 min).",
        "* **mean gap** = mean of (best bound - delivered) / best bound over the method's own proven bounds (exact or "
        "relaxation methods, e.g. B3 on S instances only); a method that runs on fewer instances is summed over fewer "
        "residents (see the size table).",
        "* **Bound-only methods** (e.g. `e4_flow_bound`, `docs/ASSUMPTIONS.md` #94) plan nothing and only prove an "
        "upper bound on the residents any plan can deliver. Their bounds enter the best-bound column and their own "
        "bounds table (with runtime and the gap to the best plan of the table); they are left out of the method "
        "table, the verdicts and the margin figure. A proven bound does not depend on the budget that computed it, so "
        "their rows join every table of the same set and host.",
        "* **SYNTHETIC** rows are SYNTHETIC instances (`evacplan/instances/SPLIT.json`), not real-world results.",
        "",
    ]
    if not rows:
        lines += ["No results yet.", ""]
        return "\n".join(lines)
    slack_cols = [(m, margin_column(m)) for m in LEADERBOARD_MARGINS_MIN]
    for (set_name, budget, host), g_all in _tables(rows).items():
        g = [r for r in g_all if not is_bound_only(r)]               # plans (every table below but the bounds)
        gb = [r for r in g_all if is_bound_only(r)]                  # bound-only methods: their bounds only
        inst_ids = sorted({r["instance"] for r in g_all}, key=lambda i: (order.get(i, len(order)), i))
        instances = tuple(set_ids.get(set_name) or inst_ids)
        cmp = compare_to_b2(g, instances, set_name=set_name, budget=budget, host=host, observations=observations)
        labels = {r["instance"]: row_config(r)["label"] or "real" for r in g_all}
        lines += [f"## {set_name}, budget {budget:g} s, host {host}", "",
                  "Rows from this host only; no row of another host enters this table, its bar or its figure.", ""]
        bounds_lines = _bounds_table(g, gb, inst_ids, labels, residents, size_of) if gb else []
        if not g:
            lines += ["No plans for this set, budget and host (bound-only rows only).", "", *bounds_lines, ""]
            continue
        lines += ["| method | label | instances | seeds | delivered | unresolved | model_no_route | not planned | "
                  "unservable | residents | " + " | ".join(f"slack ≥ {m} min" for m, _ in slack_cols) +
                  " | min slack (s) | mean runtime (s) | over budget | mean gap | B2 verdict | commit |",
                  "|---|---|---|---|---|---|---|---|---|---|" + "---|" * len(slack_cols) + "---|---|---|---|---|---|"]
        by_method: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in g:
            by_method[(r["method"], row_config(r)["label"] or "real")].append(r)
        for (meth, label), rs in sorted(by_method.items()):
            ids = sorted({r["instance"] for r in rs})
            n_res = sum(residents[i] for i in ids) if all(i in residents for i in ids) else None
            seeds = sorted({int(r["seed"]) for r in rs})
            parts = [seed_totals(rs, c) for c in ("delivered_checked", "unresolved", "model_no_route")]
            if n_res is None:
                not_planned = "–"
            elif all(len(p) == len(seeds) for p in parts):
                not_planned = _stat([n_res - sum(p[s] for p in parts) for s in seeds])
            else:
                med = [sum(statistics.median(float(r[c]) for r in rs if r["instance"] == i) for i in ids)
                       for c in ("delivered_checked", "unresolved", "model_no_route")]
                not_planned = f"{_count(n_res - sum(med))} [seeds differ by instance]"
            us = [unserv.get((set_name, budget, host, meth, i)) for i in ids]
            slacks = [float(r["min_slack_s"]) for r in rs if r["min_slack_s"]]
            gaps = [float(r["gap"]) for r in rs if r["gap"]]
            over = sum(float(r["runtime_s"]) > budget for r in rs)
            commits = sorted({r["commit"][:12] for r in rs})
            lines.append(
                f"| {meth} | {label} | {len(ids)} | {len(seeds)} | {_total(rs, 'delivered_checked', n_res)} | "
                f"{_total(rs, 'unresolved')} | {_total(rs, 'model_no_route')} | {not_planned} | "
                f"{'–' if any(u is None for u in us) else _count(sum(us))} | {'–' if n_res is None else n_res} | "
                + " | ".join(_total(rs, c) for _, c in slack_cols) +
                f" | {_fmt(min(slacks) if slacks else None)} | "
                f"{_fmt(sum(float(r['runtime_s']) for r in rs) / len(rs), 3)} | {over} | "
                f"{_fmt(sum(gaps) / len(gaps) if gaps else None, 3)} | {cmp.verdicts.get(meth, '–')} | "
                f"{', '.join(commits)} |")
        lines += ["", cmp.bar_line()]
        for o in cmp.recorded:
            extra = "" if o.unresolved is None else f", {o.unresolved} unresolved"
            lines += ["", f"Recorded B2 observation for this set, budget and host (not in the rows; "
                          f"`docs/recorded_observations.json`): {o.delivered_checked} delivered{extra} [{o.source}]."]
        if not margin_curves(g):
            lines += ["", "Margin figure: none (no rows with margin columns on this host)."]
        elif figure_links and (set_name, budget, host) in figure_links:
            tag = "SYNTHETIC: " if any(row_config(r).get("label") == "SYNTHETIC" for r in g) else ""
            lines += ["", "Residents delivered vs required safety margin (line: median over seeds; band: min–max; this "
                          "host's rows only; noop not drawn):", "",
                      f"![{tag}residents delivered vs required margin, {set_name}, {budget:g} s, this host]"
                      f"({figure_links[(set_name, budget, host)]})"]
        methods = sorted({r["method"] for r in g})
        per_seed: dict[tuple[str, str, str], list[float | None]] = defaultdict(list)    # (instance, method, column)
        for r in g:
            for col in ("delivered_checked", "unresolved", *(c for _, c in slack_cols)):
                per_seed[(r["instance"], r["method"], col)].append(_value(r, col))

        def cell(i: str, m: str, col: str) -> str:
            v = per_seed.get((i, m, col))
            return "–" if not v or any(x is None for x in v) else _stat(v)
        median_dl = {(i, m): statistics.median(v) for (i, m, col), v in per_seed.items() if col == "delivered_checked"}
        lines += ["", "Delivered (checked) per instance, median over seeds [min–max when they differ]; **best bound** = "
                  "the smallest proven upper bound any method reports for the instance, bound-only methods included "
                  "(no plan can deliver more); **best of baselines** = the most residents any baseline delivered on the "
                  "instance (any seed), summed in the bar above:", "",
                  "| instance | label | residents | unservable | best bound | best of baselines | " + " | ".join(methods) +
                  " |", "|---|---|---|---|---|---|" + "---|" * len(methods)]
        for i in inst_ids:
            u = [x for (st, bd, hs, _m, ii), x in unserv.items() if (st, bd, hs, ii) == (set_name, budget, host, i)]
            bnd = [float(r["best_bound"]) for r in g_all if r["instance"] == i and r["best_bound"]]
            bob = cmp.best_of_baselines.get(i)
            lines.append(f"| {i} | {labels[i]} | {residents.get(i, '–')} | {_count(max(u)) if u else '–'} | "
                         f"{f'{min(bnd):g}' if bnd else '–'} | {'–' if bob is None else _count(bob)} | "
                         + " | ".join(cell(i, m, "delivered_checked") for m in methods) + " |")
        if bounds_lines:
            lines += ["", *bounds_lines]
        lines += ["", "Unresolved per instance (never safe, never delivered), median over seeds [min–max when they "
                  "differ]:", "", "| instance | label | " + " | ".join(methods) + " |", "|---|---|" + "---|" * len(methods)]
        for i in inst_ids:
            lines.append(f"| {i} | {labels[i]} | " + " | ".join(cell(i, m, "unresolved") for m in methods) + " |")
        for m_min, col in slack_cols:
            lines += ["", f"Delivered with slack ≥ {m_min} min per instance, median over seeds [min–max when they "
                      "differ] (– : rows from before the margin columns):", "",
                      "| instance | label | " + " | ".join(methods) + " |", "|---|---|" + "---|" * len(methods)]
            for i in inst_ids:
                lines.append(f"| {i} | {labels[i]} | " + " | ".join(cell(i, m, col) for m in methods) + " |")
        sizes = sorted({size_of.get(i, "other") for i in inst_ids}, key=lambda z: ("SML".find(z) % 4, z))
        if len(sizes) > 1 or any(sum(1 for i in inst_ids if (i, m) in median_dl) < len(inst_ids) for m in methods):
            lines += ["", "Delivered (checked) by instance size: sum of the per-instance medians / residents of the "
                      "instances the method ran (count); compare methods only on equal counts:", "",
                      "| method | " + " | ".join(sizes) + " |", "|---|" + "---|" * len(sizes)]
            for meth in methods:
                cells = []
                for z in sizes:
                    ids = [i for i in inst_ids if size_of.get(i, "other") == z and (i, meth) in median_dl]
                    if not ids:
                        cells.append("–")
                        continue
                    res_z = sum(residents.get(i, 0) for i in ids)
                    cells.append(f"{_count(sum(median_dl[(i, meth)] for i in ids))} / {res_z} ({len(ids)})")
                lines.append(f"| {meth} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def write_leaderboard(results_dir: Path = RESULTS_DIR, split: Split | None = None, path: Path = LEADERBOARD_PATH, *,
                      figures_dir: Path | None = None, observations: Iterable | None = None) -> Path:
    """Regenerate the leaderboard from ``results_dir`` and write one margin figure per table into ``figures_dir``
    (default: ``figures/`` next to the leaderboard, so a temporary leaderboard never writes the committed
    figures). ``observations`` default: ``docs/recorded_observations.json``."""
    if split is None:
        split = load_split(SPLIT_PATH)
    path = Path(path)
    rows = all_rows(results_dir)
    figures_dir = path.parent / "figures" if figures_dir is None else Path(figures_dir)
    links: dict[tuple, str] = {}
    for (set_name, budget, host), g in _tables(rows).items():
        if margin_curves(g):
            fig = figures_dir / figure_name(set_name, budget, host)
            write_margin_figure(g, fig, set_name=set_name, budget=budget, host=host)
            links[(set_name, budget, host)] = Path(os.path.relpath(fig, path.parent)).as_posix()
    path.write_text(render_leaderboard(rows, split, all_facility_rows(results_dir), observations=observations,
                                       figure_links=links))
    return path
