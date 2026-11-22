import geopandas as gpd, numpy as np, pandas as pd
from shapely.geometry import box
from pyproj import Transformer
to4326=Transformer.from_crs("EPSG:5070","EPSG:4326",always_xy=True)
C=375.0; X0,Y0=-2000*C, 1000*C   # grid-aligned origin in EPSG:5070
def cells(c0,r0,c1,r1):  # box covering cell columns c0..c1-1 and rows r0..r1-1 (rows upward), shrunk inside cell edges
    xa,ya=X0+c0*C+1, Y0+r0*C+1; xb,yb=X0+c1*C-1, Y0+r1*C-1
    xs,ys=to4326.transform([xa,xb,xb,xa],[ya,ya,yb,yb])
    from shapely.geometry import Polygon
    return Polygon(list(zip(xs,ys)))
rows=[
 # incident A: surveys out of order in file; duplicate timestamp at t=12h (two polys merged); shrink at 24h
 ("A-TEST_Alpha","2024-07-01T12:00:00Z",cells(0,0,4,4)),     # t=12h part 1
 ("A-TEST_Alpha","2024-07-01T00:00:00Z",cells(0,0,2,2)),     # t=0  initial 2x2
 ("A-TEST_Alpha","2024-07-01T12:00:00Z",cells(4,0,5,1)),     # t=12h part 2 (merged)
 ("A-TEST_Alpha","2024-07-02T00:00:00Z",cells(0,0,3,3)),     # t=24h SHRINK (subset of 12h) -> no new cells
 ("A-TEST_Alpha","2024-07-02T06:00:00Z",cells(0,0,6,5)),     # t=30h growth
 ("Z-DECOY_Sealed","2024-07-01T00:00:00Z",cells(100,100,140,140)),  # must never be read
]
df=gpd.GeoDataFrame({"Incident_C":[r[0] for r in rows],"UTC":[r[1] for r in rows]},geometry=[r[2] for r in rows],crs="EPSG:4326")
df.to_file("synshp/syn.shp")
pd.DataFrame({"Incident_C":["A-TEST_Alpha","B-TEST_Few"],"irwinid":["x","y"],"year":[2024,2024],"surveys":[25,5]}).to_csv("synshp/allow.csv",index=False)
