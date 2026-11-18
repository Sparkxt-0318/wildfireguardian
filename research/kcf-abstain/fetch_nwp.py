#!/usr/bin/env python3
"""Fetch issued NWP forecasts (GFS 0.25 deg or HRRR 3 km) from the NOAA open-data buckets on AWS and keep
seven fields on a fixed 0.25 deg lattice over a region box. No values are interpreted here.

  python3 fetch_nwp.py --model gfs  --region WUS --start 2021-06-30T18 --end 2021-10-07T00 --out DIR
  python3 fetch_nwp.py --model hrrr --region WUS --start 2020-07-21T12 --end 2020-11-10T00 --out DIR

Cycles 00/06/12/18 UTC in [start, end), lead hours 6..18 (PROTOCOL.md: 5 h availability delay, 8 h window).
Fields (GRIB name:level): GUST:surface, TMP:2 m, RH:2 m, UGRD:10 m, VGRD:10 m, UGRD:850 mb, VGRD:850 mb.
GFS values are read at the lattice points directly. HRRR values are averaged over the HRRR cells whose centres
round to each lattice point (a 0.25 x 0.25 deg box), so both models are read on the same lattice.
Output: OUT/<model>_<region>/<YYYYMMDDHH>.npz with arr[lead, field, lat, lon] float32 (NaN = missing),
leads, lat, lon; and OUT/<model>_<region>/log.jsonl (one line per cycle: missing leads/fields, bytes, seconds).
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import numpy as np

FIELDS = [('GUST', 'surface'), ('TMP', '2 m above ground'), ('RH', '2 m above ground'),
          ('UGRD', '10 m above ground'), ('VGRD', '10 m above ground'), ('UGRD', '850 mb'), ('VGRD', '850 mb')]
REGIONS = {'WUS': (31.0, 49.5, 235.0, 257.0), 'KOR': (33.0, 39.0, 125.0, 131.0)}  # lat0, lat1, lon0, lon1 (deg E)
LEADS = list(range(6, 19))
STEP = 0.25


def lattice(region):
    la0, la1, lo0, lo1 = REGIONS[region]
    lat = np.round(np.arange(la0, la1 + 1e-9, STEP), 4)
    lon = np.round(np.arange(lo0, lo1 + 1e-9, STEP), 4)
    return lat, lon


def url(model, cyc, lead):
    d, h = cyc[:8], cyc[8:10]
    if model == 'gfs':
        return f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{d}/{h}/atmos/gfs.t{h}z.pgrb2.0p25.f{lead:03d}'
    return f'https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{d}/conus/hrrr.t{h}z.wrfsfcf{lead:02d}.grib2'


def get(u, rng=None, attempts=5):
    for i in range(attempts):
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'wfg-kcf-abstain/1'})
            if rng:
                req.add_header('Range', f'bytes={rng[0]}-{rng[1]}')
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            time.sleep(2 ** i)
        except Exception:
            time.sleep(2 ** i)
    return None


def ranges_from_idx(text):
    L = [l.split(':') for l in text.strip().splitlines()]
    out = {}
    for i, l in enumerate(L):
        if len(l) < 6:
            continue
        key = (l[3], l[4])
        desc = l[5]
        if key in FIELDS and key not in out and re.fullmatch(r'\d+ hour fcst', desc.strip()):
            start = int(l[1])
            end = int(L[i + 1][1]) - 1 if i + 1 < len(L) else None
            out[key] = (start, end)
    return out


_HRRR_MAP = {}


def hrrr_map(msg, region):
    if region in _HRRR_MAP:
        return _HRRR_MAP[region]
    lats, lons = msg.latlons()
    lons = np.mod(lons, 360.0)
    lat, lon = lattice(region)
    li = np.rint((lats - lat[0]) / STEP).astype(int)
    lj = np.rint((lons - lon[0]) / STEP).astype(int)
    ok = (li >= 0) & (li < lat.size) & (lj >= 0) & (lj < lon.size)
    k = np.where(ok, li * lon.size + lj, -1).ravel()
    sel = np.flatnonzero(k >= 0)
    cnt = np.bincount(k[sel], minlength=lat.size * lon.size).astype(float)
    _HRRR_MAP[region] = (sel, k[sel], cnt)
    return _HRRR_MAP[region]


def one(model, region, cyc, lead):
    import pygrib
    lat, lon = lattice(region)
    out = np.full((len(FIELDS), lat.size, lon.size), np.nan, np.float32)
    u = url(model, cyc, lead)
    idx = get(u + '.idx')
    if idx is None:
        return lead, out, 'no_idx', 0
    rg = ranges_from_idx(idx.decode('utf-8', 'replace'))
    missing = [f'{a}:{b}' for a, b in FIELDS if (a, b) not in rg]
    nbytes = 0
    with ThreadPoolExecutor(len(FIELDS)) as ex:
        futs = {ex.submit(get, u, rg[f]): f for f in FIELDS if f in rg}
        blobs = {futs[f]: f.result() for f in futs}
    for fi, f in enumerate(FIELDS):
        b = blobs.get(f)
        if not b:
            if f in rg:
                missing.append(f'{f[0]}:{f[1]}(fetch)')
            continue
        nbytes += len(b)
        m = pygrib.fromstring(b)
        v = np.ma.filled(m.values.astype(np.float64), np.nan)
        if model == 'gfs':
            rows = np.rint((90.0 - lat) / STEP).astype(int)
            cols = np.rint(lon / STEP).astype(int)
            out[fi] = v[np.ix_(rows, cols)]
        else:
            sel, k, cnt = hrrr_map(m, region)
            s = np.bincount(k, weights=v.ravel()[sel], minlength=cnt.size)
            with np.errstate(invalid='ignore', divide='ignore'):
                out[fi] = (s / cnt).reshape(lat.size, lon.size)
    return lead, out, ';'.join(missing), nbytes


def cycles(start, end):
    import pandas as pd
    return [c.strftime('%Y%m%d%H') for c in pd.date_range(start, end, freq='6h', inclusive='left')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', choices=['gfs', 'hrrr'], required=True)
    ap.add_argument('--region', choices=list(REGIONS), required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--procs', type=int, default=6)
    a = ap.parse_args()
    d = os.path.join(a.out, f'{a.model}_{a.region}')
    os.makedirs(d, exist_ok=True)
    lat, lon = lattice(a.region)
    todo = [c for c in cycles(a.start, a.end) if not os.path.exists(os.path.join(d, c + '.npz'))]
    print(f'{a.model} {a.region}: {len(todo)} cycles to fetch', flush=True)
    with ProcessPoolExecutor(a.procs) as ex:
        for cyc in todo:
            t0 = time.time()
            futs = [ex.submit(one, a.model, a.region, cyc, L) for L in LEADS]
            arr = np.full((len(LEADS), len(FIELDS), lat.size, lon.size), np.nan, np.float32)
            miss, nb = {}, 0
            for f in as_completed(futs):
                lead, o, m, b = f.result()
                arr[LEADS.index(lead)] = o
                nb += b
                if m:
                    miss[lead] = m
            np.savez_compressed(os.path.join(d, cyc + '.npz'), arr=arr, leads=np.array(LEADS), lat=lat, lon=lon,
                                fields=np.array([f'{x}:{y}' for x, y in FIELDS]))
            with open(os.path.join(d, 'log.jsonl'), 'a') as fh:
                fh.write(json.dumps(dict(cycle=cyc, model=a.model, region=a.region, missing=miss, bytes=nb,
                                         seconds=round(time.time() - t0, 1),
                                         fetched_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))) + '\n')
            print(cyc, f'{nb/1e6:.1f} MB', f'{time.time()-t0:.1f}s', 'missing' if miss else '', flush=True)


if __name__ == '__main__':
    main()
