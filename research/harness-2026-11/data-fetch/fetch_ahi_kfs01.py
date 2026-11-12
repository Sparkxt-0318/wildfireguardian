#!/usr/bin/env python3
"""Himawari-9 AHI Japan-area band 7 / band 14 brightness temperatures over the KFS_01 export grid (keyless).

Source: NOAA Open Data Dissemination, public AWS bucket `noaa-himawari9` (no account or key),
prefix AHI-L1b-Japan/YYYY/MM/DD/HHMM/. Each 10-minute slot holds four Japan-area scans, JP01–JP04, about 2.5 min apart.
Files are HSD, 2 km for bands 7 and 14, roughly 0.87 MB each (bz2). Data are distributed by NOAA/JMA; see
https://registry.opendata.aws/noaa-himawari/.

For every scan in [--start, --end), the script downloads B07 and B14, decodes them with satpy's `ahi_hsd` reader to
brightness temperature (K), keeps only pixels whose centre lies inside the KFS_01 grid rectangle (EPSG:5179
x 1085250–1174125, y 1815750–1845375, from forecast/data/environment/events.json), writes the values, and deletes
the raw files. No hotspot thresholding is applied.

Output (--out, .npz):
  scan_start_utc [n_scans] (ISO strings), scan_end_utc, scan_id (JP01–JP04), slot
  lat, lon, x5179, y5179, line, column [n_pixels]   (pixel centres; the pixel set is fixed)
  b07_K, b14_K [n_scans, n_pixels] float32           (NaN where missing)
  b07_minus_b14_K = b07_K − b14_K
Use --csv to also write a long table (time, lat, lon, b07, b07 − b14).

Needs: satpy 0.54, pyresample, pyproj (see the README for the pinned venv).
usage: fetch_ahi_kfs01.py --start 2025-03-24T18:00 --end 2025-03-25T18:00 --work DIR --out kfs01_ahi.npz [--csv out.csv.gz]
"""
import argparse, bz2, gzip, os, sys, time, urllib.request, warnings
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from pyproj import Transformer

warnings.filterwarnings('ignore')
BUCKET = 'https://noaa-himawari9.s3.amazonaws.com/AHI-L1b-Japan'
GRID = dict(x0=1085250.0, x1=1174125.0, y0=1815750.0, y1=1845375.0)


def fetch(url, path, attempts=4):
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'wfg-data-fetch/1'})
            with urllib.request.urlopen(req, timeout=120) as r, open(path + '.part', 'wb') as f:
                f.write(r.read())
            os.replace(path + '.part', path); return True
        except urllib.error.HTTPError as e:
            if e.code == 404: return False
            time.sleep(2 ** (i + 1))
        except Exception:
            time.sleep(2 ** (i + 1))
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--start', required=True); ap.add_argument('--end', required=True)
    ap.add_argument('--work', required=True); ap.add_argument('--out', required=True); ap.add_argument('--csv')
    a = ap.parse_args()
    from satpy import Scene
    os.makedirs(a.work, exist_ok=True)
    slots = pd.date_range(pd.Timestamp(a.start, tz='UTC'), pd.Timestamp(a.end, tz='UTC'), freq='10min', inclusive='left')
    idx = None; meta = {}; times = []; b7s = []; b14s = []; missing = []
    for slot in slots:
        for jp in ['JP01', 'JP02', 'JP03', 'JP04']:
            names = {b: f'HS_H09_{slot:%Y%m%d_%H%M}_{b}_{jp}_R20_S0101.DAT.bz2' for b in ('B07', 'B14')}
            urls = {b: f'{BUCKET}/{slot:%Y/%m/%d/%H%M}/{n}' for b, n in names.items()}
            paths = {b: os.path.join(a.work, n) for b, n in names.items()}
            with ThreadPoolExecutor(2) as pool:
                ok = list(pool.map(lambda b: fetch(urls[b], paths[b]), ['B07', 'B14']))
            if not all(ok):
                missing.append(f'{slot:%Y-%m-%dT%H:%M} {jp}')
                for p in paths.values():
                    if os.path.exists(p): os.remove(p)
                continue
            try:
                scn = Scene(reader='ahi_hsd', filenames=list(paths.values()))
                scn.load(['B07', 'B14'])
                if idx is None:
                    lon, lat = scn['B07'].attrs['area'].get_lonlats()
                    x, y = Transformer.from_crs(4326, 5179, always_xy=True).transform(lon, lat)
                    m = np.isfinite(x) & (x >= GRID['x0']) & (x <= GRID['x1']) & (y >= GRID['y0']) & (y <= GRID['y1'])
                    idx = np.where(m)
                    meta = dict(lat=lat[idx].astype('float64'), lon=lon[idx].astype('float64'), x5179=x[idx], y5179=y[idx],
                                line=idx[0].astype('int32'), column=idx[1].astype('int32'))
                b7 = scn['B07'].values[idx].astype('float32'); b14 = scn['B14'].values[idx].astype('float32')
                times.append((str(scn['B07'].attrs['start_time']), str(scn['B07'].attrs['end_time']), jp, f'{slot:%Y-%m-%dT%H:%M}'))
                b7s.append(b7); b14s.append(b14)
            except Exception as ex:
                missing.append(f'{slot:%Y-%m-%dT%H:%M} {jp} decode-error {type(ex).__name__}')
            finally:
                for p in paths.values():
                    if os.path.exists(p): os.remove(p)
        print(f'{slot:%Y-%m-%d %H:%M} scans so far {len(times)} missing {len(missing)}', flush=True)
    B7, B14 = np.array(b7s), np.array(b14s)
    t = np.array(times)
    np.savez_compressed(a.out, scan_start_utc=t[:, 0], scan_end_utc=t[:, 1], scan_id=t[:, 2], slot=t[:, 3],
                        b07_K=B7, b14_K=B14, b07_minus_b14_K=B7 - B14, missing=np.array(missing), **meta)
    if a.csv:
        n_s, n_p = B7.shape
        df = pd.DataFrame(dict(scan_start_utc=np.repeat(t[:, 0], n_p), scan_id=np.repeat(t[:, 2], n_p),
                               lat=np.tile(meta['lat'], n_s).round(5), lon=np.tile(meta['lon'], n_s).round(5),
                               b07_K=B7.ravel().round(2), b07_minus_b14_K=(B7 - B14).ravel().round(2)))
        df.to_csv(a.csv, index=False, compression='gzip')
    print(f'DONE scans {len(times)} pixels {len(meta.get("lat", []))} missing {len(missing)}')


if __name__ == '__main__':
    main()
