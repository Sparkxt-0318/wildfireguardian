"""Rothermel rate-of-spread engine — single-class and multi-class.

Two public entry points live here:

- :func:`compute_spread_rate` — accepts EITHER a Session 1 single-class
  :class:`FuelModel` OR a Session 2 :class:`MultiClassFuelModel` and
  dispatches to the appropriate algorithm. Returns a :class:`SpreadResult`
  with intermediates exposed.
- :func:`compute_multi_class_spread_rate` — explicit multi-class entry
  point. Use when you have per-particle moisture inputs (the
  high-level :func:`compute_spread_rate` accepts dead/live moisture pairs
  and forwards them).

The multi-class algorithm follows Andrews (2018) GTR-RMRS-371 §3:

1. Per-particle surface-area weights A_ij = σ_ij w_o_ij / ρ_p.
2. Within-category weights f_ij = A_ij / Σ_j A_ij  (Andrews 2018 eq. (54)).
3. Across-category weights f_i = A_i / A_T (eq. (55)).
4. Characteristic σ_T = Σ_i f_i Σ_j f_ij σ_ij (eq. (72)).
5. Bulk density ρ_b = (Σ w_o) / δ (eq. (31)).
6. Per-category w_n_i = Σ_j (1 - s_T_ij) w_o_ij (eq. (24) extended).
7. Per-category M_f, h, s_e via f_ij weighting (eq. (60)).
8. Live moisture of extinction: Burgan 1979 dynamic formula (eq. (26)).
9. Reaction intensity I_R = Γ'(σ_T,β,β_op) Σ_i w_n_i h_i η_M_i η_s_i  (eq. (58)).
10. Heat sink ρ_b Σ_i f_i Σ_j f_ij ε_ij Q_ig_ij (Andrews 2018 §3, modified
    form of eq. (52) denominator).
11. R = I_R ξ(σ_T,β) (1 + φ_w + φ_s) / heat_sink.

The single-class path is preserved from Session 1 for backwards
compatibility and for the demo_sensitivity figure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ...utils import units as U
from . import equations as eq
from .fuel_model import (
    FUEL_MODELS,
    FuelCategory,
    FuelClass,
    FuelModel,
    FuelModelRegistry,
    MultiClassFuelModel,
    REGISTRY,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpreadResult:
    """Output of :func:`compute_spread_rate`: R plus every intermediate.

    Attributes
    ----------
    rate_m_min, rate_ft_min : float
        Rate of spread in SI and imperial.
    I_R_Btu_ft2_min : float
        Reaction intensity, Btu/ft²/min.
    xi : float
        Propagating flux ratio.
    phi_w, phi_s : float
        Wind / slope coefficients (dimensionless).
    rho_b_lb_ft3 : float
        Bulk density.
    epsilon_Qig : float
        Heat sink ε·Q_ig (single-class) or its multi-class equivalent.
    eta_M_dead, eta_M_live : float
        Moisture damping per category (live is 0 for dead-only models).
    eta_s : float
        Mineral damping (effectively the same across categories with
        constant s_e, but stored as the characteristic value).
    beta, beta_op : float
        Packing ratios.
    sigma_T : float
        Characteristic SAV.
    gamma_prime, gamma_prime_max : float
        Reaction velocities.
    m_x_dead, m_x_live : float
        Moistures of extinction. m_x_live is computed dynamically via
        Burgan 1979 for multi-class models with live fuels.
    inputs : dict
        Echo of inputs for traceability.
    """

    rate_m_min: float
    rate_ft_min: float
    I_R_Btu_ft2_min: float
    xi: float
    phi_w: float
    phi_s: float
    rho_b_lb_ft3: float
    epsilon_Qig: float
    eta_M_dead: float
    eta_M_live: float
    eta_s: float
    beta: float
    beta_op: float
    sigma_T: float
    gamma_prime: float
    gamma_prime_max: float
    m_x_dead: float
    m_x_live: float
    inputs: dict = field(default_factory=dict)

    # ----- Session 1 compatibility shims -----
    # These properties present the v1 SpreadResult API so Session 1 callers
    # (notably tests/test_rothermel.py) continue to work unmodified.

    @property
    def eta_M(self) -> float:
        """Single characteristic moisture damping. Returns the dead-category
        value, which matches the Session 1 single-class semantics for dead-
        only fuels."""
        return self.eta_M_dead

    @property
    def Q_ig_Btu_lb(self) -> float:
        """Heat of preignition for the dead-fuel side, Btu/lb.
        Computed as ε·Q_ig / ε(σ_T) for back-compat — this is exact for
        single-class fuels and a SA-weighted characteristic for multi-class."""
        eps = eq.effective_heating_number(self.sigma_T)
        return self.epsilon_Qig / eps if eps > 0 else 0.0

    @property
    def epsilon(self) -> float:
        """Characteristic effective heating number ε(σ_T)."""
        return eq.effective_heating_number(self.sigma_T)


# ---------------------------------------------------------------------------
# Per-particle moisture inputs
# ---------------------------------------------------------------------------
#
# We accept moisture inputs in two equivalent ways:
# (a) two scalars `dead_moisture` and `live_moisture` (the common case),
#     in which case every dead-class particle gets `dead_moisture` and every
#     live-class particle gets `live_moisture`.
# (b) a `per_class_moisture: dict[FuelClassKind, float]` for explicit control.
# Both are accepted by `compute_multi_class_spread_rate`.


def _resolve_per_class_moisture(
    fm: MultiClassFuelModel,
    *,
    dead_moisture: float | None,
    live_moisture: float | None,
    per_class_moisture: dict | None,
) -> dict:
    if per_class_moisture is not None:
        return dict(per_class_moisture)
    if dead_moisture is None:
        raise ValueError("must provide either dead_moisture or per_class_moisture")
    out: dict = {}
    for p in fm.particles:
        if p.category is FuelCategory.DEAD:
            out[p.kind] = dead_moisture
        else:
            out[p.kind] = (
                live_moisture if live_moisture is not None else dead_moisture
            )
    return out


# ---------------------------------------------------------------------------
# Multi-class engine
# ---------------------------------------------------------------------------


def compute_multi_class_spread_rate(
    fuel_model: MultiClassFuelModel,
    *,
    dead_moisture: float | None = None,
    live_moisture: float | None = None,
    per_class_moisture: dict | None = None,
    wind_speed_ms: float = 0.0,
    slope_degrees: float = 0.0,
) -> SpreadResult:
    """Rothermel rate of spread for a multi-class fuel model.

    Parameters
    ----------
    fuel_model : MultiClassFuelModel
        The fuel model, e.g. ``ANDERSON_13["FM10"]`` or ``KOREAN_PINUS``.
    dead_moisture, live_moisture : float | None
        Moisture content (fraction, e.g. 0.06 for 6 %) applied uniformly to
        every dead- and live-class particle respectively. Live can be None,
        in which case live particles fall back to ``dead_moisture``.
    per_class_moisture : dict | None
        Explicit override mapping FuelClassKind → moisture fraction.
        If supplied, the scalar inputs are ignored. Use this for
        per-particle fuel-moisture inputs from NFDRS or similar.
    wind_speed_ms : float
        Midflame wind speed, m/s.
    slope_degrees : float
        Slope angle, degrees.

    Returns
    -------
    SpreadResult
        With ``rate_m_min`` the final SI rate of spread and every
        intermediate quantity exposed.

    Notes
    -----
    - All internal computation is in Rothermel imperial units. SI ↔
      imperial conversions are isolated to this function.
    - Per Andrews 2018, σ_T (characteristic SAV) drives wind, slope, ξ,
      ε, and the reaction-velocity terms. The per-category damping
      coefficients enter only via the reaction-intensity sum.
    """
    # ----- resolve per-particle moisture -----
    m_f_by_kind = _resolve_per_class_moisture(
        fuel_model,
        dead_moisture=dead_moisture,
        live_moisture=live_moisture,
        per_class_moisture=per_class_moisture,
    )

    # ----- per-particle A_ij and category groupings -----
    dead = list(fuel_model.dead_classes)
    live = list(fuel_model.live_classes)
    A_dead_list = [p.surface_area_per_ground_area for p in dead]
    A_live_list = [p.surface_area_per_ground_area for p in live]
    A_dead = sum(A_dead_list)
    A_live = sum(A_live_list)
    A_T = A_dead + A_live

    if A_T <= 0.0:
        return _zero_result(fuel_model, m_f_by_kind, wind_speed_ms, slope_degrees)

    # within-category weights f_ij
    f_dead_j = [a / A_dead if A_dead > 0 else 0.0 for a in A_dead_list]
    f_live_j = [a / A_live if A_live > 0 else 0.0 for a in A_live_list]

    # across-category weights f_i
    f_dead = A_dead / A_T
    f_live = A_live / A_T

    # ----- characteristic SAVs -----
    sigma_dead = sum(f_dead_j[i] * dead[i].sigma for i in range(len(dead))) if dead else 0.0
    sigma_live = sum(f_live_j[i] * live[i].sigma for i in range(len(live))) if live else 0.0
    sigma_T = f_dead * sigma_dead + f_live * sigma_live
    if sigma_T <= 0.0:
        return _zero_result(fuel_model, m_f_by_kind, wind_speed_ms, slope_degrees)

    # ----- bulk density and packing -----
    w_o_total = fuel_model.total_loading_lb_ft2
    rho_b = eq.bulk_density(w_o_total, fuel_model.delta)
    beta = eq.packing_ratio(rho_b)
    beta_op = eq.optimum_packing_ratio(sigma_T)

    # ----- net loadings per category (Andrews 2018 eq. 24 extended) -----
    w_n_dead = sum((1.0 - p.s_T) * p.w_o for p in dead)
    w_n_live = sum((1.0 - p.s_T) * p.w_o for p in live)

    # ----- characteristic moistures, mineral content, heat content per cat. -----
    m_f_dead_list = [m_f_by_kind[p.kind] for p in dead]
    m_f_live_list = [m_f_by_kind[p.kind] for p in live]

    M_f_dead = sum(f_dead_j[i] * m_f_dead_list[i] for i in range(len(dead))) if dead else 0.0
    M_f_live = sum(f_live_j[i] * m_f_live_list[i] for i in range(len(live))) if live else 0.0

    s_e_dead = (
        sum(f_dead_j[i] * dead[i].s_e for i in range(len(dead))) if dead else 0.01
    )
    s_e_live = (
        sum(f_live_j[i] * live[i].s_e for i in range(len(live))) if live else 0.01
    )

    h_dead = sum(f_dead_j[i] * dead[i].h for i in range(len(dead))) if dead else 8000.0
    h_live = sum(f_live_j[i] * live[i].h for i in range(len(live))) if live else 8000.0

    # ----- moisture of extinction -----
    m_x_dead = fuel_model.m_x_dead
    if live:
        m_x_live = eq.live_moisture_of_extinction_burgan1979(
            dead_loadings_w_o=tuple(p.w_o for p in dead),
            dead_savs=tuple(p.sigma for p in dead),
            dead_moistures=tuple(m_f_dead_list),
            live_loadings_w_o=tuple(p.w_o for p in live),
            live_savs=tuple(p.sigma for p in live),
            m_x_dead=m_x_dead,
        )
    else:
        m_x_live = m_x_dead  # irrelevant if no live fuel

    # ----- damping per category -----
    eta_s_dead = eq.mineral_damping_coefficient(max(s_e_dead, 1e-6))
    eta_M_dead = eq.moisture_damping_coefficient(M_f_dead, m_x_dead)

    if live:
        eta_s_live = eq.mineral_damping_coefficient(max(s_e_live, 1e-6))
        eta_M_live = eq.moisture_damping_coefficient(M_f_live, m_x_live)
    else:
        eta_s_live = 0.0
        eta_M_live = 0.0

    # ----- reaction velocity at σ_T -----
    gamma_prime_max, gamma_prime = eq.reaction_velocities(sigma_T, beta, beta_op)

    # ----- reaction intensity per Andrews 2018 §3 -----
    contributions = (
        (w_n_dead, h_dead, eta_M_dead, eta_s_dead),
        (w_n_live, h_live, eta_M_live, eta_s_live),
    )
    I_R = eq.reaction_intensity_multi_class(gamma_prime, contributions)

    # ----- propagating flux, wind, slope -----
    xi = eq.propagating_flux_ratio(sigma_T, beta)
    U_ftmin = wind_speed_ms * U.FTMIN_PER_MS
    phi_w = eq.wind_coefficient(U_ftmin, sigma_T, beta, beta_op)
    slope_tan = math.tan(math.radians(slope_degrees))
    phi_s = eq.slope_coefficient(slope_tan, beta)

    # ----- heat sink: ρ_b · Σ_i f_i · Σ_j f_ij · ε_ij · Q_ig_ij -----
    inner_dead = sum(
        f_dead_j[i]
        * eq.effective_heating_number(dead[i].sigma)
        * eq.heat_of_preignition(m_f_dead_list[i])
        for i in range(len(dead))
    ) if dead else 0.0
    inner_live = sum(
        f_live_j[i]
        * eq.effective_heating_number(live[i].sigma)
        * eq.heat_of_preignition(m_f_live_list[i])
        for i in range(len(live))
    ) if live else 0.0
    heat_sink_factor = f_dead * inner_dead + f_live * inner_live
    epsilon_Qig = heat_sink_factor   # ρ_b is applied inside rate_of_spread()

    # ----- master equation -----
    R_ftmin = eq.rate_of_spread(I_R, xi, phi_w, phi_s, rho_b, epsilon_Qig)
    R_mmin = R_ftmin * U.M_PER_FT

    return SpreadResult(
        rate_m_min=R_mmin,
        rate_ft_min=R_ftmin,
        I_R_Btu_ft2_min=I_R,
        xi=xi,
        phi_w=phi_w,
        phi_s=phi_s,
        rho_b_lb_ft3=rho_b,
        epsilon_Qig=epsilon_Qig,
        eta_M_dead=eta_M_dead,
        eta_M_live=eta_M_live,
        eta_s=eta_s_dead,  # report dead-category value; rarely differs
        beta=beta,
        beta_op=beta_op,
        sigma_T=sigma_T,
        gamma_prime=gamma_prime,
        gamma_prime_max=gamma_prime_max,
        m_x_dead=m_x_dead,
        m_x_live=m_x_live,
        inputs={
            "fuel_model": fuel_model.code,
            "fuel_model_kind": "multi-class",
            "dead_moisture": dead_moisture,
            "live_moisture": live_moisture,
            "wind_speed_ms": wind_speed_ms,
            "slope_degrees": slope_degrees,
        },
    )


def _zero_result(
    fuel_model: MultiClassFuelModel,
    m_f_by_kind: dict,
    wind_speed_ms: float,
    slope_degrees: float,
) -> SpreadResult:
    """Construct a SpreadResult with R=0 for degenerate inputs."""
    return SpreadResult(
        rate_m_min=0.0, rate_ft_min=0.0, I_R_Btu_ft2_min=0.0,
        xi=0.0, phi_w=0.0, phi_s=0.0, rho_b_lb_ft3=0.0, epsilon_Qig=0.0,
        eta_M_dead=0.0, eta_M_live=0.0, eta_s=0.0,
        beta=0.0, beta_op=0.0, sigma_T=1.0,
        gamma_prime=0.0, gamma_prime_max=0.0,
        m_x_dead=fuel_model.m_x_dead, m_x_live=fuel_model.m_x_dead,
        inputs={
            "fuel_model": fuel_model.code,
            "fuel_model_kind": "multi-class",
            "wind_speed_ms": wind_speed_ms,
            "slope_degrees": slope_degrees,
            "degenerate": True,
        },
    )


# ---------------------------------------------------------------------------
# Single-class engine (Session 1 algorithm, preserved for back-compat)
# ---------------------------------------------------------------------------


def compute_single_class_spread_rate(
    fuel_model: FuelModel,
    fuel_moisture: float,
    wind_speed_ms: float = 0.0,
    slope_degrees: float = 0.0,
) -> SpreadResult:
    """Single-class Rothermel — Session 1 algorithm, multi-class-shaped result.

    Wrapped in the multi-class :class:`SpreadResult` so calling code sees a
    consistent interface. The ``eta_M_live`` and ``m_x_live`` fields are
    inert.
    """
    # ----- imperial inputs -----
    U_ftmin = wind_speed_ms * U.FTMIN_PER_MS
    slope_tan = math.tan(math.radians(slope_degrees))

    # ----- bed properties -----
    rho_b = eq.bulk_density(fuel_model.w_o, fuel_model.delta)
    beta = eq.packing_ratio(rho_b)
    beta_op = eq.optimum_packing_ratio(fuel_model.sigma)

    # ----- reaction term -----
    eta_s = eq.mineral_damping_coefficient(fuel_model.s_e)
    eta_M = eq.moisture_damping_coefficient(fuel_moisture, fuel_model.m_x)
    gamma_prime_max, gamma_prime = eq.reaction_velocities(
        fuel_model.sigma, beta, beta_op,
    )
    w_n = fuel_model.w_o * (1.0 - fuel_model.s_T)
    I_R = eq.reaction_intensity_single_class(
        w_n, fuel_model.h, eta_M, eta_s, gamma_prime,
    )

    # ----- propagation / heating -----
    xi = eq.propagating_flux_ratio(fuel_model.sigma, beta)
    phi_w = eq.wind_coefficient(U_ftmin, fuel_model.sigma, beta, beta_op)
    phi_s = eq.slope_coefficient(slope_tan, beta)
    epsilon = eq.effective_heating_number(fuel_model.sigma)
    Q_ig = eq.heat_of_preignition(fuel_moisture)
    epsilon_Qig = epsilon * Q_ig

    R_ftmin = eq.rate_of_spread(I_R, xi, phi_w, phi_s, rho_b, epsilon_Qig)
    R_mmin = R_ftmin * U.M_PER_FT

    return SpreadResult(
        rate_m_min=R_mmin,
        rate_ft_min=R_ftmin,
        I_R_Btu_ft2_min=I_R,
        xi=xi,
        phi_w=phi_w,
        phi_s=phi_s,
        rho_b_lb_ft3=rho_b,
        epsilon_Qig=epsilon_Qig,
        eta_M_dead=eta_M,
        eta_M_live=0.0,
        eta_s=eta_s,
        beta=beta,
        beta_op=beta_op,
        sigma_T=fuel_model.sigma,
        gamma_prime=gamma_prime,
        gamma_prime_max=gamma_prime_max,
        m_x_dead=fuel_model.m_x,
        m_x_live=fuel_model.m_x,
        inputs={
            "fuel_model": fuel_model.code,
            "fuel_model_kind": "single-class",
            "fuel_moisture": fuel_moisture,
            "wind_speed_ms": wind_speed_ms,
            "slope_degrees": slope_degrees,
        },
    )


# ---------------------------------------------------------------------------
# Polymorphic dispatcher
# ---------------------------------------------------------------------------


def compute_spread_rate(
    fuel_model: FuelModel | MultiClassFuelModel | str,
    fuel_moisture: float | None = None,
    *,
    dead_moisture: float | None = None,
    live_moisture: float | None = None,
    per_class_moisture: dict | None = None,
    wind_speed_ms: float = 0.0,
    slope_degrees: float = 0.0,
    registry: FuelModelRegistry | None = None,
) -> SpreadResult:
    """Compute Rothermel rate of spread; dispatches single- vs multi-class.

    Backwards-compatible with Session 1:

    >>> compute_spread_rate("FM10", fuel_moisture=0.08, wind_speed_ms=2.0)
    SpreadResult(...)

    New multi-class form:

    >>> from .fuel_model import ANDERSON_13
    >>> compute_spread_rate(
    ...     ANDERSON_13["FM10"],
    ...     dead_moisture=0.06, live_moisture=1.00,
    ...     wind_speed_ms=2.0,
    ... )
    SpreadResult(...)

    Parameters
    ----------
    fuel_model : FuelModel | MultiClassFuelModel | str
        - String: resolves to legacy single-class entry via the registry.
          For multi-class, use ``ANDERSON_13[code]`` or
          ``registry.multi(code)`` explicitly.
        - :class:`FuelModel`: routes to the single-class algorithm.
        - :class:`MultiClassFuelModel`: routes to the multi-class algorithm.
    fuel_moisture : float | None
        Session 1 single-class moisture input. Required when
        ``fuel_model`` is a single-class entry. For multi-class entries,
        if neither ``dead_moisture`` nor ``per_class_moisture`` is set,
        this value is broadcast to all particles.
    dead_moisture, live_moisture : float | None
        Multi-class scalar moistures (preferred multi-class API).
    per_class_moisture : dict | None
        Multi-class per-particle override.
    wind_speed_ms, slope_degrees : float
        Midflame wind speed (m/s) and slope angle (degrees).
    registry : FuelModelRegistry | None
        Lookup for string codes. Defaults to the module-level
        :data:`REGISTRY`.
    """
    reg = registry or REGISTRY

    # ----- string lookup -----
    if isinstance(fuel_model, str):
        if reg.has_single(fuel_model):
            fm: FuelModel = reg.single(fuel_model)
            if fuel_moisture is None:
                if dead_moisture is None:
                    raise ValueError(
                        "fuel_moisture (or dead_moisture) required for "
                        f"single-class fuel model {fuel_model!r}"
                    )
                fuel_moisture = dead_moisture
            return compute_single_class_spread_rate(
                fm, fuel_moisture,
                wind_speed_ms=wind_speed_ms, slope_degrees=slope_degrees,
            )
        raise KeyError(
            f"Unknown fuel model {fuel_model!r}; "
            f"available single-class codes: {reg.single_codes}"
        )

    # ----- multi-class -----
    if isinstance(fuel_model, MultiClassFuelModel):
        if dead_moisture is None and fuel_moisture is not None:
            dead_moisture = fuel_moisture
        return compute_multi_class_spread_rate(
            fuel_model,
            dead_moisture=dead_moisture,
            live_moisture=live_moisture,
            per_class_moisture=per_class_moisture,
            wind_speed_ms=wind_speed_ms,
            slope_degrees=slope_degrees,
        )

    # ----- single-class -----
    if isinstance(fuel_model, FuelModel):
        if fuel_moisture is None:
            if dead_moisture is None:
                raise ValueError(
                    "fuel_moisture (or dead_moisture) required for single-class FuelModel"
                )
            fuel_moisture = dead_moisture
        return compute_single_class_spread_rate(
            fuel_model, fuel_moisture,
            wind_speed_ms=wind_speed_ms, slope_degrees=slope_degrees,
        )

    raise TypeError(f"Unknown fuel_model type: {type(fuel_model)}")


def rate_of_spread(
    I_R: float, xi: float, phi_w: float, phi_s: float,
    rho_b: float, epsilon: float, Q_ig: float,
) -> float:
    """Session 1 signature shim: ``rate_of_spread(I_R, ξ, φ_w, φ_s, ρ_b, ε, Q_ig)``.

    Kept identical to the Session 1 API so tests/test_rothermel.py continues
    to work. Internally factors ε·Q_ig and dispatches to the canonical
    :func:`equations.rate_of_spread`.
    """
    return eq.rate_of_spread(I_R, xi, phi_w, phi_s, rho_b, epsilon * Q_ig)


__all__ = [
    "SpreadResult",
    "compute_spread_rate",
    "compute_multi_class_spread_rate",
    "compute_single_class_spread_rate",
    "rate_of_spread",
]
