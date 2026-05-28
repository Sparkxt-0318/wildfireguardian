"""Scaffold: an empirical test for SUPER-multiplicative moisture-wind coupling.

Session 5 Deliverable 6 (stretch). The honest conclusion of
`interaction.md` is that the *sign* of the moisture-wind cross-partial is
structurally guaranteed because raw Rothermel is separable. The genuinely
novel scientific question is therefore:

    Does REAL fire spread show a cross-partial ∂²R/∂M∂U *stronger* than the
    separable Rothermel baseline predicts? (super-multiplicativity, from
    processes Rothermel omits — spotting, fire-induced wind, crown transitions)

This module scaffolds the test. It cannot use real fire+weather data
offline, so it trains an XGBoost regressor on a **CLEARLY-LABELLED
SYNTHETIC** dataset and shows the test can *detect* injected
super-multiplicativity. When real data is available (a later session with
data access), the same pipeline runs unchanged on it.

ALL DATA HERE IS SYNTHETIC. No empirical claim about real fire is made.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .interaction import dR_dU as rothermel_dR_dU
from .interaction import spread_rate as rothermel_R


@dataclass
class SyntheticSpreadDataset:
    """A labelled-synthetic (features → spread rate) dataset.

    Features: dead_moisture, midflame_wind_ms, slope_deg.
    Target: spread rate (m/min). ``super_strength`` injects a
    super-multiplicative moisture×wind term on top of the separable
    Rothermel baseline.
    """

    X: np.ndarray            # (N, 3): [dead_moisture, u_midflame, slope_deg]
    y: np.ndarray            # (N,)
    feature_names: tuple[str, ...]
    super_strength: float
    synthetic: bool = True


def make_synthetic_dataset(
    n: int = 4000, super_strength: float = 0.0, noise_frac: float = 0.05,
    seed: int = 0,
) -> SyntheticSpreadDataset:
    """Generate a synthetic (features → R) dataset.

    The base target is the separable Rothermel R(dead, U) (slope ignored in
    the label for simplicity, but kept as a feature/decoy). With
    ``super_strength = s > 0`` we inject a super-multiplicative term:

        R_label = R_roth · (1 + s · dryness · (U / U_ref))

    where ``dryness = (m_x - dead)/m_x`` ∈ [0,1] and ``U_ref = 3 m/s``. This
    is a synthetic stand-in for the real super-multiplicative processes; the
    sign of the *extra* cross-partial it creates is negative w.r.t. moisture
    (drier + windier ⇒ disproportionately faster), mimicking spotting.
    """
    rng = np.random.default_rng(seed)
    dead = rng.uniform(0.04, 0.28, n)          # dead 1-h moisture
    u = rng.uniform(0.2, 4.0, n)               # midflame wind, m/s
    slope = rng.uniform(0.0, 25.0, n)          # decoy feature
    base = np.array([rothermel_R(float(d), float(uu)) for d, uu in zip(dead, u)])

    m_x = 0.30
    dryness = np.clip((m_x - dead) / m_x, 0.0, 1.0)
    factor = 1.0 + super_strength * dryness * (u / 3.0)
    y = base * factor
    y = y * (1.0 + rng.normal(0.0, noise_frac, n))
    y = np.clip(y, 0.0, None)

    X = np.column_stack([dead, u, slope])
    return SyntheticSpreadDataset(
        X=X, y=y, feature_names=("dead_moisture", "u_midflame_ms", "slope_deg"),
        super_strength=super_strength,
    )


@dataclass
class EmpiricalInteractionResult:
    """Empirical vs Rothermel-separable cross-partial comparison."""

    super_strength: float
    empirical_d2R_dM_dU: float
    rothermel_d2R_dM_dU: float
    empirical_minus_rothermel: float
    train_r2: float
    detects_super: bool


def _empirical_cross_partial(model, dead0: float, u0: float, dM: float = 0.02,
                             dU: float = 0.3, slope0: float = 0.0) -> float:
    """Finite-difference ∂²R/∂M∂U from the fitted surface at (dead0, u0)."""
    def pred(d, u):
        return float(model.predict(np.array([[d, u, slope0]]))[0])
    # mixed second difference
    f_pp = pred(dead0 + dM, u0 + dU)
    f_pm = pred(dead0 + dM, u0 - dU)
    f_mp = pred(dead0 - dM, u0 + dU)
    f_mm = pred(dead0 - dM, u0 - dU)
    return (f_pp - f_pm - f_mp + f_mm) / (4.0 * dM * dU)


def run_empirical_test(
    super_strength: float = 0.0, n: int = 4000, seed: int = 0,
    dead0: float = 0.12, u0: float = 1.5,
) -> EmpiricalInteractionResult:
    """Train XGBoost on synthetic data; compare empirical vs Rothermel ∂²R/∂M∂U.

    On separable data (``super_strength = 0``) the empirical cross-partial
    should match Rothermel's. With injected super-multiplicativity it should
    be detectably *more negative* (drier+windier disproportionately faster).
    """
    import xgboost as xgb

    ds = make_synthetic_dataset(n=n, super_strength=super_strength, seed=seed)
    model = xgb.XGBRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9, random_state=seed,
    )
    model.fit(ds.X, ds.y)

    # R² on training data (scaffold-level fit quality).
    pred = model.predict(ds.X)
    ss_res = float(np.sum((ds.y - pred) ** 2))
    ss_tot = float(np.sum((ds.y - ds.y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    emp = _empirical_cross_partial(model, dead0, u0)

    # Analytic Rothermel-separable cross-partial at the same point.
    h = 0.02
    roth = (rothermel_dR_dU(dead0 + h, u0) - rothermel_dR_dU(dead0 - h, u0)) / (2 * h)

    diff = emp - roth
    # "Detects super" if the empirical cross-partial is materially more
    # negative than the separable baseline (drier+windier extra-fast).
    detects = diff < -0.5 * abs(roth)

    return EmpiricalInteractionResult(
        super_strength=super_strength,
        empirical_d2R_dM_dU=emp,
        rothermel_d2R_dM_dU=roth,
        empirical_minus_rothermel=diff,
        train_r2=r2,
        detects_super=detects,
    )


__all__ = [
    "SyntheticSpreadDataset",
    "make_synthetic_dataset",
    "EmpiricalInteractionResult",
    "run_empirical_test",
]
