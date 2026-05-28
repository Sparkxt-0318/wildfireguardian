"""Sub-equation primitives for the Rothermel (1972) surface fire spread model.

Each function in this module implements **one** sub-equation of the
Rothermel master equation, with its source equation number from
Andrews (2018) cited in the docstring. The functions are deliberately
unit-aware (imperial, since that is what Rothermel's coefficients were
fit to) and pure — they accept floats and return floats.

The aggregation that combines these primitives into a rate of spread
lives in :mod:`wildfireguardian.spread_model.rothermel.spread`. The
fuel-model data structures (single-class and multi-class) live in
:mod:`wildfireguardian.spread_model.rothermel.fuel_model`.

References
----------
- Rothermel, R.C. (1972). *A mathematical model for predicting fire spread
  in wildland fuels.* USDA FS Research Paper INT-115. 40 pp.
- Albini, F.A. (1976). *Estimating wildfire behavior and effects.* USDA FS
  General Technical Report INT-30. 92 pp.
- Andrews, P.L. (2018). *The Rothermel surface fire spread model and
  associated developments: a comprehensive explanation.* USDA FS General
  Technical Report RMRS-GTR-371. 121 pp.

Notation in this module follows Andrews 2018. All inputs and outputs are
in **imperial units** (lb/ft², ft, 1/ft, Btu/lb, ft/min). SI conversions
are handled by the public wrapper :func:`spread.compute_spread_rate`.
"""

from __future__ import annotations

import math
from typing import Final

#: Particle density of wildland fuels, lb/ft³. Rothermel 1972 §III; Andrews
#: 2018 Table 1. Treated as a universal constant for all Anderson 13 fuel
#: models and for the Korean fuel model.
PARTICLE_DENSITY_LB_FT3: Final[float] = 32.0


# ---------------------------------------------------------------------------
# Fuel-bed geometry
# ---------------------------------------------------------------------------


def bulk_density(w_o_total: float, delta: float) -> float:
    """Oven-dry bulk density of the fuel bed, ρ_b  [lb/ft³].

    .. math:: \\rho_b = w_o / \\delta

    Andrews 2018 eq. (31). For a multi-class fuel, ``w_o_total`` is the sum
    of loadings across all particles (dead + live).
    """
    if delta <= 0.0:
        raise ValueError("fuel bed depth delta must be > 0")
    return w_o_total / delta


def packing_ratio(rho_b: float, rho_p: float = PARTICLE_DENSITY_LB_FT3) -> float:
    """β = ρ_b / ρ_p.

    Andrews 2018 eq. (32).
    """
    return rho_b / rho_p


def optimum_packing_ratio(sigma: float) -> float:
    """β_op, optimum packing ratio  (Andrews 2018 eq. (37)).

    .. math:: \\beta_{op} = 3.348 \\, \\sigma^{-0.8189}

    Parameters
    ----------
    sigma : float
        Characteristic surface-area-to-volume ratio of the fuel bed, 1/ft.
        For multi-class fuels this is the SA-weighted σ_T.
    """
    return 3.348 * sigma ** -0.8189


# ---------------------------------------------------------------------------
# Damping coefficients
# ---------------------------------------------------------------------------


def mineral_damping_coefficient(s_e: float) -> float:
    """Mineral damping coefficient, η_s  (Andrews 2018 eq. (62)).

    .. math:: \\eta_s = 0.174 \\, s_e^{-0.19}, \\quad \\eta_s \\le 1
    """
    if s_e <= 0.0:
        raise ValueError("effective mineral content s_e must be > 0")
    eta_s = 0.174 * s_e ** -0.19
    return min(eta_s, 1.0)


def moisture_damping_coefficient(m_f: float, m_x: float) -> float:
    """Moisture damping coefficient, η_M  (Andrews 2018 eq. (64)).

    Drives the LFMC sensitivity of fire spread. Zero when m_f ≥ m_x.

    .. math::
        \\eta_M = 1 - 2.59 r + 5.11 r^2 - 3.52 r^3, \\quad r = m_f / m_x
    """
    if m_f < 0.0:
        raise ValueError("fuel moisture m_f must be >= 0")
    if m_x <= 0.0:
        raise ValueError("moisture of extinction m_x must be > 0")
    if m_f >= m_x:
        return 0.0
    r = m_f / m_x
    eta_M = 1.0 - 2.59 * r + 5.11 * r * r - 3.52 * r * r * r
    return max(eta_M, 0.0)


# ---------------------------------------------------------------------------
# Reaction velocities
# ---------------------------------------------------------------------------


