#!/usr/bin/env python3
"""H0 hazard intensity: SYNTHETIC dev instances vs Korean router packets (dev fires).

A measurement, not a method experiment: no tuning; generators, methods and hazard_contract are
unchanged. The pre-registration is README.md in this folder. Run from the worktree root; every step
holds the shared bench lock (program rule 6):

    .venv/bin/python program/benchlock.py --label H0-compute -- \\
        .venv/bin/python evacplan/experiments/H0-hazard-intensity/h0_hazard_intensity.py compute
    .venv/bin/python program/benchlock.py --label H0-analyze -- \\
        .venv/bin/python evacplan/experiments/H0-hazard-intensity/h0_hazard_intensity.py analyze
    .venv/bin/python program/benchlock.py --label H0-posthoc -- \\
        .venv/bin/python evacplan/experiments/H0-hazard-intensity/h0_hazard_intensity.py posthoc

``compute`` queries every (receiver node, window, member) exposure through ``hazard_contract`` (a
single-point geometry = a stationary occupancy) and writes per-exposure records to
``evacplan/runs/H0-hazard-intensity/`` (git-ignored, regenerable). ``analyze`` writes the CSVs and the
figures next to this file and prints the README tables. ``posthoc`` (added after the results were
seen; descriptive, not part of the pre-registration) counts the known-burning and unknown cells around
the receivers per band.

Data rules. SYNTHETIC: the frozen dev split only, regenerated through ``evacplan.instances`` (fingerprints
verified); refused when ``EVACPLAN_MILESTONE`` is set. Korean: the router packets of the dev fires only,
converted only through ``hazard_contract.from_wfg_packet`` (program rule 4 applied inside it; this file
never reads a packet), receivers from the matching router graph through ``evacplan.adapters.wfg_graph``,
all from ``$WFG_ROUTING_INPUTS``. The KR-2025 test-season fires are refused by name and never opened
(rule 5). Nothing here declares an itinerary state (rule 3): contact and support are reported as the
query returned them.

Config: ``config.yaml`` here, parsed with PyYAML (already in ``evacplan/requirements.lock``).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import os
import platform
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

import hazard_contract as hc

EXP_DIR = Path(__file__).resolve().parent
EVACPLAN_DIR = EXP_DIR.parents[1]
REPO_DIR = EVACPLAN_DIR.parent
CONFIG_PATH = EXP_DIR / "config.yaml"
RUNS_DIR = EVACPLAN_DIR / "runs" / "H0-hazard-intensity"
FIG_DIR = EXP_DIR / "figures"

DEV_FIRES = ("uljin_2022", "hongseong_2023", "miryang_2022")
TEST_SEASON_FIRES = ("uiseong_andong_2025", "yeongdeok_2025")     # rule 5: never opened
GENERATED = ("results.csv", "results_by_source.csv", "inventory.csv", "peak_flux.csv", "verdict.csv",
             "posthoc_burning_area.csv", "figures")
BAND_NAMES = ("0-375 m", "375-750 m", "0.75-1.5 km", "1.5-3 km")
BEYOND, ALL = "beyond 3 km", "all"
CONTACT_CODE = {True: 1, False: 0, None: -1}                     # certain / none / unknown
SYN, KOR = "SYNTHETIC", "KOREAN"
SYN_1H = "SYNTHETIC first hour"
SYN_DIAG = "SYNTHETIC 66-min burning (diagnostic)"
EST_S_PER_QUERY = 0.0023                                         # measured before pre-registration
TARGET_TASK_S = 6.0


# ----------------------------------------------------------------------------------- basics
def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def _git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=REPO_DIR, capture_output=True, text=True, check=True).stdout


def git_commit() -> str:
    """HEAD, with ``+dirty`` when evacplan/, hazard_contract/ or program/ has uncommitted changes
    (untracked files included) other than this experiment's generated outputs."""
    try:
        sha = _git(["rev-parse", "HEAD"]).strip()
        rel = EXP_DIR.relative_to(REPO_DIR).as_posix()
        specs = [":(top)evacplan", ":(top)hazard_contract", ":(top)program"]
        specs += [f":(top,exclude){rel}/{g}" for g in GENERATED]
        status = _git(["status", "--porcelain", "--untracked-files=all", "--", *specs])
    except (OSError, ValueError, subprocess.CalledProcessError):
        return "unknown"
    return sha + ("+dirty" if status.strip() else "")


def host_string() -> str:
    return (f"{socket.gethostname()} ({platform.system()} {platform.machine()}, {os.cpu_count()} cpu, "
            f"python {platform.python_version()})")


def windows_for(horizon_s: float, lengths_min, step_min: float) -> list[tuple[float, float]]:
    """(t0, length) in seconds after issue: t0 = 0, step, 2 step, ... while t0 + length <= horizon."""
    out = []
    for length_min in lengths_min:
        length = 60.0 * float(length_min)
        k = 0
        while k * 60.0 * step_min + length <= horizon_s:
            out.append((k * 60.0 * float(step_min), length))
            k += 1
    return out


def strictly_inside(grid: hc.Grid, xy: np.ndarray) -> np.ndarray:
    a, _b, c, _d, e, f = grid.transform
    xa, xb = sorted((c, c + a * grid.width))
    ya, yb = sorted((f, f + e * grid.height))
    return (xy[:, 0] > xa) & (xy[:, 0] < xb) & (xy[:, 1] > ya) & (xy[:, 1] < yb)


def q_rad(ss: hc.ScenarioSet) -> float:
    h = ss.meta.heat_source
    return float(h.emission_kw_m2(h.burn_duration_s))


