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
    t = ignitions.schedule(a, start_h=10.0, horizon_s=5 * 3600, quantum_s=300)
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
    t = ignitions.schedule(a, start_h=10.0, horizon_s=8 * 3600, quantum_s=300)
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
