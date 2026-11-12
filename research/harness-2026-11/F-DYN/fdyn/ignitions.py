"""F-DYN ignition schedule (v2): per-cell ignition times from an arrival-time raster over a multi-hour horizon, on the
full event grid, for the packet writer's ``bridge.draw_ignitions`` injection point.

SCENARIO built from a reconstruction, not "the 2025 fire", not a forecast.

v2 rules (Iris / orchestrator decisions, 2026-11-12):
* The arrival raster is an explicit, swappable input (hours since t0 on the KFS_01 export grid) with a ``variant``
  label and SHA-256 recorded in the plan metadata: the kriged mean (Choi 2026), FIRMS detection brackets, dilations...
* Members: the base workload is the central member only; each speed/offset variant is its own single-member packet;
  one 4-member packet exercises the all-members code path.
* Quantization: ignition is floored to a multiple of Q (earlier start). Extinction must not be earlier than the exact
  ignition + T, so the packet's burning duration is widened to T + Q, and consumed_fraction is scaled by (T+Q)/T so
  the emitted flux density (energy per unit time) is unchanged (see _packet_child.py). Contact then covers
  [floor(t), floor(t) + T + Q) which contains [t, t + T): conservative for contact and radiation.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

FDYN_VERSION = 'wfg.fdyn.arrival-field-ignitions/2'
LABEL = 'SCENARIO built from an arrival-time reconstruction; not the 2025 fire; not a forecast'
MEMBER_RULES = {
    'central': {'speed_factor': 1.0, 'shift_s': 0.0},
    'faster_1.33x': {'speed_factor': 0.75, 'shift_s': 0.0},
    'faster_2x': {'speed_factor': 0.5, 'shift_s': 0.0},
    'earlier_1h': {'speed_factor': 1.0, 'shift_s': 3600.0},
}
MEMBER_SETS = {'central': ['central'], 'faster_1.33x': ['faster_1.33x'], 'faster_2x': ['faster_2x'],
               'earlier_1h': ['earlier_1h'], 'all4': ['central', 'faster_1.33x', 'faster_2x', 'earlier_1h']}
DEFAULT_QUANTUM_S = 300.0


def schedule(arrival_h: np.ndarray, start_h: float, horizon_s: float, quantum_s: float = DEFAULT_QUANTUM_S,
             members=('central',), burned_at_start=None, burn_duration_s: float | None = None) -> np.ndarray:
    """Ignition times [S, H, W] in seconds from the start (inf = no ignition within the horizon).

    ``burned_at_start`` (the recorded export's known-burned cells, present fire included) never ignite: the writer
    keeps them as recorded. A variant raster can place a cell's arrival before the start although the export has it
    unburned (e.g. a FIRMS detection earlier than the kriged mean); such a cell ignites at t = 0 if its variant arrival
    lies within one burn duration before the start (it would still be burning), otherwise it is taken as burned out."""
    a = np.asarray(arrival_h, float)
    rel = (a - start_h) * 3600.0
    burned = np.zeros(a.shape, bool) if burned_at_start is None else np.asarray(burned_at_start, bool)
    if burned_at_start is not None and burn_duration_s is None:
        raise ValueError('burn_duration_s required with burned_at_start')
    late_lo = -float(burn_duration_s) if burn_duration_s is not None else 0.0
    future = np.isfinite(a) & ~burned & (rel > late_lo)
    out = np.full((len(members),) + a.shape, np.inf)
    for k, name in enumerate(members):
        m = MEMBER_RULES[name]
        t = m['speed_factor'] * rel - m['shift_s']
        t = np.floor(np.maximum(t, 0.0) / quantum_s) * quantum_s
        ok = future & (t < horizon_s)
        out[k][ok] = t[ok]
    return out


def digest(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype='<f8').tobytes()).hexdigest()


def plan(arrival_h, sd_h, *, arrival_variant: str, arrival_source: dict, start_h: float, start_utc: str,
         horizon_s: float, quantum_s: float, member_set: str, region: str, window: dict | None,
         burned_at_start: np.ndarray, burn_duration_s: float, arrival_hi_h: np.ndarray | None = None) -> dict:
    hi_rel = None
    if arrival_hi_h is not None:
        if member_set != 'central':
            raise ValueError('the envelope is a single member')
        members = ['envelope']
        times, hi_rel = envelope_schedule(arrival_h, arrival_hi_h, start_h, horizon_s, quantum_s, burned_at_start,
                                          burn_duration_s)
    else:
        members = MEMBER_SETS[member_set]
        times = schedule(arrival_h, start_h, horizon_s, quantum_s, members, burned_at_start, burn_duration_s)
    a = np.asarray(arrival_h, float)
    rel = (a - start_h) * 3600.0
    catch_up = np.isfinite(a) & ~burned_at_start & (rel <= 0) & (rel > -burn_duration_s)
    burned_out = np.isfinite(a) & ~burned_at_start & (rel <= -burn_duration_s)
    inwin = np.ones(arrival_h.shape, bool)
    if window is not None:
        inwin[:] = False
        inwin[window['r0']:window['r1'] + 1, window['c0']:window['c1'] + 1] = True
    fin = np.isfinite(times)
    sd_ign = sd_h[np.isfinite(times[0]) & inwin] if sd_h is not None else np.array([])
    meta = {
        'fdyn_version': FDYN_VERSION, 'label': LABEL, 'region': region, 'start_utc': start_utc,
        'start_hours_since_t0': start_h, 'horizon_s': horizon_s, 'quantum_s': quantum_s,
        'member_set': 'envelope' if hi_rel is not None else member_set,
        'members': ([{'name': 'envelope', 'rule': 'burn [lo, hi + T): lo = arrival raster, hi = arrival_hi raster'}]
                    if hi_rel is not None else [{'name': n, **MEMBER_RULES[n]} for n in members]),
        'arrival_hi_raster_sha256': digest(arrival_hi_h) if arrival_hi_h is not None else None,
        'envelope_width_h_in_igniting_cells': (
            {'max': float(np.nanmax((arrival_hi_h - arrival_h)[np.isfinite(times[0])])),
             'cells_with_positive_width': int(np.sum((arrival_hi_h - arrival_h)[np.isfinite(times[0])] > 0))}
            if arrival_hi_h is not None and np.isfinite(times[0]).any() else None),
        'arrival_variant': arrival_variant, 'arrival_source': arrival_source,
        'arrival_raster_sha256': digest(arrival_h),
        'rule': ('t_k = floor_Q(s_k*(a-h)*3600 - shift_k) clamped at 0, for cells with a > h and t_k < horizon; '
                 'NaN arrival never ignites; packet burning duration T+Q with consumed_fraction*(T+Q)/T'),
        'ignitions_full_grid': [int(fin[k].sum()) for k in range(len(members))],
        'ignitions_in_domain': [int((fin[k] & inwin).sum()) for k in range(len(members))],
        'distinct_ignition_times_in_domain': [int(np.unique(times[k][fin[k] & inwin]).size)
                                              for k in range(len(members))],
        'kriging_sd_h_at_first_member_ignitions': (
            {'min': float(sd_ign.min()), 'median': float(np.median(sd_ign)), 'max': float(sd_ign.max())}
            if sd_ign.size else None),
        'sd_note': ('The kriging sd (median ~17 h) exceeds the 5-8 h horizon: absolute arrival times are not '
                    'identified. Members vary spread speed and offset (never later than the arrival raster) and '
                    'are NOT sd quantiles or a probability model.'),
        'ignition_times_sha256': digest(times),
        'variant_cells_before_start_not_in_export': {'ignite_at_0_still_burning': int(catch_up.sum()),
                                                     'taken_as_burned_out': int(burned_out.sum())},
    }
    meta['plan_sha256'] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    return {'meta': meta, 'times': times, 'hi_rel': hi_rel}


def envelope_schedule(lo_h: np.ndarray, hi_h: np.ndarray, start_h: float, horizon_s: float, quantum_s: float,
                      burned_at_start: np.ndarray, burn_duration_s: float):
    """Envelope member (F-9.3 interval source): a cell with arrival in [lo, hi] burns from lo until hi + T.

    Returns (births [1,H,W], hi_rel [1,H,W]) in seconds from the start: births = floor_Q(lo - h) clamped at 0 (inf = no
    ignition within the horizon); hi_rel = floor_Q(hi - h) clamped at 0, so the packet end hi_rel + T + Q >= exact hi + T.
    Export-burned cells never ignite; a cell with lo before the start but not export-burned ignites at 0 if hi + T is
    after the start (it may still be burning), otherwise it is taken as burned out."""
    lo = np.asarray(lo_h, float)
    hi = np.asarray(hi_h, float)
    if not np.array_equal(np.isfinite(lo), np.isfinite(hi)) or np.any(lo[np.isfinite(lo)] > hi[np.isfinite(hi)]):
        raise ValueError('envelope needs lo <= hi on the same footprint')
    rlo, rhi = (lo - start_h) * 3600.0, (hi - start_h) * 3600.0
    ok = np.isfinite(lo) & ~np.asarray(burned_at_start, bool) & (rhi > -float(burn_duration_s))
    births = np.floor(np.maximum(rlo, 0.0) / quantum_s) * quantum_s
    hi_rel = np.floor(np.maximum(rhi, 0.0) / quantum_s) * quantum_s
    ok &= births < horizon_s
    b = np.full(lo.shape, np.inf)
    e = np.full(lo.shape, np.inf)
    b[ok], e[ok] = births[ok], hi_rel[ok]
    return b[None], e[None]
