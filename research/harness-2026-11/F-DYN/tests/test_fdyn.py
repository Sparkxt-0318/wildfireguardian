import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fdyn import ignitions  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
DATA = Path(__file__).resolve().parents[1] / '_data'
EXPORTS = REPO / 'data' / 'routing' / 'latest_inputs_try02' / 'exports' / 'KFS_01'
STARTS = ['20250323T010000Z', '20250324T090000Z', '20250325T170000Z', '20250325T190000Z', '20250325T230000Z',
          '20250326T080000Z']


def test_schedule_rules():
    a = np.array([[np.nan, 9.0, 10.0, 10.5, 11.0, 16.0]])
    t = ignitions.schedule(a, start_h=10.0, horizon_s=5 * 3600, quantum_s=300, members=ignitions.MEMBER_SETS['all4'])
    # NaN, burned (9.0) and exactly-at-start (10.0) never ignite
    assert np.all(np.isinf(t[:, 0, :3]))
    assert t[0, 0, 3] == 1800 and t[0, 0, 4] == 3600 and np.isinf(t[0, 0, 5])     # central; 6 h > horizon
    assert t[1, 0, 3] == 1200 and t[1, 0, 4] == 2700                           # 0.75x: 1350 -> 1200, 2700
    assert t[2, 0, 3] == 900 and t[2, 0, 5] == 10800                            # 2x faster brings 6 h to 3 h
    # 1 h earlier: 1800-3600 and 3600-3600 clamp to 0; 6 h - 1 h = 18000 s is not < horizon -> no ignition
    assert t[3, 0, 3] == 0 and t[3, 0, 4] == 0 and np.isinf(t[3, 0, 5])


def test_members_never_later_than_central_and_quantized():
    rng = np.random.default_rng(0)
    a = rng.uniform(0, 30, (40, 40))
    t = ignitions.schedule(a, start_h=10.0, horizon_s=8 * 3600, quantum_s=300, members=ignitions.MEMBER_SETS['all4'])
    c = t[0]
    for k in range(1, 4):
        both = np.isfinite(c)
        assert np.all(np.isfinite(t[k][both]))          # ignites whenever central ignites
        assert np.all(t[k][both] <= c[both])            # never later
    fin = t[np.isfinite(t)]
    assert np.all(fin % 300 == 0) and fin.min() >= 0 and fin.max() < 8 * 3600


@pytest.mark.skipif(not (DATA / 'KFS_01_pswt_ok_toa.tif').exists() or not EXPORTS.exists(),
                    reason='needs Daniel KFS_01 TOA (daniel/data-fetch) and data/routing')
@pytest.mark.parametrize('start', STARTS)
def test_recorded_export_is_the_field_thresholded(start):
    """The recorded c651 export's present fire / burned state equal the arrival field thresholded at the start, so
    F-DYN ignitions (a > h) continue the same reconstruction and never touch present or burned cells."""
    import rasterio
    with rasterio.open(DATA / 'KFS_01_pswt_ok_toa.tif') as s:
        toa = s.read(1).astype(float)
        t0 = dt.datetime.fromisoformat(s.tags()['t0_utc']).replace(tzinfo=dt.timezone.utc)
    z = np.load(EXPORTS / f'FORECAST_{start}.npz')
    h = (dt.datetime.strptime(start, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc) - t0).total_seconds() / 3600
    T = float(z['contract__cell_duration_s']) / 3600
    burned = np.isfinite(toa) & (toa <= h)
    assert np.array_equal(z['source_burned_area_valid'], np.isfinite(toa))
    assert np.array_equal(z['source_burned_area_valid'] & (z['source_burned_area'] == 1), burned)
    assert np.array_equal(z['heat__initial_active_burning_probability'] > 0, burned & (toa > h - T))
    t = ignitions.schedule(toa, h, 8 * 3600)
    assert not np.isfinite(t[:, burned]).any()


def test_catch_up_cells_moved_before_start():
    # variant arrival before the start for a cell the export has unburned: still burning -> ignite at 0; burned out -> no
    a = np.array([[9.5, 8.0, 9.9, 10.5]])
    burned = np.array([[False, False, True, False]])
    t = ignitions.schedule(a, start_h=10.0, horizon_s=3600 * 5, quantum_s=300, burned_at_start=burned,
                           burn_duration_s=3970.0)
    assert t[0, 0, 0] == 0.0                      # 0.5 h before start < T: still burning
    assert np.isinf(t[0, 0, 1])                   # 2 h before start > T: burned out
    assert np.isinf(t[0, 0, 2])                   # export already burned: kept as recorded, never re-ignited
    assert t[0, 0, 3] == 1800.0


def test_dilation_isotropic():
    from fdyn.variants import dilate
    a = np.full((7, 7), np.nan)
    a[3, 3] = 10.0
    d = dilate(a, 375.0, 600.0)
    assert d[3, 3] == 10.0
    assert d[2, 3] == d[3, 4] == pytest.approx(10.0 + 600 / 3600)
    assert np.isnan(d[2, 2])                      # diagonal centre distance 530 m > 375 m
    d2 = dilate(a, 750.0, 0.0)
    assert d2[2, 2] == 10.0 and d2[1, 3] == 10.0 and np.isnan(d2[1, 2])   # 838 m > 750 m


