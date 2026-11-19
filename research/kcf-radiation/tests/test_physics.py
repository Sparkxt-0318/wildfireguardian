"""Implementation checks of the published formulas (PROTOCOL.md section 8, tests T1-T8)."""
import math

import numpy as np
import pytest

from kcf_radiation import fire, radiation, ros, viewfactor as vf


def test_byram_and_thomas_constants():
    assert fire.flame_length_byram(1000.0) == pytest.approx(0.0775 * 1000 ** 0.46)
    assert fire.flame_length_thomas(1000.0) == pytest.approx(0.0266 * 1000 ** (2 / 3))
    # Byram 1959 reference points: 1 m at ~260 kW/m, 3.4 m at ~3,500 kW/m (FARSITE/BehavePlus tables)
    assert fire.flame_length_byram(259.0) == pytest.approx(1.0, rel=0.02)


def test_van_wagner_initiation():
    # CBH 5 m, FMC 100 %: I0 = (0.010*5*(460+2590))^1.5 = 152.5^1.5
    assert fire.van_wagner_initiation_intensity(5.0, 100.0) == pytest.approx(152.5 ** 1.5)
    assert fire.van_wagner_active_ros(0.15) == pytest.approx(20.0 / 60.0)


def test_cfb_limits():
    r0, ra = 0.05, 0.3
    assert fire.crown_fraction_burned(0.04, r0, ra) == 0.0
    assert fire.crown_fraction_burned(0.3, r0, ra) == 1.0
    # 90 % of the way from R_init to R_active gives CFB = 0.9 by construction
    assert fire.crown_fraction_burned(r0 + 0.9 * (ra - r0), r0, ra) == pytest.approx(0.9)


def test_ros_eikonal_plane_and_radial():
    # plane front at 0.5 m/s along x: t = x / R
    x = np.arange(20) * 375.0
    t = np.tile(x / 0.5, (10, 1))
    R, info = ros.rate_of_spread(t, 375.0, 1e-4, 10.0)
    assert np.allclose(R, 0.5)
    # radial front at 0.2 m/s from the centre
    n = 41
    yy, xx = np.mgrid[0:n, 0:n] * 375.0
    r = np.hypot(xx - 20 * 375.0, yy - 20 * 375.0)
    t = r / 0.2
    R, _ = ros.rate_of_spread(t, 375.0, 1e-4, 10.0)
    ring = (r > 3 * 375) & (r < 18 * 375)
    assert np.allclose(R[ring], 0.2, rtol=0.03)


def test_mcguire_equals_numeric_at_zero_tilt():
    for d, H, W, z in [(5, 2, 20, 0), (20, 10, 375, 1.5), (60, 20, 100, 5)]:
        assert vf.tilted_numeric(d, H, W, 0.0, z) == pytest.approx(vf.planar_mcguire(d, H, W, z), rel=1e-4)


def test_mcguire_corner_limits():
    # infinite rectangle seen from its corner normal gives 1/4
    assert vf._corner(1e7, 1e7, 1.0) == pytest.approx(0.25, rel=1e-4)


def test_cylinder_mudan_against_numeric():
    """Mudan's closed form against direct integration over the visible half of the cylinder."""
    X, D, H = 20.0, 10.0, 15.0
    R0 = D / 2
    n = 400
    phis = np.linspace(-math.pi, math.pi, n, endpoint=False) + math.pi / n
    zs = (np.arange(n) + 0.5) * H / n
    P, Z = np.meshgrid(phis, zs, indexing="ij")
    px, py = R0 * np.cos(P), R0 * np.sin(P)
    rx, ry, rz = X - px, -py, -Z
    r2 = rx ** 2 + ry ** 2 + rz ** 2
    c1 = (rx * np.cos(P) + ry * np.sin(P)) / np.sqrt(r2)
    c2 = rx / np.sqrt(r2)  # receiver faces -x toward the cylinder
    f = np.where((c1 > 0) & (c2 > 0), c1 * c2 / (math.pi * r2), 0.0)
    num = f.sum() * (R0 * 2 * math.pi / n) * (H / n)
    assert vf.cylinder_mudan(X, D, H) == pytest.approx(num, rel=0.01)


def test_flux_decreasing_and_safe_distance():
    fl = radiation.Flame(L=10.0, theta=math.radians(30), W=375.0)
    for kind in ("planar", "tilted", "tilted_max"):
        ds = [6.0, 10.0, 20.0, 40.0, 80.0]
        q = [radiation.flux(d, fl, T_flame_K=1200.0, vf_kind=kind) for d in ds]
        assert all(a > b for a, b in zip(q, q[1:])), kind
        d7 = radiation.safe_distance(7.0, fl, T_flame_K=1200.0, vf_kind=kind)
        assert radiation.flux(d7 + 0.05, fl, T_flame_K=1200.0, vf_kind=kind) <= 7.0 + 1e-9


def test_transmissivity_reference():
    # Pietersen and Huerta: Pw x = 2.02^(1/0.09)... check one value directly
    pw = 0.5 * radiation.saturation_vapour_pressure_pa(15.0)
    assert radiation.transmissivity_pietersen(50.0, 50.0, 15.0) == pytest.approx(min(1.0, 2.02 * (pw * 50.0) ** -0.09))
    assert radiation.transmissivity_pietersen(1.0, 50.0, 15.0) == 1.0
