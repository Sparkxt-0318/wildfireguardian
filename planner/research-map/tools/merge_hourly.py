#!/usr/bin/env python3
"""Attach export_hourly_cumulative.py output (native EPSG:5179 event grid) to a region's 375 m cells.

usage: python tools/merge_hourly.py kfs01_hourly.npz uiseong_andong_2025 [yeongdeok_2025 ...]
Writes ../.cache/hourly_<region>.json; tools/build_regions.py --only <region> then embeds it as bundle.hourly.
Values are sqrt-encoded uint8 (v = round(sqrt(p) * 255)). A synthetic rehearsal export is refused at build time."""
import sys, json, base64
from pathlib import Path
import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
if len(sys.argv) < 3:
    sys.exit(__doc__)
src, regions = sys.argv[1], sys.argv[2:]
z = np.load(src, allow_pickle=False)
meta = json.loads(str(z['meta_json']))
for rid in regions:
  js = (ROOT / 'site/regions' / f'{rid}.js').read_text()
  B = json.loads(js[js.index('=', js.index(']')) + 1:].rstrip().rstrip(';'))
  out = ROOT / '.cache' / f'hourly_{rid}.json'; out.parent.mkdir(parents=True, exist_ok=True)
  C = B['cells']; NR, NC = C['nr'], C['nc']
  lat = np.array(C['lattice']).reshape(NR + 1, NC + 1, 2)
  cen = (lat[:-1, :-1] + lat[1:, 1:] + lat[:-1, 1:] + lat[1:, :-1]) / 4
  a, b, c, d, e, f = z['affine_transform'][:6]
  tr = Transformer.from_crs(4326, int(z['epsg']), always_xy=True)
  x, y = tr.transform(cen[..., 0].ravel(), cen[..., 1].ravel())
  col = np.floor((np.asarray(x) - c) / a).astype(int); row = np.floor((np.asarray(y) - f) / e).astype(int)
  H = len(meta['hours']); enc = lambda v: np.clip(np.round(np.sqrt(np.clip(v, 0, 1)) * 255), 0, 255).astype(np.uint8)
  res = dict(meta={k: meta[k] for k in ('event', 'cutoffs', 'hours', 'n_samples', 'seed', 'env', 'method', 'boundary', 'missing_burned_area', 'checkpoint_sha256', 'generated_at')},
             p=[], se=[], valid=[], expected_new_km2=[], event_grid_expected_new_km2=[r['expected_new_km2'] for r in meta['runs']],
             synthetic=bool(meta.get('synthetic_test_only')))
  for k in range(len(meta['cutoffs'])):
      P = z[f'c{k}_probability']; S = z[f'c{k}_mc_standard_error']; V = z[f'c{k}_valid']
      hgt, wid = P.shape[-2:]
      inside = (row >= 0) & (row < hgt) & (col >= 0) & (col < wid)
      rr, cc = np.where(inside, row, 0), np.where(inside, col, 0)
      p = np.where(inside[None], P[:, rr, cc], 0); s = np.where(inside[None], S[:, rr, cc], 0); v = inside & V[:, rr, cc].all(0)
      p = np.where(v[None], p, 0); s = np.where(v[None], s, 0)
      res['p'].append(base64.b64encode(enc(p).tobytes()).decode()); res['se'].append(base64.b64encode(enc(s).tobytes()).decode())
      res['valid'].append(base64.b64encode(v.astype(np.uint8).tobytes()).decode())
      res['expected_new_km2'].append([round(float(p[h].sum()) * 0.140625, 4) for h in range(H)])  # map-area cells only
      print(rid, meta['cutoffs'][k], 'cells mapped', int(inside.sum()), 'valid', int(v.sum()), 'max F(H)', float(p[-1].max()))
  json.dump(res, open(out, 'w'), separators=(',', ':'))
  print('wrote', out)
