"""Run a bounded real-data integration audit across all 44 event rectangles."""
import json
import hashlib
from pathlib import Path
import time

import numpy as np
import pandas as pd
import rasterio
import torch

from .dataset import WildfireSequenceDataset, collate_fire_sequences


def main():
    started=time.monotonic()
    dataset=WildfireSequenceDataset(sequence_length=2)
    raw=WildfireSequenceDataset(sequence_length=2,categorical_encoding='raw')
    output=Path(__file__).resolve().parent/'real_data_validation.json'
    assert dataset.source_channel_names==raw.channel_names
    rows=[]
    try:
        for ei,state in enumerate(dataset._events):
            index=dataset._ends[ei-1] if ei else 0
            sample=dataset[index];e=state['info'];x=sample['features'];mask=sample['feature_valid']
            original=raw[index]
            assert x.shape==(2,len(dataset.channel_names),e['height'],e['width'])
            assert sample['pixel_valid'].all() and sample['time_valid'].all()
            assert torch.isfinite(x).all()
            assert int(sample['channel_present'].sum())==sum(
                len(group) for name,group in dataset.channel_groups.items() if name in state['layers'])
            assert int(sample['epsg'])==e['epsg']
            assert sample['affine_transform'].tolist()==e['transform']
            assert np.all(np.diff(sample['time_utc'].numpy())==3600)
            categorical_checks=[]
            for j,info in enumerate(dataset.channel_info):
                name=info['source_channel']
                if name not in state['layers']:
                    assert not mask[:,j].any()
                    if info['encoding']=='one_hot':assert not x[:,j].any()
                    continue
                layer=state['layers'][name]
                if layer.role=='static':
                    assert torch.equal(x[0,j],x[1,j])
                if layer.role=='daily':
                    assert torch.all(sample['source_interval_end_utc'][:,j]<=sample['time_utc'])
                if info['encoding']!='one_hot':
                    old=raw.channel_names.index(name)
                    assert torch.equal(x[:,j],original['features'][:,old])
                    assert torch.equal(mask[:,j],original['feature_valid'][:,old])
                    assert torch.equal(sample['feature_quality'][:,j],original['feature_quality'][:,old])
            for name,group in dataset.channel_groups.items():
                if name not in dataset.categorical_classes or name not in state['layers']:continue
                with rasterio.open(state['layers'][name].path) as s:
                    source=s.read(1,masked=True,out_dtype='float64')
                expected_valid=(~np.ma.getmaskarray(source) & np.isfinite(source.data)
                                & np.isin(source.data,dataset.categorical_classes[name]))
                sums=np.zeros(source.shape,dtype='int16')
                for j in group:
                    code=dataset.channel_info[j]['class_code']
                    expected=expected_valid & (source.data==code)
                    for t in range(2):
                        assert np.array_equal(x[t,j].numpy(),expected)
                        assert np.array_equal(mask[t,j].numpy(),expected_valid)
                    sums+=x[0,j].numpy().astype('int16')
                assert np.array_equal(sums,expected_valid.astype('int16'))
                categorical_checks.append(dict(source_channel=name,classes=len(group),
                                                all_pixels_two_hours_equal_native_codes=True,
                                                one_hot_sum_equals_valid=True))
            for key in ('coordinates','affine_transform','time_utc','burned_area','burned_area_valid'):
                assert torch.equal(sample[key],original[key])
            with rasterio.open(dataset.root/'regions'/e['id']/'arrival_time_hours.tif') as s:
                a=s.read(1,masked=True)
                expected=((a.data[None]<=sample['elapsed_hours'].numpy()[:,None,None])
                          & ~np.ma.getmaskarray(a)[None])
                assert np.array_equal(sample['burned_area'][:,0].numpy(),expected)
            j=dataset.channel_names.index('weather.temperature_2m')
            with rasterio.open(state['layers']['weather.temperature_2m'].path) as s:
                a=s.read([1,2],masked=True)
                assert np.array_equal(x[:,j].numpy(),a.filled(0))
            assert len(dataset.channel_groups['biome.biome_class'])==14
            rows.append(dict(event_id=e['id'],shape=list(x.shape),
                             available_channels=int(sample['channel_present'].sum()),
                             first_hour_utc=pd.to_datetime(int(sample['time_utc'][0]),unit='s',utc=True).isoformat(),
                             one_hot_category_checks=categorical_checks,
                             continuous_values_masks_quality_and_coordinates_equal_raw=True,
                             passed=True))
            print('REAL DATA CHECKED',e['id'],list(x.shape),flush=True)
            del sample,x,mask,original
        # Check invalid soil values at their actual event hours, not just the first window.
        quality_cases=[]
        for identifier in ('KFS_05','CA-BTU-009205_Dixie'):
            path=dataset.root/'quality_flags'/identifier/'ecmwf_ifs_native_quality_flags.npz'
            with np.load(path) as q:
                valid_hour=np.any(q['soil_moisture_0_to_7cm']==1,axis=1)
                times=pd.to_datetime(q['time_utc'][valid_hour],utc=True)
            event=next(e for e in dataset._events if e['info']['id']==identifier)
            times=times[(times>=pd.Timestamp(event['info']['start_utc']))
                        &(times<=pd.Timestamp(event['info']['end_utc']))]
            stamp=times[0].isoformat()
            probe=WildfireSequenceDataset(events=[identifier],sequence_length=1,
                    channels=['weather.soil_moisture_0_to_7cm'],time_range=(stamp,stamp))
            sample=probe[0];bad=sample['feature_quality']==1
            # Extra downloaded native nodes can lie outside every target pixel.
            # Check the actual mapped quality raster, allowing zero affected
            # pixels when an invalid native node was not selected by this fire.
            band=int((times[0]-pd.Timestamp(event['info']['start_utc'])).total_seconds()/3600)+1
            qpath=dataset.root/'quality_flags'/identifier/'soil_moisture_0_to_7cm_quality_flags_375m.tif'
            with rasterio.open(qpath) as s:
                expected_quality=s.read(band)
            assert np.array_equal(sample['feature_quality'][0,0].numpy(),expected_quality)
            assert not sample['feature_valid'][bad].any()
            assert torch.all(sample['features'][bad]==0)
            quality_cases.append(dict(event_id=identifier,time_utc=stamp,masked_pixel_values=int(bad.sum()),
                                      mapped_quality_mask_equal=True))
            probe.close();del sample
        result=dict(passed=True,regions=len(rows),channel_count=len(dataset.channel_names),
                    channels=dataset.channel_names,channel_info=dataset.channel_info,
                    rectangular_full_grid_samples=True,real_data_detail=rows,
                    categorical_encoding=dataset.categorical_encoding,
                    raw_source_channel_count=len(dataset.source_channel_names),
                    categorical_classes=dataset.categorical_classes,
                    channel_groups=dataset.channel_groups,
                    raw_mode_source_order_preserved=True,
                    source_quality_cases=quality_cases,
                    loader_sha256=hashlib.sha256(Path(__file__).with_name('dataset.py').read_bytes()).hexdigest(),
                    scope='first two hours of every full event grid, all encoded channels; every categorical plane compared to native class codes; continuous/raw parity; targeted invalid-soil hours',
                    pytorch_version=torch.__version__,elapsed_seconds=round(time.monotonic()-started,2),
                    checked_utc=pd.Timestamp.now(tz='UTC').isoformat())
        output.write_text(json.dumps(result,indent=2)+'\n')
        print('REAL DATA VALIDATED',len(rows),'fires,',len(dataset.channel_names),'channels',flush=True)
    finally:dataset.close();raw.close()


if __name__=='__main__':main()
