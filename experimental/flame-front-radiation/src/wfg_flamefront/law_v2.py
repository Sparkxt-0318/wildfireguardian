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
from .isochrone import front_segments, UnsupportedGeometry, as_grid, _quad_gradient
from .solidflame import rectangle_flux
from .intensity import fireline_intensity,flame_length
from .verified_view import lower_float
from .geometric_bounds import quad_bound


def _inputs(member, fuel):
    if not isinstance(member,dict) or "ignition_time_s" not in member:
        raise ValueError("member mapping with ignition_time_s required")
    tau=np.asarray(member["ignition_time_s"],dtype=float)
    if tau.ndim!=2 or min(tau.shape)<1:raise ValueError("nonempty ignition matrix required")
    for name in ("unknown_mask","valid"):
        if name in member:
            mask=np.asarray(member[name])
            if mask.shape!=tau.shape or mask.dtype!=np.bool_:raise ValueError(name+" must be an aligned Boolean mask")
            missing=mask if name=="unknown_mask" else ~mask
            tau=np.where(missing,np.nan,tau)
    if min(tau.shape)<2 and not np.isposinf(tau).all():raise UnsupportedGeometry("at least two cell centres per axis are needed to identify a front")
    f=dict(fuel or {})
    if member.get("present_fire_representation")=="SCALAR_MAX_REMAINING_ENCLOSURE":
        raise UnsupportedGeometry("scalar present-fire enclosure does not identify a front")
    if "current_active" in member and np.any(member["current_active"]) and not member.get("past_ignitions_known",False):
        raise UnsupportedGeometry("present-fire cells require explicit past ignition times")
    residence=member.get("residence_s",f.get("residence_s",11.52))
    if "extinction_breakpoint_s" in member:
        expiry=np.asarray(member["extinction_breakpoint_s"],dtype=float)
        if expiry.shape != tau.shape or not np.isfinite(expiry).all():
            raise UnsupportedGeometry("extinction field must be finite and aligned with ignition times")
        residence=expiry-tau
    residence=np.broadcast_to(np.asarray(residence,dtype=float),tau.shape)
    if np.any(~np.isfinite(residence)|(residence<=0)):
        raise UnsupportedGeometry("finite positive per-cell residence is required")
    power=np.broadcast_to(np.asarray(f.get("emissive_power_kw_m2",100.),dtype=float),tau.shape)
    if np.any(~np.isfinite(power)|(power<0)):raise ValueError("finite nonnegative emissive power required")
    trans=float(f.get("atmospheric_transmissivity",1.))
    if not math.isfinite(trans) or not 0<=trans<=1:raise ValueError("transmissivity must be in [0,1]")
    return tau,residence,power,trans,f


def _domain(tau,residence,grid,fuel,interval,box=None):
    """Check the point model's domain over a closed query time interval.

    Potential activity in a quad is [min(tau), max(tau+residence)). If either
    boundary field has zero mean gradient, its moving-front interpretation is
    unsupported over that activity interval, even between contour events.
    A closed [a,b] intersects [birth,expiry) iff b>=birth and a<expiry.
    The same rule is used for singleton point times and enclosure intervals.
    """
    a,b=map(float,interval)
    # The contour interpolation still uses binary64 before verified radiation
    # evaluation. Refuse arithmetic overflow consistently for both APIs.
    finite=np.isfinite(tau)
    with np.errstate(over="ignore",invalid="ignore"):
        expiry=tau+residence
    if np.any(finite&~np.isfinite(expiry)):
        raise UnsupportedGeometry("extinction arithmetic exceeds the finite contour domain")
    try:
        for field in (tau[finite],expiry[finite]):
            if field.size:
                extremes=[Fraction(float(field.min()))-Fraction(b),Fraction(float(field.max()))-Fraction(a)]
                if not all(math.isfinite(float(v)) for v in extremes):raise OverflowError()
    except OverflowError as exc:
        raise UnsupportedGeometry("time arithmetic exceeds the finite contour domain") from exc
    segments=front_segments(tau,a,grid,residence,fuel=fuel)
    strict=fuel.get("unsupported_policy","raise")!="exclude"
    if segments.unsupported_cells and strict:
        raise UnsupportedGeometry("unknown or infinite-boundary cells do not identify a finite front")
    effective=np.where(np.isposinf(tau),float(fuel["never_time_s"]),tau) if "never_time_s" in fuel else tau
    g=as_grid(grid);ga,gb,_,gd,ge,_=g.transform
    inverse=np.linalg.inv(np.array([[ga,gb],[gd,ge]])).T
    if strict:
        for row in range(tau.shape[0]-1):
            for col in range(tau.shape[1]-1):
                cells=[(row,col),(row,col+1),(row+1,col+1),(row+1,col)]
                values=np.array([effective[c] for c in cells])
                if not np.isfinite(values).all():continue
                ends=values+np.array([residence[c] for c in cells])
                if b>=float(values.min()) and a<float(ends.max()):
                    if _quad_gradient(values,inverse)[1]==0 or _quad_gradient(ends,inverse)[1]==0:
                        raise UnsupportedGeometry("zero-gradient ignition or extinction field during a potentially active interval")
    # A point on an emitting panel is outside the radiation law. For a box
    # query, conservatively refuse possible panel intersections over the whole
    # interval. The entire tilted panel lies in its quad expanded by Lmax in
    # x/y and between heights zero and Lmax. This guard can reject extra boxes;
    # it cannot convert an undefined point into a finite certificate.
    if box is not None:
        max_length=float(flame_length(fireline_intensity(float(fuel.get("ros_max_m_s",3.)),float(np.max(fuel.get("consumed_fuel_kg_m2",1.))),float(np.max(fuel.get("heat_of_combustion_kj_kg",18608.))))))
        max_length=float(np.nextafter(max_length,math.inf))
        height=float(fuel.get("receiver_height_m",0.))
        if not math.isfinite(height):raise ValueError("receiver_height_m must be finite")
        if 0<=height<=max_length:
            for row in range(tau.shape[0]-1):
                for col in range(tau.shape[1]-1):
                    values=effective[row:row+2,col:col+2]
                    if not np.isfinite(values).all():continue
                    ends=values+residence[row:row+2,col:col+2]
                    if not any(float(v.min())<float(v.max()) and float(v.min())<=b and float(v.max())>=a for v in (values,ends)):continue
                    xy=np.array([g.xy(col+.5,row+.5),g.xy(col+1.5,row+.5),g.xy(col+1.5,row+1.5),g.xy(col+.5,row+1.5)])
                    lo=np.nextafter(xy.min(axis=0)-max_length,-math.inf)
                    hi=np.nextafter(xy.max(axis=0)+max_length,math.inf)
                    if box[1]>=lo[0] and box[0]<=hi[0] and box[3]>=lo[1] and box[2]<=hi[1]:
                        raise UnsupportedGeometry("receiver box may intersect an emitting panel during the query interval")
    return segments,effective


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
        segments,_=_domain(tau,residence,grid,f,(t,t))
        for i,point in enumerate(points):
            values=[]
            for segment in segments:
                try:
                    value=rectangle_flux(point,segment.start_xy,segment.end_xy,segment.flame_height_m,float(power[segment.cell]),tip_shift_xy=segment.tip_shift_xy,receiver=receiver,transmissivity=trans,receiver_height_m=f.get("receiver_height_m",0.))
                except ValueError as exc:
                    if "receiver intersects" in str(exc) or "receiver on emitter" in str(exc):
                        raise UnsupportedGeometry(str(exc)) from exc
                    raise
                values.append(value)
            output[i,j]=lower_float(sum((Fraction(v) for v in values),Fraction(0)))
    return output


