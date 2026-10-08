#!/usr/bin/env python3
"""Acquire public environmental data and align to the 44 original TOA grids.

Run from any directory with the project's .venv Python. No downloaded code is run.
All stages are restartable; raw subsets and requests are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import shutil
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import rasterio
import requests
from affine import Affine
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds
from scipy.io import netcdf_file
from scipy.ndimage import uniform_filter
from scipy.spatial import cKDTree
from scipy.special import roots_legendre

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT.parent
ARCHIVE = BUNDLE / 'sources/zenodo_21788344/extracted'
NODATA = -9999.0
WX_VARS = ['temperature_2m', 'relative_humidity_2m',
           'precipitation', 'rain', 'wind_speed_10m', 'wind_direction_10m',
           'wind_gusts_10m', 'shortwave_radiation',
           'soil_moisture_0_to_7cm', 'soil_moisture_7_to_28cm']
LC_LAYERS = {'landcover_class': 'Discrete-Classification-map',
             'forest_type': 'Forest-Type-layer',
             **{f'{k.lower()}_cover_percent': f'{k}-CoverFraction-layer'
                for k in ['Tree', 'Shrub', 'Grass', 'Crops', 'Bare', 'BuiltUp',
                          'PermanentWater', 'SeasonalWater', 'Snow', 'MossLichen']}}
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'WildfireGuardian-research-data-acquisition/1.0'


def jsave(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def get(url, params=None, attempts=6):
    for attempt in range(attempts):
        try:
            r = SESSION.get(url, params=params, timeout=(30, 240))
            if r.status_code == 429 or r.status_code >= 500:
                delay = min(60, 10 * (attempt + 1))
                if 'Hourly API request limit' in r.text:
                    delay=60
                if 'Daily API request limit' in r.text:
                    raise RuntimeError('Daily public API limit reached; cached downloads preserved. Do not bypass the service limit.')
                print(f'RETRY HTTP {r.status_code} after {delay}s: {url}; {r.text[:200]}', flush=True)
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt + 1 == attempts:
                raise
            time.sleep(min(30, 3 * (attempt + 1)))
    raise RuntimeError(f'Public endpoint repeatedly unavailable: {url}')


def raw_response(path, url, params=None):
    path = Path(path)
    if not path.exists():
        r = get(url, params)
        tmp = path.with_suffix(path.suffix + '.part')
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(r.content)
        tmp.replace(path)
        jsave(path.with_suffix(path.suffix + '.source.json'),
              {'url': r.url, 'downloaded_utc': pd.Timestamp.now(tz='UTC').isoformat(),
               'content_type': r.headers.get('Content-Type'), 'kind': 'original_response'})
    return path


def grid(event):
    with rasterio.open(ROOT / event['arrival_path']) as src:
        return src.profile.copy(), src.read(1, masked=True), src.bounds


def write_tif(path, data, profile, names=None, tags=None, nodata=NODATA):
    a = np.asarray(data)
    if a.ndim == 2:
        a = a[None]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    p = dict(driver='GTiff', width=a.shape[2], height=a.shape[1], count=a.shape[0],
             dtype=a.dtype, crs=profile['crs'], transform=profile['transform'],
             nodata=nodata, compress='deflate', predictor=3 if a.dtype.kind == 'f' else 2,
             interleave='band',
             tiled=True, blockxsize=128, blockysize=128, BIGTIFF='IF_SAFER')
    if a.dtype.kind == 'f':
        a = np.where(np.isfinite(a), a, nodata).astype(a.dtype)
    temp = path.with_suffix('.part.tif')
    with rasterio.open(temp, 'w', **p) as dst:
        dst.write(a)
        if names:
            for i, name in enumerate(names, 1):
                dst.set_band_description(i, name)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    temp.replace(path)


def inventory():
    kr = pd.read_csv(ARCHIVE / 'results/kr_events_21.csv').set_index('id')
    us = pd.read_csv(ARCHIVE / 'results/us_selection_29.csv').set_index('incident', drop=False)
    events = []
    for file in sorted(ARCHIVE.glob('rasters_*/*_toa.tif')):
        with rasterio.open(file) as s:
            identifier = s.tags()['event']
            t0 = pd.Timestamp(s.tags()['t0_utc'], tz='UTC')
            a = s.read(1, masked=True)
            start = min(t0, t0 + pd.Timedelta(hours=float(a.min())))
            end = t0 + pd.Timedelta(hours=float(a.max()))
            country = 'KR' if identifier.startswith('KFS_') else 'US'
            if country == 'KR':
                row = kr.loc[identifier]
                name = str(row.locality)
                window = 't0 and finite reconstructed arrival range; not an official containment time'
            else:
                row = us.loc[identifier]
                name = str(row.incident).split('_', 1)[1]
                start = min(start, pd.Timestamp(row.window_start_utc, tz='UTC'))
                end = max(end, pd.Timestamp(row.window_end_utc, tz='UTC'))
                window = 'union of NIROPS survey window, t0 and finite reconstructed arrival range'
            start, end = start.floor('h'), end.ceil('h')
            out = ROOT / 'regions' / identifier
            out.mkdir(parents=True, exist_ok=True)
            arrival = out / 'arrival_time_hours.tif'
            shutil.copy2(file, arrival)
            std = file.with_name(file.name.replace('_toa.tif', '_std.tif'))
            if std.exists():
                shutil.copy2(std, out / 'kriging_std_hours.tif')
            bounds = transform_bounds(s.crs, 'EPSG:4326', *s.bounds, densify_pts=51)
            e = dict(id=identifier, name=name, country=country,
                     year=int(t0.year), t0_utc=t0.isoformat(),
                     start_utc=start.isoformat(), end_utc=end.isoformat(),
                     acquisition_window_basis=window,
                     rain_history_start_utc=(start - pd.Timedelta(days=30)).isoformat(),
                     arrival_path=str(arrival.relative_to(ROOT)),
                     source_arrival_path=str(file.relative_to(BUNDLE)),
                     width=s.width, height=s.height, epsg=s.crs.to_epsg(),
                     transform=list(s.transform)[:6], bounds_wgs84=list(bounds),
                     resolution_m=[375, 375], burned_label='retrospective reconstructed arrival',
                     valid_arrival_pixels=int(a.count()))
            jsave(out / 'grid.json', e)
            events.append(e)
    assert len(events) == 44
    jsave(ROOT / 'events.json', events)
    pd.DataFrame(events).drop(columns=['transform', 'bounds_wgs84']).to_csv(ROOT / 'catalog.csv', index=False)
    print('INVENTORY 44 exact reference grids', flush=True)


def event_xy(e):
    t = Affine(*e['transform'])
    x, y = np.meshgrid(t.c + (np.arange(e['width']) + .5) * t.a,
                       t.f + (np.arange(e['height']) + .5) * t.e)
    return x, y


GAUSSIAN_LATITUDES = np.degrees(np.arcsin(roots_legendre(2560)[0]))


def o1280_key(latitude, longitude):
    row=int(np.argmin(np.abs(GAUSSIAN_LATITUDES-latitude)))
    nlon=4*(min(row,2559-row)+1)+16
    return row,int(round(longitude/360*nlon))%nlon


def o1280_locations(e,p):
    """Closest model node to every target pixel, from documented O1280 geometry.

    Compare the closest latitude circle and its neighbours in the target metric
    projection. Verify every returned API centroid against the requested node.
    This removes redundant API requests used only to discover the grid.
    """
    x,y=event_xy(e)
    lon,lat=Transformer.from_crs(p['crs'],4326,always_xy=True).transform(x.ravel(),y.ravel())
    upper=np.searchsorted(GAUSSIAN_LATITUDES,lat)
    lower=upper-1
    near=np.where(abs(GAUSSIAN_LATITUDES[lower]-lat)<abs(GAUSSIAN_LATITUDES[upper]-lat),lower,upper)
    best=np.full(lat.shape,np.inf);brow=np.zeros(lat.shape,'int32');bcol=brow.copy()
    project=Transformer.from_crs(4326,p['crs'],always_xy=True)
    for off in [-1,0,1]:
        row=near+off
        nlon=4*(np.minimum(row,2559-row)+1)+16
        col=np.rint(lon*nlon/360).astype('int32')
        nnlat=GAUSSIAN_LATITUDES[row];nnlon=col*360/nlon
        xx,yy=project.transform(nnlon,nnlat)
        d=(xx-x.ravel())**2+(yy-y.ravel())**2
        use=d<best;best[use]=d[use];brow[use]=row[use];bcol[use]=col[use]
    keys=sorted(set(zip(brow.tolist(),bcol.tolist())))
    points=[]
    for row,col in keys:
        nlon=4*(min(row,2559-row)+1)+16
        points.append((float(GAUSSIAN_LATITUDES[row]),col*360/nlon))
    return points


def era5_locations(e,p):
    x,y=event_xy(e)
    lon,lat=Transformer.from_crs(p['crs'],4326,always_xy=True).transform(x.ravel(),y.ravel())
    nearrow=np.rint(lat*4).astype('int32');nearcol=np.rint(lon*4).astype('int32')
    best=np.full(lat.shape,np.inf);brow=nearrow.copy();bcol=nearcol.copy()
    project=Transformer.from_crs(4326,p['crs'],always_xy=True)
    for dy in [-1,0,1]:
        for dx in [-1,0,1]:
            row=nearrow+dy;col=nearcol+dx
            xx,yy=project.transform(col/4,row/4)
            d=(xx-x.ravel())**2+(yy-y.ravel())**2
            use=d<best;best[use]=d[use];brow[use]=row[use];bcol[use]=col[use]
    return [(r/4,c/4) for r,c in sorted(set(zip(brow.tolist(),bcol.tolist())))]


def weather(e, model='ecmwf_ifs'):
    out = ROOT / 'regions' / e['id'] / 'weather'
    marker = out / f'{model}_complete.json'
    if marker.exists():
        return
    p, _, _ = grid(e)
    variables = WX_VARS if model == 'ecmwf_ifs' else ['boundary_layer_height']
    start, end = pd.Timestamp(e['start_utc']), pd.Timestamp(e['end_utc'])
    hist = start - pd.Timedelta(days=30) if model=='ecmwf_ifs' else start
    common = dict(models=model, timezone='UTC', elevation=None, cell_selection='nearest',
                  wind_speed_unit='ms', temperature_unit='celsius', precipitation_unit='mm')
    raw = ROOT / 'raw' / e['id'] / 'weather' / model
    locations = o1280_locations(e,p) if model=='ecmwf_ifs' else era5_locations(e,p)
    all_times = pd.date_range(hist.floor('D'), end.floor('D') + pd.Timedelta(hours=23), freq='h')
    values = {v: np.full((len(all_times), len(locations)), np.nan, 'float32') for v in variables}
    units = {}
    covered=np.zeros((len(all_times),len(locations)),dtype=bool)
    dependencies=[]
    # Reuse overlapping original responses, including partial runs. Coverage is
    # based on timestamps and requested keys, not on nonmissing values.
    if model=='ecmwf_ifs':
        keyindex={o1280_key(*loc):j for j,loc in enumerate(locations)}
        for cached in sorted((ROOT/'raw').glob('*/weather/ecmwf_ifs/hourly_*.json')):
            if cached.name.endswith('.source.json'):continue
            records=json.loads(cached.read_text())
            reused=False
            for item in records if isinstance(records,list) else [records]:
                key=o1280_key(item['latitude'],item['longitude'])
                if key not in keyindex or not all(v in item.get('hourly',{}) for v in variables):continue
                j=keyindex[key]
                idx=all_times.get_indexer(pd.to_datetime(item['hourly']['time'],utc=True))
                use=idx>=0
                if not use.any():continue
                for v in variables:
                    values[v][idx[use],j]=np.asarray(item['hourly'][v],dtype='float32')[use]
                covered[idx[use],j]=True
                units.update(item['hourly_units'])
                locations[j]=(item['latitude'],item['longitude'])
                reused=True
            if reused:dependencies.append(str(cached.relative_to(ROOT)))
    groups={}
    for j in range(len(locations)):
        missing=np.flatnonzero(~covered[:,j])
        if len(missing):
            # Typically only a leading/trailing extension is missing. If both
            # ends are absent, the intervening cached period may be downloaded again.
            key=(all_times[missing[0]].strftime('%Y-%m-%d'),all_times[missing[-1]].strftime('%Y-%m-%d'))
            groups.setdefault(key,[]).append(j)
    batches=[]
    for dates,js in groups.items():
        for n in range(0,len(js),12):batches.append((dates,js[n:n+12]))
    for batchnum,(dates,js) in enumerate(batches):
        chunk=[locations[j] for j in js]
        params = dict(common, latitude=','.join(str(v[0]) for v in chunk),
                      longitude=','.join(str(v[1]) for v in chunk), elevation=','.join(['nan'] * len(chunk)),
                      start_date=dates[0], end_date=dates[1], hourly=','.join(variables))
        signature=hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest()[:16]
        path = raw_response(raw / f'hourly_cached_{signature}.json',
                            'https://archive-api.open-meteo.com/v1/archive', params)
        data = json.loads(path.read_text())
        items = data if isinstance(data, list) else [data]
        assert len(items) == len(chunk)
        for j, item in enumerate(items):
            # A nearest-cell query at its returned centroid must return the same cell.
            actual = (round(item['latitude'], 5), round(item['longitude'], 5))
            if model=='ecmwf_ifs':
                assert o1280_key(*actual)==o1280_key(*chunk[j]),(actual,chunk[j])
            else:assert actual == chunk[j], (actual, chunk[j])
            times = pd.to_datetime(item['hourly']['time'], utc=True)
            idx = all_times.get_indexer(times)
            assert np.all(idx >= 0)
            units.update(item['hourly_units'])
            for v in variables:
                values[v][idx, js[j]] = np.asarray(item['hourly'][v], dtype='float32')
            locations[js[j]]=(item['latitude'],item['longitude'])
            covered[idx,js[j]]=True
        dependencies.append(str(path.relative_to(ROOT)))
        print(f'WEATHER fetched {e["id"]} {model} batch {batchnum+1}/{len(batches)}, {len(locations)} total cells', flush=True)
        time.sleep(.4)
    assert covered.all(),e['id']
    if model == 'ecmwf_ifs':
        angle = np.deg2rad(values['wind_direction_10m'])
        values['wind_eastward_10m'] = -values['wind_speed_10m'] * np.sin(angle)
        values['wind_northward_10m'] = -values['wind_speed_10m'] * np.cos(angle)
        units.update(wind_eastward_10m='m/s', wind_northward_10m='m/s')
        rain = pd.DataFrame(values['precipitation'])
        for hours, label in [(24, '24h'), (168, '7d'), (720, '30d')]:
            values[f'precipitation_trailing_{label}'] = rain.rolling(hours, min_periods=hours).sum().to_numpy('float32')
            units[f'precipitation_trailing_{label}'] = 'mm'
        # Dry-hour streak is a lower bound if it extends to the start of the downloaded history.
        dry = np.full_like(values['precipitation'], np.nan)
        last = np.zeros(len(locations), 'float32')
        for i, row in enumerate(values['precipitation']):
            last = np.where(np.isfinite(row), np.where(row >= .1, 0, last + 1), np.nan)
            dry[i] = last
        values['dry_hours_since_ge_0p1mm_lower_bound'] = dry
        units['dry_hours_since_ge_0p1mm_lower_bound'] = 'h'
    # Preserve all source nodes and the full 30-day history without expanding redundant data.
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f'{model}_native_nodes.npz',
                        time_utc=all_times.strftime('%Y-%m-%dT%H:%M:%SZ').to_numpy(dtype='U20'),
                        latitude=np.array([v[0] for v in locations]),
                        longitude=np.array([v[1] for v in locations]), **values)
    xy = Transformer.from_crs(4326, p['crs'], always_xy=True)
    nx, ny = xy.transform([v[1] for v in locations], [v[0] for v in locations])
    xx, yy = event_xy(e)
    dist, indexes = cKDTree(np.c_[nx, ny]).query(np.c_[xx.ravel(), yy.ravel()])
    indexes = indexes.reshape(xx.shape)
    write_tif(out / f'{model}_node_index_375m.tif', indexes.astype('int32'), p, nodata=-1)
    write_tif(out / f'{model}_node_distance_m_375m.tif', dist.reshape(xx.shape).astype('float32'), p)
    chosen = (all_times >= start) & (all_times <= end)
    times = all_times[chosen]
    pd.DataFrame({'band': np.arange(1, len(times)+1), 'time_utc': times.strftime('%Y-%m-%dT%H:%M:%SZ')}).to_csv(out / f'{model}_bands.csv', index=False)
    availability = {}
    for v, a in values.items():
        a = a[chosen]
        availability[v] = dict(unit=units[v], finite_node_hours=int(np.isfinite(a).sum()),
                               total_node_hours=int(a.size))
        if not np.isfinite(a).any():
            print(f'UNAVAILABLE {e["id"]} {model} {v}', flush=True)
            continue
        file = out / f'{v}_375m.tif'
        pp = dict(driver='GTiff', width=e['width'], height=e['height'], count=len(times),
                  dtype='float32', crs=p['crs'], transform=p['transform'], nodata=NODATA,
                  tiled=True, blockxsize=128, blockysize=128, compress='deflate', predictor=3,
                  interleave='band',
                  BIGTIFF='IF_SAFER', NUM_THREADS='2')
        tmp = file.with_suffix('.part.tif')
        with rasterio.open(tmp, 'w', **pp) as dst:
            dst.update_tags(variable=v, unit=units[v], source_model=model,
                            native_resolution_km=9 if model=='ecmwf_ifs' else 25,
                            resampling='nearest returned model-cell centre', time_zone='UTC',
                            spatial_information='coarse source data resampled; not measured at 375m')
            for i in range(len(times)):
                band = a[i, indexes]
                dst.write(np.where(np.isfinite(band), band, NODATA).astype('float32'), i+1)
                dst.set_band_description(i+1, times[i].strftime('%Y-%m-%dT%H:%M:%SZ'))
        tmp.replace(file)
        print(f'WEATHER raster {e["id"]} {v}, {len(times)} bands',flush=True)
    jsave(marker, dict(model=model, native_resolution_km=9 if model=='ecmwf_ifs' else 25,
                      nodes=len(locations), hours=len(times), max_node_distance_m=float(dist.max()),
                      original_response_dependencies=sorted(set(dependencies)),
                      variables=availability, missing_is_nodata=True,
                      rain_and_solar_time_support='preceding hour; most other variables instantaneous',
                      boundary_layer_height_note='ERA5 mixing-depth proxy; not a direct stability/CAPE measurement'))
    print(f'WEATHER COMPLETE {e["id"]} {model}, {len(times)} hours', flush=True)


def remote_subset(url, file, bounds):
    file = Path(file)
    if file.exists():
        return file
    with rasterio.open(url) as src:
        bbox = transform_bounds(4326, src.crs, *bounds, densify_pts=31)
        w = from_bounds(*bbox, src.transform)
        col, row = math.floor(w.col_off)-2, math.floor(w.row_off)-2
        width, height = math.ceil(w.col_off+w.width)-col+2, math.ceil(w.row_off+w.height)-row+2
        w = Window(col, row, width, height).intersection(Window(0, 0, src.width, src.height))
        a = src.read(1, window=w)
        file.parent.mkdir(parents=True, exist_ok=True)
        prof = src.profile.copy()
        prof.update(driver='GTiff', width=a.shape[1], height=a.shape[0], count=1,
                    transform=src.window_transform(w), tiled=True, blockxsize=256, blockysize=256,
                    compress='deflate', BIGTIFF='IF_SAFER')
        tmp = file.with_suffix('.part.tif')
        with rasterio.open(tmp, 'w', **prof) as dst:
            dst.write(a, 1)
        tmp.replace(file)
        jsave(file.with_suffix('.tif.source.json'), dict(url=url, kind='native-grid spatial subset',
                  requested_bounds_wgs84=list(bounds), source_crs=str(src.crs),
                  source_transform=list(src.transform)[:6], source_window=list(w.flatten()),
                  source_nodata=src.nodata if src.nodata is not None and np.isfinite(src.nodata) else None,
                  downloaded_utc=pd.Timestamp.now(tz='UTC').isoformat()))
    return file


def warp_raw(file, p, method, invalid=None):
    with rasterio.open(file) as s:
        a = s.read(1, masked=True).filled(0).astype('float32')
        mask = s.read_masks(1) == 0
        if invalid is not None:
            mask |= invalid(a)
        a[mask] = NODATA
        dst = np.full((p['height'], p['width']), NODATA, 'float32')
        reproject(a, dst, src_transform=s.transform, src_crs=s.crs, src_nodata=NODATA,
                  dst_transform=p['transform'], dst_crs=p['crs'], dst_nodata=NODATA,
                  resampling=method, num_threads=2)
        dst[dst == NODATA] = np.nan
        return dst


def landcover(events):
    for name, layer in LC_LAYERS.items():
        url = f'https://zenodo.org/records/3939050/files/PROBAV_LC100_global_v3.0.1_2019-nrt_{layer}_EPSG-4326.tif'
        for e in events:
            out = ROOT / 'regions' / e['id'] / 'vegetation' / f'{name}_375m.tif'
            if out.exists():
                continue
            p, _, _ = grid(e)
            raw = remote_subset(url, ROOT / 'raw' / e['id'] / 'landcover_2019' / f'{name}.tif', e['bounds_wgs84'])
            categorical = name in ['landcover_class', 'forest_type']
            invalid = (lambda a: a == 0) if name == 'landcover_class' else (lambda a: a > 100) if not categorical else (lambda a: a > 5)
            a = warp_raw(raw, p, Resampling.mode if categorical else Resampling.average, invalid)
            write_tif(out, a, p, tags=dict(source='Copernicus Global Land Cover v3.0.1, 2019 NRT',
                      native_resolution_m=100, epoch=2019, unit='class code' if categorical else 'percent',
                      resampling='mode' if categorical else 'valid-pixel area-weighted average',
                      meaning='vegetation indicator, not measured dry fuel mass'))
            print(f'LANDCOVER {e["id"]} {name}', flush=True)


def terrain(e):
    out = ROOT / 'regions' / e['id'] / 'terrain'
    if (out / 'complete.json').exists():
        return
    p, _, b = grid(e)
    halo = 4  # 1.5 km; supports 9-cell neighbourhood terrain metrics
    pp = p.copy()
    pp.update(height=e['height']+2*halo, width=e['width']+2*halo,
              transform=p['transform'] * Affine.translation(-halo, -halo))
    factor = 12  # 31.25m intermediate grid, not finer than the nominal 30m DEM
    fine = pp.copy()
    fine.update(height=pp['height']*factor, width=pp['width']*factor,
                transform=pp['transform'] * Affine.scale(1/factor))
    fb = rasterio.transform.array_bounds(fine['height'], fine['width'], fine['transform'])
    bounds = transform_bounds(p['crs'], 4326, *fb, densify_pts=51)
    dem = np.full((fine['height'], fine['width']), NODATA, 'float32')
    sources = []
    for lat in range(math.floor(bounds[1]), math.floor(bounds[3])+1):
        for lon in range(math.floor(bounds[0]), math.floor(bounds[2])+1):
            tile = f'Copernicus_DSM_COG_10_{"N" if lat>=0 else "S"}{abs(lat):02d}_00_{"E" if lon>=0 else "W"}{abs(lon):03d}_00_DEM'
            url = f'https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif'
            clip = [max(bounds[0], lon), max(bounds[1], lat), min(bounds[2], lon+1), min(bounds[3], lat+1)]
            raw = remote_subset(url, ROOT / 'raw' / e['id'] / 'dem' / f'{tile}.tif', clip)
            with rasterio.open(raw) as s:
                reproject(s.read(1), dem, src_transform=s.transform, src_crs=s.crs,
                          src_nodata=s.nodata, dst_transform=fine['transform'], dst_crs=p['crs'],
                          dst_nodata=NODATA, resampling=Resampling.bilinear,
                          init_dest_nodata=False, num_threads=2)
            sources.append(url)
    dem[dem == NODATA] = np.nan
    dy, dx = np.gradient(dem, 31.25, 31.25)
    grade = np.hypot(dx, dy)
    slope = np.rad2deg(np.arctan(grade))
    # Array y increases southwards. The downslope north component is +dy.
    aspect = np.mod(np.arctan2(-dx, dy), 2*np.pi)
    aspect[grade < 1e-5] = np.nan
    def coarse(a):
        a = a.reshape(pp['height'], factor, pp['width'], factor)
        counts = np.isfinite(a).sum(axis=(1,3))
        return np.divide(np.nansum(a, axis=(1,3)), counts,
                         out=np.full(counts.shape,np.nan),where=counts>0).astype('float32')
    elev, sl = coarse(dem), coarse(slope)
    east, north = coarse(np.sin(aspect)), coarse(np.cos(aspect))
    aspect375 = np.mod(np.rad2deg(np.arctan2(east,north)),360)
    strength = np.hypot(east,north)
    aspect375[strength < 1e-5] = np.nan
    valid = np.isfinite(elev).astype('float32')
    mean = uniform_filter(np.nan_to_num(elev),9,mode='constant') / np.maximum(uniform_filter(valid,9,mode='constant'),1e-12)
    tpi = elev-mean
    mean2 = uniform_filter(np.nan_to_num(elev)**2,9,mode='constant') / np.maximum(uniform_filter(valid,9,mode='constant'),1e-12)
    std = np.sqrt(np.maximum(0,mean2-mean**2))
    crop = (slice(halo,-halo),slice(halo,-halo))
    fields = {'elevation_m':elev,'slope_degrees':sl,'aspect_degrees':aspect375,
              'aspect_eastness':east,'aspect_northness':north,
              'aspect_resultant_length':strength,'tpi_3375m_m':tpi,
              'elevation_std_3375m_m':std}
    for name,a in fields.items():
        write_tif(out / f'{name}_375m.tif',a[crop].astype('float32'),p,
                  tags=dict(source='Copernicus DEM GLO-30 2021 release; acquisition 2011-2015',
                            native_resolution_m=30, surface='DSM includes vegetation and buildings',
                            method='31.25m metric intermediate; slope and circular aspect aggregated before 375m output',
                            slope_reference='projected grid; approximate ground slope',
                            aspect_reference='clockwise from projected grid north'))
    jsave(out/'complete.json',dict(sources=sources, fine_resolution_m=31.25, halo_cells=halo,
                                  missing_pixels=int(np.sum(~np.isfinite(elev[crop])))))
    print(f'TERRAIN COMPLETE {e["id"]}',flush=True)


def canopy(e):
    out=ROOT/'regions'/e['id']/'vegetation/canopy_height_2019_m_375m.tif'
    if out.exists(): return
    region='NASIA' if e['country']=='KR' else 'NAM'
    url=f'https://glad.geog.umd.edu/Potapov/Forest_height_2019/Forest_height_2019_{region}.tif'
    raw=remote_subset(url,ROOT/'raw'/e['id']/'canopy_2019.tif',e['bounds_wgs84'])
    p,_,_=grid(e)
    a=warp_raw(raw,p,Resampling.average,lambda x:x>60)
    write_tif(out,a,p,tags=dict(source='UMD GLAD GEDI-Landsat 2019 forest height prototype',
              native_resolution='0.00025 degree, approximately 30m', epoch=2019,unit='m',
              zero='0 is a valid downloadable map height; 101 water,102 snow,103 missing excluded',
              limitations='model saturation above 30m; buildings and steep slopes can bias height'))
    print(f'CANOPY {e["id"]}',flush=True)


def canopy_worker(e):
    for attempt in range(4):
        try:
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT='240',
                              GDAL_HTTP_MAX_RETRY='4',GDAL_HTTP_RETRY_DELAY='3',
                              CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',CPL_VSIL_CURL_CACHE_SIZE=268435456):
                canopy(e)
            return
        except rasterio.errors.RasterioIOError:
            if attempt==3:raise
            print(f'CANOPY RETRY {e["id"]}, attempt {attempt+2}',flush=True)
            time.sleep(5*(attempt+1))


def gridmet(e):
    if e['country']!='US': return
    p,_,_=grid(e)
    start=pd.Timestamp(e['start_utc']).floor('D')-pd.Timedelta(days=30)
    end=pd.Timestamp(e['end_utc']).floor('D')
    w,s,ee,n=e['bounds_wgs84']
    for code,hours in [('fm100',100),('fm1000',1000)]:
        out=ROOT/'regions'/e['id']/'fuel_moisture'/f'{code}_daily_375m.tif'
        if out.exists():continue
        url=f'https://tds-proxy.nkn.uidaho.edu/thredds/ncss/grid/MET/{code}/{code}_{e["year"]}.nc'
        variable=f'dead_fuel_moisture_{hours}hr'
        params=dict(var=variable,north=n+.05,south=s-.05,west=w-.05,east=ee+.05,
                    time_start=start.strftime('%Y-%m-%dT00:00:00Z'),time_end=end.strftime('%Y-%m-%dT00:00:00Z'),
                    accept='netcdf',addLatLon='true')
        raw=raw_response(ROOT/'raw'/e['id']/'gridmet'/f'{code}.nc',url,params)
        with netcdf_file(raw,mmap=False) as nc:
            la=nc.variables['lat'][:].copy();lo=nc.variables['lon'][:].copy()
            v=nc.variables[variable];a=v[:].copy().astype('float32')
            a[a==v._FillValue]=NODATA
            valid=a!=NODATA;a[valid]=a[valid]*float(v.scale_factor)+float(v.add_offset)
            dates=pd.Timestamp('1900-01-01',tz='UTC')+pd.to_timedelta(nc.variables['day'][:].copy(),unit='D')
        if la[0]<la[-1]:la=la[::-1];a=a[:,::-1,:]
        tr=Affine(float(lo[1]-lo[0]),0,float(lo[0]-(lo[1]-lo[0])/2),0,
                  float(la[1]-la[0]),float(la[0]-(la[1]-la[0])/2))
        dst=np.full((len(dates),e['height'],e['width']),NODATA,'float32')
        for i in range(len(dates)):
            reproject(a[i],dst[i],src_transform=tr,src_crs='EPSG:4326',src_nodata=NODATA,
                      dst_transform=p['transform'],dst_crs=p['crs'],dst_nodata=NODATA,resampling=Resampling.nearest)
        write_tif(out,dst,p,names=[d.strftime('%Y-%m-%d') for d in dates],
                  tags=dict(source='gridMET',native_resolution_km=4,temporal_resolution='daily',
                            unit='percent of dry fuel mass',meaning=f'modeled {hours}-hour dead fuel moisture; not live/fine fuel moisture',
                            date_semantics='nominal midnight-to-midnight Mountain Standard Time; 07 UTC boundary',
                            temporal_resampling='none; daily values retained'))
        pd.DataFrame({'band':np.arange(1,len(dates)+1),'date_mst':dates.strftime('%Y-%m-%d')}).to_csv(out.with_suffix('.bands.csv'),index=False)
        print(f'GRIDMET {e["id"]} {code}, {len(dates)} daily maps',flush=True)


def landfire(e):
    if e['country']!='US':return
    p,_,b=grid(e)
    # Service native grid is 30m EPSG:5070, origin at -2362425,3177435.
    x0=-2362425+math.floor((b.left+2362425)/30)*30
    y1=3177435-math.floor((3177435-b.top)/30)*30
    width=math.ceil((b.right-x0)/30);height=math.ceil((y1-b.bottom)/30)
    bounds=(x0,y1-height*30,x0+width*30,y1)
    for code in ['FBFM40','FCCS','CH','CC','CBH','CBD']:
        out=ROOT/'regions'/e['id']/'fuel'/f'landfire_2016_{code.lower()}_375m.tif'
        if out.exists():continue
        url=f'https://lfps.usgs.gov/arcgis/rest/services/Landfire_LF2016/LF2016_{code}_CONUS/ImageServer/exportImage'
        params=dict(bbox=','.join(map(str,bounds)),bboxSR=5070,imageSR=5070,
                    size=f'{width},{height}',format='tiff',pixelType='S32' if code=='FCCS' else 'S16',
                    interpolation='RSP_NearestNeighbor',adjustAspectRatio='false',
                    renderingRule=json.dumps({'rasterFunction':'None'}),f='image',compression='LZ77')
        raw=raw_response(ROOT/'raw'/e['id']/'landfire_2016'/f'{code}.tif',url,params)
        with rasterio.open(raw) as src:
            assert src.count==1 and src.crs==p['crs'],(code,src.profile)
        cat=code in ['FBFM40','FCCS']
        a=warp_raw(raw,p,Resampling.mode if cat else Resampling.average,lambda x:x<0)
        # Keep the official integer encoding. Metadata/README supplies the conversion,
        # avoiding any unsupported inference about fuel load from a class label.
        write_tif(out,a,p,tags=dict(source='LANDFIRE 2016 Remap, LF2.0.0',product=code,
                  native_resolution_m=30,resampling='mode' if cat else 'valid-pixel area-weighted average',
                  units='official encoded product value; consult product legend',
                  temporal_note='static 2016 Remap baseline, including capable fuels conventions; not event-date field measurements'))
        print(f'LANDFIRE {e["id"]} {code}',flush=True)


def validate(events):
    rows=[];coverage=[];pending=[]
    validator_version=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for e in events:
        p,arrival,_=grid(e)
        region=ROOT/'regions'/e['id']
        expected=[region/'arrival_time_hours.tif',region/'kriging_std_hours.tif']
        if (ROOT/'biome_classes.json').exists():
            expected.append(region/'biome/biome_class_375m.tif')
        expected += [region/'vegetation'/f'{v}_375m.tif' for v in LC_LAYERS]
        expected += [region/'vegetation'/f'{v}_375m.tif' for v in
                     ['canopy_height_2019_m','vegetated_cover_percent','vegetation_neighbourhood_cover_1125m_percent']]
        expected += [region/'terrain'/f'{v}_375m.tif' for v in
                     ['elevation_m','slope_degrees','aspect_degrees','aspect_eastness','aspect_northness',
                      'aspect_resultant_length','tpi_3375m_m','elevation_std_3375m_m']]
        required=WX_VARS+['wind_eastward_10m','wind_northward_10m','precipitation_trailing_24h',
                         'precipitation_trailing_7d','precipitation_trailing_30d',
                         'dry_hours_since_ge_0p1mm_lower_bound','boundary_layer_height']
        expected += [region/'weather'/f'{v}_375m.tif' for v in required]
        if e['country']=='US':
            expected += [region/'fuel'/f'landfire_2016_{v}_375m.tif' for v in ['fbfm40','fccs','ch','cc','cbh','cbd']]
            expected += [region/'fuel'/f'{v}_375m.tif' for v in
                         ['canopy_height_m','canopy_base_height_m','canopy_bulk_density_kg_m3',
                          'canopy_cover_percent','fuel_loading_lookup_coverage_fraction']]
            expected += [region/'fuel'/f'{v}_tons_per_acre_375m.tif' for v in
                         ['total_available_fuel_loading','ladder_fuel_loading','litter_loading',
                          'overstory_loading','midstory_loading','understory_loading']]
            expected += [region/'fuel_moisture'/f'{v}_daily_375m.tif' for v in ['fm100','fm1000']]
        missing=[str(f.relative_to(ROOT)) for f in expected if not f.exists()]
        if missing:
            pending.append(dict(id=e['id'],missing_files=missing))
            print(f'VALIDATION PENDING {e["id"]}: {len(missing)} files',flush=True)
            continue
        assert not list(region.rglob('*.part.tif')),e['id']
        signature=[(str(f.relative_to(region)),f.stat().st_size,f.stat().st_mtime_ns)
                   for f in sorted(region.rglob('*')) if f.is_file()]
        signature_hash=hashlib.sha256(json.dumps(signature).encode()).hexdigest()
        checkpoint=ROOT/'validation_progress'/f'{e["id"]}.json'
        if checkpoint.exists():
            saved=json.loads(checkpoint.read_text())
            if saved['validator_version']==validator_version and saved['input_signature']==signature_hash:
                rows.append(saved['result']);coverage.extend(saved['weather_availability'])
                print(f'VALIDATION REUSED {e["id"]}: unchanged checked files',flush=True)
                continue
        coverage_start=len(coverage)
        # The two copied label rasters must remain byte-identical to the archive.
        for label,suffix in [('arrival_time_hours.tif','_toa.tif'),('kriging_std_hours.tif','_std.tif')]:
            src=BUNDLE/e['source_arrival_path']
            if suffix=='_std.tif':src=src.with_name(src.name.replace('_toa.tif','_std.tif'))
            assert hashlib.sha256(src.read_bytes()).digest()==hashlib.sha256((region/label).read_bytes()).digest()
        weather_data={};band_tables={};expected_hours=pd.date_range(e['start_utc'],e['end_utc'],freq='h')
        for model in ['ecmwf_ifs','era5']:
            wx=json.loads((region/f'weather/{model}_complete.json').read_text())
            assert wx['hours']==len(expected_hours)
            band_tables[model]=pd.read_csv(region/f'weather/{model}_bands.csv')
            timestamps=pd.to_datetime(band_tables[model].time_utc,utc=True)
            assert np.array_equal(timestamps.astype('int64'),expected_hours.astype('int64'))
            native=np.load(region/f'weather/{model}_native_nodes.npz')
            native_times=pd.to_datetime(native['time_utc'],utc=True)
            assert np.all(np.diff(native_times.astype('int64'))==3600*10**9)
            indexes_time=native_times.get_indexer(expected_hours)
            assert np.all(indexes_time>=0)
            if model=='ecmwf_ifs':assert native_times[0]<=expected_hours[0]-pd.Timedelta(days=30)
            with rasterio.open(region/f'weather/{model}_node_index_375m.tif') as s:node_map=s.read(1)
            assert node_map.min()>=0 and node_map.max()<len(native['latitude'])
            weather_data[model]=(native,indexes_time,node_map)
            for var,details in wx['variables'].items():
                coverage.append(dict(id=e['id'],country=e['country'],category='weather',variable=var,
                                     source=model,source_interval='hourly',
                                     finite_native_values=details['finite_node_hours'],
                                     total_native_values=details['total_node_hours'],
                                     native_availability_fraction=details['finite_node_hours']/details['total_node_hours']))
        files=sorted(region.rglob('*.tif'))
        checks=[]
        for file in files:
            with rasterio.open(file) as s:
                assert s.crs==p['crs'] and s.transform==p['transform'] and s.shape==arrival.shape,file
                assert s.res==(375,375),file
                compare_weather=file.parent.name=='weather' and s.tags().get('variable') is not None
                if compare_weather:
                    model=s.tags()['source_model'];var=s.tags()['variable']
                    native,time_map,node_map=weather_data[model]
                    assert s.count==len(expected_hours)
                    assert s.descriptions==tuple(band_tables[model].time_utc)
                # Read every band, checking successful decompression and missing-value metadata.
                finite=0;missing=0;minimum=None;maximum=None
                for i in range(0,s.count,32):
                    stop=min(i+32,s.count)
                    a=s.read(list(range(i+1,stop+1)),masked=True)
                    if compare_weather:
                        expected_values=native[var][time_map[i:stop]][:,node_map]
                        actual=a.filled(np.nan)
                        assert np.array_equal(actual,expected_values,equal_nan=True),(file,i)
                    vals=a.compressed()
                    vals=vals[np.isfinite(vals)]
                    finite+=len(vals);missing+=a.size-len(vals)
                    if len(vals):
                        minimum=float(vals.min()) if minimum is None else min(minimum,float(vals.min()))
                        maximum=float(vals.max()) if maximum is None else max(maximum,float(vals.max()))
                checks.append(dict(file=str(file.relative_to(ROOT)),bands=s.count,finite_values=finite,
                                   missing_values=missing,min=minimum,max=maximum))
                if s.tags().get('variable') in required:assert finite>0,file
                if 'cover_percent' in file.name and minimum is not None:
                    assert minimum>=-1e-4 and maximum<=100.0001,(file,minimum,maximum)
                if 'coverage_fraction' in file.name:assert minimum>=0 and maximum<=1.000001
                if file.parent.name=='biome':
                    assert s.count==1 and s.dtypes==('int16',) and s.nodata==NODATA
                    assert minimum is not None and minimum>=1 and maximum<=14
                if file.parent.name=='fuel_moisture':
                    dates=pd.read_csv(file.with_suffix('.bands.csv'))
                    dates=pd.to_datetime(dates.date_mst)
                    assert len(dates)==s.count and np.all(np.diff(dates.astype('int64'))==86400*10**9)
                    assert s.descriptions==tuple(dates.dt.strftime('%Y-%m-%d'))
                    assert minimum is not None and minimum>=0
        wx=json.loads((region/'weather/ecmwf_ifs_complete.json').read_text())
        rows.append(dict(id=e['id'],country=e['country'],raster_files=len(files),
                         hours=wx['hours'],weather_nodes=wx['nodes'],checks=checks,
                         exact_crs_transform_shape_resolution=True,
                         weather_all_pixels_all_hours_equal_native_node_mapping=True,
                         archive_label_copies_byte_identical=True,all_required_outputs_present=True))
        for native,_,_ in weather_data.values():native.close()
        jsave(checkpoint,dict(validator_version=validator_version,input_signature=signature_hash,
                              result=rows[-1],weather_availability=coverage[coverage_start:]))
        print(f'VALIDATED REGION {e["id"]}: {len(files)} rasters, {wx["hours"]} hourly timestamps',flush=True)
    pd.DataFrame(coverage).to_csv(ROOT/'weather_availability.csv',index=False)
    jsave(ROOT/'validation_summary.json',dict(regions=len(rows),expected_regions=len(events),passed=not pending,
          pending_regions=pending,
          checked_utc=pd.Timestamp.now(tz='UTC').isoformat(),
          raster_files=sum(r['raster_files'] for r in rows),
          raster_bands=sum(c['bands'] for r in rows for c in r['checks']),
          hourly_timestamps_across_regions=sum(r['hours'] for r in rows),
          regions_detail=rows))
    if pending:
        print(f'VALIDATION INCOMPLETE: {len(rows)} checked, {len(pending)} waiting for downloads',flush=True)
        return
    manifest=[]
    for file in sorted(ROOT.rglob('*')):
        if not file.is_file() or file.name in ['file_manifest.json'] or file.suffix=='.pyc':continue
        h=hashlib.sha256()
        with file.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        manifest.append(dict(path=str(file.relative_to(ROOT)),bytes=file.stat().st_size,sha256=h.hexdigest()))
    jsave(ROOT/'file_manifest.json',manifest)
    print(f'VALIDATED {len(rows)} regions, {sum(r["raster_files"] for r in rows)} exact-grid GeoTIFFs',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['inventory','weather','boundary_layer','landcover','terrain','canopy','gridmet','landfire','validate'])
    parser.add_argument('--event',action='append')
    args=parser.parse_args()
    if args.stage=='inventory':inventory();return
    events=json.loads((ROOT/'events.json').read_text())
    if args.event:events=[e for e in events if e['id'] in args.event]
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT='240',
                      GDAL_HTTP_MAX_RETRY='4',GDAL_HTTP_RETRY_DELAY='3',
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',CPL_VSIL_CURL_CACHE_SIZE=268435456,
                      GDAL_CACHEMAX=256*1024*1024):
        if args.stage=='landcover':landcover(events)
        elif args.stage=='validate':validate(events)
        elif args.stage=='canopy':
            with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(canopy_worker,events))
        else:
            for e in events:
                if args.stage=='weather':weather(e)
                elif args.stage=='boundary_layer':weather(e,'era5')
                else:globals()[args.stage](e)


if __name__=='__main__':main()
