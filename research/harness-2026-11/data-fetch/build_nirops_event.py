#!/usr/bin/env python3
"""Build forecast-v2-style grid and labels for one NIROPS incident (S-D9 part a only).

Grid rule reproduced from the Choi et al. 2026 code (evaluate_sc.reference_grid): EPSG:5070, 375 m cells, the
union-of-surveys bounds plus a 2 km margin, edges on multiples of 375 m. It reproduces the archived grids of Moose,
GreenRidge, Dixie and CameronPeak exactly.
Times follow the S-D9 A1 frozen rule: start_utc = t0 = floor_hour(first survey); end_utc = ceil_hour(last survey).

Outputs, in <workspace>/data/environment/regions/<incident>/:
  arrival_time_hours.tif      first-survey time (h since t0) whose cumulative union contains the cell centre; -1 = never mapped.
                              It is the grid template environment.py reads, and is also the stepwise NIROPS reference.
  grid.json                   the event record, in the same schema as forecast/data/environment/events.json
  labels/cumulative_masks.npz survey_utc (ISO strings), hours (since t0), masks [n_surveys, h, w] uint8 (cell centres)
  labels/intervals.csv        consecutive survey pairs with 0 < dt <= 48 h
The event is appended to <workspace>/data/environment/events.json.
Also, in the format of research/forecast-v2/scripts/prepare_perimeters.py (read by pipeline.py):
  <workspace>/data/perimeters/<incident>/perimeters.geojson and states.npz (times, states from the repo's own
  wildfire.survival.survey_states; arrival_* keys are NaN because part-a fires have no kriged field), and
  <workspace>/data/perimeters/PERIMETER_MANIFEST.json (updated per incident).

The script refuses any incident that is not in the part-a allowlist, and reads only that incident's features
(OGR attribute filter), so no other fire's geometry is loaded.
"""
import argparse, csv, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'forecast'))
from wildfire.survival import consecutive_intervals, survey_states  # noqa: E402  (repo's own rasterizer)

import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
from affine import Affine
from rasterio import features
from rasterio.warp import transform_bounds

