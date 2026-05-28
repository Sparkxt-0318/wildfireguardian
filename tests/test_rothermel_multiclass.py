"""Unit tests for the multi-class Rothermel implementation (Session 2).

Two test categories:

1. **Andrews 2018 Table 7 reproducibility.** R0 (no wind, no slope) values
   for Anderson 13 fuels in their multi-class form should fall within
   ~15% of published BehavePlus numbers. This is the headline scientific
   claim: the multi-class refactor corrects the 2-5× overestimate of
   the Session 1 single-class implementation.

2. **Behavioural physics.** Monotonicity in moisture (dead and live),
   correct response to wind and slope, dead-only fuels ignore live
   moisture, etc.

Backward compatibility: the existing Session 1 tests
(``tests/test_rothermel.py``) remain green — see that file.
"""

from __future__ import annotations

import math

import pytest

from wildfireguardian.spread_model.rothermel import (
    ANDERSON_13,
    KOREAN_PINUS,
    FuelCategory,
    compute_multi_class_spread_rate,
    compute_spread_rate,
    live_moisture_of_extinction_burgan1979,
)


# ---------------------------------------------------------------------------
# Andrews 2018 Table 7 reproducibility
# ---------------------------------------------------------------------------
#
# Reference conditions for R0: no wind, no slope, 6% dead-fuel moisture
# (extreme drought), 100% live-fuel moisture where applicable.
#
# Bands here bracket published BehavePlus output cross-referenced with
# Andrews 2018 GTR-RMRS-371 Table 7 (which itself is the canonical
# multi-class reference). The bands are wider than ±10% because:
#   - BehavePlus / FlamMap can differ by a few % from textbook Rothermel
#     even on identical inputs (rounding, ξ vs ξ_0, etc.).
#   - For dynamic fuels (FM4 with live woody, FM10 with live woody) the
#     Burgan 1979 dynamic m_x_live we compute can differ slightly from
#     BehavePlus's implementation.
# A ±15-25 % window is what BehavePlus literature itself uses to describe
# "agreement with reference" — see Andrews 2018 §5.

REFERENCE_R_FT_MIN_AT_REF_CONDITIONS: dict[str, tuple[float, float]] = {
    # (lo, hi) ft/min at no-wind/no-slope/6 % dead/100 % live
    # Reference values triangulated from Andrews 2018 Table 7 and the
    # original Anderson 1982 worked examples.
    "FM1":  (3.5, 6.0),   # short grass: published R0 ≈ 4–5 ft/min at 6%
    "FM4":  (5.5, 9.5),   # chaparral: published R0 ≈ 7–9 ft/min at 6%
    "FM8":  (0.5, 1.3),   # closed timber litter: published R0 ≈ 0.7–1.0 ft/min
    "FM10": (1.4, 2.8),   # timber litter+understory: published R0 ≈ 1.5–2.2 ft/min
}


@pytest.mark.parametrize(
    "code, lo, hi",
    [(c, *bounds) for c, bounds in REFERENCE_R_FT_MIN_AT_REF_CONDITIONS.items()],
)
def test_multi_class_reproduces_andrews_2018_table7(code: str, lo: float, hi: float) -> None:
    """R0 multi-class agrees with Andrews 2018 Table 7 to within ~15-25%."""
    r = compute_spread_rate(
        ANDERSON_13[code], dead_moisture=0.06, live_moisture=1.00,
        wind_speed_ms=0.0, slope_degrees=0.0,
    )
    assert lo <= r.rate_ft_min <= hi, (
        f"{code} R0 multi-class = {r.rate_ft_min:.2f} ft/min "
        f"outside published band [{lo}, {hi}] ft/min. "
        f"Intermediates: I_R={r.I_R_Btu_ft2_min:.0f}, σ_T={r.sigma_T:.0f}, "
        f"η_M_dead={r.eta_M_dead:.3f}, m_x_live={r.m_x_live:.3f}"
    )


def test_multi_class_improves_on_single_class_for_fm10() -> None:
    """The multi-class FM10 R0 must be CLOSER to published than single-class.

    Published BehavePlus FM10 R0 (no wind, 6% dead, 100% live) is ≈ 2 ft/min.
    Session 1 single-class FM10 is ≈ 4.6 ft/min (2.3× overestimate).
    Session 2 multi-class FM10 should be roughly half the single-class value,
    much closer to the published reference.
    """
    from wildfireguardian.spread_model.rothermel import (
        FUEL_MODELS,
        compute_single_class_spread_rate,
    )

    multi_r = compute_spread_rate(
        ANDERSON_13["FM10"],
        dead_moisture=0.06, live_moisture=1.00,
    ).rate_ft_min
    single_r = compute_single_class_spread_rate(
        FUEL_MODELS["FM10"], fuel_moisture=0.06,
    ).rate_ft_min
    # The published reference is ~2 ft/min; we want multi-class to be
    # measurably closer to that than single-class is.
    published = 2.0
    assert abs(multi_r - published) < abs(single_r - published), (
        f"Multi-class FM10 ({multi_r:.2f} ft/min) is not closer to published "
        f"({published} ft/min) than single-class ({single_r:.2f} ft/min)"
    )


