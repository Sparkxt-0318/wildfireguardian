"""Quantify the years-since-fire / calendar-year aliasing, before any fit.

Owner: A4. Written for `research/landslides/PREREG_landslides_2026-09-16_v0.1.md`
section 7. It is deliberately outcome free: every input is the **exposure**
side (which fires burned, in which calendar year, how large), read from
`kfs_fire_stats_csv`, which is registry status `verified`. Nothing here reads
the landslide occurrence record, so running it does not put the direction into
section 4 of `research/eval/SIGNOFF.md`.

WHAT IT MEASURES
----------------
Write `F` for a fire's calendar year, `Y` for an observation calendar year and
`t = Y - F` for years since fire. Inside the committed occurrence window the
three are bound by the identity `t = Y - F` exactly, which is the age, period
and cohort identity. Two consequences follow and this script measures both.

1. **Rank.** With a free calendar-year factor and a free fire-cohort factor in
   the same design, the column for `t` is a linear combination of the other
   two, so the linear component of the years-since-fire term is not identified.
   Adding `t^2` adds a rank, so the curvature is. The script reports the rank
   of four design matrices so the claim is checked rather than asserted.

2. **Separation.** How much of `t`'s variation survives conditioning on the
   calendar year. Reported as an exposure-weighted `R^2` of `t` on calendar
   year dummies, and, more usefully, as the count of distinct calendar years in
   which each value of `t` is observed at all.

A CEILING, NOT AN ESTIMATE
--------------------------
The cell grid gives every cohort the same weight in every later year, as
though every burned hectare stayed in the risk set with equal exposure for the
rest of the window. The realised design will be weighted by storms and by
assignable units, both of which are smaller and neither of which is known yet.
So every separation number here is an **upper bound** on the separation the fit
will actually have. It is reported as a ceiling and read as a ceiling.

Run:  .auto/venv/bin/python research/landslides/design/aliasing_separation.py
Writes: research/landslides/design/design_numbers.json (key path `aliasing`)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from research.shared.loaders.kfs import load_fire_stats_csv  # noqa: E402

#: The calendar years the committed landslide occurrence record covers.
#: Registry `kfs_landslide_history`, temporal_coverage verified 2026-09-16.
OBSERVATION_YEARS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)

#: Burned-area floors, in hectares, at which a fire is counted as a cohort
#: member. Declared in the pre-registration, section 7.3, and not moved after
#: any number below was seen.
SIZE_FLOORS_HA: tuple[float, ...] = (1.0, 10.0, 100.0)


def cell_grid(cohort_weight: dict[int, float],
              observation_years: "tuple[int, ...]" = OBSERVATION_YEARS) -> pd.DataFrame:
    """Every (fire year, observation year) cell with `t = Y - F >= 0`."""
    rows = []
    for fire_year, weight in cohort_weight.items():
        for obs_year in observation_years:
            t = obs_year - fire_year
            if t < 0:
                continue
            rows.append((int(fire_year), int(obs_year), int(t), float(weight)))
    return pd.DataFrame(rows, columns=["fire_year", "obs_year", "t", "weight"])


def weighted_r2_t_on_year(grid: pd.DataFrame) -> float:
    """Exposure-weighted `R^2` of `t` regressed on calendar-year dummies.

    One minus this is the share of `t`'s variation that survives a free
    calendar-year effect, which is the only variation the time term can be
    identified from once the calendar is absorbed.
    """
    design = pd.get_dummies(grid.obs_year, prefix="Y").astype(float).values
    y = grid.t.astype(float).values
    w = grid.weight.astype(float).values
    wmat = np.diag(w)
    beta, *_ = np.linalg.lstsq(design.T @ wmat @ design, design.T @ wmat @ y, rcond=None)
    resid = y - design @ beta
    ybar = (w * y).sum() / w.sum()
    sst = float((w * (y - ybar) ** 2).sum())
    if sst <= 0.0:
        return float("nan")
    return float(1.0 - (w * resid ** 2).sum() / sst)


def ranks(grid: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Rank of four design matrices, to check the age-period-cohort claim.

    A deficiency of one in `[1, t, year]` and in `[1, t, cohort]` is the
    ordinary dummy trap (the dummies sum to the intercept). The interesting
    number is `[1, t, year, cohort]`: a deficiency of three is two dummy traps
    plus the `t = Y - F` identity. If `[1, t, t^2, year, cohort]` gains a rank
    over it, the curvature is identified where the linear term is not.
    """
    ones = np.ones((len(grid), 1))
    tcol = grid.t.values.reshape(-1, 1).astype(float)
    year_d = pd.get_dummies(grid.obs_year, prefix="Y").astype(float).values
    cohort_d = pd.get_dummies(grid.fire_year, prefix="F").astype(float).values
    mats = {
        "1_t_year": np.hstack([ones, tcol, year_d]),
        "1_t_cohort": np.hstack([ones, tcol, cohort_d]),
        "1_t_year_cohort": np.hstack([ones, tcol, year_d, cohort_d]),
        "1_t_tsq_year_cohort": np.hstack([ones, tcol, tcol ** 2, year_d, cohort_d]),
    }
    out = {}
    for name, m in mats.items():
        r = int(np.linalg.matrix_rank(m))
        out[name] = {"rank": r, "columns": int(m.shape[1]), "deficiency": int(m.shape[1] - r)}
    return out


