"""WIDENED_GRAPH_RULE.md §2.1: a padded copy of a recorded KFS_01 export for the widened road graph. Adds no fire.

Every 2-D array is padded by N cells on each side (N = 14 for the KFS_01 export grid + 5,250 m). Padding cells get:
  probability_valid = false, new_burn_probability = NaN      (no new-burn source; the writer's policy_assigned_zero)
  rate_valid = false, rate_per_h = NaN
  source_burned_area_valid = false, source_burned_area = 0  (not burned: bridge.py 173/179, WIDENED_GRAPH_RULE §8(i))
  heat__initial_burning_valid = false, heat__initial_active_burning_probability = 0, heat__initial_remaining_... = 0
Scalars (contract__*) are copied unchanged. The affine origin moves by N cells (x0 - N*res, y_top + N*res).
The record is copied with npz/npz_sha256 replaced and `fdyn_padding` added (original npz sha256, N, rule).
The output directory must not exist (written fresh); the source export is never modified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

FILL = {'new_burn_probability': np.nan, 'probability_valid': False, 'rate_per_h': np.nan, 'rate_valid': False,
        'source_burned_area': 0.0, 'source_burned_area_valid': False,
        'heat__initial_active_burning_probability': 0.0, 'heat__initial_remaining_burning_duration_s': 0.0,
        'heat__initial_burning_valid': False}
RULE = 'WIDENED_GRAPH_RULE.md §2.1'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pad2(a: np.ndarray, n: int, fill) -> np.ndarray:
    out = np.full((a.shape[0] + 2 * n, a.shape[1] + 2 * n), fill, dtype=a.dtype)
    out[n:n + a.shape[0], n:n + a.shape[1]] = a
    return out


def write(src_dir: Path, tag: str, n: int, out_dir: Path) -> Path:
    src_npz, src_rec = src_dir / f'FORECAST_{tag}.npz', src_dir / f'FORECAST_RECORD_{tag}.json'
    rec = json.loads(src_rec.read_text())
    if rec['npz_sha256'] != sha(src_npz):
        raise SystemExit('PAD_SOURCE_HASH_MISMATCH')
    out_dir.mkdir(parents=True, exist_ok=False)
    with np.load(src_npz, allow_pickle=False) as z:
        arrs = {k: z[k] for k in z.files}
    shape = arrs['new_burn_probability'].shape
    out = {}
    for k, v in arrs.items():
        if v.ndim == 2:
            if v.shape != shape or k not in FILL:
                raise SystemExit(f'PAD_UNKNOWN_2D_ARRAY {k} {v.shape}')
            out[k] = pad2(v, n, FILL[k])
        elif k == 'affine_transform':
            aff = v.astype(float).copy()
            if not (aff[1] == 0 and aff[3] == 0 and aff[0] > 0 and aff[4] < 0):
                raise SystemExit('PAD_AFFINE')
            aff[2] -= n * aff[0]
            aff[5] -= n * aff[4]          # aff[4] < 0: the top edge moves up (north) by n cells
            out[k] = aff
        else:
            out[k] = v
    npz = out_dir / f'FORECAST_{tag}.npz'
    np.savez(npz, **out)
    rec['npz'] = npz.name
    rec['npz_sha256'] = sha(npz)
    rec['fdyn_padding'] = {'rule': RULE, 'cells': n, 'original_npz_sha256': sha(src_npz),
                           'original_record_sha256': sha(src_rec), 'original_shape': list(shape),
                           'padded_shape': [shape[0] + 2 * n, shape[1] + 2 * n], 'fill': {k: str(v) for k, v in FILL.items()}}
    (out_dir / f'FORECAST_RECORD_{tag}.json').write_text(json.dumps(rec, indent=1))
    return out_dir


def pad_raster(a: np.ndarray | None, n: int, fill=np.nan):
    """Arrival / sd rasters: NaN (no arrival, never ignites) in padding; boolean masks: False."""
    if a is None:
        return None
    return pad2(a, n, False if a.dtype == bool else fill)
