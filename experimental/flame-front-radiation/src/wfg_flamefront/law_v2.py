"""Opt-in finite-source solid-flame law, kW/m2 and seconds.

Receiver 'worst_case' maximizes each panel independently. This over-encloses
any single common receiver orientation when contributions are summed.
Unknown front geometry is refused by default, not interpreted as no fire.
The law omits convection, smoke, embers and vehicle shielding. Literature
burnover heat and toxicity observations do not validate vehicle tenability.
The loose enclosure is a proof-bearing fallback, not a useful universal
certificate: numerical random tests do not establish its mathematical proof.
"""
from __future__ import annotations

import math
from fractions import Fraction
import numpy as np
from .isochrone import front_segments, UnsupportedGeometry
from .solidflame import rectangle_flux


def _inputs(member, fuel):
    if not isinstance(member,dict) or "ignition_time_s" not in member:
        raise ValueError("member mapping with ignition_time_s required")
    tau=np.asarray(member["ignition_time_s"],dtype=float)
    if tau.ndim!=2 or min(tau.shape)<2:raise UnsupportedGeometry("at least two cell centres per axis are needed to identify a front")
    for name in ("unknown_mask","valid"):
        if name in member:
            mask=np.asarray(member[name])
            if mask.shape!=tau.shape or mask.dtype!=np.bool_:raise ValueError(name+" must be an aligned Boolean mask")
            missing=mask if name=="unknown_mask" else ~mask
            tau=np.where(missing,np.nan,tau)
    f=dict(fuel or {})
    if member.get("present_fire_representation")=="SCALAR_MAX_REMAINING_ENCLOSURE":
        raise UnsupportedGeometry("scalar present-fire enclosure does not identify a front")
    if "current_active" in member and np.any(member["current_active"]) and not member.get("past_ignitions_known",False):
        raise UnsupportedGeometry("present-fire cells require explicit past ignition times")
    residence=member.get("residence_s",f.get("residence_s",11.52))
    if "extinction_breakpoint_s" in member:
        expiry=np.asarray(member["extinction_breakpoint_s"],dtype=float)
        if expiry.shape==tau.shape:
            residence=expiry-tau
    residence=np.broadcast_to(np.asarray(residence,dtype=float),tau.shape)
    if np.any(~np.isfinite(residence)|(residence<=0)):
        raise UnsupportedGeometry("finite positive per-cell residence is required")
    power=np.broadcast_to(np.asarray(f.get("emissive_power_kw_m2",100.),dtype=float),tau.shape)
    if np.any(~np.isfinite(power)|(power<0)):raise ValueError("finite nonnegative emissive power required")
    trans=float(f.get("atmospheric_transmissivity",1.))
    if not math.isfinite(trans) or not 0<=trans<=1:raise ValueError("transmissivity must be in [0,1]")
    return tau,residence,power,trans,f


def flux_at_points(points_xy,times_s,member,grid,fuel=None,receiver="worst_case"):
    """Return [P,T] kW/m2 from actual subcell source and receiver geometry.

    Leading and trailing fronts are represented as emitting panels. This
    two-boundary construction is an explicitly declared model scenario.
    Scalar old-cell activity without past arrival cannot select these panels.
    """
    points=np.asarray(points_xy,dtype=float);times=np.asarray(times_s,dtype=float)
    if points.ndim!=2 or points.shape[1]!=2 or times.ndim!=1 or not np.isfinite(points).all() or not np.isfinite(times).all():
        raise ValueError("finite points [P,2] and times [T] required")
    tau,residence,power,trans,f=_inputs(member,fuel)
    output=np.zeros((len(points),len(times)))
    for j,t in enumerate(times):
        segments=front_segments(tau,float(t),grid,residence,fuel=f)
        if segments.unsupported_cells and f.get("unsupported_policy","raise")!="exclude":
            raise UnsupportedGeometry("unknown or infinite-boundary cells do not identify a finite front")
        for row,col in segments.degenerate_quads:
            values=tau[row:row+2,col:col+2]
            ends=values+residence[row:row+2,col:col+2]
            if float(values.min())<=t<float(ends.max()) and f.get("unsupported_policy","raise")!="exclude":
                raise UnsupportedGeometry("simultaneous ignition has no identifiable moving-front gradient")
        for i,point in enumerate(points):
            values=[]
            for segment in segments:
                values.append(rectangle_flux(point,segment.start_xy,segment.end_xy,segment.flame_height_m,float(power[segment.cell]),tip_shift_xy=segment.tip_shift_xy,receiver=receiver,transmissivity=trans))
            output[i,j]=math.fsum(values)
    return output


