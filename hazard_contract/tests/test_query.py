"""Query semantics: contact, support, horizon, flux and dose bounds on hand-worked cases."""
import numpy as np
import pytest

from hazard_contract import HazardMember, SegmentHazard
from hazard_contract.geometry import solid_angle_cap
from helpers import center, exact_flux_at, make_set

INF, NAN = np.inf, np.nan


def grid3(ig_center=0.0, ex_center=None, **kw):
    ig = np.full((3, 3), INF)
    ig[1, 1] = ig_center
    ex = np.full((3, 3), INF)
    ex[1, 1] = ig_center + 100.0 if ex_center is None else ex_center
    return make_set(ig, ex, **kw)


def test_member_implements_protocol():
    s = grid3()
    assert isinstance(s.member(0), HazardMember)


@pytest.mark.parametrize("t_in,t_out,expected", [
    (0.0, 10.0, True),      # burning during the interval
    (-50.0, 0.0, True),     # closed occupancy meets ignition instant
    (100.0, 120.0, False),  # extinguished exactly at 100: half-open burning interval
    (150.0, 200.0, False),  # burned out
    (-80.0, -10.0, False),  # not yet ignited
])
def test_contact_interval_conventions(t_in, t_out, expected):
    s = grid3()
    hz = s.member(0).segment(center(s, 1, 1), t_in, t_out)
    assert hz.contact is expected and hz.supported


def test_closed_cells_touching_a_boundary_counts():
    s = grid3()
    edge_point = np.array([100.0, 150.0])     # on the shared edge of cells (1,0) and (1,1)
    assert s.member(0).segment(edge_point, 0.0, 1.0).contact is True
    seg = np.array([[50.0, 50.0], [100.0, 100.0]])  # ends exactly at the corner of (1,1)
    assert s.member(0).segment(seg, 0.0, 1.0).contact is True
    near = np.array([[50.0, 50.0], [99.0, 99.0]])
    assert s.member(0).segment(near, 0.0, 1.0).contact is False


def test_unknown_cells_are_never_safe():
    ig = np.full((3, 3), INF)
    ig[1, 1] = NAN
    s = make_set(ig)
    hz = s.member(0).segment(center(s, 1, 1), 0.0, 10.0)
    assert hz.contact is None and hz.supported is False
    # a geometry crossing both an unknown and a burning cell: contact is certain, support is not
    ig[1, 2] = 0.0
    s = make_set(ig)
    seg = np.vstack([center(s, 1, 1), center(s, 1, 2)])
    hz = s.member(0).segment(seg, 0.0, 10.0)
    assert hz.contact is True and hz.supported is False


def test_unknown_cell_nearby_raises_upper_bound_only():
    ig = np.full((5, 5), INF)
    known = make_set(ig)
    ig2 = ig.copy()
    ig2[2, 3] = NAN
    unk = make_set(ig2)
    p = center(known, 2, 1)
    a, b = known.member(0).segment(p, 0, 50), unk.member(0).segment(p, 0, 50)
    assert a.flux_upper == 0.0 and b.flux_upper > 0.0
    assert b.flux_lower == 0.0 and b.supported  # unknown cell not touched: query still supported


def test_outside_grid_and_beyond_horizon_are_unsupported():
    s = grid3(horizon=500.0)
    out = s.member(0).segment(np.array([[150.0, 150.0], [450.0, 150.0]]), 0.0, 10.0)
    assert out.supported is False and out.contact is True and out.flux_upper == INF
    far = s.member(0).segment(np.array([[150.0, 50.0]]), 400.0, 600.0)
    assert far.supported is False and far.contact is None and far.flux_upper == INF and far.dose_upper == INF
    edge = s.member(0).segment(np.array([[0.0, 150.0]]), 400.0, 450.0)   # on the grid's outer edge
    assert edge.supported is False


def test_single_cell_flux_matches_sheet_law():
    s = make_set(np.array([[INF, INF, INF], [INF, 0.0, INF], [INF, INF, INF]]), cell=375.0, burn=3970.4642815249267)
    q = s.meta.heat_source.emission_kw_m2(s.meta.heat_source.burn_duration_s)
    assert q == pytest.approx(1.405981669694301, rel=1e-12)
    own = s.member(0).segment(center(s, 1, 1), 10.0, 20.0)
    assert own.flux_lower == pytest.approx(0.6861181, rel=1e-6)            # wfg_latest: 0.686 kW/m^2
    assert own.flux_upper == pytest.approx(q * solid_angle_cap(375, 375, 5) / (4 * np.pi), rel=1e-8)
    nb = s.member(0).segment(center(s, 1, 2), 10.0, 20.0)
    assert nb.flux_lower == pytest.approx(0.0021478, rel=1e-4)              # wfg_latest: 0.00215 kW/m^2
    assert nb.flux_lower <= nb.flux_upper < 0.01
    assert own.dose_lower == pytest.approx(10 * own.flux_lower, rel=1e-12)