CELL, MARGIN = 375.0, 2000.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('incident')
    ap.add_argument('--shp', required=True, help='NIROPS_2020_2024_R1_R6.shp')
    ap.add_argument('--allowlist', required=True, help='S-D9 cohort/PART_A_ALLOWLIST.csv')
    ap.add_argument('--workspace', required=True, help='directory holding data/environment (outside git)')
    ap.add_argument('--exposed-reference', metavar='EVENTS_JSON',
                    help='also allow incidents already in this events.json (the 44 exposed project events), for '
                         'rebuilt-vs-archive checks only')
    a = ap.parse_args()

    allowed = {r['Incident_C'] for r in csv.DictReader(open(a.allowlist))}
    if a.exposed_reference:
        allowed |= {e['id'] for e in json.load(open(a.exposed_reference))}
    if a.incident not in allowed:
        sys.exit(f'REFUSED: {a.incident} is not in the part-a allowlist')
    if "'" in a.incident:
        sys.exit('bad incident id')

    g = pyogrio.read_dataframe(a.shp, where=f"Incident_C = '{a.incident}'", fid_as_index=True)
    if g.empty:
        sys.exit(f'no NIROPS features for {a.incident}')
    raw4326 = g.copy()
    g = g.to_crs(5070)
    g['geometry'] = shapely.make_valid(g.geometry.values)
    g['t'] = pd.to_datetime(g['UTC'], utc=True)
    surveys = g.groupby('t').geometry.agg(lambda s: shapely.union_all(s.values)).sort_index()

    x0, y0, x1, y1 = shapely.union_all(surveys.values).bounds
    gx0 = np.floor((x0 - MARGIN) / CELL) * CELL
    gy1 = np.ceil((y1 + MARGIN) / CELL) * CELL
    w = int(np.ceil((x1 + MARGIN - gx0) / CELL)); h = int(np.ceil((gy1 - (y0 - MARGIN)) / CELL))
    tr = Affine(CELL, 0, gx0, 0, -CELL, gy1)

    first, last = surveys.index[0], surveys.index[-1]
    t0 = first.floor('h')  # S-D9 A1 frozen rule: start_utc = floor_hour(first survey), end_utc = ceil_hour(last survey)
    hours = ((surveys.index - t0).total_seconds() / 3600).to_numpy()

    masks = np.zeros((len(surveys), h, w), np.uint8)
    covered = np.zeros((h, w), bool)
    toa = np.full((h, w), -1.0, np.float32)
    for i, geom in enumerate(surveys.values):
        inside = features.geometry_mask([geom], out_shape=(h, w), transform=tr, invert=True)
        toa[inside & ~covered] = hours[i]
        covered |= inside
        masks[i] = covered

    ws = Path(a.workspace) / 'data' / 'environment'
    out = ws / 'regions' / a.incident
    (out / 'labels').mkdir(parents=True, exist_ok=True)
    prof = dict(driver='GTiff', dtype='float32', nodata=-1.0, width=w, height=h, count=1, crs='EPSG:5070',
                transform=tr, tiled=True, blockxsize=128, blockysize=128, compress='deflate')
    with rasterio.open(out / 'arrival_time_hours.tif', 'w', **prof) as dst:
        dst.write(toa, 1)
        dst.update_tags(event=a.incident, t0_utc=str(t0.tz_localize(None)),
                        source='NIROPS 2020-2024 (Mendeley 10.17632/95rj5d379g.1) cumulative survey unions, cell centres')
    np.savez_compressed(out / 'labels' / 'cumulative_masks.npz', masks=masks, hours=hours,
                        survey_utc=np.array([t.isoformat() for t in surveys.index]))
    with open(out / 'labels' / 'intervals.csv', 'w', newline='') as fh:
        wr = csv.writer(fh); wr.writerow(['i0', 'i1', 'start_utc', 'end_utc', 'dt_h', 'cells_start', 'cells_end'])
        for i in range(len(surveys) - 1):
            dt = hours[i + 1] - hours[i]
            if 0 < dt <= 48:
                wr.writerow([i, i + 1, surveys.index[i].isoformat(), surveys.index[i + 1].isoformat(), round(dt, 4),
                             int(masks[i].sum()), int(masks[i + 1].sum())])

    bounds = transform_bounds('EPSG:5070', 'EPSG:4326', gx0, gy1 - h * CELL, gx0 + w * CELL, gy1, densify_pts=51)
    start, end = first.floor('h'), last.ceil('h')
    e = dict(id=a.incident, name=a.incident.split('_', 1)[1], country='US', year=int(first.year),
             t0_utc=t0.isoformat(), start_utc=start.isoformat(), end_utc=end.isoformat(),
             acquisition_window_basis='S-D9 A1: floor_hour(first NIROPS survey) to ceil_hour(last survey)',
             rain_history_start_utc=(start - pd.Timedelta(days=30)).isoformat(),
             arrival_path=f'regions/{a.incident}/arrival_time_hours.tif', source_arrival_path='NIROPS cumulative unions',
             width=w, height=h, epsg=5070, transform=list(tr)[:6], bounds_wgs84=list(bounds), resolution_m=[375, 375],
             burned_label='NIROPS cumulative mapped extent at cell centres', valid_arrival_pixels=int(covered.sum()))
    (out / 'grid.json').write_text(json.dumps(e, indent=1))
    ev_path = ws / 'events.json'
    events = json.loads(ev_path.read_text()) if ev_path.exists() else []
    events = [x for x in events if x['id'] != a.incident] + [e]
    ev_path.write_text(json.dumps(events, indent=1))
    # prepare_perimeters.py-format outputs, rasterized by the repo's own survey_states
    feats = []
    for fid, row in raw4326.iterrows():
        props = {k: (v.isoformat() if hasattr(v, 'isoformat') else (None if pd.isna(v) else v))
                 for k, v in row.drop('geometry').items()}
        stamp = pd.Timestamp(row['UTC'])
        stamp = stamp.tz_localize('UTC') if stamp.tzinfo is None else stamp.tz_convert('UTC')
        props.update(time_utc=stamp.isoformat(), source_record_id=int(fid))
        feats.append(dict(type='Feature', id=int(fid), properties=props, geometry=shapely.geometry.mapping(row.geometry)))
    feats.sort(key=lambda f: (f['properties']['time_utc'], f['id']))
    times, states = survey_states(feats, e)
    same = states.shape == masks.shape and bool((states.astype(bool) == masks.astype(bool)).all())
    pdir = Path(a.workspace) / 'data' / 'perimeters'
    (pdir / a.incident).mkdir(parents=True, exist_ok=True)
    gj = pdir / a.incident / 'perimeters.geojson'
    gj.write_text(json.dumps(dict(type='FeatureCollection', name=a.incident, features=feats)) + '\n')
    nan = np.full((h, w), np.nan, np.float32)
    np.savez_compressed(pdir / a.incident / 'states.npz', times=np.array([t.isoformat() for t in times]),
                        states=states, arrival_hours=nan, arrival_std_hours=nan, arrival_t0_utc=np.array(''))
    sha = lambda f: hashlib.sha256(open(f, 'rb').read()).hexdigest()
    ivs = consecutive_intervals(times, 48.0)
    mpath = pdir / 'PERIMETER_MANIFEST.json'
    man = json.loads(mpath.read_text()) if mpath.exists() else dict(
        shapefile_sha256=sha(a.shp), created_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__), events={},
        note='written by research/harness-2026-11/data-fetch/build_nirops_event.py in the prepare_perimeters.py format')
    man['events'][a.incident] = dict(records=len(feats), distinct_times=len(times), intervals_le_48h=len(ivs),
        growth_intervals_le_48h=int(sum(int((states[j] > states[i]).sum()) > 0 for i, j, _ in ivs)),
        final_mapped_cells=int(states[-1].sum()), geojson_sha256=sha(gj), states_sha256=sha(pdir / a.incident / 'states.npz'),
        survey_states_equals_builder_masks=same)
    mpath.write_text(json.dumps(man, indent=1) + '\n')
    n_int = sum(1 for _ in open(out / 'labels' / 'intervals.csv')) - 1
    print(f'BUILT {a.incident}: grid {h}x{w}, {len(surveys)} survey times, {n_int} intervals <=48 h, '
          f'window {start} .. {end}, {int(covered.sum())} mapped cells; survey_states identical: {same}')


if __name__ == '__main__':
    main()