@pytest.mark.skipif(not (DATA / 'variants' / 'firms_constrained.npz').exists(), reason='needs variants.py output')
def test_firms_variants_never_later_than_kriged_and_ordered():
    import rasterio
    with rasterio.open(DATA / 'KFS_01_pswt_ok_toa.tif') as s:
        toa = s.read(1).astype(float)
    c = np.load(DATA / 'variants' / 'firms_constrained.npz')['arrival_h']
    e = np.load(DATA / 'variants' / 'firms_early.npz')['arrival_h']
    assert np.array_equal(np.isfinite(c), np.isfinite(toa)) and np.array_equal(np.isfinite(e), np.isfinite(toa))
    f = np.isfinite(toa)
    assert np.all(c[f] <= toa[f]) and np.all(e[f] <= c[f])


@pytest.mark.skipif(not (DATA / 'KFS_01_pswt_ok_toa.tif').exists() or not EXPORTS.exists(),
                    reason='needs Daniel KFS_01 TOA and data/routing')
@pytest.mark.parametrize('start', STARTS)
def test_synthetic_export_reproduces_recorded(start):
    """The SYNTHETIC present-fire generator, run at a recorded start, reproduces the recorded c651 export's burned,
    active and remaining fields (booleans exactly; remaining within 1e-9 s)."""
    from fdyn import build, synthetic_export
    toa = build.read_raster(DATA / 'KFS_01_pswt_ok_toa.tif').astype(np.float64)
    z = np.load(EXPORTS / f'FORECAST_{start}.npz')
    h = (dt.datetime.strptime(start, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc) - build.T0_UTC).total_seconds() / 3600
    s = synthetic_export.present_fire_arrays(toa, h, float(z['contract__cell_duration_s']))
    for k in ('source_burned_area_valid', 'source_burned_area', 'heat__initial_active_burning_probability',
              'heat__initial_burning_valid'):
        assert np.array_equal(s[k], z[k]), k
    np.testing.assert_allclose(s['heat__initial_remaining_burning_duration_s'],
                               z['heat__initial_remaining_burning_duration_s'], rtol=0, atol=1e-9)


def test_v31_boundary_exact():
    """v3.1: a minute-resolution arrival exactly on a 300 s boundary floors to that boundary, whatever the binary64
    representation error (Thomas's cell 8228: lo = 82.01666666666667, start 80.6 h -> 5100 s)."""
    start_h = (dt.datetime(2025, 3, 25, 11, 0) - dt.datetime(2025, 3, 22, 2, 24)).total_seconds() / 3600
    lo = np.array([[82.01666666666667, 80.6 + 4800 / 3600 - 1e-13, 80.6 + 4800 / 3600 + 1e-13]])
    t = ignitions.schedule(lo, start_h, 5 * 3600, 300)
    assert t[0, 0, 0] == 5100.0 and t[0, 0, 1] == 4800.0 and t[0, 0, 2] == 4800.0


def test_v31_envelope_end_covers_exact():
    """v3.1: envelope births = floor_Q(lo), hi_rel = floor_Q(hi), so hi_rel + T + Q >= hi + T exactly in integer ms."""
    rng = np.random.default_rng(0)
    start_h = 80.0
    lo = start_h + rng.uniform(0, 5, (20, 20))
    hi = lo + rng.uniform(0, 3, (20, 20))
    hi[0, 0] = lo[0, 0] = start_h + 5100 / 3600           # exact boundary
    b, e = ignitions.envelope_schedule(lo, hi, start_h, 8 * 3600, 300, np.zeros(lo.shape, bool), 3970)
    lo_ms, _ = ignitions.to_ms(lo)
    hi_ms, _ = ignitions.to_ms(hi)
    h_ms = ignitions.hour_ms(start_h)
    ok = np.isfinite(b[0])
    assert np.all(b[0][ok] * 1000 <= lo_ms[ok] - h_ms)
    assert np.all((e[0][ok] + 300) * 1000 >= hi_ms[ok] - h_ms)
    assert b[0, 0, 0] == 5100.0 and e[0, 0, 0] == 5100.0