def describe(grid: pd.DataFrame) -> dict:
    per_t = {int(tv): sorted(int(v) for v in grid[grid.t == tv].obs_year.unique())
             for tv in sorted(grid.t.unique())}
    r2 = weighted_r2_t_on_year(grid)
    return {
        "cells": int(len(grid)),
        "t_values_observed": sorted(int(v) for v in grid.t.unique()),
        "t_max": int(grid.t.max()),
        "calendar_years_per_t": {str(k): v for k, v in per_t.items()},
        "n_calendar_years_per_t": {str(k): len(v) for k, v in per_t.items()},
        "r2_t_on_calendar_year": round(r2, 4),
        "residual_share_of_t": round(1.0 - r2, 4),
        "variance_inflation_on_t": (round(1.0 / (1.0 - r2), 3) if r2 < 1.0 else None),
        "ranks": ranks(grid),
    }


def main() -> int:
    fires = load_fire_stats_csv()
    fires = fires.assign(
        fire_year=pd.to_numeric(fires["발생일시_년"], errors="coerce"),
        area_ha=pd.to_numeric(fires["피해면적_합계"], errors="coerce"),
    )

    out: dict = {
        "generated_by": "research/landslides/design/aliasing_separation.py",
        "outcome_free": True,
        "inputs": [{"dataset_id": "kfs_fire_stats_csv", "status": "verified"}],
        "observation_years": list(OBSERVATION_YEARS),
        "note": ("every separation figure here is a ceiling; see the module "
                 "docstring. The grid weights each cohort equally in every "
                 "later year, which the realised design will not."),
        "committed_record": {},
        "counterfactual": {},
    }

    for floor in SIZE_FLOORS_HA:
        sub = fires[fires.area_ha >= floor]
        by_count = sub.groupby("fire_year").size().to_dict()
        by_area = sub.groupby("fire_year")["area_ha"].sum().to_dict()
        block = {
            "cohorts_by_count": {str(int(k)): int(v) for k, v in by_count.items()},
            "cohorts_by_area_ha": {str(int(k)): round(float(v), 2) for k, v in by_area.items()},
            "weighted_by_fire_count": describe(cell_grid({int(k): float(v) for k, v in by_count.items()})),
            "weighted_by_burned_area": describe(cell_grid({int(k): float(v) for k, v in by_area.items()})),
        }
        out["committed_record"]["floor_%g_ha" % floor] = block

    # What a longer exposure record would buy. Equal weights, so this measures
    # the geometry of the design and nothing about Korean fire sizes.
    scenarios = {
        "back_to_2019": {y: 1.0 for y in (2019, 2022, 2023, 2025)},
        "back_to_2011": {y: 1.0 for y in range(2011, 2026)},
    }
    for name, cohorts in scenarios.items():
        out["counterfactual"][name] = describe(cell_grid(cohorts))
    out["counterfactual"]["back_to_2011_with_matching_occurrence_record"] = describe(
        cell_grid({y: 1.0 for y in range(2011, 2026)}, tuple(range(2011, 2026))))

    dest = Path(__file__).resolve().parent / "design_numbers.json"
    existing = {}
    if dest.exists():
        existing = json.loads(dest.read_text(encoding="utf-8"))
    existing["aliasing"] = out
    dest.write_text(json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(json.dumps(out["committed_record"]["floor_100_ha"], ensure_ascii=False, indent=2))
    print("wrote %s key path aliasing" % dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
