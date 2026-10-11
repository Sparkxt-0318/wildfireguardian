"""Semantic tests: temporal joins, labels, missingness, geometry and workers."""
import json
import pickle
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine
import torch
from torch.utils.data import DataLoader

from wildfire.data import WildfireSequenceDataset
from wildfire.data import collate_fire_sequences

# Existing semantics remain covered explicitly for saved raw-channel contracts.
raw_dataset = partial(WildfireSequenceDataset, categorical_encoding="raw")


def write(path, values, transform, descriptions=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    a=np.asarray(values,dtype='float32')
    if a.ndim==2:a=a[None]
    with rasterio.open(path,'w',driver='GTiff',count=len(a),height=a.shape[1],width=a.shape[2],
                       dtype='float32',crs='EPSG:5179',transform=transform,nodata=-9999) as s:
        s.write(a)
        if descriptions is not None:
            for i,name in enumerate(descriptions,1):s.set_band_description(i,name)


@pytest.fixture
def bundle(tmp_path):
    times=pd.date_range('2021-07-15T06:00:00Z',periods=3,freq='h')
    transform=Affine(375,0,1000000,0,-375,2000000)
    events=[]
    for identifier,country,shape in [('KR_TEST','KR',(2,3)),('US_TEST','US',(3,2))]:
        r=tmp_path/'regions'/identifier;h,w=shape
        e=dict(id=identifier,name=identifier,country=country,epsg=5179,width=w,height=h,
               transform=list(transform)[:6],start_utc=times[0].isoformat(),
               end_utc=times[-1].isoformat(),t0_utc='2021-07-15T06:30:00+00:00')
        events.append(e)
        arrival=np.array([[-.25,1.25,-9999],[2.1,-1.5,0]],'float32').reshape(shape)
        write(r/'arrival_time_hours.tif',arrival,transform)
        write(r/'kriging_std_hours.tif',np.ones(shape)*2,transform)
        write(r/'terrain/elevation_m_375m.tif',np.arange(h*w).reshape(shape)+10,transform)
        write(r/'vegetation/landcover_class_375m.tif',np.ones(shape)*111,transform)
        weather=np.stack([np.full(shape,v) for v in [10,20,30]])
        weather[2,-1,-1]=-9999
        write(r/'weather/temperature_2m_375m.tif',weather,transform,times.strftime('%Y-%m-%dT%H:%M:%SZ'))
        soil=np.full((3,h,w),.2,'float32');soil[1,0,0]=-.005
        write(r/'weather/soil_moisture_0_to_7cm_375m.tif',soil,transform)
        info=dict(variables={'temperature_2m':{},'soil_moisture_0_to_7cm':{}})
        (r/'weather/ecmwf_ifs_complete.json').write_text(json.dumps(info))
        pd.DataFrame(dict(band=[1,2,3],time_utc=times.strftime('%Y-%m-%dT%H:%M:%SZ'))).to_csv(r/'weather/ecmwf_ifs_bands.csv',index=False)
        q=np.zeros((3,h,w),'float32');q[1,0,0]=1
        write(tmp_path/'quality_flags'/identifier/'soil_moisture_0_to_7cm_quality_flags_375m.tif',q,transform)
        if country=='US':
            write(r/'fuel/landfire_2016_fbfm40_375m.tif',np.full(shape,101),transform)
            dates=['2021-07-13','2021-07-14','2021-07-15']
            daily=np.stack([np.full(shape,v) for v in [13,14,15]])
            path=r/'fuel_moisture/fm100_daily_375m.tif'
            write(path,daily,transform,dates)
            pd.DataFrame(dict(band=[1,2,3],date_mst=dates)).to_csv(path.with_suffix('.bands.csv'),index=False)
    (tmp_path/'events.json').write_text(json.dumps(events))
    return tmp_path


def test_all_types_order_static_missing_padding_geometry_and_labels(bundle):
    d=raw_dataset(bundle,sequence_length=4,patch_size=4)
    a=d[0];names=d.channel_names
    assert a['features'].shape==(4,6,4,4)
    temp=names.index('weather.temperature_2m');terrain=names.index('terrain.elevation_m')
    fuel=names.index('fuel.landfire_2016_fbfm40')
    assert torch.equal(a['features'][:3,temp,0,0],torch.tensor([10.,20.,30.]))
    assert torch.equal(a['features'][:3,terrain,0,0],torch.tensor([10.,10.,10.]))
    assert not a['channel_present'][fuel] and not a['feature_valid'][:,fuel].any()
    assert a['feature_quality'][0,fuel,0,0]==3
    assert a['feature_quality'][0,temp,3,0]==4
    assert a['feature_quality'][3,temp,0,0]==5
    assert a['time_valid'].tolist()==[True,True,True,False]
    assert a['time_utc'][3]==-1 and torch.isnan(a['elapsed_hours'][3])
    assert not a['burned_area_valid'][:,:,0,2].any()
    assert a['elapsed_hours'][:3].tolist()==[-.5,.5,1.5]
    assert a['burned_area'][:3,0,0,0].tolist()==[0,1,1]
    assert a['newly_burned_area'][:3,0,0,0].tolist()==[0,1,0]
    assert a['coordinates'][:,0,0].tolist()==[1000187.5,1999812.5]
    assert torch.isnan(a['coordinates'][:,3,0]).all()
    assert 'arrival' not in ' '.join(names)
    d.close()


def test_source_quality_and_nodata_are_not_numeric_negatives(bundle):
    d=raw_dataset(bundle,events=['KR_TEST'],sequence_length=3,patch_size=None)
    a=d[0];soil=d.channel_names.index('weather.soil_moisture_0_to_7cm')
    temp=d.channel_names.index('weather.temperature_2m')
    assert a['feature_quality'][1,soil,0,0]==1
    assert not a['feature_valid'][1,soil,0,0] and a['features'][1,soil,0,0]==0
    assert a['feature_quality'][2,temp,1,2]==2 and not a['feature_valid'][2,temp,1,2]
    d.close()


def test_nodata_overrides_zero_source_quality_flag(bundle):
    path=bundle/'regions/KR_TEST/weather/soil_moisture_0_to_7cm_375m.tif'
    with rasterio.open(path,'r+') as s:
        a=s.read(1);a[0,1]=-9999;s.write(a,1)
    d=raw_dataset(bundle,events=['KR_TEST'],sequence_length=3)
    a=d[0];j=d.channel_names.index('weather.soil_moisture_0_to_7cm')
    assert not a['feature_valid'][0,j,0,1]
    assert a['feature_quality'][0,j,0,1]==2
    d.close()


def test_completed_day_join_at_07_utc_boundary(bundle):
    d=raw_dataset(bundle,events=['US_TEST'],sequence_length=3,patch_size=None)
    a=d[0];j=d.channel_names.index('fuel_moisture.fm100_daily')
    assert a['features'][:,j,0,0].tolist()==[13,14,14]
    assert torch.all(a['source_interval_end_utc'][:,j]<=a['time_utc'])
    retrospective=raw_dataset(bundle,events=['US_TEST'],sequence_length=3,
                                         patch_size=None,daily_policy='containing_day')
    b=retrospective[0]
    assert b['features'][:,j,0,0].tolist()==[14,15,15]
    assert torch.all(b['source_interval_end_utc'][:,j]>b['time_utc'])
    d.close();retrospective.close()


def test_same_location_windows_stay_in_order_and_crop_coordinates(bundle):
    d=raw_dataset(bundle,events=['KR_TEST'],sequence_length=2,patch_size=2)
    locations=[d.sample_location(i) for i in range(len(d))]
    assert [(v['row'],v['col']) for v in locations]==[(0,0),(0,0),(0,2),(0,2)]
    assert locations[1]['start_utc']>locations[0]['start_utc']
    a=d[2]
    assert a['affine_transform'][2]==1000750
    assert a['coordinates'][:,0,0].tolist()==[1000937.5,1999812.5]
    assert not a['pixel_valid'][:,:,1].any()
    assert d.sample_location(-1)==d.sample_location(len(d)-1)
    with pytest.raises(IndexError):d[len(d)]
    d.close()


def test_collation_pads_different_full_event_grids(bundle):
    d=raw_dataset(bundle,sequence_length=3,patch_size=None)
    batch=collate_fire_sequences([d[0],d[1]])
    assert batch['features'].shape==(2,3,6,3,3)
    assert not batch['pixel_valid'][0,0,2].any()
    assert not batch['pixel_valid'][1,0,:,2].any()
    assert batch['event_id']==['KR_TEST','US_TEST']
    d.close()


def test_default_full_bitmap_retains_rectangle_without_resampling(bundle):
    d=raw_dataset(bundle,sequence_length=3)
    kr=d[0];us=d[1]
    assert kr['features'].shape==(3,6,2,3)
    assert us['features'].shape==(3,6,3,2)
    assert kr['spatial_window'].tolist()==[0,0,2,3]
    assert us['spatial_window'].tolist()==[0,0,3,2]
    assert int(kr['pixel_valid'].sum())==6 and int(us['pixel_valid'].sum())==6
    assert kr['pixel_valid'].all() and us['pixel_valid'].all()
    j=d.channel_names.index('terrain.elevation_m')
    assert kr['features'][0,j,:2,:3].tolist()==[[10,11,12],[13,14,15]]
    d.close()


def test_spawn_workers_and_pickling_after_parent_read(bundle):
    d=raw_dataset(bundle,sequence_length=3,patch_size=4,max_open_files=2)
    expected=d[0]
    restored=pickle.loads(pickle.dumps(d))
    assert not restored._readers
    assert torch.equal(restored[0]['features'],expected['features'])
    loader=DataLoader(d,batch_size=2,num_workers=2,multiprocessing_context='spawn',
                      collate_fn=collate_fire_sequences)
    batch=next(iter(loader))
    assert batch['features'].shape==(2,3,6,4,4)
    assert torch.equal(batch['features'][0],expected['features'])
    assert len(d._readers)<=2
    restored.close();d.close()


def test_invalid_arguments_and_hour_range(bundle):
    with pytest.raises(ValueError):raw_dataset(bundle,events=['bad'])
    with pytest.raises(ValueError):raw_dataset(bundle,sequence_length=0)
    with pytest.raises(ValueError):raw_dataset(bundle,time_range=('2021-01-01','2021-01-02'))
    d=raw_dataset(bundle,events=['KR_TEST'],channels=['weather.temperature_2m'],
             sequence_length=2,patch_size=None,time_range=('2021-07-15T07:00:00Z','2021-07-15T08:00:00Z'))
    assert d[0]['features'].shape==(2,1,2,3)
    assert d[0]['features'][:,0,0,0].tolist()==[20,30]
    d.close()


def test_channel_schema_is_stable_across_event_subsets(bundle):
    kr=raw_dataset(bundle,events=['KR_TEST'],sequence_length=3)
    us=raw_dataset(bundle,events=['US_TEST'],sequence_length=3)
    assert kr.channel_names==us.channel_names
    assert len(kr.channel_names)==6
    j=kr.channel_names.index('fuel_moisture.fm100_daily')
    assert not kr[0]['channel_present'][j] and us[0]['channel_present'][j]
    kr.close();us.close()


def test_biome_static_categorical_rectangle_missing_and_existing_channels_unchanged(bundle):
    previous=raw_dataset(bundle,events=['KR_TEST'],sequence_length=3)
    original=previous[0];old_names=previous.channel_names
    previous.close()
    transform=Affine(375,0,1000000,0,-375,2000000)
    codes=np.array([[4,-9999,5],[4,5,4]],dtype='int16')
    write(bundle/'regions/KR_TEST/biome/biome_class_375m.tif',codes,transform)
    (bundle/'biome_classes.json').write_text(json.dumps(dict(classes=[
        dict(code=4,name='Temperate Broadleaf & Mixed Forests'),
        dict(code=5,name='Temperate Conifer Forests')])))
    d=raw_dataset(bundle,events=['KR_TEST'],sequence_length=4)
    a=d[0];j=d.channel_names.index('biome.biome_class')
    assert d.channel_names[:-1]==old_names and j==6
    assert a['features'].shape==(4,7,2,3)
    assert torch.equal(a['features'][:3,:6],original['features'])
    assert torch.equal(a['feature_valid'][:3,:6],original['feature_valid'])
    assert torch.equal(a['coordinates'],original['coordinates'])
    assert d.channel_info[j]['class_names'][4]=='Temperate Broadleaf & Mixed Forests'
    assert d.channel_info[j]['time_support']=='static' and d.categorical_channel[j]
    assert a['features'][:3,j,0,0].tolist()==[4,4,4]
    assert a['features'][:3,j,0,2].tolist()==[5,5,5]
    assert not a['feature_valid'][:,j,0,1].any()
    assert a['feature_quality'][0,j,0,1]==2
    assert not a['feature_valid'][3,j].any() and torch.all(a['feature_quality'][3,j]==5)
    assert torch.all(a['source_interval_start_utc'][:,j]==-1)
    us=raw_dataset(bundle,events=['US_TEST'],sequence_length=3)
    assert us.channel_names==d.channel_names
    assert not us[0]['channel_present'][j] and not us[0]['feature_valid'][:,j].any()
    selected=raw_dataset(bundle,events=['KR_TEST'],sequence_length=3,channels=old_names)
    assert torch.equal(selected[0]['features'],original['features'])
    d.close();us.close();selected.close()


def add_categories(bundle):
    transform=Affine(375,0,1000000,0,-375,2000000)
    for event in ('KR_TEST','US_TEST'):
        shape=(2,3) if event=='KR_TEST' else (3,2)
        # Include legitimate zero, sparse IDs and categories seen only in US.
        land=np.array([0,111,-9999,111,0,111]).reshape(shape)
        if event=='US_TEST':land[-1,-1]=200
        write(bundle/f'regions/{event}/vegetation/landcover_class_375m.tif',land,transform)
    biome=np.array([[4,-9999,5],[4,5,4]])
    write(bundle/'regions/KR_TEST/biome/biome_class_375m.tif',biome,transform)
    (bundle/'biome_classes.json').write_text(json.dumps(dict(classes=[
        dict(code=4,name='Temperate Broadleaf & Mixed Forests'),
        dict(code=5,name='Temperate Conifer Forests'),
        dict(code=13,name='Deserts & Xeric Shrublands')])))
    write(bundle/'regions/US_TEST/fuel/landfire_2016_fccs_375m.tif',
          [[0,3190132],[3190132,-9999],[0,3190132]],transform)


def test_default_one_hot_zero_sparse_classes_missing_time_and_geometry(bundle):
    add_categories(bundle)
    d=WildfireSequenceDataset(bundle,events=['KR_TEST'],sequence_length=4,patch_size=(3,4),fill_value=-7)
    a=d[0]
    assert d.categorical_encoding=='one_hot'
    assert d.categorical_classes['vegetation.landcover_class']==(0,111,200)
    assert d.categorical_classes['fuel.landfire_2016_fccs']==(0,3190132)
    assert d.categorical_classes['biome.biome_class']==(4,5,13)
    assert len(d.channel_names)==13
    group=d.channel_groups['vegetation.landcover_class']
    block=a['features'][:,list(group)]
    assert block[0,:,0,0].tolist()==[1,0,0]  # Class 0 is a valid class.
    assert block[0,:,0,1].tolist()==[0,1,0]
    assert block[0,:,0,2].tolist()==[0,0,0]  # NoData is not class 0.
    assert not a['feature_valid'][:,list(group),0,2].any()
    assert a['feature_quality'][0,list(group),0,2].tolist()==[2,2,2]
    assert not block[3].any() and not block[:,:,2].any() and not block[:,:,:,3].any()
    assert a['feature_quality'][3,list(group),0,0].tolist()==[5,5,5]
    assert a['feature_quality'][0,list(group),2,0].tolist()==[4,4,4]
    assert a['feature_valid'][0,list(group),0,1].tolist()==[True,True,True]
    # A globally known but locally absent class is a valid zero indicator.
    assert not block[:3,2].any() and a['feature_valid'][:3,group[2],0,0].all()
    bg=d.channel_groups['biome.biome_class']
    assert a['features'][:3,bg[0],0,0].tolist()==[1,1,1]
    assert d.channel_info[bg[0]]['class_code']==4
    assert d.channel_info[bg[0]]['class_name']=='Temperate Broadleaf & Mixed Forests'
    assert torch.all(a['source_interval_start_utc'][:,list(bg)]==-1)
    assert a['coordinates'][:,0,0].tolist()==[1000187.5,1999812.5]
    temp=d.channel_names.index('weather.temperature_2m')
    assert a['features'][:3,temp,0,0].tolist()==[10,20,30]
    d.close()


def test_one_hot_schema_subsets_selection_and_continuous_compatibility(bundle):
    add_categories(bundle)
    kr=WildfireSequenceDataset(bundle,events=['KR_TEST'],sequence_length=3)
    us=WildfireSequenceDataset(bundle,events=['US_TEST'],sequence_length=3)
    assert kr.channel_names==us.channel_names and kr.categorical_classes==us.categorical_classes
    group=us.channel_groups['fuel.landfire_2016_fccs']
    assert us[0]['features'][0,list(group),0,1].tolist()==[0,1]
    assert not kr[0]['feature_valid'][:,list(group)].any()
    assert torch.all(kr[0]['feature_quality'][:,list(group)]==3)
    chosen=WildfireSequenceDataset(bundle,events=['KR_TEST'],sequence_length=3,
                                  channels=['biome.biome_class','weather.temperature_2m'])
    assert chosen.channel_names==('biome.biome_class=4','biome.biome_class=5',
                                  'biome.biome_class=13','weather.temperature_2m')
    single=WildfireSequenceDataset(bundle,sequence_length=3,channels=['biome.biome_class=5'])
    assert single.channel_names==('biome.biome_class=5',)
    assert torch.equal(single[0]['features'][:,0],kr[0]['features'][:,kr.channel_names.index('biome.biome_class=5')])
    old=raw_dataset(bundle,events=['KR_TEST'],sequence_length=3,channels=['weather.temperature_2m','terrain.elevation_m'])
    now=WildfireSequenceDataset(bundle,events=['KR_TEST'],sequence_length=3,channels=old.channel_names)
    assert now.channel_names==old.channel_names
    assert torch.equal(now[0]['features'],old[0]['features'])
    assert torch.equal(now[0]['feature_valid'],old[0]['feature_valid'])
    assert torch.equal(now[0]['burned_area'],old[0]['burned_area'])
    for d in (kr,us,chosen,single,old,now):d.close()


def test_one_hot_unknown_classes_and_fractional_values_are_masked(bundle):
    add_categories(bundle)
    d=WildfireSequenceDataset(bundle,events=['KR_TEST'],sequence_length=3,
            channels=['vegetation.landcover_class'],
            categorical_classes={'vegetation.landcover_class':[111,0]})
    assert d.channel_names==('vegetation.landcover_class=0','vegetation.landcover_class=111')
    path=bundle/'regions/KR_TEST/vegetation/landcover_class_375m.tif'
    with rasterio.open(path,'r+') as s:
        a=s.read(1);a[0,0]=555;a[0,1]=111.5;s.write(a,1)
    a=d[0]
    assert not a['features'][:,:,:1,:2].any()
    assert not a['feature_valid'][:,:,:1,:2].any()
    assert torch.all(a['feature_quality'][:,:,:1,:2]==6)
    d.close()
    with pytest.raises(ValueError,match='Noninteger'):
        WildfireSequenceDataset(bundle)


def test_one_hot_collation_keeps_zero_padding_with_nonzero_fill(bundle):
    add_categories(bundle)
    d=WildfireSequenceDataset(bundle,sequence_length=3,fill_value=-7)
    a,b=d[0],d[1]
    batch=collate_fire_sequences([a,b]);cat=d.categorical_channel
    assert batch['features'].shape==(2,3,13,3,3)
    assert not batch['features'][0,:,cat,2].any()
    assert not batch['features'][1,:,cat,:,2].any()
    temp=d.channel_names.index('weather.temperature_2m')
    assert torch.all(batch['features'][0,:,temp,2]==-7)
    assert not batch['feature_valid'][0,:,:,2].any()
    assert torch.all(batch['feature_quality'][1,:,:,:,2]==4)
    d.close()


def test_one_hot_sparse_large_integer_ids_do_not_lose_precision(bundle):
    transform=Affine(375,0,1000000,0,-375,2000000)
    path=bundle/'regions/US_TEST/fuel/landfire_2016_fccs_375m.tif'
    path.parent.mkdir(exist_ok=True)
    values=np.array([[0,16777217],[16777216,-9999],[0,16777217]],dtype='int32')
    with rasterio.open(path,'w',driver='GTiff',count=1,height=3,width=2,dtype='int32',
                       crs='EPSG:5179',transform=transform,nodata=-9999) as s:s.write(values,1)
    d=WildfireSequenceDataset(bundle,events=['US_TEST'],sequence_length=1,channels=['fuel.landfire_2016_fccs'])
    assert d.categorical_classes['fuel.landfire_2016_fccs']==(0,16777216,16777217)
    assert d[0]['features'][0,:,0,1].tolist()==[0,0,1]
    assert d[0]['features'][0,:,1,0].tolist()==[0,1,0]
    d.close()


def test_one_hot_spawn_workers_after_parent_read(bundle):
    add_categories(bundle)
    d=WildfireSequenceDataset(bundle,sequence_length=3,patch_size=(3,4),max_open_files=2)
    expected=d[0]
    restored=pickle.loads(pickle.dumps(d))
    assert not restored._readers and restored.channel_names==d.channel_names
    assert torch.equal(restored[0]['features'],expected['features'])
    loader=DataLoader(d,batch_size=2,num_workers=2,multiprocessing_context='spawn',
                      collate_fn=collate_fire_sequences)
    batch=next(iter(loader))
    assert batch['features'].shape==(2,3,13,3,4)
    assert torch.equal(batch['features'][0],expected['features'])
    assert torch.equal(batch['feature_valid'][0],expected['feature_valid'])
    restored.close();d.close()


def test_one_hot_configuration_errors(bundle):
    with pytest.raises(ValueError,match='categorical_encoding'):
        WildfireSequenceDataset(bundle,categorical_encoding='ordinal')
    with pytest.raises(ValueError,match='distinct'):
        WildfireSequenceDataset(bundle,categorical_classes={'vegetation.landcover_class':[111,111]})
    with pytest.raises(ValueError,match='categorical source'):
        WildfireSequenceDataset(bundle,categorical_classes={'weather.temperature_2m':[10]})
    with pytest.raises(ValueError,match='overlapping'):
        WildfireSequenceDataset(bundle,channels=['vegetation.landcover_class','vegetation.landcover_class=111'])
    with pytest.raises(ValueError,match='only with'):
        raw_dataset(bundle,categorical_classes={'vegetation.landcover_class':[111]})