def test_stationary_dose_tracks_burning_time():
    s = grid3(ig_center=0.0, ex_center=100.0)
    p = center(s, 1, 0)
    half = s.member(0).segment(p, 50.0, 150.0)      # burning only during [50, 100)
    full = s.member(0).segment(p, 0.0, 100.0)
    assert half.dose_upper == pytest.approx(full.dose_upper / 2, rel=1e-9)
    assert half.dose_lower == pytest.approx(full.dose_lower / 2, rel=1e-9)
    after = s.member(0).segment(p, 100.0, 150.0)
    assert after.flux_lower == 0.0 and after.dose_upper == 0.0


def test_flux_upper_never_exceeds_half_the_emission():
    s = make_set(np.zeros((6, 6)), cell=375.0, burn=3970.4642815249267)   # everything burning
    q = s.meta.heat_source.emission_kw_m2(3970.4642815249267)
    hz = s.member(0).segment(np.array([[100.0, 100.0], [2000.0, 2100.0]]), 0.0, 60.0)
    assert hz.flux_upper <= 0.5 * q * (1 + 1e-8)
    assert hz.dose_upper <= 60 * 0.5 * q * (1 + 1e-8)


def test_bounds_bracket_direct_evaluation_along_uniform_motion():
    rng = np.random.default_rng(3)
    ig = rng.uniform(-200, 600, size=(2, 8, 8))
    ig[rng.random((2, 8, 8)) < 0.4] = INF
    s = make_set(ig, burn=150.0, horizon=2000.0)
    for _ in range(25):
        p, q = rng.uniform(80, 720, size=(2, 2))
        a = float(rng.uniform(0, 400))
        b = a + float(rng.uniform(1, 300))
        hz = s.query(np.vstack([p, q]), a, b)
        for k in range(2):
            ts = np.linspace(a, b, 601)
            pts = p[None, :] + (ts - a)[:, None] / (b - a) * (q - p)[None, :]
            vals = np.array([exact_flux_at(s, k, x, t) for x, t in zip(pts, ts)])
            assert vals.max() <= hz[k].flux_upper * (1 + 1e-9) + 1e-12
            dose = np.trapz(vals, ts)
            assert hz[k].dose_lower <= dose * 1.02 + 1e-9
            assert dose <= hz[k].dose_upper * 1.02 + 1e-9


def test_query_uniform_refines_contact_with_router_occupancy():
    ig = np.full((1, 3), INF)
    ig[0, 0] = 15.0                          # left cell ignites at 15 s
    s = make_set(ig, burn=1000.0)
    seg = np.array([[50.0, 50.0], [250.0, 50.0]])     # left cell during [0, 5], ends in the right cell at 20
    assert s.member(0).segment(seg, 0.0, 20.0).contact is True               # whole interval: conservative
    assert s.member(0).segment_uniform(seg, 0.0, 20.0).contact is False      # uniform motion: left at t<=5
    ig[0, 2] = 18.0
    s2 = make_set(ig, burn=1000.0)
    assert s2.member(0).segment_uniform(seg, 0.0, 20.0).contact is True     # right cell burning on arrival


def test_segment_hazard_rejects_inconsistent_values():
    with pytest.raises(ValueError):
        SegmentHazard(contact=False, flux_lower=0, flux_upper=1, supported=False)
    with pytest.raises(ValueError):
        SegmentHazard(contact=None, flux_lower=2, flux_upper=1, supported=False)
    with pytest.raises(ValueError):
        SegmentHazard(contact=None, flux_lower=0, flux_upper=NAN, supported=False)


def test_query_rejects_bad_intervals():
    s = grid3()
    with pytest.raises(ValueError):
        s.query(center(s, 1, 1), 10.0, 5.0)
    with pytest.raises(ValueError):
        s.query(center(s, 1, 1), 0.0, INF)
