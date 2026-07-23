#!/usr/bin/env python
"""Forecast-error robustness: deterministic breaking-point sweep + Monte Carlo.

Re-scores the FIXED npz routes (naive 28 nodes, future-aware 23 nodes) against
perturbed hazard fields. Never re-routes. See ``mc_perturb.py`` for the exact
re-scorer (verified against the stored node hazards to <1e-6).

Two outputs, written to ``data/processed/forecast_robustness.json``:

  PRIMARY — a deterministic SWEEP. For each perturbation axis independently,
  the smallest displacement at which the future-aware route's maximum on-route
  hazard first reaches ``p_cut`` = 0.5 (it peaks at 0.2597 unperturbed, so it
  has margin). Reported both on the documented discrete grid and as a
  fine-grained continuous threshold via monotone bisection.

  SECONDARY — a 2000-draw Monte Carlo sampling the three axes JOINTLY from the
  documented ranges. Fraction of perturbed worlds in which (i) the future-aware
  route stays below ``p_cut`` and (ii) its exposure stays below the naive
  route's (both re-scored in the SAME perturbed world).

The perturbation magnitudes are EXPLORATORY ranges, not a calibrated
forecast-error model. This is a robustness analysis of the METHOD on one real
route pair — NOT a restatement of the committed routing_demo.json headline.

Run:  python scripts/run_routing_monte_carlo.py
Additive & non-destructive: refuses to overwrite an existing JSON unless
``--force`` is passed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

import mc_perturb as mp
from mc_perturb import (DIRECTIONS, HazardField, REPO, load_routes, npz_sha256,
                        score_route)

# Documented (exploratory) perturbation ranges ----------------------------- #
DT_GRID_MIN = [0, 15, 30, 60, 90, 120]            # (a) front arrives early
SPACE_GRID_M = [0, 250, 500, 1000, 2000]          # (b) translation magnitude
K_GRID = [1.0, 1.2, 1.5, 2.0]                     # (c) probability scaling
# Continuous search bounds for the crisp breaking point (may exceed the grid).
DT_MAX_MIN = 720.0        # one horizon of early arrival
SPACE_MAX_M = 20000.0     # ~ the fire's linear reach
K_MAX = 20.0


def _bisect_threshold(f, lo, hi, target, iters=60):
    """Smallest x in [lo, hi] with monotone-increasing f(x) >= target.

    Returns (x, value_at_x) or (None, f(hi)) if f(hi) < target within range.
    """
    if f(hi) < target:
        return None, f(hi)
    if f(lo) >= target:
        return lo, f(lo)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if f(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi, f(hi)


def sweep_temporal(field, routes, p_cut):
    fa, naive = routes["fa"], routes["naive"]
    grid = []
    for dt in DT_GRID_MIN:
        sfa = score_route(field, fa, p_cut, dt_earlier=dt)
        snv = score_route(field, naive, p_cut, dt_earlier=dt)
        grid.append({"dt_earlier_min": dt, "fa_max_hazard": round(sfa.max_hazard, 4),
                     "fa_exposure": round(sfa.exposure, 4), "fa_enters": sfa.enters_hazard,
                     "naive_max_hazard": round(snv.max_hazard, 4),
                     "naive_exposure": round(snv.exposure, 4),
                     "fa_exposure_below_naive": bool(sfa.exposure < snv.exposure)})
    f = lambda dt: score_route(field, fa, p_cut, dt_earlier=dt).max_hazard
    thr, val = _bisect_threshold(f, 0.0, DT_MAX_MIN, p_cut)
    first_grid = next((g["dt_earlier_min"] for g in grid if g["fa_max_hazard"] >= p_cut), None)
    return {"axis": "temporal_shift_earlier",
            "unit": "minutes_front_arrives_early",
            "monotone": True,
            "grid": grid,
            "first_grid_point_reaching_pcut": first_grid,
            "reaches_pcut_within_bound": thr is not None,
            "continuous_breaking_point": (None if thr is None else round(thr, 2)),
            "max_hazard_at_search_bound": round(val, 4),
            "search_bound_min": DT_MAX_MIN}


def _radial_first_crossing(field, route, p_cut, ux, uy, max_m, step_m=5.0):
    """Smallest displacement magnitude (metres) along unit dir (ux, uy) at which
    the route's max on-route hazard first reaches ``p_cut``. Radial fine scan —
    the spatial response is NON-monotone (a route pushed far enough can exit the
    fire on the far side), so bisection is invalid; we scan and take the FIRST
    crossing. Returns (mag_or_None, max_hazard_at_that_mag_or_at_bound)."""
    mags = np.arange(0.0, max_m + step_m, step_m)
    peak = 0.0
    for m in mags:
        h = score_route(field, route, p_cut, dx=m * ux, dy=m * uy).max_hazard
        peak = max(peak, h)
        if h >= p_cut:
            return float(m), round(h, 4)
    return None, round(peak, 4)


def sweep_spatial(field, routes, p_cut):
    fa, naive = routes["fa"], routes["naive"]
    grid = []
    for mag in SPACE_GRID_M:
        per_dir = {}
        worst = -1.0
        worst_dir = None
        for name, (ux, uy) in DIRECTIONS.items():
            sc = score_route(field, fa, p_cut, dx=mag * ux, dy=mag * uy)
            per_dir[name] = round(sc.max_hazard, 4)
            if sc.max_hazard > worst:
                worst, worst_dir = sc.max_hazard, name
        grid.append({"magnitude_m": mag, "fa_max_hazard_by_dir": per_dir,
                     "worst_dir": worst_dir, "worst_fa_max_hazard": round(worst, 4),
                     "worst_fa_enters": bool(worst >= p_cut)})
    # True smallest breaking displacement: radial fine scan per direction (the
    # response is non-monotone in magnitude), then min over the 8 directions.
    per_dir_break = {}
    best_mag = None
    best_dir = None
    for name, (ux, uy) in DIRECTIONS.items():
        m, _ = _radial_first_crossing(field, fa, p_cut, ux, uy, SPACE_MAX_M)
        per_dir_break[name] = m
        if m is not None and (best_mag is None or m < best_mag):
            best_mag, best_dir = m, name
    first_grid = next((g["magnitude_m"] for g in grid if g["worst_fa_max_hazard"] >= p_cut), None)
    return {"axis": "spatial_translation",
            "unit": "metres_front_displacement",
            "directions_tested": list(DIRECTIONS.keys()),
            "note": "response is NON-monotone in magnitude; breaking point is first radial crossing",
            "grid": grid,
            "first_grid_point_reaching_pcut": first_grid,
            "breaking_magnitude_by_dir_m": per_dir_break,
            "breaking_point_m": best_mag,
            "breaking_direction": best_dir,
            "radial_step_m": 5.0,
            "search_bound_m": SPACE_MAX_M}


def sweep_probability(field, routes, p_cut):
    fa, naive = routes["fa"], routes["naive"]
    grid = []
    for k in K_GRID:
        sfa = score_route(field, fa, p_cut, k=k)
        snv = score_route(field, naive, p_cut, k=k)
        grid.append({"k": k, "fa_max_hazard": round(sfa.max_hazard, 4),
                     "fa_exposure": round(sfa.exposure, 4), "fa_enters": sfa.enters_hazard,
                     "naive_max_hazard": round(snv.max_hazard, 4),
                     "fa_exposure_below_naive": bool(sfa.exposure < snv.exposure)})
    f = lambda k: score_route(field, fa, p_cut, k=k).max_hazard
    thr, val = _bisect_threshold(f, 1.0, K_MAX, p_cut)
    first_grid = next((g["k"] for g in grid if g["fa_max_hazard"] >= p_cut), None)
    return {"axis": "probability_scaling",
            "unit": "multiplicative_factor_k_clipped_0_1",
            "monotone": True,
            "documented_max_k": K_GRID[-1],
            "grid": grid,
            "first_grid_point_reaching_pcut": first_grid,
            "reaches_pcut_within_bound": thr is not None,
            "continuous_breaking_point_k": (None if thr is None else round(thr, 4)),
            "max_hazard_at_search_bound": round(val, 4),
            "search_bound_k_beyond_documented": K_MAX}


def monte_carlo(field, routes, p_cut, n_draws, seed):
    fa, naive = routes["fa"], routes["naive"]
    rng = np.random.default_rng(seed)
    dt = rng.uniform(0.0, float(DT_GRID_MIN[-1]), n_draws)          # [0, 120] min
    mag = rng.uniform(0.0, float(SPACE_GRID_M[-1]), n_draws)        # [0, 2000] m
    ang = rng.uniform(0.0, 2.0 * np.pi, n_draws)                    # continuous direction
    k = rng.uniform(float(K_GRID[0]), float(K_GRID[-1]), n_draws)   # [1.0, 2.0]
    dx = mag * np.cos(ang)
    dy = mag * np.sin(ang)

    fa_safe = 0
    fa_below_naive = 0
    fa_max_vals = np.empty(n_draws)
    for i in range(n_draws):
        sfa = score_route(field, fa, p_cut, dt_earlier=dt[i], dx=dx[i], dy=dy[i], k=k[i])
        snv = score_route(field, naive, p_cut, dt_earlier=dt[i], dx=dx[i], dy=dy[i], k=k[i])
        fa_max_vals[i] = sfa.max_hazard
        if sfa.max_hazard < p_cut:
            fa_safe += 1
        if sfa.exposure < snv.exposure:
            fa_below_naive += 1
    return {"n_draws": n_draws, "seed": seed,
            "sampling": {"dt_earlier_min": [0.0, float(DT_GRID_MIN[-1])],
                         "translation_m": [0.0, float(SPACE_GRID_M[-1])],
                         "translation_direction": "uniform_continuous_0_2pi",
                         "k": [float(K_GRID[0]), float(K_GRID[-1])]},
            "frac_fa_below_pcut": round(fa_safe / n_draws, 4),
            "frac_fa_exposure_below_naive": round(fa_below_naive / n_draws, 4),
            "fa_max_hazard_p50": round(float(np.percentile(fa_max_vals, 50)), 4),
            "fa_max_hazard_p95": round(float(np.percentile(fa_max_vals, 95)), 4),
            "fa_max_hazard_max": round(float(fa_max_vals.max()), 4)}


def git_head(repo: Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default=str(mp.DEFAULT_NPZ))
    ap.add_argument("--p-cut", type=float, default=0.5)
    ap.add_argument("--n-draws", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260723)
    ap.add_argument("--out", default=str(REPO / "data" / "processed" / "forecast_robustness.json"))
    ap.add_argument("--force", action="store_true", help="overwrite existing JSON")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"REFUSING to overwrite existing {out} (pass --force). Nothing written.")
        return 3

    assert mp.self_check(Path(args.npz), args.p_cut), "re-scorer self-check failed"
    npz = np.load(args.npz)
    field = HazardField.from_npz(npz)
    routes = load_routes(npz)

    fa0 = score_route(field, routes["fa"], args.p_cut)
    nv0 = score_route(field, routes["naive"], args.p_cut)

    result = {
        "analysis": "forecast_error_robustness",
        "scope": ("Robustness of the routing METHOD on ONE real npz route pair "
                  "(naive 28 nodes, future-aware 23 nodes). This origin DIFFERS "
                  "from the committed routing_demo.json headline (origin_node "
                  "3316, 23/23 nodes). NOT a restatement of that headline."),
        "caveat": ("Perturbation magnitudes are exploratory ranges, not a "
                   "calibrated forecast-error model. Routes are FIXED; we "
                   "re-score, never re-route."),
        "p_cut": args.p_cut,
        "unperturbed": {
            "fa_max_hazard": round(fa0.max_hazard, 4), "fa_exposure": round(fa0.exposure, 4),
            "fa_enters": fa0.enters_hazard,
            "naive_max_hazard": round(nv0.max_hazard, 4), "naive_exposure": round(nv0.exposure, 4),
            "naive_enters": nv0.enters_hazard,
            "fa_margin_to_pcut": round(args.p_cut - fa0.max_hazard, 4),
        },
        "perturbation_ranges": {
            "temporal_shift_earlier_min": DT_GRID_MIN,
            "spatial_translation_m": SPACE_GRID_M,
            "spatial_directions": list(DIRECTIONS.keys()),
            "probability_scale_k": K_GRID,
        },
        "sweep": {
            "temporal": sweep_temporal(field, routes, args.p_cut),
            "spatial": sweep_spatial(field, routes, args.p_cut),
            "probability": sweep_probability(field, routes, args.p_cut),
        },
        "monte_carlo": monte_carlo(field, routes, args.p_cut, args.n_draws, args.seed),
        "provenance": {
            "npz": str(Path(args.npz).relative_to(REPO)),
            "npz_sha256": npz_sha256(Path(args.npz)),
            "git_head": git_head(REPO),
            "seed": args.seed,
            "n_route_nodes": {"naive": int(len(routes["naive"].xy)),
                              "fa": int(len(routes["fa"].xy))},
        },
    }
    out.write_text(json.dumps(result, indent=2))
    sw = result["sweep"]
    print(f"unperturbed fa max_hazard = {fa0.max_hazard:.4f} (margin {args.p_cut - fa0.max_hazard:.4f})")
    print(f"BREAKING POINTS (fa max_hazard -> {args.p_cut}):")
    t = sw["temporal"]
    print(f"  temporal : {'%.1f min early' % t['continuous_breaking_point'] if t['reaches_pcut_within_bound'] else 'NEVER within %g min (max %.3f)' % (t['search_bound_min'], t['max_hazard_at_search_bound'])}")
    s = sw["spatial"]
    print(f"  spatial  : {'%.0f m [%s]' % (s['breaking_point_m'], s['breaking_direction']) if s['breaking_point_m'] is not None else 'never within %g m' % s['search_bound_m']}  (grid first {s['first_grid_point_reaching_pcut']} m)")
    p = sw["probability"]
    print(f"  probScale: {'k=%.3f' % p['continuous_breaking_point_k'] if p['reaches_pcut_within_bound'] else 'NEVER within k<=%g (max %.3f); documented k<=%g gives max %.3f' % (p['search_bound_k_beyond_documented'], p['max_hazard_at_search_bound'], p['documented_max_k'], p['grid'][-1]['fa_max_hazard'])}")
    mc = result["monte_carlo"]
    print(f"MC {mc['n_draws']} draws: fa<pcut {mc['frac_fa_below_pcut']:.3f}, "
          f"fa exposure<naive {mc['frac_fa_exposure_below_naive']:.3f}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