def test_footprint_law_never_clears_a_burn_set_cell():
    """ENVELOPE_BURNSET_RULE.md (Iris/orchestrator condition): under envelope_burnset no burn-set cell, and no
    present-fire cell, is ever marked clear within the horizon - including cells the export lists as burned and present
    fire whose writer `remaining` falls inside the horizon. Uses the real burnset_members with a stub radiation model."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('pc', str(Path(__file__).resolve().parents[1] / 'fdyn' / '_packet_child.py'))
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)

    class _Pred:
        def __init__(self, a):
            self.incident_heat_flux_w_m2 = a * 1000.0

    class _Model:
        def predict_details(self, a):
            return _Pred(a)

    class _B:
        @staticmethod
        def radiation_model(*_a):
            return _Model()

    rng = np.random.default_rng(1)
    footprint = rng.random((20, 30)) < 0.4
    current = np.zeros_like(footprint); current[3, 4] = current[10, 11] = True          # present fire, maybe outside
    births = np.where(footprint & (rng.random(footprint.shape) < 0.7), 0.0, np.inf)     # export-burned cells skipped
    built = {'settings': {'horizon_s': 18000.0}, 'affine_transform': None, 'current': current,
             'remaining_s': 3000.0, 'events': births[None]}
    (m,) = pc.burnset_members(_B, np, built, 5179, footprint)
    assert m['breakpoints'] == [0.0, 18000.0]                                           # one interval, whole window
    assert m['flame'].shape[0] == 1 and np.array_equal(m['flame'][0], footprint | current)
    assert np.all(np.isinf(m['extinction_breakpoint_s']))                               # nothing ends in the horizon


def test_hazard_only_arrays_are_refused_by_contactmodel():
    """PACKET_CONSISTENCY_RULE.md B: a HAZARD-only packet's arrays carry NaN births, which the router-side
    ContactModel.from_arrays must reject loudly (it is only called here, never patched)."""
    sys.path.insert(0, str(REPO / 'experimental' / 'scenario-members' / 'src'))
    from wfg_scenario_members.contact import ContactModel
    ign = np.full((1, 3, 4), np.nan)
    cur = np.zeros((3, 4), bool)
    with pytest.raises(ValueError):
        ContactModel.from_arrays(ign, cur, 4270.0, 0.0)
    ok = np.full((1, 3, 4), np.inf); ok[0, 1, 1] = 0.0
    assert len(ContactModel.from_arrays(ok, cur, 18000.0, 0.0).cell_intervals) == 1


def test_repo_relative_radiation_identity():
    """IDENTITY_PATH_RULE.md (c): the injected identity is repo-relative with the vendored pin; outside-repo or
    unpinned modules are refused."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('fdyn_packet_child', Path(__file__).resolve().parents[1] / 'fdyn' / '_packet_child.py')
    child = importlib.util.module_from_spec(spec); spec.loader.exec_module(child)
    heat = child.WFG / 'radiation' / 'heat.py'
    pin = 'f52b4c31ba83d59c9a9b29e669c738e94d7de3b8bff723b1108ebcc11984acfb'
    got = child.repo_relative_radiation_identity({'module': str(heat), 'sha256': pin}, pin)
    assert got == {'module': 'integration/src/wfg_latest/radiation/heat.py', 'sha256': pin,
                   'module_path_form': 'repo-relative (F-DYN IDENTITY_PATH_RULE.md)'}
    with pytest.raises(SystemExit, match='RADIATION_MODULE_OUTSIDE_REPO'):
        child.repo_relative_radiation_identity({'module': '/usr/lib/heat.py', 'sha256': pin}, pin)
    with pytest.raises(SystemExit, match='RADIATION_MODULE_NOT_PINNED'):
        child.repo_relative_radiation_identity({'module': str(heat), 'sha256': '0' * 64}, '0' * 64)


def test_noreentry2_b0_born_at_0():
    """NOREENTRY2_RULE.md 1, 6.1, 6.2: C0 = export burned | arrival <= start (inclusive, integer ms); B0 = C0 minus
    present fire minus cells already born at 0; a later /1 birth of a B0 cell is replaced by 0."""
    from fdyn import build
    start_h = 10.0
    #             export-burned  present  arrival<=start(out)  arr==start  catch-up(born 0)  later birth  future  NaN
    arrival = np.array([[np.nan, 9.0, 2.0, 10.0, 9.9, 12.0, 11.0, np.nan]])
    export = np.array([[True, True, False, False, False, True, False, False]])
    present = np.array([[False, True, False, False, False, False, False, False]])
    times = np.array([[[np.inf, np.inf, np.inf, 0.0, 0.0, 7200.0, 3600.0, np.inf]]])
    p = {'times': times.copy(), 'meta': {'plan_sha256': 'x', 'ignition_times_sha256': 'y'}}
    added = build.add_b0(p, arrival, export, present, start_h)
    assert p['times'][0, 0].tolist() == [0.0, np.inf, 0.0, 0.0, 0.0, 0.0, 3600.0, np.inf]
    assert added == [{'export_burned_not_present': 2, 'variant_burned_out': 1, 'replaced_later_birth': 1, 'b0_total': 3}]
    m = p['meta']
    assert m['transform'] == 'no_reentry/2' and m['no_reentry2']['c0_cells'] == 6
    assert m['no_reentry2']['base_plan'] == {'plan_sha256': 'x', 'ignition_times_sha256': 'y'}
    assert m['ignition_times_sha256'] == ignitions.digest(p['times']) and m['plan_sha256'] != 'x'
