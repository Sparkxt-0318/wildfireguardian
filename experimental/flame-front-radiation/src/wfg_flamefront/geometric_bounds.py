"""Exact rational swept-hull bounds for the declared parallelogram panels.

The whole quad is a containing hull for every leading/trailing segment over
the queried interval. It is deliberately independent of time subdivision.
Interpolated binary64 endpoints are bounded using monotonic rounded arithmetic,
including the subtract/add roundoff at each quad edge. Tip displacement and
height are the same represented constants used by the point evaluator.
"""
from fractions import Fraction as F
import math
import numpy as np
from .isochrone import as_grid,_at,_quad_gradient,UnsupportedGeometry
from .intensity import fireline_intensity,flame_length,flame_geometry


def _rounded(value):
    try:result=float(value)
    except OverflowError as exc:raise UnsupportedGeometry("contour coordinate arithmetic exceeds binary64") from exc
    if not math.isfinite(result):raise UnsupportedGeometry("contour coordinate arithmetic exceeds binary64")
    return F(result)


def quad_bound(row,col,tau,grid,fuel,box):
    """Return a rational per-panel view-factor upper and its proof quantities.

    Let Dx,Dy enclose base endpoint differences, s=(sx,sy,h) the flame side.
    Area=|edge cross s| <= h(Dx+Dy)+Dx|sy|+Dy|sx| = A.
    Let d2 be box-to-swept-prism squared minimum distance, D2 its squared
    diameter. If 2*d2>D2, every pair of possible source rays has positive dot
    product. The full-patch maximizing normal sees every vertex, so the point
    evaluator's orientation-envelope branch is impossible. Then
    F <= min(1,A/(pi*d2)) <= min(1,A/(3*d2)), using the proved pi>3.
    Outside that cone use F<=1. All arithmetic after represented geometry
    construction is exact Fraction arithmetic, not an epsilon allowance.
    """
    g=as_grid(grid);ga,gb,_,gd,ge,_=g.transform
    inverse=np.linalg.inv(np.array([[ga,gb],[gd,ge]])).T
    cells=[(row,col),(row,col+1),(row+1,col+1),(row+1,col)]
    values=np.array([tau[c] for c in cells]);gradient,norm=_quad_gradient(values,inverse)
    max_rate=float(fuel.get("ros_max_m_s",3.))
    rate=min(max_rate,1/norm) if norm else max_rate
    intensity=float(fireline_intensity(rate,_at(fuel.get("consumed_fuel_kg_m2",1.),(row,col),tau.shape,"consumed_fuel"),_at(fuel.get("heat_of_combustion_kj_kg",18608.),(row,col),tau.shape,"heat")))
    length=float(flame_length(intensity));height,_,shift=flame_geometry(length,fuel.get("wind_xy",(0,0)))
    if not np.isfinite([height,*shift]).all():raise UnsupportedGeometry("nonfinite emitting geometry")
    xy=[g.xy(col+.5,row+.5),g.xy(col+1.5,row+.5),g.xy(col+1.5,row+1.5),g.xy(col+.5,row+1.5)]
    if not np.isfinite(xy).all():raise UnsupportedGeometry("nonfinite contour coordinates")
    base=[]
    for axis in (0,1):
        endpoints=[]
        for i,j in ((0,1),(1,2),(2,3),(3,0)):
            start=F(float(xy[i][axis]));delta=_rounded(F(float(xy[j][axis]))-start)
            endpoints.extend([start,_rounded(start+delta)])
        base.append((min(endpoints),max(endpoints)))
    sx,sy=map(lambda v:F(float(v)),shift);h=F(float(height))
    dx=base[0][1]-base[0][0];dy=base[1][1]-base[1][0]
    area=h*(dx+dy)+dx*abs(sy)+dy*abs(sx)
    hull=[(base[0][0]+min(F(0),sx),base[0][1]+max(F(0),sx)),
          (base[1][0]+min(F(0),sy),base[1][1]+max(F(0),sy)),(F(0),h)]
    receiver=[(F(float(box[0])),F(float(box[1]))),(F(float(box[2])),F(float(box[3])))]
    rh=F(float(fuel.get("receiver_height_m",0.)));receiver.append((rh,rh))
    gaps=[max(F(0),lo-bhi,blo-hi) for (lo,hi),(blo,bhi) in zip(hull,receiver)]
    distance2=sum((v*v for v in gaps),F(0))
    diameter2=sum(((hi-lo)**2 for lo,hi in hull),F(0))
    if not distance2:
        raise UnsupportedGeometry("receiver box may intersect the exact swept emitter hull")
    cone=2*distance2>diameter2
    factor=min(F(1),area/(3*distance2)) if cone else F(1)
    return factor,{"area_upper":area,"distance2_lower":distance2,"diameter2_upper":diameter2,"cone_proved":cone,"hull":hull}
