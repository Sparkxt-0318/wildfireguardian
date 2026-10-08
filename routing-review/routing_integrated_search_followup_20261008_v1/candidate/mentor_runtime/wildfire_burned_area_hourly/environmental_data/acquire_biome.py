#!/usr/bin/env python3
"""Acquire RESOLVE 2017 biomes and sample them on the original fire grids.

Classify target pixel centres against WGS84 source polygons. No interpolation
of categorical IDs, nearest-land extrapolation, or time-varying inference.
Run with the workspace .venv Python; public downloading occurs only if uncached.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio
from rasterio.features import rasterize
import requests
import shapefile
import shapely
from shapely.geometry import box, mapping, shape
from shapely.ops import transform as transform_geometry

if __package__:
    from .acquire_environment import ROOT, event_xy, grid, jsave, write_tif
else:  # Compatibility with direct execution of this file.
    from acquire_environment import ROOT, event_xy, grid, jsave, write_tif

URL = 'https://storage.googleapis.com/teow2016/Ecoregions2017.zip'
SOURCE = ROOT / 'sources/resolve_ecoregions_2017'
NODATA = -9999


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def acquire_source():
    archive = SOURCE / 'Ecoregions2017.zip'
    SOURCE.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        temp = archive.with_suffix('.zip.part')
        with requests.get(URL, stream=True, timeout=(30, 240)) as response:
            response.raise_for_status()
            with temp.open('wb') as f:
                for block in response.iter_content(1024 * 1024):
                    f.write(block)
            temp.replace(archive)
            jsave(SOURCE / 'source.json', dict(
                url=URL, downloaded_utc=pd.Timestamp.now(tz='UTC').isoformat(),
                etag=response.headers.get('ETag'), provider='RESOLVE', version=2017,
                license='CC BY 4.0', source_page='https://ecoregions.world/',
                sha256=sha256(archive)))
    record = json.loads((SOURCE / 'source.json').read_text())
    if record['sha256'] != sha256(archive):
        raise ValueError('Cached RESOLVE archive hash does not match provenance')
    extracted = SOURCE / 'extracted'
    extracted.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('Source archive CRC check failed')
        for member in z.infolist():
            path = (extracted / member.filename).resolve()
            if not path.is_relative_to(extracted.resolve()):
                raise ValueError(f'Unsafe archive member: {member.filename}')
            # Verify cached extraction too, rather than trust mere existence.
            if not path.exists() or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(z.read(member)).digest():
                z.extract(member, extracted)
    return extracted / 'Ecoregions2017.shp'


def read_catalog(path):
    # This DBF supplies LDID 0x57 without a .cpg; its names decode with cp1252.
    reader = shapefile.Reader(str(path), encoding='cp1252')
    records = [r.as_dict() for r in reader.iterRecords()]
    classes, excluded = {}, []
    for i, r in enumerate(records):
        if r['ECO_ID'] == 0 or r['BIOME_NAME'] == 'N/A':
            excluded.append(dict(record_index=i, eco_id=r['ECO_ID'],
                                 eco_name=r['ECO_NAME'], nominal_biome_num=r['BIOME_NUM'],
                                 reason='Source BIOME_NAME is N/A; do not mislabel Rock and Ice as Tundra'))
            continue
        code, name = int(r['BIOME_NUM']), r['BIOME_NAME']
        if code in classes and classes[code]['name'] != name:
            raise ValueError(f'Inconsistent biome name for {code}')
        classes[code] = dict(code=code, name=name, color=r['COLOR_BIO'])
    if set(classes) != set(range(1, 15)):
        raise ValueError(f'Unexpected biome codes: {sorted(classes)}')
    legend = dict(product='RESOLVE Ecoregions 2017', source_url=URL,
                  source_page='https://ecoregions.world/', license='CC BY 4.0',
                  source_crs='EPSG:4326', shapefile_record_count=len(records),
                  classified_ecoregion_count=len(records)-len(excluded),
                  dbf_encoding='cp1252; DBF language driver ID 0x57',
                  classes=[classes[k] for k in sorted(classes)],
                  excluded_source_records=excluded, nodata=NODATA,
                  temporal_support='static biogeographic classification, version 2017',
                  interpretation='Broad terrestrial biomes; not current land cover, fuel type, or 375m observations',
                  assignment='Source polygon containing each projected target pixel centre transformed to WGS84',
                  missing_policy='Uncovered water, unclassified source areas and conflicting biomes are NoData')
    jsave(ROOT / 'biome_classes.json', legend)
    return reader, records, legend


def build_event(e, reader, records, excluded, source_digest):
    profile, arrival, _ = grid(e)
    x, y = event_xy(e)
    lon, lat = Transformer.from_crs(e['epsg'], 4326, always_xy=True).transform(x, y)
    # Bounds include a halo so artificial subset edges cannot reach a pixel centre.
    west, south, east, north = e['bounds_wgs84']
    bounds = (west-.01, south-.01, east+.01, north+.01)
    clip = box(*bounds)
    output = np.full(x.shape, NODATA, dtype='int16')
    conflict = np.zeros(x.shape, dtype=bool)
    features, projected, repaired = [], [], []
    forward = Transformer.from_crs(4326, e['epsg'], always_xy=True).transform
    for i, rec in enumerate(records):
        if i in excluded:
            continue
        native_shape = reader.shape(i, bbox=bounds)
        if native_shape is None:
            continue
        geometry = shape(native_shape.__geo_interface__)
        if not geometry.is_valid:
            geometry = shapely.make_valid(geometry)
            repaired.append(int(rec['ECO_ID']))
        geometry = geometry.intersection(clip)
        if geometry.is_empty:
            continue
        code = int(rec['BIOME_NUM'])
        properties = {k: rec[k] for k in ('ECO_ID', 'ECO_NAME', 'BIOME_NAME', 'REALM', 'LICENSE')}
        properties['BIOME_NUM'] = code
        features.append(dict(type='Feature', properties=properties, geometry=mapping(geometry)))
        projected.append((mapping(transform_geometry(forward, geometry)), code))
        shapely.prepare(geometry)
        present = shapely.intersects_xy(geometry, lon, lat)
        conflict |= present & (output != NODATA) & (output != code)
        output[present & (output == NODATA)] = code
    output[conflict] = NODATA
    region = ROOT / 'regions' / e['id'] / 'biome'
    raw = ROOT / 'raw' / e['id'] / 'resolve_biome_2017_subset.geojson'
    jsave(raw, dict(type='FeatureCollection', features=features))
    jsave(raw.with_suffix('.source.json'), dict(
        source_archive=str((SOURCE/'Ecoregions2017.zip').relative_to(ROOT)),
        source_archive_sha256=source_digest,
        source_crs='EPSG:4326', subset_bounds_wgs84=list(bounds),
        processing='Clip original polygons to target WGS84 bounds plus 0.01 degree halo; repair invalid geometries',
        repaired_ecoregion_ids=repaired))
    path = region / 'biome_class_375m.tif'
    write_tif(path, output, profile, ['RESOLVE 2017 BIOME_NUM'], nodata=NODATA,
              tags=dict(product='RESOLVE Ecoregions 2017', source_url=URL,
                        unit='categorical biome ID; see biome_classes.json', categorical='true',
                        temporal_support='static biogeographic classification; version 2017',
                        source_crs='EPSG:4326', source_geometry='terrestrial ecoregion polygons',
                        resampling='polygon membership at target pixel centre; no interpolation',
                        legend='biome_classes.json', missing_policy='uncovered or unclassified or conflicting biome: NoData',
                        license='CC BY 4.0'))
    # A second algorithm projects vectors and rasterizes them, independently of
    # the WGS84 point-membership classifier used to produce the output.
    comparison = rasterize(projected, out_shape=x.shape, transform=profile['transform'],
                           fill=NODATA, dtype='int16', all_touched=False)
    comparison[conflict] = NODATA
    differing = int(np.count_nonzero(output != comparison))
    if differing:
        raise ValueError(f'{e["id"]}: {differing} centre-membership/projected-rasterization disagreements')
    with rasterio.open(path) as s:
        assert s.shape == arrival.shape and s.crs == profile['crs']
        assert s.transform == profile['transform'] and s.res == (375, 375)
        assert s.count == 1 and s.dtypes == ('int16',) and s.nodata == NODATA
        a = s.read(1, masked=True)
        assert np.array_equal(a.data, output)
        assert np.array_equal(np.ma.getmaskarray(a), output == NODATA)
        assert set(np.unique(a.compressed())).issubset(set(range(1, 15)))
    valid = output != NODATA
    arrival_valid = ~np.ma.getmaskarray(arrival) & np.isfinite(arrival.data)
    codes, counts = np.unique(output[valid], return_counts=True)
    result = dict(event_id=e['id'], country=e['country'], epsg=e['epsg'],
                  height=e['height'], width=e['width'], pixel_size_m=375,
                  file=str(path.relative_to(ROOT)), sha256=sha256(path),
                  biome_codes=[int(k) for k in codes],
                  class_pixel_counts={str(int(k)): int(v) for k, v in zip(codes, counts)},
                  total_pixels=output.size, valid_pixels=int(valid.sum()),
                  missing_pixels=int((~valid).sum()), valid_fraction=float(valid.mean()),
                  valid_arrival_pixels=int(arrival_valid.sum()),
                  biome_covered_arrival_pixels=int((valid & arrival_valid).sum()),
                  biome_missing_arrival_pixels=int((~valid & arrival_valid).sum()),
                  conflicting_biome_pixels=int(conflict.sum()), repaired_ecoregion_ids=repaired,
                  retained_ecoregion_ids=sorted(int(f['properties']['ECO_ID']) for f in features),
                  exact_reference_grid=True, all_pixel_centres_checked=True,
                  independent_projected_rasterization_disagreements=differing, passed=True)
    jsave(region / 'biome_metadata.json', result)
    print('BIOME CHECKED', e['id'], 'codes', result['biome_codes'],
          f'{result["valid_pixels"]}/{result["total_pixels"]} pixels', flush=True)
    return result


def main():
    path = acquire_source()
    reader, records, legend = read_catalog(path)
    excluded = {r['record_index'] for r in legend['excluded_source_records']}
    events = json.loads((ROOT/'events.json').read_text())
    source_digest = sha256(SOURCE/'Ecoregions2017.zip')
    try:
        results = [build_event(e, reader, records, excluded, source_digest) for e in events]
    finally:
        reader.close()
    jsave(ROOT/'biome_validation.json', dict(
        passed=True, regions=len(results), expected_regions=len(events),
        checked_utc=pd.Timestamp.now(tz='UTC').isoformat(),
        source_archive_sha256=sha256(SOURCE/'Ecoregions2017.zip'),
        acquisition_code_sha256=sha256(Path(__file__)),
        scope='Every pixel of all target biome rasters; exact reference grids and independent polygon rasterization',
        regions_detail=results))
    table = pd.DataFrame(results).drop(columns=['class_pixel_counts', 'repaired_ecoregion_ids', 'retained_ecoregion_ids'])
    table['biome_names'] = ['; '.join(next(c['name'] for c in legend['classes'] if c['code']==code)
                                    for code in row['biome_codes']) for row in results]
    table.to_csv(ROOT/'biome_coverage.csv', index=False)
    print('BIOMES VALIDATED', len(results), 'fires', flush=True)


if __name__ == '__main__':
    main()