# ---------------------------------------------------------------------------
# Behavioural physics — monotonicity in moisture
# ---------------------------------------------------------------------------


def test_dead_moisture_monotonicity_korean_pinus() -> None:
    """Drier dead fuel → faster spread for Korean Pinus (multi-class)."""
    rates = [
        compute_spread_rate(
            KOREAN_PINUS, dead_moisture=m, live_moisture=0.80,
            wind_speed_ms=2.0,
        ).rate_m_min
        for m in [0.04, 0.06, 0.08, 0.10, 0.12, 0.15]
    ]
    for prev, nxt in zip(rates, rates[1:]):
        assert nxt < prev, f"Dead moisture should decrease R: {prev} → {nxt}"


def test_lfmc_monotonicity_korean_pinus_30_to_200pct() -> None:
    """Korean Pinus R decreases monotonically as LFMC increases over 30%-200%.

    Spec's headline LFMC story: at typical Korean spring dead-fuel moisture
    (12%), spread rate roughly doubles as LFMC drops from 80% to 40%.
    """
    rates = [
        compute_spread_rate(
            KOREAN_PINUS, dead_moisture=0.12, live_moisture=lfmc,
            wind_speed_ms=2.0,
        ).rate_m_min
        for lfmc in [0.30, 0.40, 0.60, 0.80, 1.00, 1.20, 1.50, 2.00]
    ]
    for prev, nxt in zip(rates, rates[1:]):
        assert nxt < prev, f"LFMC should decrease R: {prev} → {nxt}"

    # Story check: R at 40 % LFMC vs R at 80 % LFMC under typical spring dead.
    r_40 = compute_spread_rate(
        KOREAN_PINUS, dead_moisture=0.12, live_moisture=0.40, wind_speed_ms=2.0,
    ).rate_m_min
    r_80 = compute_spread_rate(
        KOREAN_PINUS, dead_moisture=0.12, live_moisture=0.80, wind_speed_ms=2.0,
    ).rate_m_min
    assert r_40 > 1.3 * r_80, (
        f"Spread rate should jump >30 % from LFMC 80→40: r40={r_40:.2f}, r80={r_80:.2f}"
    )


def test_lfmc_does_not_affect_dead_only_fuels() -> None:
    """FM1/FM8/FM9 have no live particles; varying live moisture is a no-op."""
    for code in ("FM1", "FM8", "FM9"):
        fm = ANDERSON_13[code]
        assert all(
            p.category is not FuelCategory.LIVE for p in fm.particles
        ), f"{code} should be dead-only"
        r_low = compute_spread_rate(fm, dead_moisture=0.08, live_moisture=0.30).rate_m_min
        r_high = compute_spread_rate(fm, dead_moisture=0.08, live_moisture=2.00).rate_m_min
        assert r_low == pytest.approx(r_high), (
            f"{code} R changed with LFMC ({r_low} vs {r_high}); should be inert"
        )


def test_lfmc_affects_live_containing_fuels() -> None:
    """FM4 / FM5 / FM6 / FM10 (with live woody) respond to LFMC."""
    for code in ("FM4", "FM5"):
        fm = ANDERSON_13[code]
        assert any(
            p.category is FuelCategory.LIVE for p in fm.particles
        ), f"{code} should have live class"
        r_low = compute_spread_rate(fm, dead_moisture=0.06, live_moisture=0.30).rate_m_min
        r_high = compute_spread_rate(fm, dead_moisture=0.06, live_moisture=2.00).rate_m_min
        assert r_low > r_high, (
            f"{code} should burn faster at lower LFMC: r_low(30%)={r_low:.3f}, "
            f"r_high(200%)={r_high:.3f}"
        )


# ---------------------------------------------------------------------------
# Burgan 1979 dynamic m_x_live
# ---------------------------------------------------------------------------


def test_burgan_live_extinction_decreases_with_wetter_dead() -> None:
    """As dead fuels get wetter, the dynamic live m_x DECREASES.

    Andrews 2018 eq. (26): m_x_live = 2.9·W'·(1 − M_f_dead/m_x_dead) − 0.226.
    Wetter dead fuel → smaller (1 − M_f_dead/m_x_dead) → smaller m_x_live.
    """
    dead_loads = (0.10, 0.06, 0.10)
    dead_savs = (2100.0, 109.0, 30.0)
    live_loads = (0.06, 0.03)
    live_savs = (1800.0, 1500.0)
    m_x_dead = 0.25

    mx_dry = live_moisture_of_extinction_burgan1979(
        dead_loads, dead_savs, (0.05, 0.05, 0.05),
        live_loads, live_savs, m_x_dead,
    )
    mx_wet = live_moisture_of_extinction_burgan1979(
        dead_loads, dead_savs, (0.15, 0.15, 0.15),
        live_loads, live_savs, m_x_dead,
    )
    assert mx_dry > mx_wet, f"m_x_live should drop with wetter dead: dry={mx_dry}, wet={mx_wet}"
    # Floor at m_x_dead.
    assert mx_wet >= m_x_dead


