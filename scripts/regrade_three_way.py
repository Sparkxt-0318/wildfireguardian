#!/usr/bin/env python
"""WFG-213 second pass: three-way classification of the committed 영덕 routes against the
observed FIRMS footprint under declared evidence bounds. Rule: docs/regrade_three_way.md
(written BEFORE this ran). Writes data/processed/regrade_three_way_yeongdeok.json and
appends §5 to the doc. Reproduces the committed 414 / 42 / 2 partition first.

    python scripts/regrade_three_way.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402

from measure_present_perimeter_yeongdeok import (  # noqa: E402
    EXPECTED, NPZ, build, present_perimeter_view, sha256,
)
from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402

OUT = REPO / "data/processed/regrade_three_way_yeongdeok.json"
DOC = REPO / "docs/regrade_three_way.md"
MISS = [0, 1, "inf"]
ARMS = ("fire_blind", "forecast_aware", "present_perimeter")


def first_seen_grid(z):
    obs = z["obs_stack"]; t = np.asarray(z["obs_times"], float)
    fs = np.full(obs.shape[1:], np.inf)
    for i in range(len(t) - 1, -1, -1):
        fs[obs[i] == 1] = t[i]
    return fs, t


def earliest(first, t, m):
    """Earliest possible fire-affected time for a cell first seen at `first` (A2)."""
    if not np.isfinite(first):
        return np.inf
    k = int(np.where(t == first)[0][0])
    if m == "inf":
        return 0.0
    j = k - 1 - int(m)
    return float(t[j]) if j >= 0 else 0.0


def classify_route(net, path, fs, t, grid):
    """Per-node cells and presence times -> class per miss allowance."""
    times = [0.0]
    for i in range(len(path) - 1):
        times.append(times[-1] + net.graph[path[i]][path[i + 1]]["time_min"])
    xmin, ymin, xmax, ymax, cell = grid.minx, grid.miny, grid.maxx, grid.maxy, grid.cell_size_m
    nrows, ncols = fs.shape
    out = {"unsupported": False, "inadmissible_all": False}
    worst = {m: "admissible_all" for m in MISS}
    for n, tp in zip(path, times):
        x, y = net.node_xy(n)
        col = int(math.floor((x - xmin) / cell)); row = int(math.floor((ymax - y) / cell))
        if not (0 <= col < ncols and 0 <= row < nrows):
            out["unsupported"] = True
            continue
        f = fs[row, col]
        if not np.isfinite(f):
            continue
        if f <= tp:
            out["inadmissible_all"] = True
        for m in MISS:
            if tp >= earliest(f, t, m):
                worst[m] = "indeterminate"
    for m in MISS:
        out[f"class_m{m}"] = ("unsupported" if out["unsupported"] else
                              "inadmissible_all" if out["inadmissible_all"] else worst[m])
    out["total_time_min"] = times[-1]
    return out


def main() -> int:
    canon, prm, hazard, haz, extent, net, snaps = build()
    p_cut = float(prm["p_cut"]); budget = float(prm["time_budget_min"]); step = float(prm["time_step_min"])
    z = np.load(NPZ); fs, t = first_seen_grid(z)
    cand, _ign = candidate_origins(net, hazard, haz, extent, p_cut)
    view, vstats = present_perimeter_view(net, hazard, p_cut)
    counts = {"both_safe": 0, "naive_into_FA_safe": 0, "no_safe_route": 0, "other": 0}
    rows = []; t0 = time.monotonic()
    for i, n in enumerate(cand):
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m")
        fa = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=budget, p_cut=p_cut, time_step_min=step)
        pp = naive_route(view, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m") if n in view.graph else None
        if nv.reached and nv.enters_hazard and fa.reached and not fa.enters_hazard: b = "naive_into_FA_safe"
        elif nv.reached and nv.enters_hazard and not fa.reached: b = "no_safe_route"
        elif nv.reached and not nv.enters_hazard and fa.reached and not fa.enters_hazard: b = "both_safe"
        else: b = "other"
        counts[b] += 1
        row = {"origin": int(n), "forecast_bucket": b}
        for arm, r, g in (("fire_blind", nv, net), ("forecast_aware", fa, net), ("present_perimeter", pp, view)):
            if r is None or not r.reached or r.total_time_min > budget:
                row[arm] = {"forecast_reached": bool(r is not None and r.reached), "over_budget": bool(r is not None and r.reached and r.total_time_min > budget),
                            **{f"class_m{m}": "not_reached" for m in MISS}}
            else:
                c = classify_route(g, list(r.route), fs, t, hazard.grid)
                row[arm] = {"forecast_reached": True, "over_budget": False, "forecast_enters": bool(r.enters_hazard), **c}
        rows.append(row)
        if (i + 1) % 100 == 0: print(f"  [{i+1}/{len(cand)}] {time.monotonic()-t0:.0f}s", flush=True)
    if {k: counts[k] for k in EXPECTED} != EXPECTED:
        print(f"STOP: partition {counts} != {EXPECTED}", file=sys.stderr); return 3

    classes = ["admissible_all", "indeterminate", "inadmissible_all", "unsupported", "not_reached"]
    def tally(arm, m):
        return {c: sum(1 for r in rows if r[arm][f"class_m{m}"] == c) for c in classes}
    summary = {arm: {f"m{m}": tally(arm, m) for m in MISS} for arm in ARMS}
    fa_only = [r for r in rows if r["forecast_bucket"] == "naive_into_FA_safe"]
    summary["forecast_only_42"] = {f"m{m}": {c: sum(1 for r in fa_only if r["forecast_aware"][f"class_m{m}"] == c) for c in classes} for m in MISS}
    summary["settled_by_one_more_overpass"] = {arm: sum(1 for r in rows if r[arm]["class_m0"] == "admissible_all" and r[arm]["class_m1"] == "indeterminate") for arm in ARMS}
    paired = {}
    for m in MISS:
        tab = {}
        for r in rows:
            k = f"{r['fire_blind'][f'class_m{m}']}|{r['forecast_aware'][f'class_m{m}']}"
            tab[k] = tab.get(k, 0) + 1
        paired[f"m{m}"] = dict(sorted(tab.items()))
    # link to the first pass's two rules
    first_pass = {"seen_so_far_safe_equals_not_inadmissible": {arm: sum(1 for r in rows if r[arm]["class_m0"] not in ("inadmissible_all", "not_reached", "unsupported")) for arm in ARMS}}
    result = {
        "schema_version": 1, "title": "WFG-213 second pass: three-way classification against the observed FIRMS footprint",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/regrade_three_way.md §2-§3 (pre-registered)",
        "inputs": {"npz": str(NPZ.relative_to(REPO)), "npz_sha256": sha256(NPZ), **{k: str(v.relative_to(REPO)) for k, v in snaps.items()},
                   "obs_times_min": [float(v) for v in t], "first_seen_histogram": {str(k): int(v) for k, v in zip(*np.unique(fs, return_counts=True))}},
        "parameters": {"p_cut": p_cut, "time_budget_min": budget, "time_step_min": step, "n_origins": len(cand), "miss_allowances": MISS, "present_perimeter_view": vstats},
        "forecast_partition_reproduced": counts, "summary": summary, "paired_fire_blind_x_forecast_aware": paired,
        "first_pass_link": first_pass, "per_origin": rows,
        "caveats": ["exposure under the model's own admissibility rule, not passability (A3)", "never-detected cells assumed unaffected (A4)", "node sampling only (A5)", "영덕 present-perimeter arm is the zero-buffer experiment, not the stated 의성·안동 budgeted opponent"],
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["", f"_Run {result['generated_utc']} at `{result['git_commit'][:7]}`; artifact `{OUT.relative_to(REPO)}`; partition re-derived as {counts['both_safe']} / {counts['naive_into_FA_safe']} / {counts['no_safe_route']}; 458 origins each row._", "",
             "| arm | m | admissible for all | indeterminate | inadmissible for all | unsupported | not reached |", "|---|---|---:|---:|---:|---:|---:|"]
    label = {"fire_blind": "fire-blind", "forecast_aware": "forecast-aware", "present_perimeter": "present perimeter (영덕, 0 buffer)"}
    for arm in ARMS:
        for m in MISS:
            c = summary[arm][f"m{m}"]
            lines.append(f"| {label[arm]} | {m} | {c['admissible_all']} | {c['indeterminate']} | {c['inadmissible_all']} | {c['unsupported']} | {c['not_reached']} |")
    lines += ["", "The 42 forecast-only origins, forecast-aware route:", ""]
    for m in MISS:
        c = summary["forecast_only_42"][f"m{m}"]
        lines.append(f"- m = {m}: admissible {c['admissible_all']}, indeterminate {c['indeterminate']}, inadmissible {c['inadmissible_all']}, not reached {c['not_reached']}")
    lines += ["", "Paired fire-blind × forecast-aware (class of fire-blind route | class of forecast-aware route):", ""]
    for m in MISS:
        lines.append(f"- m = {m}: " + ", ".join(f"{k} = {v}" for k, v in paired[f'm{m}'].items()))
    s = summary["settled_by_one_more_overpass"]
    lines += ["", f"Routes admissible under m = 0 but indeterminate under m = 1 (what one more overpass between 0 and 333 min would settle): fire-blind {s['fire_blind']}, forecast-aware {s['forecast_aware']}, present perimeter {s['present_perimeter']}.", "",
              "Reading: the count of routes 「inadmissible for all」 is the same under every m, because it rests on A1 alone; what m moves is the split of the remainder between 「admissible」 and 「indeterminate」. Under m = ∞ nothing that touches a cell detected at any time through 2403 min can be called admissible, which is the honest floor without an absence product. These are repository measurements of the committed routes under the declared assumptions; none is a safety rate."]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
