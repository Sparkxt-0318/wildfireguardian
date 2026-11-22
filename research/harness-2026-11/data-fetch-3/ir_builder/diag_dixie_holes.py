"""Diagnosis (after the run, not an acceptance test): Dixie built vs archive per night, with and without interior holes filled.
Usage: python3 -I diag_dixie_holes.py NIROPS.shp BUILT.gpkg"""
import sys,os,pandas as pd,geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
sys.path.insert(0,'/home/user/wildfireguardian/research/harness-2026-11/data-fetch-3/nirops_access')
import nirops_access as na
INC='CA-BTU-009205_Dixie'
arch=na.read_incident(sys.argv[1],INC,{INC}).to_crs(5070); arch['d']=pd.to_datetime(arch.UTC).dt.strftime('%Y-%m-%d')
b=gpd.read_file(sys.argv[2]).to_crs(5070)
def fill(g):
    ps=[g] if g.geom_type=='Polygon' else list(g.geoms)
    return MultiPolygon([Polygon(p.exterior) for p in ps]).buffer(0)
def holes(g):
    ps=[g] if g.geom_type=='Polygon' else list(g.geoms)
    return sum(len(p.interiors) for p in ps), len(ps)
for _,r in b.iterrows():
    a=arch[arch.d==r.DateUTC]
    if a.empty: continue
    x=a.iloc[0].geometry; g=r.geometry
    iou=g.intersection(x).area/g.union(x).area
    gf=fill(g); xf=fill(x)
    iouf=gf.intersection(xf).area/gf.union(xf).area
    only_a=x.difference(g).area/1e6; only_b=g.difference(x).area/1e6
    print(r.DateUTC, round(iou,4),'filled-both',round(iouf,4),'holes built/arch',holes(g),holes(x),'km2 arch-only',round(only_a,1),'built-only',round(only_b,1))
