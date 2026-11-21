#!/usr/bin/env python3
"""Cohort-R survey states for the A1 §5.2 native-marginal demo (Hannah's ruling, option A, 13 Nov 03:08Z).

NIROPS is read ONLY through nirops_access.py (@ab065e85, sha256 checked), with the R allowlist (R_ALLOWLIST.csv
@c4d74159, sha256 checked):
  - nirops_access.id_index(shp)          the Incident_C column alone, for all records;
  - nirops_access.read_incident(shp, inc, allowed=R, ids=...)   geometry + attributes BY FID, R records only.
Every call is logged (UTC, call, Incident_C, fids) to <out>/access_log.txt and summarised on stdout. The logging wraps
nirops_access.read_by_fid, which read_incident calls for its only geometry/attribute read.

Survey times come only from the R records just read (column UTC). The event grid of each R fire is read READ-ONLY from
the US2024 workspace's events.json; before and after the run every file in the US2024 pins manifest is hashed and must
equal it (the manifest sha256 is also asserted). Nothing is written inside the US2024 workspace or the repo.

Output (a NEW directory): <out>/<event>/states.npz (times, states from the repo's own wildfire.survival.survey_states;
arrival_* keys NaN as in build_nirops_event.py), <out>/PERIMETER_MANIFEST.json with per-event states_sha256, and
<out>/access_log.txt.

usage: build_r_states.py --shp NIROPS.shp --allowlist R_ALLOWLIST.csv --nirops-access nirops_access.py
         --events US2024/data/environment/events.json --pins us2024_input_manifest_night1.json --pins-root US2024/data
         --out NEW_DIR [--expect-allowlist-sha SHA] [--expect-access-sha SHA] [--expect-pins-sha SHA]
"""
import argparse, csv, hashlib, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'forecast'))

