#!/usr/bin/env python3
"""Flag physically out-of-range source values without modifying downloaded data."""
import json
import numpy as np
import pandas as pd
import rasterio
if __package__:
    from .acquire_environment import ROOT, grid, write_tif, jsave
else:  # Compatibility with direct execution of this file.
    from acquire_environment import ROOT, grid, write_tif, jsave

LIMITS = {
    'relative_humidity_2m': (0, 100), 'wind_speed_10m': (0, None),
    'wind_gusts_10m': (0, None), 'precipitation': (0, None), 'rain': (0, None),
    'shortwave_radiation': (0, None), 'soil_moisture_0_to_7cm': (0, 1),
    'soil_moisture_7_to_28cm': (0, 1), 'boundary_layer_height': (0, None),
}


def main():
    events = {e['id']: e for e in json.loads((ROOT/'events.json').read_text())}
    rows = []; rasters = []
    for file in sorted(ROOT.glob('regions/*/weather/*_native_nodes.npz')):
        identifier = file.parent.parent.name
        source = file.stem.removesuffix('_native_nodes')
        e = events[identifier]
        with np.load(file) as data:
            times = pd.to_datetime(data['time_utc'], utc=True)
            window = (times >= pd.Timestamp(e['start_utc'])) & (times <= pd.Timestamp(e['end_utc']))
            flags = {k: data[k] for k in ['time_utc', 'latitude', 'longitude']}
            out = ROOT/'quality_flags'/identifier
            out.mkdir(parents=True, exist_ok=True)
            for name, (lo, hi) in LIMITS.items():
                if name not in data: continue
                a = data[name]; finite = np.isfinite(a); valid = a[finite]
                assert len(valid) > 0
                bad = finite & ((a < lo-1e-6) | ((a > hi+1e-6) if hi is not None else False))
                q = np.where(~finite, 2, np.where(bad, 1, 0)).astype('uint8')
                flags[name] = q
                row = dict(event_id=identifier, source=source, variable=name,
                           minimum=float(valid.min()), maximum=float(valid.max()),
                           source_values=int(valid.size), physical_lower_bound=lo, physical_upper_bound=hi,
                           out_of_range_native_values_full_history=int(bad.sum()),
                           out_of_range_native_values_fire_window=int(bad[window].sum()),
                           missing_source_values=int((~finite).sum()),
                           policy='original values retained; flags: 0 within limits, 1 out of range, 2 missing')
                if bad[window].any():
                    with rasterio.open(file.parent/f'{source}_node_index_375m.tif') as s:
                        nodes = s.read(1)
                    profile, _, _ = grid(e)
                    mapped = q[window][:, nodes]
                    target = out/f'{name}_quality_flags_375m.tif'
                    names = times[window].strftime('%Y-%m-%dT%H:%M:%SZ').tolist()
                    write_tif(target, mapped, profile, names=names, nodata=255,
                              tags={'flag_values': '0=within physical bounds;1=out of range;2=missing source',
                                    'source_variable': name, 'source_model': source,
                                    'purpose': 'source quality flags; source values retained unchanged',
                                    'tolerance': '0.000001', 'time_zone': 'UTC'})
                    with rasterio.open(target) as s:
                        assert s.crs == profile['crs'] and s.transform == profile['transform']
                        assert s.shape == nodes.shape and s.descriptions == tuple(names)
                        assert np.array_equal(s.read(), mapped)
                    row['out_of_range_target_pixel_hours'] = int((mapped == 1).sum())
                    row['aligned_quality_raster'] = str(target.relative_to(ROOT))
                    rasters.append(row['aligned_quality_raster'])
                rows.append(row)
            np.savez_compressed(out/f'{source}_native_quality_flags.npz', **flags)
    pd.DataFrame(rows).to_csv(ROOT/'physical_weather_range_checks.csv', index=False)
    jsave(ROOT/'quality_flags/validation.json',
          dict(passed=True, event_variable_checks=len(rows), aligned_flag_rasters=rasters,
               exact_grid_and_values_checked=True,
               out_of_range_source_values_full_history=sum(r['out_of_range_native_values_full_history'] for r in rows),
               out_of_range_source_values_fire_window=sum(r['out_of_range_native_values_fire_window'] for r in rows),
               checked_utc=pd.Timestamp.now(tz='UTC').isoformat()))
    print('QUALITY FLAGS', len(rows), 'checks,', len(rasters), 'aligned rasters', flush=True)


if __name__ == '__main__': main()
