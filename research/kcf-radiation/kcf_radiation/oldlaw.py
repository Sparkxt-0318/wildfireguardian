"""The old kcf-heat law (research/kcf-heat/kcf_heat/law.py, DERIVATION.md) expressed in this study's closure rule,
for comparison (b) only.

Old law: lead time T*(q*) = chi E_A / (2 pi q*) - t_r / 2 (independent of R), halo h = R_packet T*.
In closure.HeatClosure terms: every burning cell gets R = R_packet and d* = R_packet * T*(q*), so a piece in the cell
closes at A - T* and a piece within h of the cell closes at A - (h - delta)/R_packet. kcf-heat's own rule closes the
lateral pieces at A (not earlier); the difference is at most T* on pieces within h (<= 8 m at 10 kW/m2) of a burning
neighbour and is stated where counts are reported.
"""
from __future__ import annotations

import math

CHI = 0.30
E_A_KJ_M2 = 18608.0          # 10 kg/m2 x 0.1 x 18,608 kJ/kg
T_R_S = 11.52
R_PACKET_M_S = 341.0 / 3600.0


def lead_s(q_star: float) -> int:
    """Rounded up to a whole second, as kcf_heat.closure.HeatRule.lead_s."""
    return int(math.ceil(CHI * E_A_KJ_M2 / (2 * math.pi * q_star) - T_R_S / 2 - 1e-12))


def dstar_m(q_star: float) -> float:
    return R_PACKET_M_S * lead_s(q_star)
