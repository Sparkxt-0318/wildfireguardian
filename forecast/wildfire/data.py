"""Data operations for the wildfire workspace."""
from __future__ import annotations

from .paths import resolve_recorded_path



# Dataset
# Load colocated raster variables as chronological CPU tensor sequences.
# 
# Physical units are retained; categorical inputs are one-hot encoded by default.
# Missing, padded and
# source-quality-invalid values are filled only for storage; masks carry validity.
# Arrival/uncertainty are targets, never environmental input channels.


from bisect import bisect_right
from collections import OrderedDict
from dataclasses import dataclass
import json
import math
import operator
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from affine import Affine
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
import torch
from torch.utils.data import Dataset

from .paths import DATA_ROOT as DEFAULT_ROOT
CATEGORIES = ('weather', 'terrain', 'vegetation', 'fuel', 'fuel_moisture', 'biome')
QUALITY = {'valid': 0, 'out_of_range': 1, 'source_missing': 2,
           'channel_absent': 3, 'spatial_padding': 4, 'temporal_padding': 5,
           'unknown_category': 6}


@dataclass(frozen=True)
class Layer:
    path: Path
    role: str
    model: str | None = None


def _utc(value: str) -> pd.Timestamp:
    try:
        t = pd.Timestamp(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'Time must be a finite timestamp with a UTC offset: {value!r}') from error
    if pd.isna(t):
        raise ValueError(f'Time must be finite: {value!r}')
    if t.tzinfo is None:
        raise ValueError(f'Time must include a UTC offset: {value!r}')
    return t.tz_convert('UTC')