# ---------------------------------------------------------------------------------- sources
@dataclass
class Source:
    key: str                      # SYNTHETIC instance id, or "<fire>/<packet>"
    panel: str                    # SYN or KOR
    group: str                    # SYNTHETIC size (S/M/L) or the Korean fire
    ss: hc.ScenarioSet
    xy: np.ndarray                # receivers [n, 2], hazard CRS metres
    windows: list
    ss_diag: hc.ScenarioSet | None = None
    windows_diag: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def synthetic_sources(cfg: dict) -> list[Source]:
    if os.environ.get("EVACPLAN_MILESTONE"):
        raise SystemExit("EVACPLAN_MILESTONE is set: refusing (rule 5; H0 uses the dev set only)")
    pc = cfg["panels"][SYN]
    if pc["split_set"] != "dev":
        raise SystemExit("H0 uses the dev set only (rule 5)")
    from evacplan import instances
    ex = cfg["exposures"]
    out = []
    for entry in instances.load_split().entries("dev"):
        inst, ss = instances.load_entry(entry)          # regenerated into the cache, fingerprint verified
        if not (entry.synthetic and inst.synthetic and ss.meta.synthetic):
            raise SystemExit(f"{entry.id} is not labelled SYNTHETIC")
        if inst.hazard.t0_offset_s != 0.0:
            raise SystemExit(f"{entry.id}: hazard offset {inst.hazard.t0_offset_s} != 0")
        xy = np.array([[n.x, n.y] for n in inst.graph.nodes], dtype=float)
        if not strictly_inside(ss.grid, xy).all():
            raise SystemExit(f"{entry.id}: a road node lies outside the hazard grid")
        out.append(Source(
            key=entry.id, panel=SYN, group=str(entry.config["size"]), ss=ss, xy=xy,
            windows=windows_for(ss.meta.horizon_s, ex["window_lengths_min"], ex["start_step_min"]),
            meta={"split_set": "dev", "fingerprint": entry.fingerprint, "config": entry.config}))
    return out


def korean_sources(cfg: dict) -> list[Source]:
    from evacplan.adapters.wfg_graph import from_wfg_graph
    pc, ex = cfg["panels"][KOR], cfg["exposures"]
    root = os.environ.get("WFG_ROUTING_INPUTS")
    if not root:
        raise SystemExit("set WFG_ROUTING_INPUTS to the routing-inputs folder (graphs/, latest_inputs_try02/)")
    root = Path(root)
    out = []
    for fire in pc["fires"]:
        if fire in TEST_SEASON_FIRES or fire not in DEV_FIRES:
            raise SystemExit(f"{fire} is not a Korean dev fire: refusing (rule 5)")
        graph = from_wfg_graph(root / pc["graphs_subdir"] / fire / "graph.json")
        gxy = np.array([[n.x, n.y] for n in graph.nodes], dtype=float)
        packets = sorted(p for p in (root / pc["packets_subdir"] / fire).iterdir() if p.is_dir())
        for p in packets:
            ss = hc.from_wfg_packet(p)                   # rule 4 applied by the adapter (no opt-out)
            if ss.meta.synthetic or ss.meta.source != "packet":
                raise SystemExit(f"{fire}/{p.name}: not a real packet scenario set")
            if ss.meta.crs_epsg != graph.crs_epsg:
                raise SystemExit(f"{fire}/{p.name}: packet CRS {ss.meta.crs_epsg} != graph CRS {graph.crs_epsg}")
            inside = strictly_inside(ss.grid, gxy)
            out.append(Source(
                key=f"{fire}/{p.name}", panel=KOR, group=fire, ss=ss, xy=gxy[inside],
                windows=windows_for(ss.meta.horizon_s, ex["window_lengths_min"], ex["start_step_min"]),
                meta={"graph_nodes": len(gxy), "graph_nodes_outside_grid": int((~inside).sum()),
                      "graph_grid_equals_packet_grid":
                          tuple(graph.provenance.get("router_grid_transform") or ()) == tuple(ss.meta.transform),
                      "issue_time_utc": ss.meta.issue_time_utc.isoformat(),
                      "present_fire": ss.meta.extra.get("present_fire"), "R_max_s": ss.meta.extra.get("R_max_s"),
                      "n_unsupported_cells": ss.meta.extra.get("n_unsupported_cells"),
                      "n_present_fire_cells": ss.meta.extra.get("n_present_fire_cells")}))
    return out


def persistence_diagnostic(ss: hc.ScenarioSet, burn_s: float) -> hc.ScenarioSet:
    """The same SYNTHETIC set with every burning interval cut to ``burn_s`` (analysis only, in memory):
    extinguish = ignite + burn_s for cells that ignite; never-burning and unknown cells unchanged."""
    ig = ss.ignite_s
    ex = np.where(np.isfinite(ig), ig + float(burn_s), ss.extinguish_s)
    meta = hc.ScenarioMeta(**{**ss.meta.model_dump(),
                              "model_version": ss.meta.model_version
                              + f" | H0 diagnostic: burning cut to {burn_s:.2f} s (SYNTHETIC, analysis only)"})
    return hc.ScenarioSet(ig, ex, ss.supported, meta)


# --------------------------------------------------------------------------------- exposures
def nearby_cells(grid: hc.Grid, x: float, y: float, radius: float):
    """In-grid cells whose closed square lies within ``radius`` of (x, y), with that distance."""
    r0, r1, c0, c1 = grid.index_box(x - radius, x + radius, y - radius, y + radius)
    rr, cc = np.mgrid[r0:r1, c0:c1]
    rr, cc = rr.ravel(), cc.ravel()
    x0, x1, y0, y1 = grid.cell_rects(rr, cc)
    d = np.hypot(np.maximum(np.maximum(x0 - x, 0.0), x - x1), np.maximum(np.maximum(y0 - y, 0.0), y - y1))
    keep = d <= radius
    return rr[keep], cc[keep], d[keep]


def nearest_burning(ss: hc.ScenarioSet, xy: np.ndarray, starts: np.ndarray, radius: float) -> np.ndarray:
    """[n_nodes, K, n_starts]: distance (m) to the nearest supported cell burning at each start
    (ignite <= t0 < extinguish), inf when none lies within ``radius``."""
    out = np.full((len(xy), ss.K, len(starts)), np.inf)
    t0 = np.asarray(starts, dtype=float)[None, :, None]
    for i, (x, y) in enumerate(xy):
        rr, cc, d = nearby_cells(ss.grid, float(x), float(y), radius)
        if rr.size == 0:
            continue
        ig = ss.ignite_s[:, rr, cc][:, None, :]
        ex = ss.extinguish_s[:, rr, cc][:, None, :]
        sup = ss.supported[:, rr, cc][:, None, :]
        burning = sup & (ig <= t0) & (ex > t0)                       # nan (unknown) compares False
        out[i] = np.where(burning, d[None, None, :], np.inf).min(axis=2)
    return out


