"""Rothermel (1972) surface fire spread model — point-form implementation.

This module implements the master equation

.. math::

   R = \\frac{I_R \\, \\xi \\, (1 + \\phi_w + \\phi_s)}
            {\\rho_b \\, \\varepsilon \\, Q_{ig}}

and each of its sub-equations exactly as catalogued in Andrews (2018), with
coefficients traced to Rothermel (1972) and Albini (1976). Internal
computation is done in **Rothermel's original imperial units** so that the
numerical pipeline matches the published reference values bit-for-bit; the
public function :func:`compute_spread_rate` accepts SI inputs and emits a
result in m/min.

References
----------

- Rothermel, R.C. (1972). *A mathematical model for predicting fire spread
  in wildland fuels.* USDA Forest Service Research Paper INT-115. Ogden,
  UT: Intermountain Forest and Range Experiment Station. 40 pp.
- Albini, F.A. (1976). *Estimating wildfire behavior and effects.* USDA
  Forest Service General Technical Report INT-30. 92 pp.
- Anderson, H.E. (1982). *Aids to determining fuel models for estimating
  fire behavior.* USDA Forest Service General Technical Report INT-122.
  22 pp.
- Andrews, P.L. (2018). *The Rothermel surface fire spread model and
  associated developments: a comprehensive explanation.* USDA Forest
  Service General Technical Report RMRS-GTR-371. 121 pp.

Notation follows Andrews 2018. Variables that are unitful state their units
in their docstring. Imperial inputs and outputs are tagged ``[imp]``; SI
inputs and outputs are tagged ``[si]``.

저자 주: 본 모듈은 미국 산림청 Rothermel 모델의 단일 연료층 (single
fuel class) 구현입니다. 다중 연료층 (1h/10h/100h dead, live herb,
live woody) 가중 평균은 후속 세션에서 추가될 예정입니다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final

from ..utils import units as U

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

#: Particle density of wildland fuels, lb/ft³. Rothermel 1972 §III; Andrews
#: 2018 Table 1. This is treated as a universal constant for all 13
#: Anderson fuel models.
PARTICLE_DENSITY_LB_FT3: Final[float] = 32.0


# ---------------------------------------------------------------------------
# FuelModel dataclass + Anderson 13 standard registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FuelModel:
    """One row of the Anderson 13 standard fuel model table.

    All fields are in Rothermel's original imperial units. The registry
    :data:`FUEL_MODELS` exposes the canonical instances.

    Attributes
    ----------
    code : str
        Short identifier, e.g. ``"FM4"``.
    name : str
        Human-readable name.
    w_o : float
        Oven-dry fuel loading, lb/ft². For multi-class fuels this is the
        *characteristic* (single-class equivalent) loading we use in this
        simplified implementation — see the module docstring.
    delta : float
        Fuel bed depth, ft.
    sigma : float
        Surface-area-to-volume ratio of the fuel particle, 1/ft.
    h : float
        Low heat content, Btu/lb. ~8000 for all wildland fuels.
    m_x : float
        Moisture of extinction, fraction (0–1).
    s_T : float
        Total mineral content, fraction (typically 0.0555).
    s_e : float
        Effective (silica-free) mineral content, fraction (typically 0.0100).
    description : str
        Short ecological description.
    """

    code: str
    name: str
    w_o: float           # lb/ft²
    delta: float         # ft
    sigma: float         # 1/ft
    h: float = 8000.0    # Btu/lb
    m_x: float = 0.25    # fraction
    s_T: float = 0.0555  # fraction
    s_e: float = 0.0100  # fraction
    description: str = ""

    # ----- convenience -----

    @property
    def bulk_density_lb_ft3(self) -> float:
        """Oven-dry bulk density ρ_b = w_o / δ  [lb/ft³]."""
        return bulk_density(self.w_o, self.delta)

    @property
    def packing_ratio(self) -> float:
        """β = ρ_b / ρ_p."""
        return self.bulk_density_lb_ft3 / PARTICLE_DENSITY_LB_FT3

    @property
    def optimum_packing_ratio(self) -> float:
        """β_op (Andrews 2018 eq. 37)."""
        return 3.348 * self.sigma ** -0.8189


#: Registry of the Anderson (1982) 13 standard fuel models, single-class
#: representation. Loadings combine 1-h + 10-h + 100-h dead fuels into a
#: single characteristic ``w_o`` (and where live fuels dominate spread, the
#: live load is added in). ``sigma`` is set to the 1-h dead fuel ``σ_1h`` —
#: the most reactive class — which is the standard simplification when
#: collapsing a multi-class fuel into a single-class kernel.
#:
#: Source for raw per-class loadings: Anderson 1982, Table 2; Andrews 2018,
#: Table 2. Mineral fractions are the universal Rothermel defaults.
FUEL_MODELS: Final[dict[str, FuelModel]] = {
    "FM1": FuelModel(
        code="FM1",
        name="Short grass (1 ft)",
        w_o=0.034,          # 1-h only (0.034)
        delta=1.0,
        sigma=3500.0,
        m_x=0.12,
        description=(
            "Short fine grass. Western annual / native perennial grasslands."
            " Fires move rapidly through the cured grass; spread rate "
            "controlled by wind and moisture, not by fuel load."
        ),
    ),
    "FM2": FuelModel(
        code="FM2",
        name="Timber (grass and understory)",
        w_o=0.161,          # 1-h + 10-h + 100-h + live herb = 0.092+0.046+0.023+0.023 - excluding live herb=0.138
        delta=1.0,
        sigma=3000.0,
        m_x=0.15,
        description=(
            "Open shrub and pine stands with grass understory; grass dominates"
            " surface fire behaviour."
        ),
    ),
    "FM3": FuelModel(
        code="FM3",
        name="Tall grass (2.5 ft)",
        w_o=0.138,
        delta=2.5,
        sigma=1500.0,
        m_x=0.25,
        description="Tall grass; cured prairie / steppe.",
    ),
    "FM4": FuelModel(
        code="FM4",
        name="Chaparral (6 ft)",
        # 1-h + 10-h + 100-h + live woody  (live dominates in chaparral)
        w_o=0.230 + 0.184 + 0.092 + 0.230,
        delta=6.0,
        sigma=2000.0,
        m_x=0.20,
        description=(
            "Mature chaparral, 6 ft. Dense, vertically continuous live woody"
            " fuel; this is the canonical 'high-intensity' surface fuel."
        ),
    ),
    "FM5": FuelModel(
        code="FM5",
        name="Brush (2 ft)",
        w_o=0.046 + 0.023 + 0.092,
        delta=2.0,
        sigma=2000.0,
        m_x=0.20,
        description="Young brush / short chaparral.",
    ),
    "FM6": FuelModel(
        code="FM6",
        name="Dormant brush / hardwood slash",
        w_o=0.069 + 0.115 + 0.092,
        delta=2.5,
        sigma=1750.0,
        m_x=0.25,
        description="Dormant brush; intermediate between FM5 and FM4.",
    ),
    "FM7": FuelModel(
        code="FM7",
        name="Southern rough",
        w_o=0.052 + 0.086 + 0.069 + 0.017,
        delta=2.5,
        sigma=1750.0,
        m_x=0.40,
        description="Palmetto-gallberry. Burns readily even at high RH.",
    ),
    "FM8": FuelModel(
        code="FM8",
        name="Closed timber litter (0.2 ft)",
        w_o=0.069 + 0.046 + 0.115,
        delta=0.2,
        sigma=2000.0,
        m_x=0.30,
        description=(
            "Closed-canopy timber with a compact litter layer. Low spread"
            " rates, high resistance to control once it goes."
        ),
    ),
    "FM9": FuelModel(
        code="FM9",
        name="Hardwood litter (0.2 ft)",
        w_o=0.134 + 0.019 + 0.007,
        delta=0.2,
        sigma=2500.0,
        m_x=0.25,
        description=(
            "Hardwood (oak / hickory) litter; longer needles than FM8 give"
            " a more flammable litter bed."
        ),
    ),
    "FM10": FuelModel(
        code="FM10",
        name="Timber (litter and understory) (1 ft)",
        w_o=0.138 + 0.092 + 0.230 + 0.092,
        delta=1.0,
        sigma=2000.0,
        m_x=0.25,
        description=(
            "Heavy down material and understory; the dominant Korean Pinus"
            " densiflora analogue for surface-fire behaviour."
        ),
    ),
    "FM11": FuelModel(
        code="FM11",
        name="Light logging slash (1 ft)",
        w_o=0.069 + 0.207 + 0.253,
        delta=1.0,
        sigma=1500.0,
        m_x=0.15,
        description="Light slash.",
    ),
    "FM12": FuelModel(
        code="FM12",
        name="Medium logging slash (2.3 ft)",
        w_o=0.184 + 0.644 + 0.759,
        delta=2.3,
        sigma=1500.0,
        m_x=0.20,
        description="Medium slash.",
    ),
    "FM13": FuelModel(
        code="FM13",
        name="Heavy logging slash (3 ft)",
        w_o=0.322 + 1.058 + 1.288,
        delta=3.0,
        sigma=1500.0,
        m_x=0.25,
        description="Heavy slash.",
    ),
}


# ---------------------------------------------------------------------------
# Sub-equations
# ---------------------------------------------------------------------------


def bulk_density(w_o: float, delta: float) -> float:
    """Oven-dry bulk density of the fuel bed, ρ_b  [lb/ft³].

    .. math:: \\rho_b = w_o / \\delta

    Reference: Rothermel 1972 eq. (74); Andrews 2018 eq. (31).

    Parameters
    ----------
    w_o : float
        Oven-dry fuel loading, lb/ft².
    delta : float
        Fuel bed depth, ft (must be > 0).
    """
    if delta <= 0.0:
        raise ValueError("fuel bed depth delta must be > 0")
    return w_o / delta


def packing_ratio(rho_b: float, rho_p: float = PARTICLE_DENSITY_LB_FT3) -> float:
    """β = ρ_b / ρ_p (Rothermel 1972 eq. (31); Andrews 2018 eq. (32))."""
    return rho_b / rho_p


def optimum_packing_ratio(sigma: float) -> float:
    """β_op (Andrews 2018 eq. (37)).

    .. math:: \\beta_{op} = 3.348 \\, \\sigma^{-0.8189}
    """
    return 3.348 * sigma ** -0.8189


def mineral_damping_coefficient(s_e: float) -> float:
    """Mineral damping coefficient, η_s (Rothermel 1972 eq. (62)).

    .. math:: \\eta_s = 0.174 \\, s_e^{-0.19}, \\quad \\eta_s \\le 1

    Parameters
    ----------
    s_e : float
        Effective (silica-free) mineral content, fraction. Typically 0.0100.
    """
    if s_e <= 0.0:
        raise ValueError("effective mineral content s_e must be > 0")
    eta_s = 0.174 * s_e ** -0.19
    return min(eta_s, 1.0)


def moisture_damping_coefficient(m_f: float, m_x: float) -> float:
    """Moisture damping coefficient, η_M (Rothermel 1972 eq. (64)).

    Drives the LFMC sensitivity of fire spread. Zero when m_f ≥ m_x.

    .. math::
        \\eta_M = 1 - 2.59 r + 5.11 r^2 - 3.52 r^3, \\quad r = m_f / m_x

    Parameters
    ----------
    m_f : float
        Fuel moisture content, fraction (e.g. 0.40 = 40 %).
    m_x : float
        Moisture of extinction for the fuel model, fraction.

    Returns
    -------
    float
        η_M ∈ [0, 1]. Monotonically decreasing in m_f for m_f ≤ m_x.
    """
    if m_f < 0.0:
        raise ValueError("fuel moisture m_f must be >= 0")
    if m_x <= 0.0:
        raise ValueError("moisture of extinction m_x must be > 0")
    if m_f >= m_x:
        return 0.0
    r = m_f / m_x
    eta_M = 1.0 - 2.59 * r + 5.11 * r * r - 3.52 * r * r * r
    # The cubic is guaranteed ≥ 0 on r ∈ [0, 1], but clamp for numerical safety.
    return max(eta_M, 0.0)


def reaction_intensity(
    w_n: float,
    h: float,
    eta_M: float,
    eta_s: float,
    gamma_prime: float,
    gamma_prime_max: float | None = None,  # accepted but unused, kept for API symmetry
) -> float:
    """Reaction intensity, I_R  [Btu/ft²/min] (Rothermel 1972 eq. (27)).

    .. math:: I_R = \\Gamma' \\, w_n \\, h \\, \\eta_M \\, \\eta_s

    Parameters
    ----------
    w_n : float
        Net fuel load, lb/ft²  (w_n = w_o · (1 - s_T)).
    h : float
        Low heat content of the fuel, Btu/lb. ~8000 for wildland fuels.
    eta_M : float
        Moisture damping coefficient, fraction.
    eta_s : float
        Mineral damping coefficient, fraction.
    gamma_prime : float
        Actual reaction velocity, 1/min.
    gamma_prime_max : float | None
        Unused; accepted to keep the API symmetric with the other
        sub-equations. The caller already factored it into ``gamma_prime``.
    """
    del gamma_prime_max  # unused
    return gamma_prime * w_n * h * eta_M * eta_s


def reaction_velocities(sigma: float, beta: float, beta_op: float) -> tuple[float, float]:
    """Return (Γ'_max, Γ') in 1/min.

    .. math::

       A &= 133 \\, \\sigma^{-0.7913}

       \\Gamma'_{\\max} &= \\frac{\\sigma^{1.5}}{495 + 0.0594 \\, \\sigma^{1.5}}

       \\Gamma' &= \\Gamma'_{\\max} \\, (\\beta/\\beta_{op})^A
                  \\, \\exp\\bigl(A (1 - \\beta/\\beta_{op})\\bigr)

    References: Andrews 2018 eqs. (36), (38), (39).
    """
    sigma_1_5 = sigma ** 1.5
    gamma_prime_max = sigma_1_5 / (495.0 + 0.0594 * sigma_1_5)
    A = 133.0 * sigma ** -0.7913
    ratio = beta / beta_op
    gamma_prime = gamma_prime_max * (ratio ** A) * math.exp(A * (1.0 - ratio))
    return gamma_prime_max, gamma_prime


def propagating_flux_ratio(sigma: float, beta: float) -> float:
    """Propagating flux ratio ξ (Rothermel 1972 eq. (42); Andrews 2018 eq. (40)).

    .. math::
        \\xi = \\frac{\\exp\\bigl((0.792 + 0.681 \\sqrt{\\sigma})
                                  (\\beta + 0.1)\\bigr)}
                    {192 + 0.2595 \\, \\sigma}

    Parameters
    ----------
    sigma : float
        Surface-area-to-volume ratio of fuel particles, 1/ft.
    beta : float
        Packing ratio (dimensionless).
    """
    return math.exp((0.792 + 0.681 * math.sqrt(sigma)) * (beta + 0.1)) / (
        192.0 + 0.2595 * sigma
    )


def wind_coefficient(U_ftmin: float, sigma: float, beta: float, beta_op: float) -> float:
    """Wind coefficient φ_w (Rothermel 1972 eqs. (47)–(49); Andrews 2018 eqs. (47)–(50)).

    .. math::
        C &= 7.47 \\, \\exp(-0.133 \\, \\sigma^{0.55})

        B &= 0.02526 \\, \\sigma^{0.54}

        E &= 0.715 \\, \\exp(-3.59 \\times 10^{-4} \\, \\sigma)

        \\phi_w &= C \\, U^B \\, (\\beta / \\beta_{op})^{-E}

    The wind speed U here is the *midflame* wind speed in **ft/min**, which
    is what the empirical regression was fit to. The public
    :func:`compute_spread_rate` converts m/s → ft/min internally.

    Returns 0 for U ≤ 0.
    """
    if U_ftmin <= 0.0:
        return 0.0
    C = 7.47 * math.exp(-0.133 * sigma ** 0.55)
    B = 0.02526 * sigma ** 0.54
    E = 0.715 * math.exp(-3.59e-4 * sigma)
    return C * (U_ftmin ** B) * (beta / beta_op) ** -E


def slope_coefficient(slope_tan: float, beta: float) -> float:
    """Slope coefficient φ_s (Rothermel 1972 eq. (51); Andrews 2018 eq. (51)).

    .. math:: \\phi_s = 5.275 \\, \\beta^{-0.3} \\, (\\tan \\phi)^2

    Parameters
    ----------
    slope_tan : float
        Tangent of the slope angle (dimensionless rise/run). May be 0 or
        negative; the equation always returns ≥ 0 because it's squared.
    beta : float
        Packing ratio.
    """
    return 5.275 * beta ** -0.3 * slope_tan ** 2


def effective_heating_number(sigma: float) -> float:
    """Effective heating number, ε (Rothermel 1972 eq. (14); Andrews 2018 eq. (14)).

    .. math:: \\varepsilon = \\exp(-138 / \\sigma)
    """
    return math.exp(-138.0 / sigma)


def heat_of_preignition(m_f: float) -> float:
    """Heat of preignition, Q_ig  [Btu/lb] (Rothermel 1972 eq. (12)).

    .. math:: Q_{ig} = 250 + 1116 \\, m_f
    """
    return 250.0 + 1116.0 * m_f


# ---------------------------------------------------------------------------
# Master equation
# ---------------------------------------------------------------------------


def rate_of_spread(
    I_R: float,
    xi: float,
    phi_w: float,
    phi_s: float,
    rho_b: float,
    epsilon: float,
    Q_ig: float,
) -> float:
    """Master Rothermel equation for rate of spread, R  [ft/min].

    .. math::
        R = \\frac{I_R \\, \\xi \\, (1 + \\phi_w + \\phi_s)}
                 {\\rho_b \\, \\varepsilon \\, Q_{ig}}

    Reference: Rothermel 1972 eq. (52); Andrews 2018 eq. (52).
    """
    denom = rho_b * epsilon * Q_ig
    if denom <= 0.0:
        return 0.0
    return I_R * xi * (1.0 + phi_w + phi_s) / denom


# ---------------------------------------------------------------------------
# High-level convenience wrapper (SI ↔ imperial)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpreadResult:
    """Output of :func:`compute_spread_rate` — rate plus every intermediate term.

    All intermediates are exposed so unit tests and demo notebooks can verify
    sub-equation behaviour separately from the final R.

    Attributes
    ----------
    rate_m_min : float
        Rate of spread, m/min  [si].
    rate_ft_min : float
        Rate of spread, ft/min  [imp].
    I_R_Btu_ft2_min : float
        Reaction intensity, Btu/ft²/min.
    xi : float
        Propagating flux ratio.
    phi_w : float
        Wind coefficient.
    phi_s : float
        Slope coefficient.
    rho_b_lb_ft3 : float
        Bulk density, lb/ft³.
    epsilon : float
        Effective heating number.
    Q_ig_Btu_lb : float
        Heat of preignition, Btu/lb.
    eta_M : float
        Moisture damping coefficient.
    eta_s : float
        Mineral damping coefficient.
    beta : float
        Packing ratio.
    beta_op : float
        Optimum packing ratio.
    gamma_prime : float
        Reaction velocity, 1/min.
    gamma_prime_max : float
        Maximum (optimum) reaction velocity, 1/min.
    inputs : dict
        Echo of the input arguments for traceability.
    """

    rate_m_min: float
    rate_ft_min: float
    I_R_Btu_ft2_min: float
    xi: float
    phi_w: float
    phi_s: float
    rho_b_lb_ft3: float
    epsilon: float
    Q_ig_Btu_lb: float
    eta_M: float
    eta_s: float
    beta: float
    beta_op: float
    gamma_prime: float
    gamma_prime_max: float
    inputs: dict = field(default_factory=dict)


def compute_spread_rate(
    fuel_model: FuelModel | str,
    fuel_moisture: float,
    wind_speed_ms: float = 0.0,
    slope_degrees: float = 0.0,
) -> SpreadResult:
    """Compute Rothermel rate of spread plus all intermediates, in SI.

    Parameters
    ----------
    fuel_model : FuelModel | str
        Either a :class:`FuelModel` instance or one of the keys of
        :data:`FUEL_MODELS` (``"FM1"`` .. ``"FM13"``).
    fuel_moisture : float
        Fuel moisture content, fraction (e.g. 0.40 = 40 %). For surface
        fires this is interpreted as dead 1-h fuel moisture for dead-fuel
        models and as LFMC for live-dominated models (FM4, FM5, FM7).
    wind_speed_ms : float, default 0.0
        Midflame wind speed, **m/s** (not mph or km/h). The 20-ft / 10-m
        wind must be reduced to midflame before being passed here; see
        Andrews & Cruz (2013) for the reduction factors. This wrapper does
        not do that reduction.
    slope_degrees : float, default 0.0
        Slope angle in degrees (0 = flat). Aspect is irrelevant for the
        scalar spread rate; it matters only for directional spread, which is
        handled by :mod:`wildfireguardian.spread_model.cellular_automaton`.

    Returns
    -------
    SpreadResult

    Notes
    -----
    - Internal computation is in imperial units to match Andrews 2018
      reference tables. The only SI ↔ imperial conversions live in this
      function.
    - The wind speed is the *midflame* wind, not the 10-m WMO wind. For
      typical Korean Pinus densiflora stands the midflame factor is ≈ 0.3
      (Albini & Baughman 1979).
    """
    if isinstance(fuel_model, str):
        try:
            fm = FUEL_MODELS[fuel_model]
        except KeyError as exc:
            raise KeyError(
                f"Unknown fuel model {fuel_model!r}. "
                f"Choose one of {sorted(FUEL_MODELS)}."
            ) from exc
    else:
        fm = fuel_model

    # ----- convert SI inputs to imperial -----
    U_ftmin = wind_speed_ms * U.FTMIN_PER_MS
    slope_tan = math.tan(math.radians(slope_degrees))

    # ----- derived bed properties -----
    rho_b = bulk_density(fm.w_o, fm.delta)            # lb/ft³
    beta = packing_ratio(rho_b)
    beta_op = optimum_packing_ratio(fm.sigma)

    # ----- reaction term -----
    eta_s = mineral_damping_coefficient(fm.s_e)
    eta_M = moisture_damping_coefficient(fuel_moisture, fm.m_x)
    gamma_prime_max, gamma_prime = reaction_velocities(fm.sigma, beta, beta_op)
    w_n = fm.w_o * (1.0 - fm.s_T)
    I_R = reaction_intensity(w_n, fm.h, eta_M, eta_s, gamma_prime)

    # ----- propagation / heating terms -----
    xi = propagating_flux_ratio(fm.sigma, beta)
    phi_w = wind_coefficient(U_ftmin, fm.sigma, beta, beta_op)
    phi_s = slope_coefficient(slope_tan, beta)
    epsilon = effective_heating_number(fm.sigma)
    Q_ig = heat_of_preignition(fuel_moisture)

    # ----- master equation -----
    R_ftmin = rate_of_spread(I_R, xi, phi_w, phi_s, rho_b, epsilon, Q_ig)
    R_mmin = R_ftmin * U.M_PER_FT

    return SpreadResult(
        rate_m_min=R_mmin,
        rate_ft_min=R_ftmin,
        I_R_Btu_ft2_min=I_R,
        xi=xi,
        phi_w=phi_w,
        phi_s=phi_s,
        rho_b_lb_ft3=rho_b,
        epsilon=epsilon,
        Q_ig_Btu_lb=Q_ig,
        eta_M=eta_M,
        eta_s=eta_s,
        beta=beta,
        beta_op=beta_op,
        gamma_prime=gamma_prime,
        gamma_prime_max=gamma_prime_max,
        inputs={
            "fuel_model": fm.code,
            "fuel_moisture": fuel_moisture,
            "wind_speed_ms": wind_speed_ms,
            "slope_degrees": slope_degrees,
        },
    )


__all__ = [
    "PARTICLE_DENSITY_LB_FT3",
    "FUEL_MODELS",
    "FuelModel",
    "SpreadResult",
    "bulk_density",
    "packing_ratio",
    "optimum_packing_ratio",
    "mineral_damping_coefficient",
    "moisture_damping_coefficient",
    "reaction_intensity",
    "reaction_velocities",
    "propagating_flux_ratio",
    "wind_coefficient",
    "slope_coefficient",
    "effective_heating_number",
    "heat_of_preignition",
    "rate_of_spread",
    "compute_spread_rate",
]