def _seconds(times) -> np.ndarray:
    return np.asarray(pd.DatetimeIndex(times).asi8 // 10**9, dtype='int64')


class WildfireSequenceDataset(Dataset):
    """Map-style dataset with samples [time, channel, height, width].

    By default each full bitmap retains its original rectangle (height,width),
    without stretching or cropping. Optional rectangular patches are supported.
    Ordering is event -> spatial tile -> chronological time window. Each sample
    stays inside one event/tile. The default sequence_length=24 uses chronological
    windows, padding short events and final windows. sequence_length=None reads
    the entire selected event timeline as one sample per spatial tile.

    daily_policy='completed_day' selects the most recent daily interval that
    ended by the hourly timestamp (MST day boundaries are 07:00 UTC). This
    avoids using the remainder of that day, but is NOT an assertion about the
    actual product publication latency. 'containing_day' is available only for
    retrospective alignment and can expose future information within that day.

    Raster readers are opened lazily and cached separately per worker process.
    Construction reads metadata; pixels are read only when a sample is
    requested. Accessing a whole-event sample materializes its complete selected
    timeline in RAM. Explicit windows bound the size of each read. Samples
    remain on CPU for use with multiprocessing DataLoader.

    Categorical rasters expand to one channel per class, named 'source=code'.
    Valid known pixels have exactly one active indicator in each complete
    source group; missing/unknown/padded groups are zero with false masks.
    Published biome classes and bundle-wide observed codes define a stable
    vocabulary independently of event/time filtering. categorical_classes
    can supply frozen vocabularies; unseen codes receive quality 6. channels
    accepts source names (expand the group) or individual encoded names.
    categorical_encoding='raw' retains the previous scalar-code contract.
    """

    def __init__(self, data_root: str | Path = DEFAULT_ROOT, *,
                 events: Sequence[str] | None = None,
                 sequence_length: int | None = 24, temporal_stride: int | None = None,
                 patch_size: int | tuple[int,int] | None = None,
                 channels: Sequence[str] | None = None,
                 time_range: tuple[str, str] | None = None,
                 daily_policy: str = 'completed_day', fill_value: float = 0.0,
                 max_open_files: int = 64,
                 categorical_encoding: str = 'one_hot',
                 categorical_classes: Mapping[str, Sequence[int]] | None = None,
                 include_fire_labels: bool = True):
        self.root = resolve_recorded_path(data_root).resolve()
        if not isinstance(include_fire_labels, bool):
            raise TypeError('include_fire_labels must be a boolean')
        self.include_fire_labels = include_fire_labels
        if categorical_encoding not in ('one_hot', 'raw'):
            raise ValueError('categorical_encoding must be one_hot or raw')
        if categorical_encoding == 'raw' and categorical_classes is not None:
            raise ValueError('categorical_classes is used only with one_hot encoding')
        self.categorical_encoding = categorical_encoding
        if sequence_length is None:
            if temporal_stride is not None:
                raise ValueError('temporal_stride requires an explicit sequence_length')
            self.sequence_length = self.temporal_stride = None
        else:
            if isinstance(sequence_length, (bool, np.bool_)):
                raise ValueError('sequence_length must be a positive integer or None')
            try:
                self.sequence_length = operator.index(sequence_length)
            except TypeError as error:
                raise ValueError('sequence_length must be a positive integer or None') from error
            stride = sequence_length if temporal_stride is None else temporal_stride
            if isinstance(stride, (bool, np.bool_)):
                raise ValueError('temporal_stride must be an integer between 1 and sequence_length')
            try:
                self.temporal_stride = operator.index(stride)
            except TypeError as error:
                raise ValueError('temporal_stride must be an integer between 1 and sequence_length') from error
            if self.sequence_length <= 0 or not 1 <= self.temporal_stride <= self.sequence_length:
                raise ValueError('sequence_length must be positive; stride must be between 1 and sequence_length')
        if patch_size is None:
            self.patch_size = None
        else:
            p = (patch_size,patch_size) if isinstance(patch_size,int) else tuple(patch_size)
            if len(p)!=2 or any(operator.index(v)<=0 for v in p):
                raise ValueError('patch_size must be positive, (height,width), or None')
            self.patch_size = tuple(operator.index(v) for v in p)
        if daily_policy not in ('completed_day', 'containing_day'):
            raise ValueError('daily_policy must be completed_day or containing_day')
        if not np.isfinite(fill_value):
            raise ValueError('fill_value must be finite; use the validity masks for missingness')
        if max_open_files < 1:
            raise ValueError('max_open_files must be positive')
        self.daily_policy, self.fill_value = daily_policy, float(fill_value)
        self.max_open_files = operator.index(max_open_files)
        self._readers: OrderedDict[Path, Any] = OrderedDict()
        self._pid = os.getpid()
        catalog = json.loads((self.root/'events.json').read_text())
        all_layers = {}; exemplars = {}; catalog_layers = {}
        # Discover a bundle-wide schema before event/time filtering. Training
        # and held-out datasets therefore retain the same channel order.
        for e in catalog:
            models, layers = self._discover(e)
            catalog_layers[e['id']] = (models, layers)
            for name, layer in layers.items():
                if name in all_layers and all_layers[name] != layer.role:
                    raise ValueError(f'Inconsistent time support for {name}')
                all_layers[name] = layer.role
                exemplars.setdefault(name,layer)
        if events is not None:
            wanted = tuple(events)
            if not wanted or len(set(wanted)) != len(wanted):
                raise ValueError('events must contain distinct event IDs and cannot be empty')
            by_id = {e['id']: e for e in catalog}
            unknown = set(wanted)-by_id.keys()
            if unknown:
                raise ValueError(f'Unknown event IDs: {sorted(unknown)}')
            catalog = [by_id[v] for v in wanted]
        bounds = tuple(_utc(v) for v in time_range) if time_range else None
        if bounds and bounds[1] < bounds[0]:
            raise ValueError('time_range end must not precede start')
        self._events = []
        # Discover the union using paths/tables, without opening thousands of
        # large multiband raster headers during construction.
        for e in catalog:
            region = self.root/'regions'/e['id']
            full_times = pd.date_range(_utc(e['start_utc']), _utc(e['end_utc']), freq='h')
            chosen = np.ones(len(full_times), bool)
            if bounds:
                chosen &= (full_times >= bounds[0]) & (full_times <= bounds[1])
            times = full_times[chosen]
            if not len(times): continue
            models,layers = catalog_layers[e['id']]
            band_times = {}
            for model in models:
                table = pd.read_csv(region/'weather'/f'{model}_bands.csv')
                bt = pd.DatetimeIndex(pd.to_datetime(table.time_utc, utc=True))
                if not np.array_equal(bt.asi8, full_times.asi8):
                    raise ValueError(f'Hourly timestamps do not match grid.json for {e["id"]}/{model}')
                if not np.array_equal(table.band.to_numpy(), np.arange(1, len(bt)+1)):
                    raise ValueError(f'Invalid band numbering for {e["id"]}/{model}')
                band_times[model] = bt
            daily_times = {}
            for name, layer in layers.items():
                if layer.role == 'daily':
                    table = pd.read_csv(layer.path.with_suffix('.bands.csv'))
                    dt = pd.DatetimeIndex(pd.to_datetime(table.date_mst, utc=True)) + pd.Timedelta(hours=7)
                    if not dt.is_monotonic_increasing or dt.has_duplicates:
                        raise ValueError(f'Daily timestamps must be unique and increasing: {layer.path}')
                    if not np.array_equal(table.band.to_numpy(), np.arange(1, len(dt)+1)):
                        raise ValueError(f'Invalid daily band numbering: {layer.path}')
                    daily_times[name] = dt
            patch = self.patch_size or (e['height'],e['width'])
            length = len(times) if self.sequence_length is None else self.sequence_length
            stride = length if self.temporal_stride is None else self.temporal_stride
            nt = math.ceil(len(times)/stride)
            nr, nc = math.ceil(e['height']/patch[0]), math.ceil(e['width']/patch[1])
            self._events.append(dict(info=e, layers=layers, times=times, hourly_times=band_times,
                                     daily_times=daily_times, patch=patch, nt=nt, nr=nr, nc=nc,
                                     sequence_length=length, temporal_stride=stride))
        if not self._events:
            raise ValueError('No events intersect the requested time range')
        source_names = tuple(sorted(all_layers, key=lambda n: (CATEGORIES.index(n.split('.')[0]), n)))
        source_info = {n: self._describe(n, exemplars[n]) for n in source_names}
        self.categorical_classes = {}
        if categorical_encoding == 'one_hot':
            self.categorical_classes = self._class_vocabularies(source_info, catalog_layers,
                                                                categorical_classes)
        # Replace each categorical source by its ascending-code indicator block.
        # Names/order are determined before event/time selection, never per sample.
        expanded, source_outputs = OrderedDict(), {}
        for source_name in source_names:
            info = source_info[source_name]
            codes = self.categorical_classes.get(source_name)
            if codes is None:
                names = [source_name]
                expanded[source_name] = dict(info, source_channel=source_name,
                                             encoding='raw' if info['categorical'] else 'continuous')
            else:
                names = []
                for code in codes:
                    name = f'{source_name}={code}'
                    names.append(name)
                    expanded[name] = dict(info, name=name, source_channel=source_name,
                                          source_unit=info['unit'], unit='binary category indicator',
                                          encoding='one_hot', class_code=code,
                                          class_name=info.get('class_names', {}).get(code, str(code)))
            source_outputs[source_name] = names
        names = tuple(expanded)
        if channels is not None:
            tokens = tuple(channels)
            if not tokens or len(set(tokens)) != len(tokens):
                raise ValueError('channels must be nonempty and distinct')
            selected = []
            for token in tokens:
                if token in source_outputs:
                    selected.extend(source_outputs[token])
                elif token in expanded:
                    selected.append(token)
                else:
                    raise ValueError(f'Unknown channel: {token}')
            if len(set(selected)) != len(selected):
                raise ValueError('channels select overlapping or duplicate encoded channels')
            names = tuple(selected)
        self.channel_names = names
        self.channel_info = tuple(expanded[n] for n in names)
        self.source_channel_names = tuple(dict.fromkeys(v['source_channel'] for v in self.channel_info))
        self.source_channel_info = tuple(source_info[n] for n in self.source_channel_names)
        self.channel_groups = {n: tuple(i for i, v in enumerate(self.channel_info)
                                       if v['source_channel'] == n) for n in self.source_channel_names}
        self.categorical_channel = torch.tensor([v['categorical'] for v in self.channel_info], dtype=torch.bool)
        self.event_ids = tuple(e['info']['id'] for e in self._events)
        self._ends = np.cumsum([e['nr']*e['nc']*e['nt'] for e in self._events]).tolist()

    def _discover(self,e):
        region=self.root/'regions'/e['id'];models={};layers={}
        for model in ('ecmwf_ifs','era5'):
            marker=region/'weather'/f'{model}_complete.json'
            if marker.exists():models[model]=json.loads(marker.read_text())
        for category in CATEGORIES:
            for path in sorted((region/category).glob('*_375m.tif')):
                variable=path.stem.removesuffix('_375m');name=f'{category}.{variable}'
                role,model='static',None
                if category=='fuel_moisture':role='daily'
                elif category=='weather':
                    for m,info in models.items():
                        if variable in info['variables']:
                            role,model='hourly',m
                            break
                    if role=='static' and '_node_' not in variable:
                        raise ValueError(f'Unclassified weather layer {path}')
                layers[name]=Layer(path,role,model)
        return models,layers

    def _describe(self, name: str, layer: Layer) -> dict:
        with rasterio.open(layer.path) as s:
            tags = s.tags()
        variable = name.split('.', 1)[1]
        categorical = variable in ('landcover_class', 'forest_type', 'landfire_2016_fbfm40',
                                   'landfire_2016_fccs', 'biome_class') or '_node_index' in variable
        inferred = {'elevation_m': 'm', 'slope_degrees': 'degrees', 'aspect_degrees': 'degrees',
                    'aspect_eastness': 'dimensionless', 'aspect_northness': 'dimensionless',
                    'aspect_resultant_length': 'dimensionless', 'tpi_3375m_m': 'm',
                    'elevation_std_3375m_m': 'm'}
        unit = tags.get('unit', tags.get('units', inferred.get(variable, 'see source metadata')))
        info = dict(name=name, category=name.split('.')[0], time_support=layer.role,
                    model=layer.model, unit=unit, categorical=categorical, source_tags=tags)
        if name == 'biome.biome_class':
            legend = json.loads((self.root/'biome_classes.json').read_text())
            info['class_names'] = {int(c['code']): c['name'] for c in legend['classes']}
        return info

    def _class_vocabularies(self, source_info, catalog_layers, overrides):
        categorical = {n for n, info in source_info.items() if info['categorical']}
        supplied = {} if overrides is None else dict(overrides)
        if set(supplied)-categorical:
            raise ValueError(f'Class vocabularies require categorical source names: {sorted(set(supplied)-categorical)}')
        result = {}
        for name in sorted(categorical):
            if name in supplied:
                codes = tuple(operator.index(v) for v in supplied[name])
                if not codes or len(set(codes)) != len(codes):
                    raise ValueError(f'Class vocabulary must be nonempty and distinct: {name}')
                result[name] = tuple(sorted(codes))
                continue
            if 'class_names' in source_info[name]:
                # Use the complete published legend when supplied, including
                # classes absent from the current geographic fire selection.
                result[name] = tuple(sorted(source_info[name]['class_names']))
                continue
            codes = set()
            for _, layers in catalog_layers.values():
                if name not in layers:
                    continue
                with rasterio.open(layers[name].path) as src:
                    for band in range(1, src.count+1):
                        values = src.read(band, masked=True).compressed()
                        values = values[np.isfinite(values)]
                        if np.any(values != np.floor(values)):
                            raise ValueError(f'Noninteger categorical source values: {layers[name].path}')
                        codes.update(int(v) for v in np.unique(values))
            if not codes:
                raise ValueError(f'Cannot infer classes for entirely missing {name}; supply categorical_classes')
            # Sparse IDs become compact channels, never max(code)+1 channels.
            result[name] = tuple(sorted(codes))
        return result

    def __len__(self) -> int:
        return self._ends[-1]

    def sample_location(self, index: int) -> dict:
        """Inspect a sample's event/tile/time range without reading raster pixels."""
        state, row, col, start = self._locate(index)
        times = state['times'][start:start+state['sequence_length']]
        return dict(event_id=state['info']['id'], row=row, col=col,
                    start_utc=times[0].isoformat(), end_utc=times[-1].isoformat(),
                    valid_hours=len(times), patch_size=state['patch'])

    def _locate(self, index):
        index = operator.index(index)
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        ei = bisect_right(self._ends, index)
        state = self._events[ei]
        local = index-(self._ends[ei-1] if ei else 0)
        tile, ti = divmod(local, state['nt'])
        ri, ci = divmod(tile, state['nc'])
        return state, ri*state['patch'][0], ci*state['patch'][1], ti*state['temporal_stride']

    def _reader(self, path: Path, e: dict):
        if self._pid != os.getpid():
            self.close()
            self._pid = os.getpid()
        if path in self._readers:
            self._readers.move_to_end(path)
            return self._readers[path]
        s = rasterio.open(path)
        if (s.crs.to_epsg() != e['epsg'] or s.transform != Affine(*e['transform'])
                or s.shape != (e['height'], e['width'])):
            s.close()
            raise ValueError(f'Raster does not match event reference grid: {path}')
        self._readers[path] = s
        if len(self._readers) > self.max_open_files:
            _, old = self._readers.popitem(last=False)
            old.close()
        return s

    def _read(self, path, e, bands, window, out_dtype='float32'):
        s = self._reader(path, e)
        a = s.read(bands, window=window, masked=True, out_dtype=out_dtype)
        return a.filled(self.fill_value), ~np.ma.getmaskarray(a) & np.isfinite(a.data)

    def __getitem__(self, index: int) -> dict[str, Any]:
        state, row, col, start = self._locate(index)
        e, layers = state['info'], state['layers']
        times = state['times'][start:start+state['sequence_length']]
        seconds = _seconds(times); n = len(times)
        t, c = state['sequence_length'], len(self.channel_names)
        h, w = state['patch']; rh, rw = min(h, e['height']-row), min(w, e['width']-col)
        window = Window(col, row, rw, rh)
        features = np.full((t,c,h,w), self.fill_value, 'float32')
        for j, info in enumerate(self.channel_info):
            if info['encoding']=='one_hot':
                features[:,j]=0
        valid = np.zeros((t,c,h,w), bool)
        quality = np.full((t,c,h,w), QUALITY['channel_absent'], 'uint8')
        quality[:,:,rh:,:] = QUALITY['spatial_padding']; quality[:,:,:,rw:] = QUALITY['spatial_padding']
        quality[n:] = QUALITY['temporal_padding']
        present = np.zeros(c, bool)
        interval_start = np.full((t,c), -1, 'int64'); interval_end = interval_start.copy()
        for name in self.source_channel_names:
            if name not in layers: continue
            indices = self.channel_groups[name]
            j = indices[0]
            present[list(indices)] = True; layer = layers[name]
            one_hot = self.channel_info[j]['encoding']=='one_hot'
            read_dtype = 'float64' if one_hot else 'float32'
            if layer.role == 'static':
                a, ok = self._read(layer.path, e, [1], window, read_dtype)
                a = np.broadcast_to(a, (n,rh,rw)); ok = np.broadcast_to(ok, a.shape)
            else:
                if layer.role == 'hourly':
                    source_times = state['hourly_times'][layer.model]
                    lookup = source_times.get_indexer(times)
                    if np.any(lookup < 0): raise ValueError(f'Missing hourly timestamps: {layer.path}')
                    interval_start[:n,j] = seconds
                    variable = name.split('.',1)[1]
                    if variable in ('precipitation','rain','shortwave_radiation','direct_radiation',
                                     'diffuse_radiation','et0_fao_evapotranspiration'):
                        interval_start[:n,j] -= 3600
                    elif variable.startswith('precipitation_trailing_'):
                        hours = {'24h':24,'7d':168,'30d':720}[variable.removeprefix('precipitation_trailing_')]
                        interval_start[:n,j] -= hours*3600
                    interval_end[:n,j] = seconds
                else:
                    source_times = state['daily_times'][name]
                    source_seconds = _seconds(source_times)
                    available = source_seconds + (86400 if self.daily_policy == 'completed_day' else 0)
                    lookup = np.searchsorted(available, seconds, side='right')-1
                    # Never extrapolate missing dates or beyond the downloaded daily series.
                    good = lookup >= 0
                    safe = np.maximum(lookup,0)
                    good &= seconds < available[safe]+86400
                    lookup[~good] = -1
                    interval_start[:n,j][good] = source_seconds[lookup[good]]
                    interval_end[:n,j][good] = source_seconds[lookup[good]]+86400
                a = np.full((n,rh,rw),self.fill_value,read_dtype); ok = np.zeros(a.shape,bool)
                usable = lookup >= 0
                if usable.any():
                    unique, inverse = np.unique(lookup[usable]+1, return_inverse=True)
                    values, masks = self._read(layer.path, e, unique.tolist(), window, read_dtype)
                    a[usable] = values[inverse]; ok[usable] = masks[inverse]
                if layer.role == 'hourly':
                    qpath = self.root/'quality_flags'/e['id']/f'{name.split(".",1)[1]}_quality_flags_375m.tif'
                    if qpath.exists():
                        q, qvalid = self._read(qpath, e, (lookup+1).tolist(), window)
                        source_ok = ok.copy()
                        ok &= qvalid & (q == 0)
                        quality[:n,j,:rh,:rw] = np.where(source_ok & qvalid,q,QUALITY['source_missing']).astype('uint8')
                    else:
                        quality[:n,j,:rh,:rw] = np.where(ok,0,QUALITY['source_missing'])
            if layer.role != 'hourly':
                quality[:n,j,:rh,:rw] = np.where(ok,0,QUALITY['source_missing'])
            if one_hot:
                known = np.isin(a, self.categorical_classes[name])
                q = quality[:n,j,:rh,:rw].copy()
                q[ok & ~known] = QUALITY['unknown_category']
                ok = ok & known
                for out in indices:
                    code = self.channel_info[out]['class_code']
                    features[:n,out,:rh,:rw] = (ok & (a == code))
                    valid[:n,out,:rh,:rw] = ok
                    quality[:n,out,:rh,:rw] = q
                    interval_start[:,out] = interval_start[:,j]
                    interval_end[:,out] = interval_end[:,j]
            else:
                features[:n,j,:rh,:rw] = np.where(ok,a,self.fill_value)
                valid[:n,j,:rh,:rw] = ok
        region = self.root/'regions'/e['id']
        if self.include_fire_labels:
            arrival, av = self._read(region/'arrival_time_hours.tif',e,[1],window)
            uncertainty, uv = self._read(region/'kriging_std_hours.tif',e,[1],window)
        else:
            # Independent observed-perimeter evaluations need environmental
            # covariates without opening any reconstructed fire-label rasters.
            arrival = np.full((1,rh,rw), self.fill_value, dtype='float32')
            uncertainty = arrival.copy()
            av = np.zeros(arrival.shape, dtype=bool)
            uv = av.copy()
        arrival = np.where(av,arrival,self.fill_value); uncertainty = np.where(uv,uncertainty,self.fill_value)
        elapsed = (times.asi8-_utc(e['t0_utc']).value)/(3600*10**9)
        labels = np.zeros((t,1,h,w),'float32'); newly = labels.copy(); label_valid = np.zeros(labels.shape,bool)
        labels[:n,0,:rh,:rw] = ((arrival[0][None] <= elapsed[:,None,None]) & av[0][None])
        newly[:n,0,:rh,:rw] = ((arrival[0][None] > elapsed[:,None,None]-1)
                                           & (arrival[0][None] <= elapsed[:,None,None]) & av[0][None])
        label_valid[:n,0,:rh,:rw] = av[0][None]
        def static_pad(a, fill):
            result = np.full((1,h,w),fill,dtype=a.dtype); result[:,:rh,:rw] = a
            return torch.from_numpy(result)
        transform = Affine(*e['transform']) @ Affine.translation(col,row)
        ys,xs = np.meshgrid(np.arange(rh)+.5,np.arange(rw)+.5,indexing='ij')
        coords = np.full((2,h,w),np.nan,'float64')
        coords[0,:rh,:rw] = transform.c+transform.a*xs+transform.b*ys
        coords[1,:rh,:rw] = transform.f+transform.d*xs+transform.e*ys
        time_valid = np.arange(t)<n; time_values = np.full(t,-1,'int64'); time_values[:n] = seconds
        elapsed_values = np.full(t,np.nan,'float64'); elapsed_values[:n] = elapsed
        return dict(features=torch.from_numpy(features), feature_valid=torch.from_numpy(valid),
                    feature_quality=torch.from_numpy(quality), channel_present=torch.from_numpy(present),
                    channel_names=self.channel_names, categorical_channel=self.categorical_channel.clone(),
                    categorical_encoding=self.categorical_encoding,
                    burned_area=torch.from_numpy(labels), newly_burned_area=torch.from_numpy(newly),
                    burned_area_valid=torch.from_numpy(label_valid),
                    arrival_hours=static_pad(arrival,self.fill_value), arrival_valid=static_pad(av,False),
                    arrival_std_hours=static_pad(uncertainty,self.fill_value), arrival_std_valid=static_pad(uv,False),
                    time_utc=torch.from_numpy(time_values), time_valid=torch.from_numpy(time_valid),
                    elapsed_hours=torch.from_numpy(elapsed_values),
                    source_interval_start_utc=torch.from_numpy(interval_start),
                    source_interval_end_utc=torch.from_numpy(interval_end),
                    coordinates=torch.from_numpy(coords), pixel_valid=static_pad(np.ones((1,rh,rw),bool),False),
                    affine_transform=torch.tensor(tuple(transform)[:6],dtype=torch.float64),
                    epsg=torch.tensor(e['epsg'],dtype=torch.int64),
                    spatial_window=torch.tensor([row,col,rh,rw],dtype=torch.int64),
                    event_id=e['id'], event_name=e['name'], event_t0_utc=e['t0_utc'],
                    fill_value=self.fill_value)

    def close(self):
        for s in self._readers.values(): s.close()
        self._readers.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def __getstate__(self):
        state = self.__dict__.copy()
        state['_readers'] = OrderedDict(); state['_pid'] = None
        return state

    def __del__(self):
        if hasattr(self, '_readers'): self.close()


_TEMPORAL_FIELDS = frozenset({
    'features', 'feature_valid', 'feature_quality', 'burned_area',
    'newly_burned_area', 'burned_area_valid', 'newly_burned_area_valid', 'time_utc', 'time_valid',
    'elapsed_hours', 'source_interval_start_utc', 'source_interval_end_utc',
})


def load_data(
    data_root: str | Path = DEFAULT_ROOT, *, events: Sequence[str] | None = None,
    sequence_length: int | None = 24, temporal_stride: int | None = None,
    patch_size: int | tuple[int, int] | None = None,
    channels: Sequence[str] | None = None, time_range: tuple[str, str] | None = None,
    daily_policy: str = 'completed_day', fill_value: float = 0.0,
    max_open_files: int = 64, categorical_encoding: str = 'one_hot',
    categorical_classes: Mapping[str, Sequence[int]] | None = None,
    include_fire_labels: bool = True,
) -> WildfireSequenceDataset:
    """Load event timelines independently of any model or checkpoint.

    Return a metadata-backed dataset with 24-hour windows by default. Set
    sequence_length=None to read an event's entire available timeline as one
    sample per spatial tile. No pixels are read until indexing. events and
    time_range optionally restrict that selection. A positive sequence_length
    enables bounded windows and optional temporal_stride; patch_size enables
    spatial tiles. Channel selection and categorical vocabularies are data
    options and do not depend on a model.
    """
    return WildfireSequenceDataset(
        data_root, events=events, sequence_length=sequence_length,
        temporal_stride=temporal_stride, patch_size=patch_size, channels=channels,
        time_range=time_range, daily_policy=daily_policy, fill_value=fill_value,
        max_open_files=max_open_files, categorical_encoding=categorical_encoding,
        categorical_classes=categorical_classes, include_fire_labels=include_fire_labels,
    )


def select_time(
    sample: Mapping[str, Any], start: Any = None, end: Any = None, *, index: int | None = None,
) -> dict[str, Any]:
    """Select loaded times by exact UTC boundaries or one positional index.

    sample must be one event/tile with features shaped [T,C,H,W], rather than a
    batch. Use index=i for a zero-based position in this loaded sample; negative
    indices count from its end. A selected padding position is rejected. Index
    selection cannot be combined with start/end timestamps.
    Both boundaries must identify valid timestamps already in sample;
    end=None selects one timestamp. The time dimension is retained, so a single
    timestamp still has T=1. Known temporal fields are sliced, while static
    geometry, channel metadata, and other fields retain their original values.
    No raster files are opened. The returned mapping shares tensor/array storage
    with sample and leaves sample unchanged.
    """
    if not isinstance(sample, Mapping):
        raise TypeError('sample must be a mapping containing one loaded event/tile')
    if index is not None and (start is not None or end is not None):
        raise ValueError('Choose either index or start/end timestamps, not both')
    if index is None and start is None:
        raise ValueError('Supply a start timestamp or index to select loaded times')
    features = sample.get('features')
    if not hasattr(features, 'shape') or len(features.shape) != 4:
        raise ValueError('select_time requires an unbatched sample with features [T,C,H,W]')
    length = features.shape[0]
    if length < 1 or 'time_utc' not in sample:
        raise ValueError('sample must contain at least one time_utc timestamp')

    def as_array(value):
        if isinstance(value, torch.Tensor):
            return value.detach().cpu().numpy()
        return np.asarray(value)

    times = as_array(sample['time_utc'])
    if times.shape != (length,) or not np.issubdtype(times.dtype, np.integer):
        raise ValueError('time_utc must be a one-dimensional integer array matching T')
    valid = as_array(sample.get('time_valid', np.ones(length, dtype=bool)))
    if valid.shape != (length,) or valid.dtype != np.dtype(bool):
        raise ValueError('time_valid must be a one-dimensional boolean array matching T')
    indices = np.flatnonzero(valid)
    if not len(indices):
        raise ValueError('sample has no valid timestamps to select')
    known = times[indices]
    if np.any(known[1:] <= known[:-1]):
        raise ValueError('Valid sample timestamps must be strictly increasing and distinct')
    def boundary_index(value):
        # Loaded timestamps use integer Unix seconds. Fractional-second queries
        # must not silently round onto an existing timestamp.
        try:
            ns = value.value
        except OverflowError as error:
            raise ValueError(f'Timestamp is unavailable in the loaded sample: {value.isoformat()}') from error
        if ns % 10**9:
            raise ValueError(f'Timestamp is unavailable in the loaded sample: {value.isoformat()}')
        matches = indices[known == ns // 10**9]
        if not len(matches):
            raise ValueError(f'Timestamp is unavailable in the loaded sample: {value.isoformat()}')
        return int(matches[0])

    if index is not None:
        if (isinstance(index, (bool, np.bool_))
                or isinstance(index, torch.Tensor) and index.dtype == torch.bool):
            raise TypeError('index must be an integer, excluding booleans')
        try:
            first = operator.index(index)
        except TypeError as error:
            raise TypeError('index must be an integer') from error
        if not -length <= first < length:
            raise IndexError(f'Loaded time index {first} is outside a timeline of length {length}')
        first %= length
        if not valid[first]:
            raise ValueError(f'Loaded time index {first} identifies temporal padding')
        last = first
    else:
        left, right = _utc(start), _utc(start if end is None else end)
        if right < left:
            raise ValueError('end must not precede start')
        first, last = boundary_index(left), boundary_index(right)
    result = dict(sample)
    for key in _TEMPORAL_FIELDS & sample.keys():
        value = sample[key]
        if not hasattr(value, 'shape') or not len(value.shape) or value.shape[0] != length:
            raise ValueError(f'{key} must have a leading time dimension matching T')
        result[key] = value[first:last+1]
    return result


def collate_fire_sequences(samples: list[dict]) -> dict:
    """Stack samples, padding differing time lengths and spatial grids.

    Channel order and categorical encoding must agree. Environmental tensors
    become [batch,time,channel,height,width]. Temporal and spatial padding have
    false validity masks; padded timestamps are -1 and elapsed times are NaN.
    Metadata strings stay as lists. Original sample tensors are unchanged.
    """
    if not samples: raise ValueError('Cannot collate an empty batch')
    first = samples[0]
    if any(s['channel_names'] != first['channel_names'] for s in samples):
        raise ValueError('All samples must use the same channel schema')
    if any(s.get('categorical_encoding','raw') != first.get('categorical_encoding','raw') for s in samples):
        raise ValueError('All samples must use the same categorical encoding')
    if any(s['features'].ndim != 4 or s['features'].shape[0] < 1
           or s['features'].shape[1] != len(first['channel_names']) for s in samples):
        raise ValueError('All samples must have features [T,C,H,W] with the same channel count')
    t = max(s['features'].shape[0] for s in samples)
    h = max(s['features'].shape[-2] for s in samples); w = max(s['features'].shape[-1] for s in samples)
    spatial = {'features','feature_valid','feature_quality','burned_area','newly_burned_area',
               'burned_area_valid','newly_burned_area_valid','arrival_hours','arrival_valid','arrival_std_hours',
               'arrival_std_valid','coordinates','pixel_valid'}
    result = {}
    for key,value in first.items():
        if key == 'channel_names': result[key] = value
        elif isinstance(value,torch.Tensor):
            items = []
            for s in samples:
                a = s[key]
                shape = list(a.shape)
                if key in _TEMPORAL_FIELDS:
                    if not shape or shape[0] != s['features'].shape[0]:
                        raise ValueError(f'{key} must have a leading time dimension matching its sample')
                    shape[0] = t
                if key in spatial:
                    shape[-2:] = (h,w)
                if tuple(shape) != tuple(a.shape):
                    fill = (float('nan') if key in ('coordinates','elapsed_hours') else
                            -1 if key in ('time_utc','source_interval_start_utc','source_interval_end_utc') else
                            QUALITY['temporal_padding'] if key == 'feature_quality' else
                            False if a.dtype == torch.bool else
                            s['fill_value'] if key in ('features','arrival_hours','arrival_std_hours') else 0)
                    padded = torch.full(shape,fill,dtype=a.dtype,device=a.device)
                    if key == 'feature_quality':
                        padded[:a.shape[0]] = QUALITY['spatial_padding']
                    elif key == 'features' and s.get('categorical_encoding','raw') == 'one_hot':
                        # One-hot groups remain zero for both temporal and
                        # spatial padding, even with a nonzero fill value.
                        padded[:,s['categorical_channel']] = 0
                    padded[tuple(slice(0,size) for size in a.shape)] = a
                    a = padded
                items.append(a)
            result[key] = torch.stack(items)
        else: result[key] = [s[key] for s in samples]
    return result
