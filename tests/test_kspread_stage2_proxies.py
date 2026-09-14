"""K-SPREAD-2025 Stage 2 proxies — the declared construction, asserted rather than described.

The rule page ``docs/benchmark/stage2_proxy_rules.md`` was written before these entrants ran,
which is only worth something if the code still does what it says. Four things can rot:

1. **A declared constant drifts.** The backing fraction, the 읍면동 smoothing scale and
   Rothermel's slope coefficient are quoted as numbers on the rule page. If the module's
   values move, the page becomes a description of a run that no longer happens.
2. **The pair stops differing by exactly one term.** E1 and E2 are only a usable comparison
   because E2 IS E1 times the slope factor: on flat ground they must agree. If E2 picks up
   any other difference, 「what Rothermel's slope factor buys」 stops being what the pair
   measures.
3. **The smoothing eats the footprint.** ``p = max(binary, blur)`` keeps the deterministic
   footprint certain; a plain blur would drop T0 cells below p_cut and make any proxy look
   worse than persistence for a reason that is an artefact of the smoothing.
4. **An oracle is filed as a forecast.** These entrants choose their wind against the
   observation. Protocol §3 puts that in the hindcast track, and a bundle that says
   otherwise would put an upper bound beside a real forecast-track score.

Nothing here reads the clock, the network, or a file outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "benchmark"))

import build_entrants_stage2 as B  # noqa: E402

RULES = REPO / "docs/benchmark/stage2_proxy_rules.md"
ENTRANTS = REPO / "data/processed/benchmark/entrants"
ORACLES = ("e1_windcone_oracle", "e2_rothermel_oracle")


def _tiny_canvas(nrow=21, ncol=21, cell=500.0):
    """A small canvas with one seed cell at the centre; the module's own geometry rules."""
    x0, y1 = 0.0, nrow * cell
    xs = x0 + (np.arange(ncol) + 0.5) * cell
    ys = y1 - (np.arange(nrow) + 0.5) * cell
    seed = np.zeros((nrow, ncol), bool)
    seed[nrow // 2, ncol // 2] = True
    return dict(x0=x0, y0=0.0, x1=ncol * cell, y1=y1, cell=cell, nrow=nrow, ncol=ncol,
                X=np.broadcast_to(xs, (nrow, ncol)).copy(),
                Y=np.broadcast_to(ys[:, None], (nrow, ncol)).copy(), seed=seed)


# --- 1. the declared constants -------------------------------------------------------

def test_declared_constants_are_the_ones_the_rule_page_prints():
    text = RULES.read_text(encoding="utf-8")
    assert B.BACKING == 0.15 and "b = 0.15" in text
    assert B.SMOOTH_SIGMA_M == 2000.0 and "σ = 2,000 m" in text
    assert B.BETA == 0.05 and "β = 0.05" in text
    assert round(B.SLOPE_COEF, 2) == 12.96, B.SLOPE_COEF
    assert "**12.96**" in text


def test_the_declared_sweep_grid_is_36_bearings_by_20_rates():
    assert len(B.BEARINGS) == 36 and B.BEARINGS[0] == 0.0 and B.BEARINGS[-1] == 350.0
    assert len(B.RATES) == 20 and B.RATES[0] == 100.0 and B.RATES[-1] == 2000.0
    assert list(B.HORIZONS) == [180.0, 300.0, 480.0]
    assert B.TIMES_MIN[0] == 0.0 and B.TIMES_MIN[-1] == 720.0
    assert np.allclose(np.diff(B.TIMES_MIN), 30.0), "protocol §6's 30-minute step"


# --- 2. the cone -----------------------------------------------------------------------

def test_the_cone_runs_fastest_downwind_and_floors_at_the_backing_fraction():
    cell = 500.0
    assert B.cone_rate(90.0, cell, 0.0, cell) == pytest.approx(1.0), "straight downwind, full rate"
    assert B.cone_rate(90.0, -cell, 0.0, cell) == pytest.approx(B.BACKING), "upwind is the floor"
    assert B.cone_rate(90.0, 0.0, cell, cell) == pytest.approx(B.BACKING), "crosswind is the floor"
    assert B.cone_rate(90.0, cell, cell, cell * 2 ** 0.5) == pytest.approx(2 ** -0.5), "45° is cos 45°"
    assert B.cone_rate(0.0, 0.0, cell, cell) == pytest.approx(1.0), "bearing is clockwise from north"


def test_the_cone_is_symmetric_about_the_wind_bearing():
    cv = _tiny_canvas()
    unit = B.unit_cost(cv, 0.0, None)               # wind toward the north
    r, c = cv["nrow"] // 2, cv["ncol"] // 2
    for k in (1, 3, 5):
        assert unit[r - k, c - k] == pytest.approx(unit[r - k, c + k], rel=1e-9)


def test_arrival_time_scales_inversely_with_the_head_rate():
    cv = _tiny_canvas()
    unit = B.unit_cost(cv, 45.0, None)
    a = B.stack_from_unit_cost(cv, unit, 200.0, np.array([300.0]))[0]
    b = B.stack_from_unit_cost(cv, unit, 400.0, np.array([150.0]))[0]
    assert np.allclose(a, b), "a double rate for half the time must give the same footprint"


# --- 3. E2 is E1 plus exactly one term --------------------------------------------------

def test_on_flat_ground_the_rothermel_proxy_is_the_wind_cone_cell_for_cell():
    """The pair's whole claim. E2 minus E1 must be the slope term and nothing else.

    An earlier build had E1 as a straight ray and E2 as a least-time walk; on flat ground
    the walk beat the ray by up to 23 % crosswind, because eight headings can zigzag. The
    gap was a discretisation artefact masquerading as a method difference, so both now walk
    the same graph.
    """
    cv = _tiny_canvas()
    flat = np.zeros((cv["nrow"], cv["ncol"]))
    e1 = B.unit_cost(cv, 90.0, None)
    e2 = B.unit_cost(cv, 90.0, flat)
    assert np.array_equal(e1, e2), "flat ground must make the slope term vanish exactly"


def test_an_upslope_makes_the_rothermel_proxy_faster_and_a_downslope_does_not():
    cv = _tiny_canvas()
    flat = np.zeros((cv["nrow"], cv["ncol"]))
    r, c = cv["nrow"] // 2, cv["ncol"] // 2
    up = flat.copy()
    up[:, c:] = np.arange(cv["ncol"] - c) * 250.0        # climbing to the east
    down = flat.copy()
    down[:, c:] = -np.arange(cv["ncol"] - c) * 250.0     # falling to the east
    base = B.unit_cost(cv, 90.0, flat)[r, c + 4]
    assert B.unit_cost(cv, 90.0, up)[r, c + 4] < base, "upslope must speed the front up"
    assert B.unit_cost(cv, 90.0, down)[r, c + 4] == pytest.approx(base, rel=1e-9), \
        "Rothermel's slope factor is an upslope term; descending travel is unchanged"


# --- 4. the smoothing keeps the footprint certain ---------------------------------------

def test_smoothing_adds_a_halo_and_never_erodes_the_footprint():
    cv = _tiny_canvas()
    unit = B.unit_cost(cv, 90.0, None)
    stack = B.stack_from_unit_cost(cv, unit, 500.0, np.array([0.0, 300.0]))
    for k, t in enumerate((0.0, 300.0)):
        binary = (unit / 500.0 <= t) | cv["seed"]
        assert np.all(stack[k][binary] == 1.0), "every cell in F(t) stays certain"
        assert np.all(stack[k] >= 0.0) and np.all(stack[k] <= 1.0)
        assert stack[k][~binary].max() > 0.0, "the 읍면동 smoothing must leave a halo outside"
    assert stack[1].sum() > stack[0].sum(), "the field grows with time"


# --- 5. the bundles say what they are ---------------------------------------------------

@pytest.mark.skipif(not (ENTRANTS / ORACLES[0] / "entrant.json").exists(),
                    reason="Stage 2 bundles not built in this checkout")
@pytest.mark.parametrize("eid", ORACLES)
def test_an_oracle_entrant_is_filed_as_a_hindcast_and_says_it_is_a_bound(eid):
    ent = json.loads((ENTRANTS / eid / "entrant.json").read_text(encoding="utf-8"))
    assert ent["track"] == "hindcast", "selecting the wind against the observation is hindcast"
    assert "oracle" in ent and ent["oracle"]["grid_points_searched"] == len(B.BEARINGS) * len(B.RATES)
    assert "UPPER BOUND" in ent["track_reason"]
    assert "NOT RUN" in ent["track_reason"], "the forecast-track proxies must be named as not run"
    assert ent["oracle"]["bearing_deg"] in list(B.BEARINGS)
    assert ent["oracle"]["head_rate_m_per_30min"] in list(B.RATES)