_SOURCES: list[Source] = []          # filled in the parent before the fork


def _work(task):
    tid, si, variant, lo, hi, radius, near_r = task
    src = _SOURCES[si]
    ss = src.ss if variant == "main" else src.ss_diag
    windows = src.windows if variant == "main" else src.windows_diag
    xy = src.xy[lo:hi]
    K, nw, nn = ss.K, len(windows), hi - lo
    n = nn * nw * K
    contact = np.empty(n, np.int8)
    supported = np.empty(n, bool)
    fl, fu, dl, du = (np.empty(n) for _ in range(4))
    j = 0
    for x, y in xy:
        g = np.array([[x, y]], dtype=float)
        for t0, length in windows:
            for h in ss.query(g, t0, t0 + length, near_radius_m=near_r):
                contact[j] = CONTACT_CODE[h.contact]
                supported[j] = h.supported
                fl[j], fu[j], dl[j], du[j] = h.flux_lower, h.flux_upper, h.dose_lower, h.dose_upper
                j += 1
    assert j == n
    t0s = np.array([w[0] for w in windows])
    starts = np.unique(t0s)
    dist = nearest_burning(ss, xy, starts, radius)
    node = np.repeat(np.arange(lo, hi), nw * K)
    win = np.tile(np.repeat(np.arange(nw), K), nn)
    member = np.tile(np.arange(K), nn * nw)
    d = dist[node - lo, member, np.searchsorted(starts, t0s)[win]]
    return tid, {
        "src": np.full(n, si, np.int16), "node": node.astype(np.int32),
        "t0_s": t0s[win].astype(np.int32), "win_s": np.array([w[1] for w in windows])[win].astype(np.int32),
        "member": member.astype(np.int8), "contact": contact, "supported": supported,
        "flux_lower": fl, "flux_upper": fu, "dose_lower": dl, "dose_upper": du, "dist_m": d,
    }


def make_tasks(sources: list[Source], radius: float, near_r: float) -> list[tuple]:
    tasks = []
    for si, s in enumerate(sources):
        variants = [("main", s.windows)] + ([("diag", s.windows_diag)] if s.ss_diag is not None else [])
        for variant, wins in variants:
            step = max(1, int(TARGET_TASK_S / (len(wins) * EST_S_PER_QUERY)))
            for lo in range(0, len(s.xy), step):
                tasks.append((len(tasks), si, variant, lo, min(lo + step, len(s.xy)), radius, near_r))
    return tasks


def compute(cfg: dict, workers: int, smoke: int | None) -> None:
    global _SOURCES
    t_start = time.time()
    commit = git_commit()
    sources = synthetic_sources(cfg) + korean_sources(cfg)
    diag = cfg["secondary"]["persistence_diagnostic"]
    if diag["enabled"]:
        keep = {60.0 * float(m) for m in diag["window_lengths_min"]}
        for s in sources:
            if s.panel == SYN:
                s.ss_diag = persistence_diagnostic(s.ss, diag["burn_duration_s"])
                s.windows_diag = [w for w in s.windows if w[1] in keep]
    if smoke:
        for s in sources:
            s.xy = s.xy[:smoke]
    radius = float(cfg["distance"]["bands_m"][-1][1])
    near_r = float(cfg["exposures"]["near_radius_m"])
    tasks = make_tasks(sources, radius, near_r)
    n_queries = {v: sum((t[4] - t[3]) * len(sources[t[1]].windows if v == "main" else sources[t[1]].windows_diag)
                        for t in tasks if t[2] == v) for v in ("main", "diag")}
    print(f"[H0] commit {commit}; {len(sources)} sources, {len(tasks)} tasks, queries {n_queries}, "
          f"{workers} workers", flush=True)
    _SOURCES = sources
    results: dict[int, dict] = {}
    t0 = time.time()
    with mp.get_context("fork").Pool(workers) as pool:
        for k, (tid, res) in enumerate(pool.imap_unordered(_work, tasks), 1):
            results[tid] = res
            if k % 25 == 0 or k == len(tasks):
                print(f"[H0] {k}/{len(tasks)} tasks, {time.time() - t0:.0f} s", flush=True)
    out_dir = RUNS_DIR if not smoke else RUNS_DIR / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    for variant in ("main", "diag"):
        parts = [results[t[0]] for t in tasks if t[2] == variant]
        if not parts:
            continue
        arrays = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
        np.savez_compressed(out_dir / f"exposures_{variant}.npz", **arrays)
    src_meta = []
    for s in sources:
        hs = s.ss.meta.heat_source
        src_meta.append({
            "key": s.key, "panel": s.panel, "group": s.group, "K": s.ss.K, "horizon_s": s.ss.meta.horizon_s,
            "grid_hw": [s.ss.meta.height, s.ss.meta.width], "cell_m": s.ss.grid.cell_size[0],
            "crs_epsg": s.ss.meta.crs_epsg, "synthetic": s.ss.meta.synthetic, "source": s.ss.meta.source,
            "receivers": int(len(s.xy)), "windows": s.windows, "windows_diag": s.windows_diag,
            "q_rad_kw_m2": q_rad(s.ss), "burn_duration_s": hs.burn_duration_s,
            "burn_duration_policy": hs.burn_duration_policy, "height_gap_m": hs.height_gap_m,
            "share_cells_unsupported": float((~s.ss.supported).mean()),
            "edge_burning_members": int(s.ss.edge_burning().sum()),
            "model_version": s.ss.meta.model_version, **s.meta})
    (out_dir / "sources.json").write_text(json.dumps(src_meta, indent=1) + "\n")
    run_meta = {"commit": commit, "host": host_string(), "workers": workers, "smoke": smoke,
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start)),
                "wall_s": round(time.time() - t_start, 1), "query_wall_s": round(time.time() - t0, 1),
                "queries": n_queries, "hazard_contract": hc.__version__, "contract": hc.CONTRACT_VERSION,
                "numpy": np.__version__, "config": cfg}
    (out_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=1) + "\n")
    print(f"[H0] wrote {out_dir} in {run_meta['wall_s']} s", flush=True)