ALLOWLIST_SHA = '307fc097c7440e8b5c62a8db95c60ecb6778adf206c3980ed4ec086067d32536'
ACCESS_SHA = '08753d9669ccfedc48f50a0f6b3f42897f9a63e30ead8ea0e8c0183b80613a2b'
PINS_SHA = '286f4c47d1c21d12485b4ec2079ce09c698c21af73d64037921b34284e6592c2'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def check_pins(pins_path, root):
    pins = json.loads(Path(pins_path).read_text())
    bad = [r for r, s in pins.items() if not (Path(root) / r).is_file() or sha(Path(root) / r) != s]
    return len(pins), bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ('shp', 'allowlist', 'nirops_access', 'events', 'pins', 'pins_root', 'out'):
        ap.add_argument('--' + k.replace('_', '-'), required=True)
    ap.add_argument('--expect-allowlist-sha', default=ALLOWLIST_SHA)
    ap.add_argument('--expect-access-sha', default=ACCESS_SHA)
    ap.add_argument('--expect-pins-sha', default=PINS_SHA)
    a = ap.parse_args(argv)

    # identity checks before any NIROPS read
    for path, want, what in ((a.allowlist, a.expect_allowlist_sha, 'allowlist'), (a.nirops_access, a.expect_access_sha, 'nirops_access.py'),
                             (a.pins, a.expect_pins_sha, 'pins manifest')):
        got = sha(path)
        if got != want:
            sys.exit(f'REFUSED: {what} sha256 {got} != expected {want}')
    out = Path(a.out).resolve()
    for forbidden in (REPO.resolve(), Path(a.pins_root).resolve()):
        if out == forbidden or forbidden in out.parents:
            sys.exit(f'REFUSED: --out is inside {forbidden}')
    if out.exists() and any(out.iterdir()):
        sys.exit('REFUSED: --out must be a new or empty directory')
    n, bad = check_pins(a.pins, a.pins_root)
    if bad:
        sys.exit(f'REFUSED: US2024 pins check BEFORE failed: {len(bad)} of {n} differ, e.g. {bad[0]}')
    print(f'pins check BEFORE: {n} files, 0 differ (manifest {a.expect_pins_sha[:8]})')

    R = [r['Incident_C'] for r in csv.DictReader(open(a.allowlist))]
    events = {e['id']: e for e in json.loads(Path(a.events).read_text()) if e['id'] in set(R)}
    missing = [r for r in R if r not in events]
    if missing:
        sys.exit(f'REFUSED: no US2024 grid for {missing}')

    spec = importlib.util.spec_from_file_location('nirops_access', a.nirops_access)
    NA = importlib.util.module_from_spec(spec); spec.loader.exec_module(NA)
    out.mkdir(parents=True, exist_ok=True)
    log = (out / 'access_log.txt').open('a')
    calls = []
    real_read_by_fid = NA.read_by_fid

    def logged_read_by_fid(shp, fids, ids, allowed, columns=None):
        fl = sorted(int(f) for f in fids)
        incs = sorted({str(ids.loc[f]) for f in fids})
        line = f'{utc()}\tread_by_fid\tIncident_C={";".join(incs)}\tn={len(fl)}\tfids={",".join(map(str, fl))}'
        log.write(line + '\n'); log.flush(); calls.append((incs, fl))
        return real_read_by_fid(shp, fids, ids, allowed, columns)

    NA.read_by_fid = logged_read_by_fid
    log.write(f'{utc()}\tid_index\tcolumn=Incident_C only (no geometry, no other field)\tshp_sha256={sha(a.shp)}\n')
    ids = NA.id_index(a.shp)

    import numpy as np
    import pandas as pd
    import shapely
    from wildfire.survival import consecutive_intervals, survey_states

    pdir = out
    man = dict(shapefile_sha256=sha(a.shp), created_utc=utc(), script_sha256=sha(__file__),
               allowlist_sha256=a.expect_allowlist_sha, nirops_access_sha256=a.expect_access_sha,
               grid_source=f'US2024 events.json (read-only), pins manifest {a.expect_pins_sha}',
               note='cohort R states for the A1 §5.2 demo; prepare_perimeters.py-format states.npz', events={})
    for inc in R:
        g = NA.read_incident(a.shp, inc, allowed=R, ids=ids)
        if g.empty:
            sys.exit(f'no NIROPS features for {inc}')
        feats = []
        for fid, row in g.iterrows():
            stamp = pd.Timestamp(row['UTC'])
            stamp = stamp.tz_localize('UTC') if stamp.tzinfo is None else stamp.tz_convert('UTC')
            feats.append(dict(type='Feature', id=int(fid), properties=dict(time_utc=stamp.isoformat(), source_record_id=int(fid)),
                              geometry=shapely.geometry.mapping(row.geometry)))
        feats.sort(key=lambda f: (f['properties']['time_utc'], f['id']))
        e = events[inc]
        times, states = survey_states(feats, e)
        (pdir / inc).mkdir(parents=True, exist_ok=True)
        h, w = int(e['height']), int(e['width'])
        nan = np.full((h, w), np.nan, np.float32)
        sp = pdir / inc / 'states.npz'
        np.savez_compressed(sp, times=np.array([t.isoformat() for t in times]), states=states,
                            arrival_hours=nan, arrival_std_hours=nan, arrival_t0_utc=np.array(''))
        ivs = consecutive_intervals(times, 48.0)
        man['events'][inc] = dict(records=len(feats), distinct_times=len(times), intervals_le_48h=len(ivs),
                                  final_mapped_cells=int(states[-1].sum()), grid=[h, w], states_sha256=sha(sp))
        print(f'BUILT {inc}: records {len(feats)}, survey times {len(times)}, intervals<=48h {len(ivs)}, grid {h}x{w}')
    (pdir / 'PERIMETER_MANIFEST.json').write_text(json.dumps(man, indent=1) + '\n')
    log.close()

    n, bad = check_pins(a.pins, a.pins_root)
    if bad:
        sys.exit(f'US2024 pins check AFTER FAILED: {len(bad)} of {n} differ, e.g. {bad[0]}')
    print(f'pins check AFTER: {n} files, 0 differ (manifest {a.expect_pins_sha[:8]})')
    allfids = [f for _, fl in calls for f in fl]
    print(f'access: 1 id_index call (Incident_C only); {len(calls)} read_by_fid calls, {len(allfids)} fids, '
          f'Incident_C set {sorted({i for incs, _ in calls for i in incs})}')
    print('outputs:', json.dumps({k: v['states_sha256'] for k, v in man['events'].items()}),
          'PERIMETER_MANIFEST', sha(pdir / 'PERIMETER_MANIFEST.json'), 'access_log', sha(out / 'access_log.txt'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
