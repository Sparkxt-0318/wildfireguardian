"""F-DYN ignition schedule: per-cell ignition times from an arrival-time field (observed kriged reconstruction) over a
multi-hour horizon, on the full event grid, for the packet writer's ``bridge.draw_ignitions`` injection point.

SCENARIO, NOT WHAT HAPPENED. The field (Choi, Seo & Cha 2026, Zenodo 10.5281/zenodo.21788344, CC-BY-4.0) is a
retrospective kriging reconstruction inside the final perimeter, with ~17 h kriging sd; it is used as a realistic
dynamic fire for testing routing, not as a record of when fire reached any place.

Rules (echoed in the packet metadata):
* Start = a recorded input time of the region (so present fire, clock and contract binding come from the recorded,
  hash-bound c651 export, which is exactly this field thresholded at the start; verified in tests).
* A cell with arrival a (hours since t0) and start h ignites in member k at
      t_k = floor_Q( s_k * (a - h) * 3600 - shift_k )      clamped to >= 0
  when 0 < a - h (not burning or burned at the start) and t_k < horizon; otherwise it does not ignite in the horizon.
  floor_Q rounds DOWN to a multiple of Q seconds (earlier = conservative). Members are deterministic variants, never
  later than the reconstruction:
      m0 central (s=1, shift=0); m1 1.33x faster (s=0.75); m2 2x faster (s=0.5); m3 1 h earlier (s=1, shift=3600 s).
* Cells outside the reconstruction (NaN arrival: outside the final perimeter) never ignite: the reconstruction says the
  fire did not burn there. This is a property of the observed event, not an assumption of zero hazard elsewhere.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

FDYN_VERSION = 'wfg.fdyn.arrival-field-ignitions/1'
LABEL = 'SCENARIO from a retrospective arrival-time reconstruction; not what happened; not a forecast'
MEMBERS = [
    {'name': 'central', 'speed_factor': 1.0, 'shift_s': 0.0},
    {'name': 'faster_1.33x', 'speed_factor': 0.75, 'shift_s': 0.0},
    {'name': 'faster_2x', 'speed_factor': 0.5, 'shift_s': 0.0},
    {'name': 'earlier_1h', 'speed_factor': 1.0, 'shift_s': 3600.0},
]
DEFAULT_QUANTUM_S = 300.0


def schedule(arrival_h: np.ndarray, start_h: float, horizon_s: float, quantum_s: float = DEFAULT_QUANTUM_S,
             members=MEMBERS) -> np.ndarray:
    """Return ignition times [S, H, W] in seconds from the start (inf = no ignition within the horizon)."""
    a = np.asarray(arrival_h, float)
    rel = (a - start_h) * 3600.0
    future = np.isfinite(a) & (rel > 0)
    out = np.full((len(members),) + a.shape, np.inf)
    for k, m in enumerate(members):
        t = m['speed_factor'] * rel - m['shift_s']
        t = np.floor(np.maximum(t, 0.0) / quantum_s) * quantum_s
        ok = future & (t < horizon_s)
        out[k][ok] = t[ok]
    return out


def digest(times: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(times, dtype='<f8').tobytes()).hexdigest()


def plan(arrival_h, sd_h, *, start_h: float, start_utc: str, horizon_s: float, quantum_s: float, source: dict,
         region: str, window: dict) -> dict:
    times = schedule(arrival_h, start_h, horizon_s, quantum_s)
    r0, r1, c0, c1 = window['r0'], window['r1'], window['c0'], window['c1']
    inwin = np.zeros(arrival_h.shape, bool)
    inwin[r0:r1 + 1, c0:c1 + 1] = True
    fin = np.isfinite(times)
    sd_ign = sd_h[np.isfinite(times[0]) & inwin]
    meta = {
        'fdyn_version': FDYN_VERSION, 'label': LABEL, 'region': region, 'start_utc': start_utc,
        'start_hours_since_t0': start_h, 'horizon_s': horizon_s, 'quantum_s': quantum_s,
        'members': MEMBERS, 'source': source,
        'rule': ('t_k = floor_Q(s_k*(a-h)*3600 - shift_k) clamped at 0, for cells with a > h and t_k < horizon; '
                 'NaN arrival (outside final perimeter) never ignites'),
        'ignitions_full_grid': [int(fin[k].sum()) for k in range(len(MEMBERS))],
        'ignitions_in_window': [int((fin[k] & inwin).sum()) for k in range(len(MEMBERS))],
        'distinct_ignition_times_in_window': [int(np.unique(times[k][fin[k] & inwin]).size) for k in range(len(MEMBERS))],
        'kriging_sd_h_at_central_ignitions_in_window': (
            {'min': float(sd_ign.min()), 'median': float(np.median(sd_ign)), 'max': float(sd_ign.max())}
            if sd_ign.size else None),
        'sd_note': ('The kriging sd (median ~17 h) exceeds the 5-8 h horizon, so absolute arrival times are uncertain '
                    'by more than the horizon; members vary spread speed and offset (never later than the '
                    'reconstruction) and are NOT sd quantiles or a probability model.'),
        'ignition_times_sha256': digest(times),
    }
    meta['plan_sha256'] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    return {'meta': meta, 'times': times}
