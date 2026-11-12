import sys, glob, pandas as pd, rasterio
from rasterio.warp import transform_bounds
fdir, rdir, sel, out = sys.argv[1:5]
s = pd.read_csv(sel).set_index('incident')
held = ['ID-BOF-000683_Wapiti_Wapiti','ID-BOF-000904_Goat','ID-BOF-001080_Lava','ID-SCF-240202_RedRock','WA-SES-000173_Pioneer','WY-BTF-002416_FishCreek']
frames = []
for f in sorted(glob.glob(fdir+'/*_2024_United_States.csv')):
    d = pd.read_csv(f); d['source_file'] = f.split('/')[-1]
    d['t_utc'] = pd.to_datetime(d.acq_date+' '+d.acq_time.astype(str).str.zfill(4), format='%Y-%m-%d %H%M'); frames.append(d)
d = pd.concat(frames, ignore_index=True)
rows = []
for inc in held:
    r = rasterio.open(glob.glob(f'{rdir}/{inc}_pswt_ok_toa.tif')[0])
    w,so,e,n = transform_bounds(r.crs, 'EPSG:4326', *r.bounds); pad = 0.05
    t0 = pd.Timestamp(s.loc[inc,'window_start_utc']) - pd.Timedelta(hours=24); t1 = pd.Timestamp(s.loc[inc,'window_end_utc'])
    m = d.longitude.between(w-pad,e+pad) & d.latitude.between(so-pad,n+pad) & d.t_utc.between(t0,t1)
    x = d[m].copy(); x.insert(0,'incident',inc); rows.append(x)
    print(inc, 'bbox', [round(v,3) for v in (w-pad,so-pad,e+pad,n+pad)], 'window', t0, t1, 'n', len(x), x.source_file.value_counts().to_dict())
pd.concat(rows).drop(columns=['t_utc']).to_csv(out, index=False)
