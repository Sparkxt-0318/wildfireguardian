#!/usr/bin/env python3
"""Add physical canopy units, reference fuel loads, and land-cover indicators.

Fuel loads are looked up on the native 30m fuelbed grid BEFORE aggregation.
No fuel load is inferred from the modal 375m fuelbed class.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy.ndimage import uniform_filter

if __package__:
    from .acquire_environment import ROOT, NODATA, grid, write_tif, jsave
else:  # Compatibility with direct execution of this file.
    from acquire_environment import ROOT, NODATA, grid, write_tif, jsave


def enrich(e):
    region=ROOT/'regions'/e['id']
    p,_,_=grid(e)
    veg=region/'vegetation'
    names=['tree','shrub','grass','crops']
    cover=[]
    for name in names:
        with rasterio.open(veg/f'{name}_cover_percent_375m.tif') as s:
            cover.append(s.read(1,masked=True).filled(np.nan))
    # This sum is vegetation coverage, not fuel mass or a fire-spread calibration.
    a=np.stack(cover)
    total=np.sum(a,axis=0)
    write_tif(veg/'vegetated_cover_percent_375m.tif',total.astype('float32'),p,
              tags={'definition':'tree + shrub + grass + crop percentage; all four must be available',
                    'meaning':'vegetation-cover indicator, not available combustible fuel mass',
                    'epoch':2019})
    # A neighbourhood coverage metric on the 375m grid; no inferred subpixel connections.
    valid=np.isfinite(total).astype('float32')
    count=uniform_filter(valid,3,mode='constant')
    neigh=np.divide(uniform_filter(np.nan_to_num(total),3,mode='constant'),count,
                    out=np.full(total.shape,np.nan,'float32'),where=count>0)
    write_tif(veg/'vegetation_neighbourhood_cover_1125m_percent_375m.tif',neigh.astype('float32'),p,
              tags={'definition':'mean vegetation coverage over available cells of a 3x3 neighbourhood',
                    'meaning':'horizontal continuity proxy; does not resolve gaps within a 375m cell',
                    'edge_policy':'truncated neighbourhood; no zero padding of missing land'})
    for name in ['bare','builtup','permanentwater','seasonalwater','snow']:
        # Actual cover fractions remain separate; do not declare all built-up land nonburnable.
        assert (veg/f'{name}_cover_percent_375m.tif').exists()
    if e['country']!='US':return
    fuel=region/'fuel'
    for code,scale,unit,output in [('ch',.1,'m','canopy_height_m'),
                                  ('cbh',.1,'m','canopy_base_height_m'),
                                  ('cbd',.01,'kg/m3','canopy_bulk_density_kg_m3'),
                                  ('cc',1.,'percent','canopy_cover_percent')]:
        with rasterio.open(fuel/f'landfire_2016_{code}_375m.tif') as s:
            a=s.read(1,masked=True).filled(np.nan)
        write_tif(fuel/f'{output}_375m.tif',(a*scale).astype('float32'),p,
                  tags={'source':f'LANDFIRE 2016 Remap {code.upper()}', 'unit':unit,
                        'conversion_from_official_encoding':scale,
                        'meaning':'area mean including zero canopy on nonforest pixels; not a field measurement',
                        'source_document':f'https://www.landfire.gov/fuel/{code}'})
    lookup=pd.read_csv(ROOT/'sources/LF_ConsumeLoadings.csv')
    assert not lookup.FCCS.duplicated().any()
    lookup=lookup.set_index('FCCS')
    raw=ROOT/'raw'/e['id']/'landfire_2016/FCCS.tif'
    with rasterio.open(raw) as s:
        ids=s.read(1)
        assert ids.dtype=='int32',ids.dtype
        unique,inverse=np.unique(ids,return_inverse=True)
        table=lookup.reindex(unique)
        # A zero-loading reference row is not sufficient evidence that every
        # zero-coded map pixel has no fuel. Some such pixels have burnable FBFM40
        # codes. Conservatively exclude zero from loading inference.
        matched=np.isin(unique,lookup.index)&(unique>0)
        fields={'total_available_fuel_loading':'Total_available_fuel_loading',
                'ladder_fuel_loading':'ladderfuels_loading',
                'litter_loading':'litter_loading',
                'overstory_loading':'overstory_loading',
                'midstory_loading':'midstory_loading',
                'understory_loading':'understory_loading'}
        for name,column in fields.items():
            v=pd.to_numeric(table[column],errors='coerce').to_numpy('float32')
            v[~matched]=np.nan
            a=v[inverse].reshape(ids.shape)
            a=np.where(np.isfinite(a),a,NODATA).astype('float32')
            dst=np.full((e['height'],e['width']),NODATA,'float32')
            reproject(a,dst,src_transform=s.transform,src_crs=s.crs,src_nodata=NODATA,
                      dst_transform=p['transform'],dst_crs=p['crs'],dst_nodata=NODATA,
                      resampling=Resampling.average,num_threads=2)
            write_tif(fuel/f'{name}_tons_per_acre_375m.tif',dst,p,
                      tags={'source':'LANDFIRE LF_ConsumeLoadings.csv keyed by the original FCCS numeric map code',
                            'unit':'tons per acre, as published',
                            'meaning':'reference fuelbed loading estimate, not measured event-date fuel amount',
                            'method':'native 30m code lookup, then valid-pixel area-weighted mean',
                            'lookup_download_date':'see source provenance',
                            'unmatched_codes':'NoData; zero-coded fuelbeds also excluded; coverage fraction provided separately'})
        cov=matched[inverse].reshape(ids.shape).astype('float32')
        dst=np.zeros((e['height'],e['width']),'float32')
        reproject(cov,dst,src_transform=s.transform,src_crs=s.crs,
                  dst_transform=p['transform'],dst_crs=p['crs'],resampling=Resampling.average)
        write_tif(fuel/'fuel_loading_lookup_coverage_fraction_375m.tif',dst,p,
                  tags={'meaning':'fraction of intersecting 30m fuelbed pixels with a positive matching lookup entry; zero/unassigned excluded'})
        jsave(fuel/'fuel_loading_lookup_report.json',
              {'native_pixels':int(ids.size),'matched_pixels':int(matched[inverse].sum()),
               'unmatched_codes':[int(v) for v in unique[~matched]],
               'zero_code_policy':'excluded from loading inference; do not interpret as measured zero fuel',
               'lookup_source':'https://www.landfire.gov/sites/default/files/CSV/LF_ConsumeLoadings.csv',
               'lookup_scope':'current public reference library; not event-date field measurements',
               'lookup_grid':'native 30m pixels before 375m aggregation'})
    print('ENRICHED',e['id'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--event',action='append');args=p.parse_args()
    events=json.loads((ROOT/'events.json').read_text())
    for e in events:
        if not args.event or e['id'] in args.event:enrich(e)
