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
* v3.1 quantization (QUANT_v3_1_RULE.md, wfg.fdyn.quant/3.1): every floored time is an integer number of
  milliseconds since t0; arrivals are round(arrival_h * 3,600,000) (exact recovery for timestamp-derived values, 1 ms
  rounding for real-valued ones) and all flooring and comparisons are integer arithmetic.
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
QUANT_VERSION = 'wfg.fdyn.quant/3.1'
MS_PER_H = 3_600_000
SPEED_RATIONAL = {1.0: (1, 1), 0.75: (3, 4), 0.5: (1, 2)}


def to_ms(arrival_h):
    """(int64 ms since t0, finite mask). NaN never ignites; +-inf is not a valid arrival."""
    a = np.asarray(arrival_h, float)
    fin = np.isfinite(a)
    if np.any(np.isinf(a)):
        raise ValueError('infinite arrival')
    ms = np.zeros(a.shape, np.int64)
    ms[fin] = np.rint(a[fin] * MS_PER_H).astype(np.int64)
    return ms, fin


def hour_ms(h: float) -> int:
    """start (whole minute since t0) in exact integer ms."""
    v = int(round(h * MS_PER_H))
    if v % 60000:
        raise ValueError('start must be a whole minute since t0')
    return v


def int_s(x: float) -> int:
    v = int(round(x))
    if abs(v - x) > 1e-9:
        raise ValueError(f'{x} is not a whole number of seconds')
    return v


def t_ms_real(T_s: float) -> float:
    """T (contract cell duration, real-valued: 3970.4642815249267 s) in ms, compared against integer ms. The comparison
    is unambiguous if T*1000 is an exact integer or not within 1e-6 ms of one (checked)."""
    v = float(T_s) * 1000.0
    if 0.0 < abs(v - round(v)) < 1e-6:                    # an exact integer is unambiguous too
        raise ValueError('T*1000 too close to an integer for an unambiguous comparison')
    return v


def rounded_cells(arrival_h, exact_mask, sel=None) -> int:
    """cells whose value is real-valued (rounded to 1 ms), optionally restricted to sel."""
    a = np.asarray(arrival_h, float)
    m = np.isfinite(a) & ~(np.zeros(a.shape, bool) if exact_mask is None else np.asarray(exact_mask, bool))
    if sel is not None:
        m &= sel
    return int(m.sum())


def schedule(arrival_h: np.ndarray, start_h: float, horizon_s: float, quantum_s: float = DEFAULT_QUANTUM_S,
             members=('central',), burned_at_start=None, burn_duration_s: float | None = None) -> np.ndarray:
    """Ignition times [S, H, W] in seconds from the start (inf = no ignition within the horizon).

    ``burned_at_start`` (the recorded export's known-burned cells, present fire included) never ignite: the writer
    keeps them as recorded. A variant raster can place a cell's arrival before the start although the export has it
    unburned (e.g. a FIRMS detection earlier than the kriged mean); such a cell ignites at t = 0 if its variant arrival
    lies within one burn duration before the start (it would still be burning), otherwise it is taken as burned out."""
    a_ms, fin = to_ms(arrival_h)
    rel = a_ms - hour_ms(start_h)                                   # int64 ms
    burned = np.zeros(a_ms.shape, bool) if burned_at_start is None else np.asarray(burned_at_start, bool)
    if burned_at_start is not None and burn_duration_s is None:
        raise ValueError('burn_duration_s required with burned_at_start')
    late_lo = -t_ms_real(burn_duration_s) if burn_duration_s is not None else 0
    future = fin & ~burned & (rel > late_lo)
    Q = int_s(quantum_s) * 1000
    H = int_s(horizon_s) * 1000
    out = np.full((len(members),) + a_ms.shape, np.inf)
    for k, name in enumerate(members):
        m = MEMBER_RULES[name]
        p, q = SPEED_RATIONAL[m['speed_factor']]
        num = p * rel - q * int_s(m['shift_s']) * 1000              # q * t_ms, exact
        t = np.maximum(num, 0) // (q * Q) * Q                       # floor_Q in integer ms
        ok = future & (t < H)
        out[k][ok] = t[ok] / 1000.0                                 # whole multiples of Q seconds: exact in binary64
    return out


def digest(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype='<f8').tobytes()).hexdigest()


def plan(arrival_h, sd_h, *, arrival_variant: str, arrival_source: dict, start_h: float, start_utc: str,
         horizon_s: float, quantum_s: float, member_set: str, region: str, window: dict | None,
         burned_at_start: np.ndarray, burn_duration_s: float, arrival_hi_h: np.ndarray | None = None,
         arrival_exact=None, arrival_hi_exact=None) -> dict:
    for arr, ex in ((arrival_h, arrival_exact), (arrival_hi_h, arrival_hi_exact)):
        if arr is not None and ex is not None:            # a timestamp-derived value must be a whole millisecond
            v = np.asarray(arr, float)[np.asarray(ex, bool)] * MS_PER_H
            if v.size and np.max(np.abs(v - np.rint(v))) > 1e-3:
                raise ValueError('timestamp_exact cell is not a whole millisecond')
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
    a_ms, afin = to_ms(arrival_h)
    rel = a_ms - hour_ms(start_h)
    T_ms = t_ms_real(burn_duration_s)
    catch_up = afin & ~burned_at_start & (rel <= 0) & (rel > -T_ms)
    burned_out = afin & ~burned_at_start & (rel <= -T_ms)
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
        'quantization': {'version': QUANT_VERSION, 'rule': 'QUANT_v3_1_RULE.md',
                         'igniting_cells_with_1ms_rounded_arrival': rounded_cells(arrival_h, arrival_exact,
                                                                                np.isfinite(times[0])),
                         'igniting_cells_with_1ms_rounded_hi': (rounded_cells(arrival_hi_h, arrival_hi_exact,
                                                                               np.isfinite(times[0]))
                                                                 if arrival_hi_h is not None else None),
                         'exact_mask_supplied': arrival_exact is not None,
                         'worst_case_anticonservative_start_shift_ms': 0.5},
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
    lo_ms, fin = to_ms(lo)
    hi_ms, _ = to_ms(hi)
    h_ms = hour_ms(start_h)
    rlo, rhi = lo_ms - h_ms, hi_ms - h_ms
    Q = int_s(quantum_s) * 1000
    ok = fin & ~np.asarray(burned_at_start, bool) & (rhi > -t_ms_real(burn_duration_s))
    births = np.maximum(rlo, 0) // Q * Q
    hi_rel = np.maximum(rhi, 0) // Q * Q                            # hi_rel + T + Q >= hi + T exactly
    ok &= births < int_s(horizon_s) * 1000
    b = np.full(lo.shape, np.inf)
    e = np.full(lo.shape, np.inf)
    b[ok], e[ok] = births[ok] / 1000.0, hi_rel[ok] / 1000.0
    return b[None], e[None]