# ---------------------------------------------------------------------------------- analysis
def band_index(d: np.ndarray, edges) -> np.ndarray:
    """0..3 for the four bands ([lo, hi), the last closed), 4 for beyond / no burning cell."""
    b = np.full(d.shape, 4, dtype=np.int8)
    b[d <= edges[-1][1]] = 3
    for i in (2, 1, 0):
        b[d < edges[i][1]] = i
    return b


def qstats(x: np.ndarray) -> list[float]:
    if x.size == 0:
        return [math.nan] * 4
    q = np.quantile(x, [0.5, 0.9, 0.99])
    return [float(q[0]), float(q[1]), float(q[2]), float(x.max())]


def fmt(v) -> str:
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return "" if math.isnan(v) else f"{float(v):.6g}"
    return str(v)


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(v) for k, v in r.items()})


class Exposures:
    """Per-exposure arrays with derived masks."""

    def __init__(self, arrays: dict, edges):
        self.a = arrays
        self.band = band_index(arrays["dist_m"], edges)
        self.cf = arrays["contact"] == 0                # contact-free, hence supported
        self.n = len(self.band)

    def subset(self, mask: np.ndarray) -> "Exposures":
        e = object.__new__(Exposures)
        e.a = {k: v[mask] for k, v in self.a.items()}
        e.band, e.cf, e.n = self.band[mask], self.cf[mask], int(mask.sum())
        return e


def summary_row(e: Exposures, mask: np.ndarray, budget: float) -> dict:
    a = e.a
    n = int(mask.sum())
    cf = mask & e.cf
    ncf = int(cf.sum())
    fu, du = a["flux_upper"][cf], a["dose_upper"][cf]
    dl = a["dose_lower"][cf]
    row = {"n_exposures": n, "n_contact": int((mask & (a["contact"] == 1)).sum()),
           "n_unsupported": int((mask & ~a["supported"]).sum()),
           "n_contact_unknown": int((mask & (a["contact"] == -1)).sum()), "n_contact_free_supported": ncf}
    for k in ("contact", "unsupported", "contact_unknown"):
        row[f"share_{k}"] = row[f"n_{k}"] / n if n else math.nan
    for name, x in (("flux_lower", a["flux_lower"][cf]), ("dose_lower", dl)):
        for s, v in zip(("median", "p90", "p99", "max"), qstats(x)):
            row[f"{name}_{s}"] = v
    for name, x in (("flux_upper", fu), ("dose_upper", du)):
        fin = np.isfinite(x)
        for s, v in zip(("median", "p90", "p99", "max"), qstats(x[fin])):
            row[f"{name}_{s}"] = v
        row[f"{name}_share_inf"] = float((~fin).mean()) if ncf else math.nan
    row["share_dose_lower_ge_budget"] = float((dl >= budget).mean()) if ncf else math.nan
    row["share_dose_upper_ge_budget"] = float((du >= budget).mean()) if ncf else math.nan
    d = a["dist_m"][cf]
    d = d[np.isfinite(d)]
    if d.size:
        p10, med, p90 = np.quantile(d, [0.1, 0.5, 0.9])
    else:
        p10 = med = p90 = math.nan
    row.update(dist_p10_m=p10, dist_median_m=med, dist_p90_m=p90)
    return row


def at_least(a: float, b: float, ratio: float) -> bool:
    """'a is at least ratio x b' as pre-registered: both 0 -> False; b = 0 < a -> True."""
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    if a == 0.0 and b == 0.0:
        return False
    return a >= ratio * b


def ratio(a: float, b: float) -> float:
    if a == 0.0 and b == 0.0:
        return 1.0
    return math.inf if b == 0.0 else a / b


def band_label(triggered: bool, r: float) -> str:
    if triggered:
        return "much hotter"
    if r >= 1.25:
        return "hotter but not much"
    if r <= 0.8:
        return "cooler"
    return "comparable"


def overall_label(labels: list[str]) -> str:
    if not labels:
        return "n/a (the rule could not be applied in any band)"
    if "much hotter" in labels:
        return "much hotter"
    hot, cool = "hotter but not much" in labels, "cooler" in labels
    if hot and cool:
        return "comparable (mixed)"
    return "hotter but not much" if hot else ("cooler" if cool else "comparable")


