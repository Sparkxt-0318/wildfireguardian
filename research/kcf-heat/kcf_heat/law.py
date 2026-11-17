"""Closed-form heat laws compared in research/kcf-heat (see DERIVATION.md).

Units: kJ, kW, m, s. Flux in kW/m2, intensity in kW/m, energy per ground area in kJ/m2.

* ``frozen_cap``: supremum of the frozen wfg.hazard.construction/1 law (uniform horizontal isotropic
  source sheet of density chi*c*H/T seen by an upward receiver): chi*c*H/(2T).
* ``line_flux``: flaming zone of depth R*t_r collapsed to an isotropic line source of power chi*I per metre at
  the zone centroid; receiver faces the line, on the centreline, at distance s = d + R*t_r/2.
  Finite front of half-width a multiplies by a/sqrt(a^2+s^2).
* ``lead_time``: T*(q*) = chi*E_A/(2*pi*q*) - t_r/2 for a long front (independent of R); the finite-front
  version is solved numerically and does depend on R.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

TWO_PI = 2.0 * math.pi


@dataclass(frozen=True)
class Packet:
    """Frozen packet values (integration/src/wfg_latest/contract.py POLICY and bridge.py)."""
    chi: float = 0.30                    # radiative_fraction
    fuel_load_kg_m2: float = 10.0
    consumed_fraction: float = 0.1
    heat_kj_kg: float = 18608.0          # heat_of_combustion_j_kg / 1000
    residence_s: float = 11.52           # point_residence_s
    spread_m_s: float = 341.0 / 3600.0   # spread_rate_m_s
    cell_m: float = 375.0

    @property
    def consumed_kg_m2(self) -> float:
        return self.fuel_load_kg_m2 * self.consumed_fraction

    @property
    def energy_kj_m2(self) -> float:
        return self.consumed_kg_m2 * self.heat_kj_kg

    @property
    def cell_duration_s(self) -> float:
        """Documented scalar coarse-cell duration: point residence + front crossing of one cell."""
        return self.residence_s + self.cell_m / self.spread_m_s


PACKET = Packet()


def frozen_cap(chi: float, consumed_kg_m2: float, heat_kj_kg: float, duration_s: float) -> float:
    """Supremum (infinite sheet) of the frozen law, kW/m2: chi*c*H/(2T)."""
    _pos(duration_s, "duration_s")
    return chi * consumed_kg_m2 * heat_kj_kg / (2.0 * duration_s)


def byram_intensity(energy_kj_m2: float, spread_m_s: float) -> float:
    """I = E_A * R (kW/m)."""
    return energy_kj_m2 * spread_m_s


def finite_front_factor(half_width_m: float | None, s_m: float) -> float:
    """a/sqrt(a^2+s^2) for a receiver on the centreline of a straight front of half-width a; 1 for a=None (long front)."""
    if half_width_m is None or math.isinf(half_width_m):
        return 1.0
    _pos(half_width_m, "half_width_m")
    return half_width_m / math.hypot(half_width_m, s_m)


def line_flux_s(s_m: float, chi: float, intensity_kw_m: float, half_width_m: float | None = None) -> float:
    """Flux (kW/m2) at distance s from the line source (the flaming-zone centroid)."""
    _pos(s_m, "s_m")
    return chi * intensity_kw_m / (TWO_PI * s_m) * finite_front_factor(half_width_m, s_m)


def line_flux(d_m: float, chi: float, energy_kj_m2: float, spread_m_s: float, residence_s: float,
              half_width_m: float | None = None) -> float:
    """q(d) at distance d ahead of the leading edge (kW/m2)."""
    if d_m < 0:
        raise ValueError("d must be >= 0 (receiver ahead of the leading edge)")
    s = d_m + spread_m_s * residence_s / 2.0
    return line_flux_s(s, chi, byram_intensity(energy_kj_m2, spread_m_s), half_width_m)


def lead_time(q_star: float, chi: float, energy_kj_m2: float, residence_s: float) -> float:
    """T*(q*) for a long front, s; clipped at 0 (q* first reached at or after flame arrival)."""
    _pos(q_star, "q_star")
    return max(0.0, chi * energy_kj_m2 / (TWO_PI * q_star) - residence_s / 2.0)


def lead_time_finite(q_star: float, chi: float, energy_kj_m2: float, spread_m_s: float, residence_s: float,
                     half_width_m: float) -> float:
    """T*(q*) for a finite front of half-width a (bisection on the monotone q(R*tau)); <= the long-front value."""
    _pos(q_star, "q_star"); _pos(spread_m_s, "spread_m_s")
    f = lambda tau: line_flux(spread_m_s * tau, chi, energy_kj_m2, spread_m_s, residence_s, half_width_m) - q_star
    if f(0.0) <= 0:
        return 0.0
    lo, hi = 0.0, lead_time(q_star, chi, energy_kj_m2, residence_s) + 1.0
    while f(hi) > 0:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo


def halo_m(q_star: float, chi: float, energy_kj_m2: float, spread_m_s: float, residence_s: float) -> float:
    """Distance ahead of the leading edge at which the long-front flux equals q*: R*T*."""
    return spread_m_s * lead_time(q_star, chi, energy_kj_m2, residence_s)


def packet_lead_time(q_star: float, p: Packet = PACKET) -> float:
    return lead_time(q_star, p.chi, p.energy_kj_m2, p.residence_s)


def packet_halo_m(q_star: float, p: Packet = PACKET) -> float:
    return halo_m(q_star, p.chi, p.energy_kj_m2, p.spread_m_s, p.residence_s)


def packet_frozen_cap(p: Packet = PACKET) -> float:
    return frozen_cap(p.chi, p.consumed_kg_m2, p.heat_kj_kg, p.cell_duration_s)


def _pos(v, name):
    if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
        raise ValueError("%s must be finite and > 0, got %r" % (name, v))