def reaction_velocities(
    sigma: float, beta: float, beta_op: float,
) -> tuple[float, float]:
    """Return (Γ'_max, Γ') in 1/min  (Andrews 2018 eqs. (36), (38), (39)).

    .. math::

       \\Gamma'_{\\max} &= \\sigma^{1.5} / (495 + 0.0594 \\, \\sigma^{1.5})

       A &= 133 \\, \\sigma^{-0.7913}

       \\Gamma' &= \\Gamma'_{\\max} \\,
                   (\\beta/\\beta_{op})^A \\,
                   \\exp\\bigl(A(1 - \\beta/\\beta_{op})\\bigr)
    """
    sigma_1_5 = sigma ** 1.5
    gamma_prime_max = sigma_1_5 / (495.0 + 0.0594 * sigma_1_5)
    A = 133.0 * sigma ** -0.7913
    ratio = beta / beta_op
    gamma_prime = gamma_prime_max * (ratio ** A) * math.exp(A * (1.0 - ratio))
    return gamma_prime_max, gamma_prime


# ---------------------------------------------------------------------------
# Propagating flux, wind, slope
# ---------------------------------------------------------------------------


def propagating_flux_ratio(sigma: float, beta: float) -> float:
    """Propagating flux ratio ξ  (Andrews 2018 eq. (40)).

    .. math::
        \\xi = \\frac{\\exp\\bigl((0.792 + 0.681 \\sqrt{\\sigma})
                                  (\\beta + 0.1)\\bigr)}
                    {192 + 0.2595 \\, \\sigma}
    """
    return math.exp((0.792 + 0.681 * math.sqrt(sigma)) * (beta + 0.1)) / (
        192.0 + 0.2595 * sigma
    )


def wind_coefficient(U_ftmin: float, sigma: float, beta: float, beta_op: float) -> float:
    """Wind coefficient φ_w  (Andrews 2018 eqs. (47)–(50)).

    .. math::
        C &= 7.47 \\, \\exp(-0.133 \\, \\sigma^{0.55})

        B &= 0.02526 \\, \\sigma^{0.54}

        E &= 0.715 \\, \\exp(-3.59 \\times 10^{-4} \\, \\sigma)

        \\phi_w &= C \\, U^B \\, (\\beta / \\beta_{op})^{-E}

    Wind ``U`` is **midflame** wind in **ft/min**. Returns 0 for U ≤ 0.
    """
    if U_ftmin <= 0.0:
        return 0.0
    C = 7.47 * math.exp(-0.133 * sigma ** 0.55)
    B = 0.02526 * sigma ** 0.54
    E = 0.715 * math.exp(-3.59e-4 * sigma)
    return C * (U_ftmin ** B) * (beta / beta_op) ** -E


def slope_coefficient(slope_tan: float, beta: float) -> float:
    """Slope coefficient φ_s  (Andrews 2018 eq. (51)).

    .. math:: \\phi_s = 5.275 \\, \\beta^{-0.3} \\, (\\tan \\phi)^2
    """
    return 5.275 * beta ** -0.3 * slope_tan ** 2


# ---------------------------------------------------------------------------
# Heating
# ---------------------------------------------------------------------------


def effective_heating_number(sigma: float) -> float:
    """Effective heating number ε  (Andrews 2018 eq. (14)).

    .. math:: \\varepsilon = \\exp(-138 / \\sigma)
    """
    return math.exp(-138.0 / sigma)


def heat_of_preignition(m_f: float) -> float:
    """Heat of preignition Q_ig  [Btu/lb]  (Andrews 2018 eq. (12)).

    .. math:: Q_{ig} = 250 + 1116 \\, m_f
    """
    return 250.0 + 1116.0 * m_f


# ---------------------------------------------------------------------------
# Reaction intensity & master equation
# ---------------------------------------------------------------------------


def reaction_intensity_single_class(
    w_n: float, h: float, eta_M: float, eta_s: float, gamma_prime: float,
) -> float:
    """Reaction intensity I_R  [Btu/ft²/min] — single fuel class.

    .. math:: I_R = \\Gamma' \\, w_n \\, h \\, \\eta_M \\, \\eta_s

    Andrews 2018 eq. (27). For a multi-class fuel use
    :func:`reaction_intensity_multi_class` instead.
    """
    return gamma_prime * w_n * h * eta_M * eta_s


def reaction_intensity_multi_class(
    gamma_prime: float,
    contributions: tuple[tuple[float, float, float, float], ...],
) -> float:
    """Multi-class reaction intensity (Andrews 2018 §3, eq. (58) extended).

    .. math::
        I_R = \\Gamma' \\, \\sum_i w_{n,i} \\, h_i \\, \\eta_{M,i} \\, \\eta_{s,i}

    Parameters
    ----------
    gamma_prime : float
        Actual reaction velocity Γ' [1/min].
    contributions : tuple of (w_n_i, h_i, η_M_i, η_s_i) tuples
        One tuple per category (dead, live). Use 0-valued tuples for
        categories with no fuel.

    Returns
    -------
    float
        Total reaction intensity, Btu/ft²/min.
    """
    s = 0.0
    for w_n_i, h_i, eta_M_i, eta_s_i in contributions:
        s += w_n_i * h_i * eta_M_i * eta_s_i
    return gamma_prime * s


