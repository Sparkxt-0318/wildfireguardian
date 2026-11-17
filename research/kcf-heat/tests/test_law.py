"""Closed-form law: the derivation is checked by direct numerical integration, not by restating the formulas."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kcf_heat import law  # noqa: E402


def test_frozen_cap_packet_value():
    p = law.PACKET
    assert p.cell_duration_s == pytest.approx(3970.4643, abs=1e-3)
    assert law.packet_frozen_cap() == pytest.approx(0.3 * 18608 / (2 * 3970.4643), rel=1e-8)
    assert round(law.packet_frozen_cap(), 3) == 0.703


def test_sheet_flux_tends_to_half_the_areal_power():
    # isotropic emitters, areal power sigma, height h above an upward receiver: q -> sigma/2 as the sheet grows
    sigma, hgt = 1.0, 5.0
    for radius, lo in ((50.0, 0.40), (5000.0, 0.499)):
        r = np.linspace(0, radius, 400001)
        q = np.trapz(sigma / (4 * np.pi) * hgt / (r ** 2 + hgt ** 2) ** 1.5 * 2 * np.pi * r, r)
        assert lo < q <= sigma / 2


@pytest.mark.parametrize("a", [5.0, 29.5, 1e6])
@pytest.mark.parametrize("s", [2.0, 9.0, 36.0])
def test_line_law_matches_numerical_integral_of_point_sources(a, s):
    chi, intensity = 0.3, 4000.0
    ell = np.linspace(-a, a, 2_000_001) if a < 1e5 else np.concatenate([-np.logspace(6, -3, 1_000_000), np.logspace(-3, 6, 1_000_000)])
    ell = np.sort(ell)
    integrand = chi * intensity / (4 * np.pi * (s ** 2 + ell ** 2)) * s / np.sqrt(s ** 2 + ell ** 2)
    q_num = np.trapz(integrand, ell)
    assert law.line_flux_s(s, chi, intensity, None if a > 1e5 else a) == pytest.approx(q_num, rel=2e-4)


def test_packet_lead_times_and_halos():
    assert law.packet_lead_time(10) == pytest.approx(83.09, abs=0.01)
    assert law.packet_lead_time(5) == pytest.approx(171.93, abs=0.01)
    assert law.packet_lead_time(2.5) == pytest.approx(349.63, abs=0.01)
    assert [round(law.packet_lead_time(q) / 60, 1) for q in (10, 5, 2.5)] == [1.4, 2.9, 5.8]
    assert law.packet_halo_m(10) == pytest.approx(7.87, abs=0.01)


@pytest.mark.parametrize("R", [0.01, 0.0947, 1.33, 3.0])
def test_lead_time_is_independent_of_spread_rate(R):
    p = law.PACKET
    T = law.lead_time(10.0, p.chi, p.energy_kj_m2, p.residence_s)
    assert law.line_flux(R * T, p.chi, p.energy_kj_m2, R, p.residence_s) == pytest.approx(10.0, rel=1e-12)


@pytest.mark.parametrize("a", [10.0, 100.0, 1000.0])
def test_finite_front_lead_time_is_bounded_by_long_front(a):
    p = law.PACKET
    long_T = law.lead_time(2.5, p.chi, p.energy_kj_m2, p.residence_s)
    fin = law.lead_time_finite(2.5, p.chi, p.energy_kj_m2, p.spread_m_s, p.residence_s, a)
    assert 0 <= fin <= long_T
    assert law.line_flux(p.spread_m_s * fin, p.chi, p.energy_kj_m2, p.spread_m_s, p.residence_s, a) == pytest.approx(2.5, rel=1e-6)
    assert law.lead_time_finite(2.5, p.chi, p.energy_kj_m2, p.spread_m_s, p.residence_s, 1e9) == pytest.approx(long_T, rel=1e-6)


def test_lead_time_clips_at_zero_and_rejects_bad_input():
    assert law.lead_time(1e6, 0.3, 18608, 11.52) == 0.0
    with pytest.raises(ValueError):
        law.lead_time(0, 0.3, 18608, 11.52)
    with pytest.raises(ValueError):
        law.line_flux(-1, 0.3, 18608, 0.1, 11.52)
