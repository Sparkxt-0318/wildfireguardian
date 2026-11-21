"""Owen's independent bracket extraction for a verification check (filter-read only)."""
import sys, json, datetime, numpy as np, pandas as pd, pyogrio, shapely
from shapely import contains_xy
shp, allow, out = sys.argv[1], sys.argv[2], sys.argv[3]
C=375.0; M=3
ids=sorted(pd.read_csv(allow)["Incident_C"])
log=dict(time_utc=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), allowlist=allow, requested=ids, rows={})
res={}
for inc in ids:
    assert "'" not in inc
    gdf=pyogrio.read_dataframe(shp, where=f"Incident_C = '{inc}'", columns=["Incident_C","UTC"])
    assert (gdf["Incident_C"]==inc).all()
    log["rows"][inc]=int(len(gdf))
    gdf=gdf.to_crs(5070)
    t=pd.to_datetime(gdf["UTC"],utc=True)
    groups=sorted(set(t))
    merged=[shapely.union_all(gdf.geometry[(t==g).to_numpy()].to_numpy()) for g in groups]
    xmin,ymin,xmax,ymax=shapely.total_bounds(np.array(merged))
    x0=np.floor(xmin/C)*C-M*C; y1=np.ceil(ymax/C)*C+M*C
    w=int(np.ceil((xmax-x0)/C))+M; h=int(np.ceil((y1-ymin)/C))+M
    xc=x0+(np.arange(w)+0.5)*C; yc=y1-(np.arange(h)+0.5)*C
    XX,YY=np.meshgrid(xc,yc)
    first=np.full((h,w),-1,np.int32); cum=np.zeros((h,w),bool)
    for k,p in enumerate(merged):
        m=contains_xy(p,XX,YY)
        first[m&~cum]=k; cum|=m
    hours=np.array([(g-groups[0]).total_seconds()/3600 for g in groups])
    res[inc]=dict(first=first,hours=hours)
    np.savez(f"{out}/{inc}.npz",first_survey=first,survey_hours=hours)
json.dump(log,open(f"{out}/owen_access_log.json","w"),indent=1)
print(json.dumps(log))
