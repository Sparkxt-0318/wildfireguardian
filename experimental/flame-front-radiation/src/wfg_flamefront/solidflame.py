"""Exact planar polygon differential view factors for diffuse solid flames.

The edge-angle vector formula is Hottel and Sarofim (1967), reproduced in
Walton (2002), NISTIR 6925, Eq. 5. Radiance is E/pi. Two faces of each flame
panel emit independently; no smoke attenuation or occlusion is represented.
The maximizer for the unoccluded patch is the projected-solid-angle vector,
not in general the direction toward its centre. Fixed normals are clipped to
their forward hemisphere before integration. Overlap sums add radiance.
"""
from __future__ import annotations

import math
from fractions import Fraction
import numpy as np
from .verified_view import polygon_factor,lower_float


def polygon_view_factor(vertices, point, receiver="worst_case"):
    """Differential receiver to a planar convex emitter, dimensionless [0,1].

    Worst-case uses the maximizing vector normal if all rays lie in its
    forward hemisphere. Otherwise it uses the unit view-factor orientation
    envelope, marked by the caller's model scenario.
    Such an envelope is not an orientation-specific physical prediction.
    """
    vertices=np.asarray(vertices,dtype=float);point=np.asarray(point,dtype=float)
    if vertices.shape[1:]!=(3,) or len(vertices)<3 or point.shape!=(3,) or not np.isfinite(vertices).all() or not np.isfinite(point).all():
        raise ValueError("finite polygon [N,3] and point [3] required")
    return polygon_factor(vertices,point,receiver)


def rectangle_vertices(start_xy,end_xy,height_m,tip_shift_xy=(0.,0.)):
    p=np.asarray(start_xy,dtype=float);q=np.asarray(end_xy,dtype=float);shift=np.asarray(tip_shift_xy,dtype=float)
    h=float(height_m)
    if p.shape!=(2,) or q.shape!=(2,) or shift.shape!=(2,) or not np.isfinite(np.r_[p,q,shift,h]).all() or h<0:
        raise ValueError("finite geometry and nonnegative height required")
    return np.array([[*p,0.],[*q,0.],[*(q+shift),h],[*(p+shift),h]])


def rectangle_flux(point_xy,start_xy,end_xy,height_m,emissive_power_kw_m2=100.,*,tip_shift_xy=(0.,0.),receiver="worst_case",transmissivity=1.,receiver_height_m=0.):
    e=float(emissive_power_kw_m2);trans=float(transmissivity)
    if not math.isfinite(e) or e<0 or not math.isfinite(trans) or not 0<=trans<=1:
        raise ValueError("emissive power nonnegative and transmissivity in [0,1] required")
    if height_m==0 or np.array_equal(start_xy,end_xy):return 0.0
    # Keep the declared parallelogram exactly planar. Adding a tip shift in
    # binary64 independently at each end can create an unintended warped quad.
    rectangle_vertices(start_xy,end_xy,height_m,tip_shift_xy) # input validation
    p=[Fraction(float(v)) for v in start_xy];q=[Fraction(float(v)) for v in end_xy]
    s=[Fraction(float(v)) for v in tip_shift_xy];h=Fraction(float(height_m))
    vertices=[[p[0],p[1],Fraction(0)],[q[0],q[1],Fraction(0)],
              [q[0]+s[0],q[1]+s[1],h],[p[0]+s[0],p[1]+s[1],h]]
    factor=polygon_factor(vertices,[*point_xy,float(receiver_height_m)],receiver)
    return lower_float(Fraction(e)*Fraction(trans)*Fraction(factor))


def infinite_wall_view_factor(height_m,distance_m):
    """Ground-level horizontal normal facing an infinitely wide vertical wall.

    F = h/(2 sqrt(h*h+d*d)); this is NOT the worst-case tilted receiver.
    """
    h=float(height_m);d=float(distance_m)
    if not math.isfinite(h) or not math.isfinite(d) or h<0 or d<=0:raise ValueError("h>=0 and d>0 required")
    return .5*h/math.hypot(h,d)


def finite_panel_view_factor(width_m,height_m,distance_m,*,receiver="vertical_facing(0)",receiver_height_m=0.):
    w=float(width_m)
    if not math.isfinite(w) or w<=0:raise ValueError("width must be positive")
    return polygon_view_factor(rectangle_vertices((distance_m,-w/2),(distance_m,w/2),height_m),(0,0,float(receiver_height_m)),receiver)


def omitted_absolute_bound(emissive_powers_kw_m2):
    """Finite omitted-source envelope, sum E_i because each view factor <=1.

    No finite radius alone supplies a uniform relative-error bound: add enough
    omitted panels while retained flux tends to zero. Default evaluation has
    no cutoff. This deliberately loose absolute envelope makes that explicit.
    """
    values=np.asarray(emissive_powers_kw_m2,dtype=float)
    if np.any(~np.isfinite(values)|(values<0)):raise ValueError("nonnegative finite powers required")
    return float(np.nextafter(math.fsum(values.ravel()),math.inf)) if values.size else 0.