def judge(syn: Exposures, kor: Exposures, cfg: dict, quantity: str = "dose_lower") -> list[dict]:
    """The pre-registered rule on 30-min windows, per band, plus the overall row."""
    rule, budget = cfg["rule"], float(cfg["statistics"]["dose_budget_kj_m2"])
    win = 60 * int(rule["window_min"])
    rows, labels, any_trig = [], [], False
    for b, name in enumerate(BAND_NAMES):
        vals = {}
        for tag, e in (("syn", syn), ("kor", kor)):
            m = e.cf & (e.band == b) & (e.a["win_s"] == win)
            x = e.a[quantity][m]
            x = x[np.isfinite(x)]
            vals[tag] = (int(m.sum()), *(qstats(x)[:2] if x.size else [math.nan, math.nan]),
                         float((x >= budget).mean()) if x.size else math.nan)
        (n_s, med_s, p90_s, sh_s), (n_k, med_k, p90_k, sh_k) = vals["syn"], vals["kor"]
        judged = n_s >= rule["min_contact_free_supported_per_panel"] and n_k >= rule["min_contact_free_supported_per_panel"]
        met_med = judged and at_least(med_s, med_k, rule["ratio"])
        met_p90 = judged and at_least(p90_s, p90_k, rule["ratio"])
        met_sh = judged and (sh_s >= rule["share_ratio"] * sh_k) and (sh_s - sh_k >= rule["share_min_diff"])
        trig = bool(met_med or met_p90 or met_sh)
        r_med, r_p90 = (ratio(med_s, med_k), ratio(p90_s, p90_k)) if judged else (math.nan, math.nan)
        r = math.sqrt(r_med * r_p90) if judged else math.nan
        lab = band_label(trig, r) if judged else "not judged (fewer than 200 in a panel)"
        if judged:
            labels.append(lab)
        any_trig |= trig
        rows.append({"band": name, "window_min": rule["window_min"], "n_syn": n_s, "n_kor": n_k, "judged": judged,
                     "syn_median": med_s, "kor_median": med_k, "syn_p90": p90_s, "kor_p90": p90_k,
                     "syn_share_ge_budget": sh_s, "kor_share_ge_budget": sh_k, "met_median": met_med,
                     "met_p90": met_p90, "met_share": met_sh, "triggered": trig, "r_median": r_med, "r_p90": r_p90,
                     "r": r, "label": lab})
    rows.append({"band": "overall", "window_min": rule["window_min"], "n_syn": "", "n_kor": "",
                 "judged": sum(r["judged"] for r in rows), "syn_median": "", "kor_median": "", "syn_p90": "",
                 "kor_p90": "", "syn_share_ge_budget": "", "kor_share_ge_budget": "", "met_median": "",
                 "met_p90": "", "met_share": "", "triggered": any_trig, "r_median": "", "r_p90": "", "r": "",
                 "label": overall_label(labels)})
    return rows


def check_invariants(main: Exposures, diag: Exposures, sources: list) -> None:
    """Refuse to analyze records that break the design or hazard_contract's guarantees."""
    for name, e, wkey in (("main", main, "windows"), ("diag", diag, "windows_diag")):
        a = e.a
        hz = np.array([s["horizon_s"] for s in sources])[a["src"]]
        want = sum(s["receivers"] * len(s[wkey]) * s["K"] for s in sources)
        cap = 0.5 * max(s["q_rad_kw_m2"] for s in sources) * (1 + 1e-9)
        checks = {
            "one record per (receiver, window, member)": e.n == want,
            "distance 0 implies certain contact": not np.any((a["dist_m"] == 0) & (a["contact"] != 1)),
            "contact-free implies supported": not np.any((a["contact"] == 0) & ~a["supported"]),
            "windows end by the horizon": bool(np.all(a["t0_s"] + a["win_s"] <= hz)),
            "lower bounds <= upper bounds": bool(np.all(a["flux_lower"] <= a["flux_upper"])
                                                 and np.all(a["dose_lower"] <= a["dose_upper"])),
            "flux_lower <= q_rad/2": bool(np.all(a["flux_lower"] <= cap)),
        }
        bad = [k for k, ok in checks.items() if not ok]
        if bad:
            raise SystemExit(f"{name} exposures break: {bad}")
        print(f"[H0] {name}: {e.n:,} exposures, invariants hold: {', '.join(checks)}", flush=True)


