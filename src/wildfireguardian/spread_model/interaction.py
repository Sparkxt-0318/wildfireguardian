"""Moisture-wind interaction: the honest, dimensional cross-partial.

Session 5 replaces the Session-4 "multiplicative coupling, ratio = 1.000"
claim, which was **tautological**. Rothermel's rate of spread is
multiplicatively separable in moisture and wind,

    R(M, U) = K · g(M) · f(U),

(the wind coefficient :math:`\\phi_w` is moisture-independent; the
moisture damping and heat-sink terms are wind-independent), so the
four-corner ratio R(D)·R(A) / (R(B)·R(C)) is identically 1 for *any*
separable function. It carries zero physical information.

The correct interaction measure is the **dimensional cross-partial**
:math:`\\partial^2 R / \\partial M \\partial U`, and the operationally
meaningful statement is the marginal wind effect
:math:`\\partial R / \\partial U` (m/min of spread per m/s of wind) at
different moisture levels — "each additional m/s of midflame wind adds
more m/min of spread when the fuel is drier."

Honest caveat (stated in docs/methodology/interaction.md): because raw
Rothermel is separable, the *sign* of the cross-partial
(:math:`\\partial^2 R/\\partial M\\partial U < 0`) is structurally
guaranteed and the ratio of the two slopes is constant across U. The
genuinely novel question — whether REAL fire spread shows interaction
*stronger* than this separable baseline (super-multiplicativity) — needs
empirical data and is scaffolded separately.

All winds here are **midflame** (m/s). Convert open / 10-m winds with
:mod:`wildfireguardian.spread_model.wind` first.
"""

from __future__ import annotations

from .rothermel import KOREAN_PINUS, MultiClassFuelModel, compute_spread_rate

#: Default fuel for the project's interaction analysis.
_FUEL: MultiClassFuelModel = KOREAN_PINUS

#: Representative dry / moist dead-1-h fuel moistures (fraction).
DRY_DEAD: float = 0.06
MOIST_DEAD: float = 0.20

#: Live moisture held fixed at the measured Korean foliar value.
DEFAULT_LIVE: float = KOREAN_PINUS.live_moisture_default or 1.19

#: Representative midflame wind for reporting the marginal effect (m/s).
#: Session 7: anchored to the ACTUAL WAF-corrected Yeongdeok midflame wind
#: (10-m 13.9 m/s × Korean-pine WAF 0.10 ≈ 1.39 m/s) — the wind the surface
#: fire truly experiences — NOT an unrepresentative 4 m/s.
YEONGDEOK_MIDFLAME_U: float = 1.39
REPRESENTATIVE_MIDFLAME_U: float = YEONGDEOK_MIDFLAME_U


def spread_rate(
    dead_moisture: float, u_midflame_ms: float, live_moisture: float | None = None,
    fuel: MultiClassFuelModel | None = None,
) -> float:
    """Rate of spread (m/min) at a given dead moisture and **midflame** wind."""
    fm = fuel or _FUEL
    live = live_moisture if live_moisture is not None else DEFAULT_LIVE
    return compute_spread_rate(
        fm, dead_moisture=dead_moisture, live_moisture=live,
        wind_speed_ms=u_midflame_ms,
    ).rate_m_min


def dR_dU(
    dead_moisture: float, u_midflame_ms: float, *,
    live_moisture: float | None = None, h: float = 0.02,
    fuel: MultiClassFuelModel | None = None,
) -> float:
    """Marginal wind effect ∂R/∂U (m/min per m/s) by central difference.

    Evaluated at midflame wind ``u_midflame_ms``. Uses a one-sided
    difference near U = 0 to stay in the valid (U ≥ 0) domain.
    """
    lo = u_midflame_ms - h
    if lo < 0.0:
        # Forward difference at the boundary.
        f0 = spread_rate(dead_moisture, u_midflame_ms, live_moisture, fuel)
        f1 = spread_rate(dead_moisture, u_midflame_ms + h, live_moisture, fuel)
        return (f1 - f0) / h
    f_hi = spread_rate(dead_moisture, u_midflame_ms + h, live_moisture, fuel)
    f_lo = spread_rate(dead_moisture, lo, live_moisture, fuel)
    return (f_hi - f_lo) / (2.0 * h)


def d2R_dM_dU(
    dead_moisture: float, u_midflame_ms: float, *,
    live_moisture: float | None = None, dM: float = 0.01, h: float = 0.02,
    fuel: MultiClassFuelModel | None = None,
) -> float:
    """Mixed partial ∂²R/∂M∂U (m/min per m/s per unit moisture-fraction).

    M is the dead 1-h fuel moisture (fraction). Negative value ⇒ drier fuel
    has a larger marginal wind effect.
    """
    hi = dR_dU(dead_moisture + dM, u_midflame_ms,
               live_moisture=live_moisture, h=h, fuel=fuel)
    lo = dR_dU(max(0.0, dead_moisture - dM), u_midflame_ms,
               live_moisture=live_moisture, h=h, fuel=fuel)
    return (hi - lo) / (2.0 * dM)


def marginal_wind_effect_report(
    u_midflame_ms: float = REPRESENTATIVE_MIDFLAME_U,
) -> dict:
    """Report ∂R/∂U on dry vs moist fuel and the mixed partial.

    Returns a dict with the dimensional marginal wind effects and the
    cross-partial, for the session report.
    """
    dry_slope = dR_dU(DRY_DEAD, u_midflame_ms)
    moist_slope = dR_dU(MOIST_DEAD, u_midflame_ms)
    cross = d2R_dM_dU((DRY_DEAD + MOIST_DEAD) / 2.0, u_midflame_ms)
    return {
        "u_midflame_ms": u_midflame_ms,
        "dry_dead_moisture": DRY_DEAD,
        "moist_dead_moisture": MOIST_DEAD,
        "dR_dU_dry_m_min_per_ms": dry_slope,
        "dR_dU_moist_m_min_per_ms": moist_slope,
        "extra_wind_effect_when_dry": dry_slope - moist_slope,
        "d2R_dM_dU": cross,
        "R_dry": spread_rate(DRY_DEAD, u_midflame_ms),
        "R_moist": spread_rate(MOIST_DEAD, u_midflame_ms),
    }


def separability_slope_ratio_across_U(
    u_values_ms: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0),
) -> list[tuple[float, float]]:
    """Demonstrate separability: ∂R/∂U(dry) / ∂R/∂U(moist) is constant in U.

    Returns ``[(U, ratio), ...]``. A constant ratio is the proof that the
    cross-partial's structure carries no information beyond the separable
    factors g(M) and f(U) — i.e., why the old four-corner ratio was empty.
    """
    out: list[tuple[float, float]] = []
    for u in u_values_ms:
        dry = dR_dU(DRY_DEAD, u)
        moist = dR_dU(MOIST_DEAD, u)
        out.append((u, dry / moist if moist != 0 else float("nan")))
    return out


__all__ = [
    "DRY_DEAD",
    "MOIST_DEAD",
    "DEFAULT_LIVE",
    "REPRESENTATIVE_MIDFLAME_U",
    "spread_rate",
    "dR_dU",
    "d2R_dM_dU",
    "marginal_wind_effect_report",
    "separability_slope_ratio_across_U",
]