def flux_enclosure(box_xy,interval_s,member,grid,fuel=None):
    """Geometry-dependent [0,U] envelope, monotone on its supported domain.

    A quad has at most two segments per contour and two contours, hence at
    most four panels. Each implemented panel's view factor is in [0,1].
    A contour can meet a quad only if its time lies within its corner range
    (marching-squares definition). Increasing an interval only adds candidate
    quads. A rational swept-prism hull bounds each panel's area and its minimum
    squared distance to the receiver box. In a proved common angular cone,
    F<=min(1,A/(3*d2)); pi>3 makes this an exact rational upper bound.
    Outside that cone, retain F<=1. Increasing a receiver box only decreases
    d2, while leaving the hull and area fixed, so the upper cannot shrink. The zero
    lower bound is necessary when emission may switch off during the interval.
    Fraction arithmetic encloses represented E values before upward rounding.
    Domain checking precedes panel selection: if any potentially active quad
    has a zero-gradient ignition/expiry field anywhere in the interval, the
    interval is refused. Potential receiver/panel intersections are refused.
    Finite-bound monotonicity applies only to queries inside this domain.
    Whole-quad hulls need not converge to a point value under refinement.
    """
    box=np.asarray(box_xy,dtype=float);interval=np.asarray(interval_s,dtype=float)
    if box.shape==(2,2):box=np.array([box[0,0],box[1,0],box[0,1],box[1,1]])
    if box.shape!=(4,) or interval.shape!=(2,) or not np.isfinite(box).all() or not np.isfinite(interval).all() or box[0]>box[1] or box[2]>box[3] or interval[0]>interval[1]:
        raise ValueError("box (xmin,xmax,ymin,ymax) and ordered interval required")
    tau,residence,power,trans,f=_inputs(member,fuel)
    _,tau=_domain(tau,residence,grid,f,interval,box)
    if np.isposinf(tau).all():return 0.,0.
    h,w=tau.shape;upper=Fraction(0)
    for r in range(h-1):
        for c in range(w-1):
            values=tau[r:r+2,c:c+2]
            if not np.isfinite(values).all():continue
            ends=values+residence[r:r+2,c:c+2]
            active=any(float(v.min())<float(v.max()) and float(v.min())<=interval[1] and float(v.max())>=interval[0] for v in (values,ends))
            if active:
                factor,_=quad_bound(r,c,tau,grid,f,box)
                upper+=4*Fraction(float(power[r,c]))*Fraction(trans)*factor
    if not upper:return 0.,0.
    try:value=float(upper)
    except OverflowError:return 0.,math.inf
    if not math.isfinite(value):return 0.,math.inf
    while Fraction(value)<upper:value=float(np.nextafter(value,math.inf))
    return 0.,value


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