def rate_of_spread(
    I_R: float, xi: float, phi_w: float, phi_s: float,
    rho_b: float, epsilon_Qig: float,
) -> float:
    """Master Rothermel equation for rate of spread, R  [ft/min].

    .. math::
        R = \\frac{I_R \\, \\xi \\, (1 + \\phi_w + \\phi_s)}
                 {\\rho_b \\, (\\varepsilon \\, Q_{ig})_{\\text{eff}}}

    Andrews 2018 eq. (52) (single-class) / eq. (58)  (multi-class).

    ``epsilon_Qig`` is the *effective* product ε·Q_ig:

    - For single class: ε(σ) · Q_ig(m_f).
    - For multi class:
      Σ_i Σ_j f_i · f_ij · ε_ij(σ_ij) · Q_ig_ij(m_f_ij) — i.e. the
      heat-sink term per Andrews 2018 §3.
    """
    denom = rho_b * epsilon_Qig
    if denom <= 0.0:
        return 0.0
    return I_R * xi * (1.0 + phi_w + phi_s) / denom


# ---------------------------------------------------------------------------
# Burgan (1979) dynamic live moisture of extinction
# ---------------------------------------------------------------------------


def live_moisture_of_extinction_burgan1979(
    dead_loadings_w_o: tuple[float, ...],
    dead_savs: tuple[float, ...],
    dead_moistures: tuple[float, ...],
    live_loadings_w_o: tuple[float, ...],
    live_savs: tuple[float, ...],
    m_x_dead: float,
) -> float:
    """Dynamic live moisture of extinction (Burgan 1979 / Andrews 2018 eq. 26).

    .. math::

       W' &= \\frac{\\sum_{j \\in \\text{dead}} w_{o,j} \\exp(-138/\\sigma_j)}
                  {\\sum_{j \\in \\text{live}} w_{o,j} \\exp(-500/\\sigma_j)}

       \\bar{M}_{f,\\text{dead}} &=
            \\frac{\\sum_{j \\in \\text{dead}} w_{o,j}
                  \\exp(-138/\\sigma_j) M_{f,j}}
                 {\\sum_{j \\in \\text{dead}} w_{o,j} \\exp(-138/\\sigma_j)}

       m_x^{\\text{live}} &= \\max\\!\\left(m_x^{\\text{dead}},\\;
            2.9 \\, W' \\bigl(1 - \\bar{M}_{f,\\text{dead}} / m_x^{\\text{dead}}\\bigr)
            - 0.226\\right)

    All inputs in Rothermel imperial units (lb/ft², 1/ft, fraction).
    Returns ``m_x_dead`` if no live fuel is present (live extinction is then
    irrelevant; the live reaction-intensity contribution vanishes anyway).

    Reference: Burgan, R.E. (1979). *Estimating live fuel moisture for the
    1978 National Fire Danger Rating System.* USDA FS Research Paper INT-226.
    Andrews 2018 §3, eqs. (23)–(26).
    """
    if not live_loadings_w_o:
        return m_x_dead
    live_weighted = sum(
        w * math.exp(-500.0 / s)
        for w, s in zip(live_loadings_w_o, live_savs)
    )
    if live_weighted <= 0.0:
        return m_x_dead
    dead_weighted = sum(
        w * math.exp(-138.0 / s)
        for w, s in zip(dead_loadings_w_o, dead_savs)
    )
    if dead_weighted <= 0.0:
        return m_x_dead
    W_prime = dead_weighted / live_weighted
    M_f_dead_fine = sum(
        w * math.exp(-138.0 / s) * m
        for w, s, m in zip(dead_loadings_w_o, dead_savs, dead_moistures)
    ) / dead_weighted
    m_x_live_dynamic = 2.9 * W_prime * (1.0 - M_f_dead_fine / m_x_dead) - 0.226
    return max(m_x_dead, m_x_live_dynamic)


__all__ = [
    "PARTICLE_DENSITY_LB_FT3",
    "bulk_density",
    "packing_ratio",
    "optimum_packing_ratio",
    "mineral_damping_coefficient",
    "moisture_damping_coefficient",
    "reaction_velocities",
    "propagating_flux_ratio",
    "wind_coefficient",
    "slope_coefficient",
    "effective_heating_number",
    "heat_of_preignition",
    "reaction_intensity_single_class",
    "reaction_intensity_multi_class",
    "rate_of_spread",
    "live_moisture_of_extinction_burgan1979",
]
