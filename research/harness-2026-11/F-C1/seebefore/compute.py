"""F-C1 compute: per place, the required visible height of every fire cell of its region's three inputs; then per case
the first-visible time t_vis for flames / glow / smoke and the see-before-leave gap class (DEFINITION.md).

    python3 seebefore/compute.py --surface _data/surface_glo30_5179_30m.npz --out _data/run [--limit N]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seebefore import dem, extract, fire  # noqa: E402
from seebefore.viewshed import required_height, ring_points, subpoints  # noqa: E402

STEP_M = 15.0
EYE_PRIMARY, EYE_HIGH = 2.0, 10.0
# observer variants: (name, ring index or None for centre, eye height)
VARIANTS = ['centre_eye2', 'centre_eye10', 'best9_eye2', 'centre_eye2_cellcentre']
# v2 fixed settings (DEFINITION.md, committed before the counted run): variant row, heights, range cap
SETTINGS = {
    'optimistic': {'variant': 'best9_eye2', 'flame': 10.0, 'smoke': 1000.0, 'cap_m': None},
    'pessimistic': {'variant': 'centre_eye2_cellcentre', 'flame': 2.0, 'smoke': 300.0, 'cap_m': 15_000.0},
}
NONGROUND_DSM_EXCESS_M = 5.0     # observer DSM above the 5th percentile within 150 m -> flagged as not bare ground
NONGROUND_RADIUS_M = 150.0
# channel thresholds (target height above surface, m); primary first
HEIGHTS = {'flame': [10.0, 2.0, 30.0], 'glow': [150.0, 50.0, 300.0], 'smoke': [1000.0, 300.0, 3000.0]}
BEST9_HEIGHTS = (10.0, 150.0, 1000.0)    # primary heights; best9 variant evaluated only at these
CHUNK = 1_000_000
FLAME_RANGE_CAP_M = 15_000.0
NIGHT = {'uiseong_andong_2025/20250325T170000Z', 'yeongdeok_2025/20250325T190000Z'}     # 02:00 and 04:00 KST
DUSK = {'uiseong_andong_2025/20250324T090000Z'}                                         # 18:00 KST


def ckey(xy):
    return (int(round(xy[0])), int(round(xy[1])))


def region_cells(fsets):
    keys = {}
    for fs in fsets:
        for xy in fs.present_xy:
            keys.setdefault(ckey(xy), xy)
        for m in fs.member_new:
            for _, arr in m:
                for xy in arr:
                    keys.setdefault(ckey(xy), xy)
    k = sorted(keys)
    return k, np.array([keys[x] for x in k], float)


def place_hreq(surface, px, py, cells_xy):
    """(variants, cells) minimum over 3x3 sub-points of the required height; best9 = min over 9 observer points."""
    sp = subpoints(cells_xy).reshape(-1, 2)
    nc = len(cells_xy)
    centre_all = required_height(surface, px, py, [EYE_PRIMARY, EYE_HIGH], sp[:, 0], sp[:, 1], step=STEP_M,
                                 max_samples_per_chunk=CHUNK).reshape(2, nc, 9)
    cell_centre = centre_all[0, :, 4].copy()           # sub-point index 4 = the cell centre (offsets -125, 0, +125)
    centre = np.fmin.reduce(centre_all, axis=2) if nc else centre_all.reshape(2, 0)
    # best9 is evaluated at the primary heights only (BEST9_HEIGHTS); a cell already visible from the centre at the
    # lowest primary height needs no ring rays (best9 <= centre). Other cells get exact ring values.
    best = centre[0].copy()
    need = ~(centre[0] < min(BEST9_HEIGHTS))
    if need.any():
        spn = subpoints(cells_xy[need]).reshape(-1, 2)
        for rx, ry in ring_points(px, py)[1:]:
            h = required_height(surface, rx, ry, [EYE_PRIMARY], spn[:, 0], spn[:, 1], step=STEP_M,
                                max_samples_per_chunk=CHUNK)[0]
            best[need] = np.fmin(best[need], np.fmin.reduce(h.reshape(-1, 9), axis=1))
    return np.vstack([centre, best[None, :], cell_centre[None, :]])


_W = {}


def _init(surface_path, cells_xy):
    _W['surface'] = dem.load(Path(surface_path))[0]
    _W['cells'] = cells_xy


def _work(job):
    pid, x, y = job
    return pid, place_hreq(_W['surface'], x, y, _W['cells'])


def tvis(fs, hreq_by_key, dist_by_key, height, cap=None):
    """Per member: earliest time (s) any fire cell is visible (h_req < height), or None (> horizon)."""
    def vis(xy):
        k = ckey(xy)
        h = hreq_by_key.get(k)
        if h is None or not np.isfinite(h):
            return False
        if cap is not None and dist_by_key[k] > cap:
            return False
        return h < height
    present = any(vis(xy) for xy in fs.present_xy)
    out = []
    for m in fs.member_new:
        if present:
            out.append(0.0)
            continue
        t = None
        for t0, arr in m:
            if any(vis(xy) for xy in arr):
                t = t0
                break
        out.append(t)
    return out


def gap_class(cs, tv_members, horizon):
    """Gap class for one case and one channel/threshold (DEFINITION.md)."""
    L, by = cs['latest_s'], cs['deadline_set_by']
    known = [t for t in tv_members if t is not None]
    t_min = min(known) if known else None                # earliest member
    t_max = None if len(known) < len(tv_members) else max(known)   # None = some member > horizon
    if L is None:
        return 'no_route', t_min, t_max
    if t_max is not None and t_max == 0.0:
        return 'nonneg_visible_now', 0.0, 0.0
    if by == 'fire_or_limits':
        upper = L + 600.0                                  # true deadline in [L, L+600)
        # negative in every member if each member's t_vis >= upper (None = beyond horizon >= 3600 >= upper)
        if all(t is None or t >= upper for t in tv_members):
            return 'negative', t_min, t_max
        if all(t is not None and t <= L for t in tv_members):
            return 'nonneg', t_min, t_max
        return 'indeterminate_mixed', t_min, t_max
    # grid_end (true deadline >= L, censored) or window (fire deadline unknown, >= L)
    if all(t is not None and t <= L for t in tv_members):
        return 'nonneg', t_min, t_max
    return 'indeterminate_censored_deadline', t_min, t_max


def robust_class(opt: str, pes: str) -> str:
    """Sign is robust only when both settings agree on it (DEFINITION.md v2)."""
    sign = {'negative': '-', 'nonneg': '+', 'nonneg_visible_now': '+', 'no_route': 'no_route'}
    a, b = sign.get(opt), sign.get(pes)
    if a is not None and a == b:
        return {'-': 'robust_negative', '+': 'robust_nonneg', 'no_route': 'no_route'}[a]
    return 'indeterminate'


def observer_nonground(surface, x, y):
    """True when the DSM at the observer is > NONGROUND_DSM_EXCESS_M above the 5th percentile within 150 m."""
    g = np.arange(-NONGROUND_RADIUS_M, NONGROUND_RADIUS_M + 1, surface.res)
    gx, gy = np.meshgrid(g, g)
    m = np.hypot(gx, gy) <= NONGROUND_RADIUS_M
    z = surface.sample(x + gx[m], y + gy[m])
    z0 = float(surface.sample(x, y))
    return bool(z0 - np.nanpercentile(z, 5) > NONGROUND_DSM_EXCESS_M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--surface', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--limit', type=int, default=None, help='first N places per region (smoke test)')
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    surface, smeta = dem.load(a.surface)
    cases = extract.build()
    by_region = defaultdict(list)
    for c in cases:
        by_region[c['region']].append(c)
    rows = []
    t_start = time.time()
    for region, cs in sorted(by_region.items()):
        scopes = sorted({c['scope'] for c in cs})
        fsets = {s: fire.load(region, s.split('/')[1]) for s in scopes}
        keys, cells_xy = region_cells(fsets.values())
        places = {}
        for c in cs:
            places.setdefault(c['origin_id'], c)
        pids = sorted(places)[: a.limit] if a.limit else sorted(places)
        print(f'{region}: {len(pids)} places x {len(keys)} fire cells', flush=True)
        H = {}
        jobs = [(pid, places[pid]['place_x'], places[pid]['place_y']) for pid in pids]
        with mp.get_context('fork').Pool(a.workers, initializer=_init, initargs=(str(a.surface), cells_xy)) as pool:
            for i, (pid, hr) in enumerate(pool.imap_unordered(_work, jobs)):
                p = places[pid]
                d = np.hypot(cells_xy[:, 0] - p['place_x'], cells_xy[:, 1] - p['place_y'])
                H[pid] = (hr, d)
                if i % 10 == 0:
                    print(f'  {i}/{len(pids)} {time.time() - t_start:.0f}s', flush=True)
        np.savez_compressed(a.out / f'hreq_{region}.npz', keys=np.array(keys), pids=np.array(pids),
                            hreq=np.stack([H[p][0] for p in pids]), dist=np.stack([H[p][1] for p in pids]))
        nonground = {pid: observer_nonground(surface, places[pid]['place_x'], places[pid]['place_y']) for pid in pids}
        for c in cs:
            if c['origin_id'] not in H:
                continue
            hr, d = H[c['origin_id']]
            fs = fsets[c['scope']]
            dist_by_key = dict(zip(keys, d))
            row = {k: c[k] for k in ('scope', 'region', 'input_time', 'origin_id', 'name', 'name_en', 'origin_type',
                                     'latest_s', 'deadline_set_by', 'best_verdict', 'place_x', 'place_y')}
            row['light'] = 'night' if c['scope'] in NIGHT else 'dusk' if c['scope'] in DUSK else 'day'
            pres = np.array([dist_by_key[ckey(xy)] for xy in fs.present_xy])
            row['nearest_present_fire_km'] = float(pres.min() / 1000) if pres.size else None
            row['observer_nonground'] = nonground[c['origin_id']]
            res = {}
            for sname, st in SETTINGS.items():
                hk = dict(zip(keys, hr[VARIANTS.index(st['variant'])]))
                for ch in ('flame', 'smoke'):
                    tv = tvis(fs, hk, dist_by_key, st[ch], st['cap_m'])
                    cls, tmin, tmax = gap_class(c, tv, fs.valid_until_s)
                    res[f'{ch}@{sname}'] = {'t_vis_members_s': tv, 'class': cls}
                for ch in ('flame', 'smoke'):
                    a_, b_ = res[f'{ch}@optimistic']['class'], res.get(f'{ch}@pessimistic', {}).get('class')
                    if b_ is not None:
                        res[f'{ch}@robust'] = {'class': robust_class(a_, b_)}
            row['results'] = res
            rows.append(row)
    (a.out / 'cases_results.json').write_text(json.dumps({'surface': smeta, 'step_m': STEP_M, 'variants': VARIANTS, 'settings': SETTINGS,
                                                          'heights': HEIGHTS, 'rows': rows}, ensure_ascii=False,
                                                         default=float))
    print(f'done {len(rows)} cases in {time.time() - t_start:.0f}s -> {a.out}')


if __name__ == '__main__':
    main()