def flux_enclosure(box_xy,interval_s,member,grid,fuel=None):
    """Rigorous coarse [0,U] envelope, monotone under box/time containment.

    A quad has at most two segments per contour and two contours, hence at
    most four panels. Each implemented panel's view factor is in [0,1].
    A contour can meet a quad only if its time lies within its corner range
    (marching-squares definition). Increasing an interval only adds candidate
    quads. Therefore U=sum(4 E_quad) over candidates bounds every point/time.
    Bounds ignore position, so enlargement cannot shrink them. The zero
    lower bound is necessary when emission may switch off during the interval.
    Fraction arithmetic encloses represented E values before upward rounding.
    This finite coarse bound usually cannot decide route thermal acceptance.
    """
    box=np.asarray(box_xy,dtype=float);interval=np.asarray(interval_s,dtype=float)
    if box.shape==(2,2):box=np.array([box[0,0],box[1,0],box[0,1],box[1,1]])
    if box.shape!=(4,) or interval.shape!=(2,) or not np.isfinite(box).all() or not np.isfinite(interval).all() or box[0]>box[1] or box[2]>box[3] or interval[0]>interval[1]:
        raise ValueError("box (xmin,xmax,ymin,ymax) and ordered interval required")
    tau,residence,power,_,f=_inputs(member,fuel)
    if "never_time_s" in f:tau=np.where(np.isposinf(tau),float(f["never_time_s"]),tau)
    if np.any(~np.isfinite(tau)) and f.get("unsupported_policy","raise")!="exclude":
        raise UnsupportedGeometry("unknown or infinite-boundary cells do not identify a finite front")
    h,w=tau.shape;upper=Fraction(0)
    for r in range(h-1):
        for c in range(w-1):
            values=tau[r:r+2,c:c+2]
            if not np.isfinite(values).all():continue
            ends=values+residence[r:r+2,c:c+2]
            active=any(float(v.min())<=interval[1] and float(v.max())>=interval[0] for v in (values,ends))
            if active:upper+=4*Fraction(float(power[r,c]))
    if not upper:return 0.,0.
    value=float(upper)
    if not math.isfinite(value):return 0.,math.inf
    if Fraction(value)<upper:value=float(np.nextafter(value,math.inf))
    # One additional ulp encloses a final correctly rounded fsum of products
    # whose factors E, trans and clipped F are individually nonnegative.
    return 0.,float(np.nextafter(value,math.inf))


def dose(q,times_s,form="linear"):
    """Integrate a piecewise-linear nonnegative flux curve exactly per segment.

    Linear returns kJ/m2. TDU returns (kW/m2)^(4/3) s and analytically
    integrates q^(4/3) for linearly varying q, not a trapezoid of q^(4/3).
    This is a declared interpolation assumption, not an enclosure of an
    unsampled moving-front flux. It must not decide continuous-route acceptance.
    """
    values=np.asarray(q,dtype=float);times=np.asarray(times_s,dtype=float)
    if values.ndim!=1 or times.ndim!=1 or values.shape!=times.shape or len(times)<1 or np.any(~np.isfinite(values)|(values<0)) or not np.isfinite(times).all() or np.any(np.diff(times)<=0):
        raise ValueError("aligned finite nonnegative flux and strictly increasing times required")
    if form not in ("linear","tdu"):raise ValueError("dose form must be linear or tdu")
    a=values[:-1];b=values[1:];dt=np.diff(times)
    if form=="linear":return float(np.sum(dt*(a+b)/2))
    out=[]
    for x,y,d in zip(a,b,dt):
        if x==y:
            value=d*x**(4/3)
        elif x==0:
            value=d*3/7*y**(4/3)
        elif y==0:
            value=d*3/7*x**(4/3)
        else:
            value=d*3/7*x**(7/3)*math.expm1(7/3*math.log1p((y-x)/x))/(y-x)
        out.append(float(value))
    return math.fsum(out)


def bal_band(peak_kw_m2):
    """AS 3959 exposure-band vocabulary only, not a route safety threshold."""
    p=float(peak_kw_m2)
    if not math.isfinite(p) or p<0:raise ValueError("finite nonnegative peak required")
    for value,label in ((12.5,"BAL-12.5"),(19,"BAL-19"),(29,"BAL-29"),(40,"BAL-40")):
        if p<=value:return label
    return "above BAL-40 (flame-zone band; contact is evaluated separately)"
