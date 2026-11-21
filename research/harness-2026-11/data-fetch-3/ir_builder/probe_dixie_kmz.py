"""Feasibility probe (not the acceptance run): Dixie 2021 KMZ-derived IR layers vs the archive, read by fid via nirops_access.
Usage: python3 -I probe_dixie_kmz.py NIROPS_2020_2024_R1_R6.shp DIXIE_SHP_DIR"""
import sys,glob,os,re,pandas as pd,geopandas as gpd,pyogrio
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','nirops_access'))
import nirops_access as na
shp,rawdir=sys.argv[1],sys.argv[2]
inc='CA-BTU-009205_Dixie'
arch=na.read_incident(shp,inc,{inc})
arch['UTC']=pd.to_datetime(arch['UTC']); arch=arch.to_crs(5070)
arch['local_date']=(arch.UTC-pd.Timedelta(hours=7)).dt.date
rows=[]
for f in sorted(glob.glob(rawdir+'/*.shp')):
    b=os.path.basename(f); d=pd.to_datetime(b[:8]).date()
    if re.search(r'IntenseHeat|ScatteredHeat',b): continue
    g=pyogrio.read_dataframe(f)
    if 'Name' in g and g.Name.astype(str).str.contains('Heat').any():
        g=g[g.Name.astype(str).str.contains('Perimeter')]
    g=g.to_crs(5070); geom=g.geometry.buffer(0).union_all()
    rows.append(dict(date=d,file=b,geom=geom))
built=pd.DataFrame(rows)
out=[]
for _,r in built.iterrows():
    a=arch[arch.local_date==r.date]
    if len(a)==0:
        out.append((r.date,'no-archive-survey',None,None,None)); continue
    for _,x in a.iterrows():
        inter=r.geom.intersection(x.geometry).area; uni=r.geom.union(x.geometry).area
        out.append((r.date,str(x.UTC),round(x.Acres,1),round(r.geom.area/4046.856,1),round(inter/uni,4)))
print('archive surveys',len(arch),'| raw nights',len(built))
for o in out: print(*o)
miss=sorted(set(arch.local_date)-set(built.date)); print('archive local dates with no raw file:',len(miss))
print('--- best match within +-1 local day')
best=[]
for _,r in built.iterrows():
    a=arch[(pd.to_datetime(arch.local_date)-pd.Timestamp(r.date)).abs()<=pd.Timedelta(days=1)]
    if len(a)==0: best.append((r.date,None,None)); continue
    ious=[(r.geom.intersection(g).area/r.geom.union(g).area, str(t), ac) for g,t,ac in zip(a.geometry,a.UTC,a.Acres)]
    m=max(ious); best.append((r.date,round(m[0],4),m[1]))
import numpy as np
v=np.array([b[1] for b in best if b[1] is not None])
print('files',len(best),'with candidate',len(v),'IoU>=0.99:',int((v>=0.99).sum()),'>=0.98:',int((v>=0.98).sum()),'median',round(float(np.median(v)),4),'min',round(float(v.min()),4))
for b in best: print(*b)