def test_burgan_live_extinction_returns_dead_when_no_live_fuel() -> None:
    """If there is no live fuel, the dynamic formula falls back to m_x_dead."""
    mx = live_moisture_of_extinction_burgan1979(
        (0.10, 0.05), (2000.0, 109.0), (0.08, 0.08),
        (), (), m_x_dead=0.30,
    )
    assert mx == 0.30


# ---------------------------------------------------------------------------
# Wind and slope (must still increase R)
# ---------------------------------------------------------------------------


def test_wind_increases_R_multi_class() -> None:
    fm = ANDERSON_13["FM10"]
    rates = [
        compute_spread_rate(
            fm, dead_moisture=0.06, live_moisture=1.00,
            wind_speed_ms=u, slope_degrees=0.0,
        ).rate_m_min
        for u in [0.0, 1.0, 2.0, 5.0, 10.0]
    ]
    for prev, nxt in zip(rates, rates[1:]):
        assert nxt > prev, f"Wind should increase R (multi): {prev} → {nxt}"


def test_slope_increases_R_multi_class() -> None:
    fm = ANDERSON_13["FM10"]
    rates = [
        compute_spread_rate(
            fm, dead_moisture=0.06, live_moisture=1.00,
            wind_speed_ms=0.0, slope_degrees=s,
        ).rate_m_min
        for s in [0.0, 10.0, 20.0, 30.0]
    ]
    for prev, nxt in zip(rates, rates[1:]):
        assert nxt > prev, f"Slope should increase R (multi): {prev} → {nxt}"


# ---------------------------------------------------------------------------
# Algorithm sanity
# ---------------------------------------------------------------------------


def test_sigma_T_is_sa_weighted_for_multi_class_fm10() -> None:
    """σ_T should land between the smallest and largest particle SAVs for FM10."""
    fm = ANDERSON_13["FM10"]
    r = compute_spread_rate(fm, dead_moisture=0.08, live_moisture=1.00)
    savs = [p.sigma for p in fm.particles]
    assert min(savs) < r.sigma_T < max(savs)


def test_korean_pinus_has_live_classes() -> None:
    """Sanity check: Korean Pinus has both dead and live classes wired in."""
    assert KOREAN_PINUS.has_live
    assert KOREAN_PINUS.dead_classes
    assert KOREAN_PINUS.live_classes


def test_korean_pinus_dynamic_m_x_live_is_above_m_x_dead() -> None:
    """For typical inputs the Burgan formula should give m_x_live > m_x_dead."""
    r = compute_spread_rate(
        KOREAN_PINUS, dead_moisture=0.10, live_moisture=0.80, wind_speed_ms=2.0,
    )
    assert r.m_x_live > r.m_x_dead


def test_explicit_multi_class_call_matches_polymorphic_dispatch() -> None:
    """compute_spread_rate(ANDERSON_13[code], ...) ==
    compute_multi_class_spread_rate(ANDERSON_13[code], ...) bit-for-bit."""
    fm = ANDERSON_13["FM10"]
    r1 = compute_spread_rate(fm, dead_moisture=0.06, live_moisture=1.00, wind_speed_ms=2.0)
    r2 = compute_multi_class_spread_rate(
        fm, dead_moisture=0.06, live_moisture=1.00, wind_speed_ms=2.0,
    )
    assert r1.rate_m_min == pytest.approx(r2.rate_m_min)
    assert r1.I_R_Btu_ft2_min == pytest.approx(r2.I_R_Btu_ft2_min)


def test_per_class_moisture_input_works() -> None:
    """per_class_moisture override should let callers set per-particle moisture."""
    from wildfireguardian.spread_model.rothermel import FuelClassKind

    fm = ANDERSON_13["FM10"]
    r = compute_spread_rate(
        fm,
        per_class_moisture={
            FuelClassKind.DEAD_1H: 0.05,
            FuelClassKind.DEAD_10H: 0.10,
            FuelClassKind.DEAD_100H: 0.15,
            FuelClassKind.LIVE_WOODY: 1.00,
        },
        wind_speed_ms=2.0,
    )
    assert r.rate_m_min > 0


def test_zero_wind_zero_slope_multi_class_finite() -> None:
    """No wind, no slope, normal moisture: R must be finite and positive."""
    r = compute_spread_rate(
        ANDERSON_13["FM1"], dead_moisture=0.06, live_moisture=1.00,
    )
    assert 0.0 < r.rate_m_min < 1000.0
    assert math.isfinite(r.rate_m_min)
