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
import numpy as np


def _moment(vertices, point):
    rays=np.asarray(vertices,dtype=float)-np.asarray(point,dtype=float)
    radii=np.linalg.norm(rays,axis=1)
    if np.any(radii==0):
        raise ValueError("receiver on emitter vertex is unsupported")
    unit=rays/radii[:,None]
    result=np.zeros(3)
    for a,b in zip(unit,np.roll(unit,-1,axis=0)):
        cross=np.cross(a,b); norm=float(np.linalg.norm(cross))
        if norm:
            angle=math.atan2(norm,float(np.dot(a,b)))
            result+=angle*cross/norm/2
    if np.dot(result,rays.mean(axis=0))<0:
        result=-result
    return result


def polygon_view_factor(vertices, point, receiver="worst_case"):
    """Differential receiver to a planar convex emitter, dimensionless [0,1].

    Worst-case uses the maximizing vector normal if all rays lie in its
    forward hemisphere. Otherwise it uses a rigorous orientation envelope
    (solid angle/pi, capped at one), marked by the caller's model scenario.
    Such an envelope is not an orientation-specific physical prediction.
    """
    vertices=np.asarray(vertices,dtype=float);point=np.asarray(point,dtype=float)
    if vertices.shape[1:]!=(3,) or len(vertices)<3 or point.shape!=(3,) or not np.isfinite(vertices).all() or not np.isfinite(point).all():
        raise ValueError("finite polygon [N,3] and point [3] required")
    plane=np.cross(vertices[1]-vertices[0],vertices[2]-vertices[0]);scale=float(np.linalg.norm(plane))
    if scale==0:return 0.
    if abs(float(np.dot(point-vertices[0],plane)))<=1e-13*scale:
        signs=[float(np.dot(np.cross(b-a,point-a),plane)) for a,b in zip(vertices,np.roll(vertices,-1,axis=0))]
        if all(s>=-1e-12 for s in signs) or all(s<=1e-12 for s in signs):
            raise ValueError("receiver intersects an emitting panel; contact is outside the radiation law")
    moment=_moment(vertices,point)
    if isinstance(receiver,str) and receiver=="worst_case":
        norm=float(np.linalg.norm(moment))
        if not norm:
            return 0.0
        normal=moment/norm
        if np.all((vertices-point)@normal>=-1e-12):
            return float(np.clip(norm/math.pi,0,1))
        return 1.0
    if isinstance(receiver,str) and receiver.startswith("vertical_facing(") and receiver.endswith(")"):
        angle=float(receiver[len("vertical_facing("):-1]);normal=np.array([math.cos(angle),math.sin(angle),0.])
    else:
        normal=np.asarray(receiver,dtype=float)
        if normal.shape!=(3,) or not np.isfinite(normal).all() or np.linalg.norm(normal)==0:
            raise ValueError("receiver must be worst_case, vertical_facing(theta), or a nonzero normal")
        normal=normal/np.linalg.norm(normal)
    # Sutherland-Hodgman clipping by the receiver's horizon plane.
    clipped=[]
    for a,b in zip(vertices,np.roll(vertices,-1,axis=0)):
        da=float(np.dot(a-point,normal));db=float(np.dot(b-point,normal))
        if da>=0:clipped.append(a)
        if (da>=0)!=(db>=0):clipped.append(a+da/(da-db)*(b-a))
    if len(clipped)<3:return 0.0
    return float(np.clip(np.dot(_moment(clipped,point),normal)/math.pi,0,1))


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
    vertices=rectangle_vertices(start_xy,end_xy,height_m,tip_shift_xy)
    return e*trans*polygon_view_factor(vertices,[*point_xy,float(receiver_height_m)],receiver)


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
