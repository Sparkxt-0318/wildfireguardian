"""SYNTHETIC present-fire export for an F-DYN start that is not a recorded c651 input time.

Writes FORECAST_<tag>.npz + FORECAST_RECORD_<tag>.json in the contract layout, with present fire, burned state and
remaining burn time computed from the TOA raster at the start (the recorded exports are exactly this at the 6
recorded starts; test_synthetic_export_reproduces_recorded). It is NOT a c651 forecast:
  * new_burn_probability = 0 with probability_valid = False, rate_per_h = 0 with rate_valid = False (F-DYN injects
    ignitions; the probability is never used);
  * record.checkpoint_sha256 = "SYNTHETIC-fdyn-present-fire-from-TOA:<toa sha256>" and record.fdyn_synthetic = {...}.
F-DYN's packet child substitutes that marker for the contract's checkpoint constant, in its own process only, so the
binding accepts the record and the packet identity says SYNTHETIC.

    python3 research/harness-2026-11/F-DYN/fdyn/synthetic_export.py --toa TOA.tif --start 20250325T110000Z --out-dir DIR
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from fdyn import build  # noqa: E402

TEMPLATE_TAG = '20250325T230000Z'      # any recorded KFS_01 export: contract constants and record template
MARKER = 'SYNTHETIC-fdyn-present-fire-from-TOA:'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def present_fire_arrays(toa: np.ndarray, start_h: float, T: float) -> dict:
    """Burned / active / remaining exactly as the recorded exports encode them (hours since t0; T in seconds)."""
    valid = np.isfinite(toa)
    burned = valid & (toa <= start_h)
    active = burned & (toa > start_h - T / 3600.0)
    remaining = np.where(active, T - (start_h - toa) * 3600.0, 0.0)
    return {'source_burned_area_valid': valid, 'source_burned_area': burned.astype(np.float64),
            'heat__initial_active_burning_probability': active.astype(np.float64),
            'heat__initial_remaining_burning_duration_s': remaining.astype(np.float64),
            'heat__initial_burning_valid': np.ones(toa.shape, bool)}


def write(toa_path: Path, start_tag: str, out_dir: Path) -> tuple[Path, Path]:
    toa = build.read_raster(toa_path).astype(np.float64)
    toa_sha = sha(toa_path)
    start = dt.datetime.strptime(start_tag, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
    if start.minute or start.second:
        raise SystemExit('start must be a whole UTC hour (contract)')
    epoch = int(start.timestamp())
    start_h = (start - build.T0_UTC).total_seconds() / 3600.0
    tpl_dir = build.INPUTS / 'exports' / build.EVENT
    with np.load(tpl_dir / f'FORECAST_{TEMPLATE_TAG}.npz', allow_pickle=False) as z:
        tpl = {k: z[k].copy() for k in z.files}
    T = float(tpl['contract__cell_duration_s'])
    arrays = dict(tpl)
    arrays.update(present_fire_arrays(toa, start_h, T))
    shape = toa.shape
    arrays['new_burn_probability'] = np.zeros(shape)
    arrays['probability_valid'] = np.zeros(shape, bool)
    arrays['rate_per_h'] = np.zeros(shape)
    arrays['rate_valid'] = np.zeros(shape, bool)
    for k in ('contract__cutoff_epoch_s', 'contract__sample_time_epoch_s', 'contract__prediction_time_epoch_s'):
        arrays[k] = np.array(epoch, dtype=np.int64)
    out_dir.mkdir(parents=True, exist_ok=True)
    npz = out_dir / f'FORECAST_{start_tag}.npz'
    np.savez(npz, **arrays)
    rec = json.loads((tpl_dir / f'FORECAST_RECORD_{TEMPLATE_TAG}.json').read_text())
    keep = {k: rec[k] for k in ('schema', 'contract', 'event', 'epsg', 'policy', 'cell_burning_duration_s',
                                'heat_release_rate_density_w_m2', 'channel_names', 'contract_sha256')}
    iso = start.strftime('%Y-%m-%dT%H:00:00Z')
    out = copy.deepcopy(keep)
    out.update({
        'cutoff_utc': iso,
        'clock': {'cutoff_utc': iso, 'cutoff_epoch_s': epoch, 'sample_time_epoch_s': epoch,
                  'prediction_time_epoch_s': epoch, 'prediction_dt_hours': 1.0, 'offset_s': 0},
        'checkpoint_sha256': MARKER + toa_sha,
        'exporter_sha256': None,
        'npz': npz.name, 'npz_sha256': sha(npz),
        'fdyn_synthetic': {
            'label': 'SYNTHETIC present-fire export from the arrival-time raster; NOT a c651 forecast',
            'toa_sha256': toa_sha, 'start_hours_since_t0': start_h,
            'template_record': f'FORECAST_RECORD_{TEMPLATE_TAG}.json (contract constants and policy only)',
            'generator_sha256': sha(__file__),
            'fields': 'burned = toa <= h; active = burned & toa > h - T; remaining = T - (h - toa)*3600 on active; '
                      'probability/rate zero and invalid (unused: F-DYN injects ignitions)'},
    })
    recp = out_dir / f'FORECAST_RECORD_{start_tag}.json'
    recp.write_text(json.dumps(out, indent=1))
    return npz, recp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--toa', type=Path, required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    a = ap.parse_args()
    npz, recp = write(a.toa, a.start, a.out_dir)
    print(json.dumps({'npz': str(npz), 'npz_sha256': sha(npz), 'record': str(recp)}))


if __name__ == '__main__':
    main()
