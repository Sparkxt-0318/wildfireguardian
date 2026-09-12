#!/usr/bin/env python
"""WFG-213: re-grade the committed 영덕 routes against the OBSERVED footprint.

Rule and rationale: docs/regrade_against_observed.md, written BEFORE this ran.
Reads only committed inputs (canonical npz, snapshots). Writes ONLY
data/processed/regrade_against_observed_yeongdeok.json and appends §4 to the doc.
Reproduces the committed 414 / 42 / 2 partition first; stops if it does not.

Run:  python scripts/regrade_against_observed.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.evacuation import (  # noqa: E402
    _evaluate_path, future_aware_route, naive_route,
)
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

from measure_present_perimeter_yeongdeok import (  # noqa: E402
    EXPECTED, NPZ, build, present_perimeter_view, sha256,
)
from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402

OUT = REPO / "data/processed/regrade_against_observed_yeongdeok.json"
DOC = REPO / "docs/regrade_against_observed.md"


def observed_sequence(z, grid, rule: str) -> HazardSequence:
    """obs_stack as a HazardSequence under the pre-registered rule.

    HazardSequence.prob_at interpolates between its slices; to make the field a
    step function we give it one slice per observation and, for the backward rule,
    repeat each observation just before the next one (so linear interpolation
    between identical slices is constant). Forward rule: repeat the NEXT
    observation just after the previous one."""
    obs = z["obs_stack"].astype(np.float32)
    t = np.asarray(z["obs_times"], float)
    eps = 1e-3
    times, surfaces = [], []
    if rule == "backward":
        for i in range(len(t)):
            times.append(t[i]); surfaces.append(obs[i])
            if i + 1 < len(t):
                times.append(t[i + 1] - eps); surfaces.append(obs[i])
    elif rule == "forward":
        for i in range(len(t)):
            if i > 0:
                times.append(t[i - 1] + eps); surfaces.append(obs[i])
            times.append(t[i]); surfaces.append(obs[i])
    else:
        raise ValueError(rule)
    return HazardSequence(grid=grid, times_min=np.array(times, float), surfaces=surfaces)


def score(net, path, seq, p_cut, budget):
    if not path:
        return {"reached": False, "safe": False}
    r = _evaluate_path(net, path, seq, 0.0, p_cut, "regrade", path[-1])
    safe = bool(r.reached and not r.enters_hazard and r.total_time_min <= budget)
    return {"reached": bool(r.reached), "enters": bool(r.enters_hazard),
            "time_min": float(r.total_time_min), "safe": safe}


def main() -> int:
    canon, prm, hazard, haz, extent, net, snaps = build()
    p_cut = float(prm["p_cut"]); budget = float(prm["time_budget_min"])
    step = float(prm["time_step_min"])
    z = np.load(NPZ)
    grid = hazard.grid
    obs_b = observed_sequence(z, grid, "backward")
    obs_f = observed_sequence(z, grid, "forward")
    cand, ign = candidate_origins(net, hazard, haz, extent, p_cut)
    print(f"origins: {len(cand)} (expected {sum(EXPECTED.values())})")
    view, vstats = present_perimeter_view(net, hazard, p_cut)

    rows = []
    counts = {"both_safe": 0, "naive_into_FA_safe": 0, "no_safe_route": 0, "other": 0}
    t0 = time.monotonic()
    for i, n in enumerate(cand):
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m")
        fa = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=budget,
                                p_cut=p_cut, time_step_min=step)
        if n in view.graph:
            pp = naive_route(view, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m")
        else:
            pp = None
        if nv.reached and nv.enters_hazard and fa.reached and not fa.enters_hazard:
            b = "naive_into_FA_safe"
        elif nv.reached and nv.enters_hazard and not fa.reached:
            b = "no_safe_route"
        elif nv.reached and not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            b = "both_safe"
        else:
            b = "other"
        counts[b] += 1
        row = {"origin": int(n), "forecast_bucket": b}
        for arm, r in (("fire_blind", nv), ("forecast_aware", fa), ("present_perimeter", pp)):
            path = list(r.route) if (r is not None and r.reached) else []
            row[arm] = {
                "forecast": {"reached": bool(r.reached) if r else False,
                             "enters": bool(r.enters_hazard) if r else None,
                             "safe": bool(r.reached and not r.enters_hazard) if r else False},
                "observed_backward": score(net if arm != "present_perimeter" else view, path, obs_b, p_cut, budget),
                "observed_forward": score(net if arm != "present_perimeter" else view, path, obs_f, p_cut, budget),
            }
        rows.append(row)
        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{len(cand)}] {time.monotonic() - t0:.0f}s", flush=True)

    if {k: counts[k] for k in EXPECTED} != EXPECTED:
        print(f"STOP: partition {counts} != {EXPECTED}; nothing written", file=sys.stderr)
        return 3

    def tally(rule):
        out = {}
        for arm in ("fire_blind", "forecast_aware", "present_perimeter"):
            out[arm] = {
                "safe_forecast": sum(1 for r in rows if r[arm]["forecast"]["safe"]),
                "safe_observed": sum(1 for r in rows if r[arm][rule]["safe"]),
            }
        fa_only_forecast = [r for r in rows if r["forecast_bucket"] == "naive_into_FA_safe"]
        out["fa_only_under_forecast"] = len(fa_only_forecast)
        out["fa_only_under_forecast_and_observed"] = sum(
            1 for r in fa_only_forecast if r["forecast_aware"][rule]["safe"] and not r["fire_blind"][rule]["safe"])
        out["fa_only_under_observed_any_bucket"] = sum(
            1 for r in rows if r["forecast_aware"][rule]["safe"] and not r["fire_blind"][rule]["safe"])
        out["blind_only_under_observed"] = sum(
            1 for r in rows if r["fire_blind"][rule]["safe"] and not r["forecast_aware"][rule]["safe"])
        out["fa_route_enters_observed"] = sum(
            1 for r in rows if r["forecast_aware"]["forecast"]["safe"] and r["forecast_aware"][rule].get("enters"))
        out["blind_route_enters_observed"] = sum(
            1 for r in rows if r["fire_blind"]["forecast"]["reached"] and r["fire_blind"][rule].get("enters"))
        return out

    result = {
        "schema_version": 1,
        "title": "WFG-213: committed 영덕 routes re-graded against the observed FIRMS footprint",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/regrade_against_observed.md §2 (pre-registered)",
        "inputs": {"npz": str(NPZ.relative_to(REPO)), "npz_sha256": sha256(NPZ),
                   **{k: str(v.relative_to(REPO)) for k, v in snaps.items()},
                   "obs_times_min": [float(v) for v in z["obs_times"]],
                   "haz_times_min": [float(v) for v in z["haz_times"]]},
        "parameters": {"p_cut": p_cut, "time_budget_min": budget, "time_step_min": step,
                       "n_origins": len(cand), "present_perimeter_view": vstats},
        "forecast_partition_reproduced": counts,
        "observed_backward": tally("observed_backward"),
        "observed_forward": tally("observed_forward"),
        "per_origin": rows,
        "caveats": [
            "obs_stack is FIRMS at 500 m with a detection floor: this scores against what was seen, not against the fire.",
            "Routes are the committed ones planned on the forecast; only the grading field changed.",
            "의성·안동 has no obs_stack; this is 영덕 only.",
        ],
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    ob, of = result["observed_backward"], result["observed_forward"]
    lines = [
        "", f"_Run {result['generated_utc']} at `{result['git_commit'][:7]}`; artifact "
        f"`data/processed/regrade_against_observed_yeongdeok.json`; partition re-derived as "
        f"{counts['both_safe']} / {counts['naive_into_FA_safe']} / {counts['no_safe_route']}._", "",
        "| arm | safe, graded on the forecast | safe, graded on 「seen so far」 | safe, graded on 「will be seen」 |",
        "|---|---:|---:|---:|",
    ]
    for arm, label in (("fire_blind", "fire-blind"), ("forecast_aware", "forecast-aware"), ("present_perimeter", "present perimeter (0 buffer)")):
        lines.append(f"| {label} | {ob[arm]['safe_forecast']} | {ob[arm]['safe_observed']} | {of[arm]['safe_observed']} |")
    lines += ["",
        f"- Of the **{ob['fa_only_under_forecast']}** origins safe only on the forecast-aware route under the forecast, "
        f"**{ob['fa_only_under_forecast_and_observed']}** remain forecast-aware-only-safe under 「seen so far」 and "
        f"**{of['fa_only_under_forecast_and_observed']}** under 「will be seen」.",
        f"- Origins where the forecast-aware route is safe and the fire-blind route is not, under the observation, any bucket: "
        f"**{ob['fa_only_under_observed_any_bucket']}** (seen so far) / **{of['fa_only_under_observed_any_bucket']}** (will be seen).",
        f"- Origins where the fire-blind route is safe and the forecast-aware route is not, under the observation: "
        f"**{ob['blind_only_under_observed']}** / **{of['blind_only_under_observed']}**.",
        f"- Forecast-aware routes that were 「safe」 on the forecast but cross a cell the observation marks burned at that time: "
        f"**{ob['fa_route_enters_observed']}** / **{of['fa_route_enters_observed']}**.",
        "",
        "These counts are what the author asked to see (NH-052 A). They are not registered, not on any judge-facing "
        "surface, and not a margin until the author decides what they mean.",
    ]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT.relative_to(REPO)); print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
