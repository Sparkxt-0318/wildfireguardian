#!/usr/bin/env python3
"""Integrate an audited biome extension without rereading old weather bands.

Prior checks are retained only after scientific-file SHA-256 verification.
The baseline report/manifest are saved once. They are never resealed to accept
changed scientific inputs; such changes require the full environment validator.
"""
from __future__ import annotations

import json
from importlib.metadata import version

import pandas as pd

if __package__:
    from .acquire_biome import ROOT, sha256
else:  # Compatibility with direct execution of this file.
    from acquire_biome import ROOT, sha256
if __package__:
    from .acquire_environment import jsave
else:  # Compatibility with direct execution of this file.
    from acquire_environment import jsave


def main():
    base_manifest = ROOT/'biome_validation_baseline_manifest.json'
    base_summary = ROOT/'biome_validation_baseline_summary.json'
    if base_manifest.exists() != base_summary.exists():
        raise ValueError('Incomplete biome validation baseline; inspect before continuing')
    if not base_manifest.exists():
        current = json.loads((ROOT/'validation_summary.json').read_text())
        if not current['passed'] or any('/biome/' in c['file'] for r in current['regions_detail'] for c in r['checks']):
            raise ValueError('Need a passed pre-biome baseline report')
        base_manifest.write_bytes((ROOT/'file_manifest.json').read_bytes())
        base_summary.write_bytes((ROOT/'validation_summary.json').read_bytes())
    baseline = json.loads(base_summary.read_text())
    manifest = json.loads(base_manifest.read_text())
    manifest_by_path = {r['path']: r for r in manifest}
    # Original scientific data, their source/quality metadata, and event grids
    # must remain exactly the same bytes as at the prior full validation.
    old_files = [r for r in manifest if r['path'].startswith(('regions/', 'raw/', 'sources/', 'quality_flags/'))
                 or r['path']=='events.json']
    for record in old_files:
        path = ROOT/record['path']
        if not path.is_file() or path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
            raise ValueError(f'Previously validated scientific file changed: {record["path"]}; run the full validator')
    biome = json.loads((ROOT/'biome_validation.json').read_text())
    events = json.loads((ROOT/'events.json').read_text())
    assert baseline['passed'] and biome['passed'] and len(events)==44
    assert biome['regions']==biome['expected_regions']==len(events)
    assert biome['acquisition_code_sha256']==sha256(ROOT/'acquire_biome.py')
    by_id = {r['event_id']:r for r in biome['regions_detail']}
    assert set(by_id)=={e['id'] for e in events}
    expected_files = set()
    for region in baseline['regions_detail']:
        for c in region['checks']:
            assert c['file'] in manifest_by_path
            expected_files.add(c['file'])
        b = by_id[region['id']]
        assert b['passed'] and b['exact_reference_grid'] and b['all_pixel_centres_checked']
        assert b['independent_projected_rasterization_disagreements']==0
        assert sha256(ROOT/b['file'])==b['sha256']
        region['checks'].append(dict(file=b['file'],bands=1,finite_values=b['valid_pixels'],
                                     missing_values=b['missing_pixels'],
                                     min=min(b['biome_codes']) if b['biome_codes'] else None,
                                     max=max(b['biome_codes']) if b['biome_codes'] else None))
        region['raster_files']+=1
        region['biome_all_pixel_centres_checked']=True
        expected_files.add(b['file'])
    actual_files = {str(p.relative_to(ROOT)) for p in (ROOT/'regions').rglob('*.tif')}
    assert actual_files==expected_files, 'Unexpected or unchecked main region TIFFs'
    baseline['previous_full_validation_checked_utc']=baseline['checked_utc']
    baseline['checked_utc']=pd.Timestamp.now(tz='UTC').isoformat()
    baseline['raster_files']=sum(r['raster_files'] for r in baseline['regions_detail'])
    baseline['raster_bands']=sum(c['bands'] for r in baseline['regions_detail'] for c in r['checks'])
    baseline['incremental_extension']=dict(
        product='RESOLVE Ecoregions 2017 biomes', new_rasters=len(by_id),
        method='Verify prior scientific files by SHA-256 and retain prior full-band checks; add newly audited biome rasters',
        prior_scientific_files_verified_byte_identical=len(old_files),
        prior_full_validation_code_sha256=manifest_by_path['acquire_environment.py']['sha256'],
        baseline_summary_sha256=sha256(base_summary), baseline_manifest_sha256=sha256(base_manifest),
        biome_validation_report_sha256=sha256(ROOT/'biome_validation.json'),
        biome_every_pixel_independent_geometry_check=True,
        old_weather_bands_newly_reread=False)
    jsave(ROOT/'validation_summary.json',baseline)

    for filename,key in [('coverage_by_fire.csv','event_id'),('catalog.csv','id')]:
        table = pd.read_csv(ROOT/filename)
        table['biome_product']='RESOLVE Ecoregions 2017'
        table['biome_version']=2017
        table['biome_codes']=[';'.join(map(str,by_id[v]['biome_codes'])) for v in table[key]]
        table['biome_valid_fraction']=[by_id[v]['valid_fraction'] for v in table[key]]
        table['biome_missing_arrival_pixels']=[by_id[v]['biome_missing_arrival_pixels'] for v in table[key]]
        table.to_csv(ROOT/filename,index=False)
    coverage = pd.read_csv(ROOT/'requirements_coverage.csv')
    coverage = coverage[coverage.requested_condition!='biome']
    item = dict(requested_condition='biome',coverage='all 44 fires; uncovered pixels masked',
                downloaded_representation='RESOLVE 2017 categorical biome ID with 14-class global legend',
                native_information_scale='broad terrestrial ecoregion polygons; not 375m observations',
                time_support='static 2017 biogeographic classification',region_subfolder='biome/',
                limitation='720 uncovered target pixels, including 16 finite-arrival pixels; no local fuel inventory or hourly changes')
    pd.concat([coverage,pd.DataFrame([item])],ignore_index=True).to_csv(ROOT/'requirements_coverage.csv',index=False)
    software = json.loads((ROOT/'software_versions.json').read_text())
    software['packages'].update({name:version(name) for name in ('pyshp','shapely')})
    software['recorded_utc']=pd.Timestamp.now(tz='UTC').isoformat()
    jsave(ROOT/'software_versions.json',software)
    updated=[]
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and p.name!='file_manifest.json' and p.suffix!='.pyc':
            updated.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha256(p)))
    jsave(ROOT/'file_manifest.json',updated)
    print('INVENTORY UPDATED',len(events),'fires,',baseline['raster_files'],'main rasters,',
          baseline['raster_bands'],'bands;',len(old_files),'prior scientific files unchanged',flush=True)


if __name__=='__main__':
    main()