def analyze(cfg: dict, smoke: bool) -> None:
    run_dir = RUNS_DIR / "smoke" if smoke else RUNS_DIR
    run = json.loads((run_dir / "run_meta.json").read_text())
    sources = json.loads((run_dir / "sources.json").read_text())
    edges = cfg["distance"]["bands_m"]
    budget = float(cfg["statistics"]["dose_budget_kj_m2"])
    with np.load(run_dir / "exposures_main.npz") as z:
        main = Exposures({k: z[k] for k in z.files}, edges)
    with np.load(run_dir / "exposures_diag.npz") as z:
        diag = Exposures({k: z[k] for k in z.files}, edges)
    check_invariants(main, diag, sources)
    panel_of = np.array([s["panel"] for s in sources])
    is_syn = panel_of[main.a["src"]] == SYN
    syn, kor = main.subset(is_syn), main.subset(~is_syn)
    syn_1h = syn.subset(syn.a["t0_s"] + syn.a["win_s"] <= 3600)
    panels = {SYN: syn, KOR: kor, SYN_1H: syn_1h, SYN_DIAG: diag}
    common = {"commit": run["commit"], "analysis_commit": git_commit(), "seed": "none",
              "config": json.dumps({"windows_min": cfg["exposures"]["window_lengths_min"],
                                    "start_step_min": cfg["exposures"]["start_step_min"], "bands_m": edges,
                                    "near_radius_m": cfg["exposures"]["near_radius_m"], "budget_kj_m2": budget,
                                    "present_fire": "enclosure", "subsample": "none"}, separators=(",", ":")),
              "host": run["host"]}
    out_dir = EXP_DIR if not smoke else run_dir
    fig_dir = FIG_DIR if not smoke else run_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # results.csv: panel x band x window length
    rows = []
    for pname, e in panels.items():
        for win in sorted(set(e.a["win_s"].tolist())):
            wm = e.a["win_s"] == win
            for b, bname in list(enumerate(BAND_NAMES)) + [(4, BEYOND), (None, ALL)]:
                m = wm if b is None else wm & (e.band == b)
                rows.append({"panel": pname, "label": "SYNTHETIC" if pname.startswith(SYN) else "",
                             "band": bname, "window_min": win // 60, **summary_row(e, m, budget), **common})
    write_csv(out_dir / "results.csv", rows)

    # results_by_source.csv: 30-min windows per source and band
    rows_src = []
    for pname, e in ((SYN, syn), (KOR, kor), (SYN_DIAG, diag)):
        for si in sorted(set(e.a["src"].tolist())):
            s = sources[si]
            m0 = (e.a["src"] == si) & (e.a["win_s"] == 1800)
            for b, bname in list(enumerate(BAND_NAMES)) + [(4, BEYOND), (None, ALL)]:
                m = m0 if b is None else m0 & (e.band == b)
                rows_src.append({"panel": pname, "label": "SYNTHETIC" if pname.startswith(SYN) else "",
                                 "source": s["key"], "group": s["group"], "band": bname, "window_min": 30,
                                 **summary_row(e, m, budget), **common})
    write_csv(out_dir / "results_by_source.csv", rows_src)

    # inventory.csv: per source, all windows
    rows_inv = []
    for si, s in enumerate(sources):
        m = main.a["src"] == si
        e = main
        wins = [w[1] for w in s["windows"]]
        rows_inv.append({
            "panel": s["panel"], "label": "SYNTHETIC" if s["panel"] == SYN else "", "source": s["key"],
            "group": s["group"], "K": s["K"], "horizon_s": s["horizon_s"], "grid_hw": "x".join(map(str, s["grid_hw"])),
            "receivers": s["receivers"], **{f"windows_{L}min": wins.count(60.0 * L) for L in (5, 15, 30, 60)},
            "queries": s["receivers"] * len(wins), "exposures": int(m.sum()),
            "share_contact": float((m & (e.a["contact"] == 1)).sum() / m.sum()),
            "share_unsupported": float((m & ~e.a["supported"]).sum() / m.sum()),
            "share_contact_unknown": float((m & (e.a["contact"] == -1)).sum() / m.sum()),
            "share_contact_free_supported": float((m & e.cf).sum() / m.sum()),
            "share_beyond_3km": float((m & (e.band == 4)).sum() / m.sum()),
            "share_cells_unsupported": s["share_cells_unsupported"], "edge_burning_members": s["edge_burning_members"],
            "q_rad_kw_m2": s["q_rad_kw_m2"], "burn_duration_s": s["burn_duration_s"],
            "present_fire": s.get("present_fire", ""), "R_max_s": s.get("R_max_s", ""), **common})
    write_csv(out_dir / "inventory.csv", rows_inv)

    # peak_flux.csv: all exposures (every window length, contact and unsupported included) and contact-free
    rows_pk = []
    for pname, e in ((SYN, syn), (KOR, kor), (SYN_DIAG, diag)):
        qr = max(s["q_rad_kw_m2"] for s in sources if s["panel"] == SYN) if pname.startswith(SYN) else \
            max(s["q_rad_kw_m2"] for s in sources if s["panel"] == KOR)
        for b, bname in list(enumerate(BAND_NAMES)) + [(4, BEYOND), (None, ALL)]:
            m = np.ones(e.n, bool) if b is None else e.band == b
            fl, fu = e.a["flux_lower"][m], e.a["flux_upper"][m]
            fin = np.isfinite(fu)
            flc = e.a["flux_lower"][m & e.cf]
            rows_pk.append({"panel": pname, "label": "SYNTHETIC" if pname.startswith(SYN) else "", "band": bname,
                            "n_exposures": int(m.sum()), "flux_lower_max_all": float(fl.max()) if fl.size else math.nan,
                            "flux_upper_max_finite_all": float(fu[fin].max()) if fin.any() else math.nan,
                            "flux_upper_share_inf_all": float((~fin).mean()) if fu.size else math.nan,
                            "n_contact_free_supported": int(flc.size),
                            "flux_lower_p99_contact_free": qstats(flc)[2], "flux_lower_max_contact_free": qstats(flc)[3],
                            "cap_q_rad_half_kw_m2": qr / 2.0,
                            "above_cap": bool(fl.size and fl.max() > qr / 2.0 * (1 + 1e-9)), **common})
    write_csv(out_dir / "peak_flux.csv", rows_pk)

    # verdict.csv: the pre-registered rule, then the descriptive secondary comparisons
    comparisons = [("main (pre-registered): SYNTHETIC vs KOREAN, dose_lower", syn, kor, "dose_lower"),
                   ("secondary: SYNTHETIC first hour vs KOREAN, dose_lower", syn_1h, kor, "dose_lower"),
                   ("secondary: SYNTHETIC 66-min burning vs KOREAN, dose_lower", diag, kor, "dose_lower"),
                   ("secondary: SYNTHETIC vs KOREAN, dose_upper", syn, kor, "dose_upper")]
    rows_v = []
    for cname, a, b_, qty in comparisons:
        for r in judge(a, b_, cfg, qty):
            rows_v.append({"comparison": cname, **r, **common})
    write_csv(out_dir / "verdict.csv", rows_v)

    make_figures(cfg, panels, sources, fig_dir)
    print_tables(rows, rows_v, rows_pk, rows_inv)


# ----------------------------------------------------------------------------------- figures
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
C_SYN, C_KOR, C_DIAG = "#2a78d6", "#eb6834", "#1baf7a"            # categorical slots 1-3 (validated all-pairs)
BAND_RAMP = ("#0d366b", "#1c5cab", "#3987e5", "#86b6ef")           # blue ordinal ramp, near (dark) -> far
DOSE_FLOOR = 1e-3
P = np.linspace(0.0, 1.0, 1001)


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
        ax.spines[s].set_linewidth(0.8)
    ax.grid(True, color=GRID, linewidth=0.6, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8)


def _cdf(ax, x: np.ndarray, **kw) -> None:
    if x.size:
        ax.plot(np.quantile(np.maximum(x, DOSE_FLOOR), P), P, linewidth=1.6, solid_capstyle="round", **kw)


def make_figures(cfg: dict, panels: dict, sources: list, fig_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    t_syn, t_kor = cfg["panels"][SYN]["title"], cfg["panels"][KOR]["title"]
    budget = float(cfg["statistics"]["dose_budget_kj_m2"])

    def dose30(e, b):
        m = e.cf & (e.band == b) & (e.a["win_s"] == 1800)
        return e.a["dose_lower"][m]

    # 1: one plot per panel, a curve per band
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.4), sharex=True, sharey=True, facecolor=SURFACE)
    for ax, pname, title in zip(axes, (SYN, KOR), (t_syn, t_kor)):
        _style(ax)
        for b, bname in enumerate(BAND_NAMES):
            x = dose30(panels[pname], b)
            _cdf(ax, x, color=BAND_RAMP[b], label=f"{bname}  (n = {x.size:,})")
        ax.axvline(budget, color=MUTED, linewidth=1.0)
        ax.text(budget * 1.12, 0.03, "dose budget\n100 kJ/m²", color=INK2, fontsize=7.5)
        ax.set_xscale("log")
        ax.set_xlim(DOSE_FLOOR, 1e3)
        ax.set_ylim(0, 1)
        ax.set_title(title, color=INK, fontsize=10.5, loc="left")
        ax.set_xlabel("dose_lower over 30 min (kJ/m², log; below 0.001 drawn at 0.001)", color=INK2, fontsize=8.5)
        if ax.get_lines()[:-1]:                                  # band curves besides the budget line
            ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2,
                      labelcolor=INK2, title="distance to the nearest burning cell at window start",
                      title_fontsize=7.5)
    axes[0].set_ylabel("cumulative share of exposures", color=INK2, fontsize=8.5)
    fig.suptitle("30-min stationary dose at road nodes (contact-free, supported exposures):\n"
                 f"{t_syn} vs {t_kor}", color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(fig_dir / "cdf_dose30_by_band.png", dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)

    # 2: one plot per band, both panels and the persistence diagnostic overlaid
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.3), sharex=True, sharey=True, facecolor=SURFACE)
    series = ((t_syn, SYN, C_SYN, "-"), (t_kor, KOR, C_KOR, "-"),
              ("SYNTHETIC, 66-min burning (diagnostic)", SYN_DIAG, C_DIAG, (0, (4, 2))))
    for b, ax in enumerate(axes):
        _style(ax)
        ns = []
        for label, pname, color, ls in series:
            x = dose30(panels[pname], b)
            ns.append(f"{x.size:,}")
            _cdf(ax, x, color=color, linestyle=ls, label=label)
        ax.axvline(budget, color=MUTED, linewidth=1.0)
        ax.set_xscale("log")
        ax.set_xlim(DOSE_FLOOR, 1e3)
        ax.set_ylim(0, 1)
        ax.set_title(BAND_NAMES[b], color=INK, fontsize=10, loc="left")
        ax.text(0.98, 0.04, "n = " + " / ".join(ns), transform=ax.transAxes, ha="right", fontsize=7, color=INK2)
        ax.set_xlabel("30-min dose_lower (kJ/m², log)", color=INK2, fontsize=8)
    axes[0].set_ylabel("cumulative share of exposures", color=INK2, fontsize=8.5)
    handles = [Line2D([], [], color=color, linestyle=ls, linewidth=1.6) for _l, _p, color, ls in series]
    labels = [label for label, *_rest in series]
    handles.append(Line2D([], [], color=MUTED, linewidth=1.0))
    labels.append("dose budget 100 kJ/m²")
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=8, labelcolor=INK2)
    fig.suptitle(f"30-min dose_lower by distance to the nearest burning cell: {t_syn} vs {t_kor}",
                 color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(fig_dir / "cdf_dose30_overlay.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    # 3: peak flux by band
    fig, ax = plt.subplots(figsize=(9.5, 4.8), facecolor=SURFACE)
    _style(ax)
    for off, pname, color in ((-0.13, SYN, C_SYN), (0.13, KOR, C_KOR)):
        e = panels[pname]
        for b in range(4):
            m = e.cf & (e.band == b) & (e.a["win_s"] == 1800)
            x = e.a["flux_lower"][m]
            if x.size:
                med, _p90, p99, mx = qstats(x)
                ax.plot([b + off] * 2, [max(med, 1e-6), mx], color=color, linewidth=1.2)
                ax.plot(b + off, max(med, 1e-6), "o", ms=6.5, mfc=SURFACE, mec=color, mew=1.6)
                ax.plot(b + off, p99, "s", ms=5.5, color=color, mec=SURFACE, mew=1.0)
                ax.plot(b + off, mx, "^", ms=7, color=color, mec=SURFACE, mew=1.0)
            all_b = e.a["flux_lower"][e.band == b]
            if all_b.size:
                ax.plot(b + off, all_b.max(), "D", ms=6.5, mfc="none", mec=color, mew=1.4)
    cap = 0.5 * max(s["q_rad_kw_m2"] for s in sources)
    ax.axhline(cap, color=MUTED, linewidth=1.0)
    ax.text(3.5, cap * 1.25, f"q_rad/2 = {cap:.3f} kW/m² (cap of the flux law)", ha="right", fontsize=7.5, color=INK2)
    ax.set_yscale("log")
    ax.set_ylim(1e-5, 2.0)
    ax.set_xlim(-0.5, 3.5)
    ax.set_xticks(range(4), BAND_NAMES)
    ax.set_xlabel("distance from the receiver to the nearest burning cell at window start", color=INK2, fontsize=8.5)
    ax.set_ylabel("flux_lower (kW/m², log)", color=INK2, fontsize=8.5)
    handles = [Line2D([], [], color=C_SYN, linewidth=2, label=t_syn),
               Line2D([], [], color=C_KOR, linewidth=2, label=t_kor),
               Line2D([], [], color=INK2, marker="o", mfc=SURFACE, linestyle="none", label="30-min contact-free: median"),
               Line2D([], [], color=INK2, marker="s", linestyle="none", label="30-min contact-free: p99"),
               Line2D([], [], color=INK2, marker="^", linestyle="none", label="30-min contact-free: max"),
               Line2D([], [], color=INK2, marker="D", mfc="none", linestyle="none",
                      label="max over all exposures (contact included, any window)")]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=7.5, labelcolor=INK2, ncol=2)
    ax.set_title(f"Peak incident flux (lower bound) by distance band:\n{t_syn} vs {t_kor}",
                 color=INK, fontsize=10.5, loc="left")
    fig.tight_layout()
    fig.savefig(fig_dir / "peak_flux_by_band.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


# ------------------------------------------------------------------- post hoc (not pre-registered)
POSTHOC_RADII_M = (1500.0, 3000.0)


def posthoc(cfg: dict) -> None:
    """POST HOC, added after the results were seen (descriptive only; it cannot change the verdict).
    How much KNOWN burning area, and how many UNKNOWN (rule 4) cells, lie within 1.5 and 3 km of the
    receiver at the window start, per panel and band, for the contact-free supported 30-min exposures.
    Both panels use 375 m cells, so counts are comparable areas (1 cell = 0.14 km²)."""
    run = json.loads((RUNS_DIR / "run_meta.json").read_text())
    run_sources = json.loads((RUNS_DIR / "sources.json").read_text())
    sources = synthetic_sources(cfg) + korean_sources(cfg)
    if ([s.key for s in sources] != [s["key"] for s in run_sources]
            or [len(s.xy) for s in sources] != [s["receivers"] for s in run_sources]):
        raise SystemExit("the sources differ from the computed run")
    with np.load(RUNS_DIR / "exposures_main.npz") as z:
        a = {k: z[k] for k in ("src", "node", "t0_s", "win_s", "member", "contact", "dist_m")}
    m30 = a["win_s"] == 1800
    a = {k: v[m30] for k, v in a.items()}
    counts = {f"{kind}_cells_within_{int(r)}m": np.full(len(a["src"]), -1, np.int32)
              for kind in ("known_burning", "unknown") for r in POSTHOC_RADII_M}
    for si, s in enumerate(sources):
        sel = np.flatnonzero(a["src"] == si)
        starts = np.unique([w[0] for w in s.windows if w[1] == 1800.0])
        per = {key: np.zeros((len(s.xy), s.ss.K, len(starts)), np.int32) for key in counts}
        t0 = starts[None, :, None]
        for i, (x, y) in enumerate(s.xy):
            rr, cc, d = nearby_cells(s.ss.grid, float(x), float(y), max(POSTHOC_RADII_M))
            if rr.size == 0:
                continue
            sup = s.ss.supported[:, rr, cc]                                          # [K, n]
            burning = (sup[:, None, :] & (s.ss.ignite_s[:, rr, cc][:, None, :] <= t0)
                       & (s.ss.extinguish_s[:, rr, cc][:, None, :] > t0))            # [K, n_starts, n]
            for r in POSTHOC_RADII_M:
                inr = d <= r
                per[f"known_burning_cells_within_{int(r)}m"][i] = (burning & inr).sum(axis=2)
                per[f"unknown_cells_within_{int(r)}m"][i] = (~sup & inr).sum(axis=1)[:, None]
        idx = (a["node"][sel], a["member"][sel], np.searchsorted(starts, a["t0_s"][sel]))
        for key in counts:
            counts[key][sel] = per[key][idx]
    if any((v < 0).any() for v in counts.values()):
        raise SystemExit("an exposure was not matched to its source")
    band = band_index(a["dist_m"], cfg["distance"]["bands_m"])
    cf = a["contact"] == 0
    panel = np.array([s["panel"] for s in run_sources])[a["src"]]
    common = {"commit": run["commit"], "analysis_commit": git_commit(), "seed": "none",
              "config": "post hoc; contact-free supported 30-min exposures; 375 m cells", "host": run["host"]}
    rows = []
    for pname in (SYN, KOR):
        for b, bname in enumerate(BAND_NAMES):
            m = cf & (band == b) & (panel == pname)
            row = {"panel": pname, "label": "SYNTHETIC" if pname == SYN else "", "band": bname, "window_min": 30,
                   "n_contact_free_supported": int(m.sum())}
            for key, v in counts.items():
                x = v[m]
                row[f"{key}_median"] = float(np.median(x)) if x.size else math.nan
                row[f"{key}_p90"] = float(np.quantile(x, 0.9)) if x.size else math.nan
            u = counts["unknown_cells_within_1500m"][m]
            row["share_with_unknown_within_1500m"] = float((u > 0).mean()) if u.size else math.nan
            rows.append({**row, **common})
    write_csv(EXP_DIR / "posthoc_burning_area.csv", rows)
    for r in rows:
        print({k: v for k, v in r.items() if k not in common})


# -------------------------------------------------------------------------------- README aid
def print_tables(rows: list, rows_v: list, rows_pk: list, rows_inv: list) -> None:
    def g(v, nd=3):
        return fmt(v) if not isinstance(v, float) or math.isnan(v) else f"{v:.{nd}g}"

    print("\n## 30-min dose_lower (contact-free supported) and shares by band")
    print("| panel | band | n (cf) | share contact | share unsupported | dose_lower median | p90 | p99 | max | share ≥ 100 | dose_upper median | p90 | share ≥ 100 (upper) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["window_min"] == 30:
            print(f"| {r['panel']} | {r['band']} | {r['n_contact_free_supported']:,} | {g(r['share_contact'])} | "
                  f"{g(r['share_unsupported'])} | {g(r['dose_lower_median'])} | {g(r['dose_lower_p90'])} | "
                  f"{g(r['dose_lower_p99'])} | {g(r['dose_lower_max'])} | {g(r['share_dose_lower_ge_budget'])} | "
                  f"{g(r['dose_upper_median'])} | {g(r['dose_upper_p90'])} | {g(r['share_dose_upper_ge_budget'])} |")
    print("\n## verdict")
    for r in rows_v:
        print({k: (g(v) if isinstance(v, float) else v) for k, v in r.items()
               if k not in ("commit", "analysis_commit", "seed", "config", "host")})
    print("\n## peak flux")
    for r in rows_pk:
        print({k: (g(v, 4) if isinstance(v, float) else v) for k, v in r.items()
               if k not in ("commit", "analysis_commit", "seed", "config", "host")})
    print("\n## inventory")
    for r in rows_inv:
        print({k: (g(v) if isinstance(v, float) else v) for k, v in r.items()
               if k not in ("commit", "analysis_commit", "seed", "config", "host")})


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=("compute", "analyze", "posthoc"))
    ap.add_argument("--workers", type=int, default=None, help="default: config compute.workers")
    ap.add_argument("--smoke", type=int, default=None, help="first N receivers per source, into runs/.../smoke/")
    a = ap.parse_args(argv)
    cfg = load_config()
    if a.step == "compute":
        compute(cfg, a.workers or int(cfg["compute"]["workers"]), a.smoke)
    elif a.step == "analyze":
        analyze(cfg, smoke=bool(a.smoke))
    else:
        posthoc(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
