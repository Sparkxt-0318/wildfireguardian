"""Independent rational-interval reference for the declared finite-source law.

No candidate code, NumPy, binary64 arithmetic or libm transcendental is used.
A rectangle is split into two triangles; its solid angle is enclosed using
positive determinant/norm/dot-product triangle formulae, not corner subtraction.
All input floats mean their exact represented rational values. Units here are
source density W/m², received flux W/m², time s, dose J/m².
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as Q
from functools import lru_cache
import heapq
import math
import time

BITS = 160
ATAN_TERMS = 192


def number(x):
    if isinstance(x, bool):
        raise ValueError('Boolean is not a model coefficient')
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError('Finite input required')
    return Q(x)


def pow2(e):
    return Q(1 << e) if e >= 0 else Q(1, 1 << -e)


def exponent(x):
    x = abs(x)
    if not x:
        raise ValueError('zero exponent')
    e = x.numerator.bit_length() - x.denominator.bit_length()
    return e - 1 if x < pow2(e) else e


def rounded(x, upper, bits=BITS):
    x = number(x)
    if not x:
        return x
    step = pow2(exponent(x) - bits)
    v = x / step
    k = -((-v.numerator) // v.denominator) if upper else v.numerator // v.denominator
    return k * step


@dataclass(frozen=True)
class Interval:
    lo: Q
    hi: Q

    def __post_init__(self):
        object.__setattr__(self, 'lo', number(self.lo))
        object.__setattr__(self, 'hi', number(self.hi))
        if self.lo > self.hi:
            raise ArithmeticError('Reversed interval')

    @classmethod
    def point(cls, value):
        return cls(number(value), number(value))

    def __add__(self, other):
        other = as_interval(other)
        return Interval(rounded(self.lo + other.lo, False), rounded(self.hi + other.hi, True))

    __radd__ = __add__

    def __neg__(self):
        return Interval(-self.hi, -self.lo)

    def __sub__(self, other):
        return self + -as_interval(other)

    def __rsub__(self, other):
        return as_interval(other) - self

    def __mul__(self, other):
        other = as_interval(other)
        products = (self.lo * other.lo, self.lo * other.hi,
                    self.hi * other.lo, self.hi * other.hi)
        return Interval(rounded(min(products), False), rounded(max(products), True))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = as_interval(other)
        if other.lo <= 0 <= other.hi:
            raise ArithmeticError('Division interval contains zero')
        inv = Interval(rounded(1 / other.hi, False), rounded(1 / other.lo, True))
        return self * inv

    @property
    def width(self):
        return self.hi - self.lo

    def contains(self, value):
        return self.lo <= number(value) <= self.hi


def as_interval(x):
    return x if isinstance(x, Interval) else Interval.point(x)


def square(x):
    x = as_interval(x)
    lo = Q(0) if x.lo <= 0 <= x.hi else min(x.lo*x.lo, x.hi*x.hi)
    return Interval(rounded(lo, False), rounded(max(x.lo*x.lo, x.hi*x.hi), True))


def sqrt_point(x, bits=BITS):
    """Exact integer-square-root bracket, with relative dyadic precision."""
    x = number(x)
    if x < 0:
        raise ValueError('Negative radicand')
    if not x:
        return Interval.point(0)
    step = pow2(exponent(x)//2 - bits)
    scaled = x / (step*step)
    k = math.isqrt(scaled.numerator // scaled.denominator)
    lo = k*step
    return Interval(lo, lo if lo*lo == x else (k+1)*step)


def sqrt_interval(x):
    x = as_interval(x)
    if x.lo < 0:
        raise ValueError('Negative interval radicand')
    return Interval(sqrt_point(x.lo).lo, sqrt_point(x.hi).hi)


def _atan_unit(x):
    """Euler's positive series with geometric tail, 0 <= x <= 1.

    atan x = x/(1+x²) sum_n a_n r^n, r=x²/(1+x²),
    a_0=1, a_(n+1)/a_n=(2n+2)/(2n+3). Since a_n decreases,
    the remaining tail after N terms is <= term_N/(1-r).
    """
    x = number(x)
    if not 0 <= x <= 1:
        raise ValueError('Unit atan precondition')
    if not x:
        return Interval.point(0)
    r = as_interval(x*x/(1+x*x))
    factor = as_interval(x/(1+x*x))
    total = Interval.point(0)
    term = Interval.point(1)
    for n in range(ATAN_TERMS):
        total = total + term
        term = term * r * Q(2*n+2, 2*n+3)
        # The exact positive tail is already bounded.  Stop once its relative
        # size is below the working arithmetic scale; this prevents enormous
        # exponents from repeated powers of subnormal-scale arguments.
        if (term/(1-r)).hi <= max(total.lo, Q(1))*pow2(-BITS-8):
            break
    lower = (factor * total).lo
    upper = (factor * (total + term/(1-r))).hi
    return Interval(max(Q(0), lower), upper)


@lru_cache(maxsize=1)
def pi_interval():
    # atan(1/2)+atan(1/3)=pi/4, with both angles in (0,pi/2).
    return 4 * (_atan_unit(Q(1,2)) + _atan_unit(Q(1,3)))


def atan_point(x):
    x = number(x)
    if x < 0:
        return -atan_point(-x)
    if x > 1:
        return pi_interval()/2 - _atan_unit(1/x)
    return _atan_unit(x)


def _triangle_angle(vectors, determinant):
    """Rigorous solid angle of an upper-half-space triangle.

    det > 0 is exact and invariant under horizontal receiver translations.
    X encloses |a||b||c|+(a.b)|c|+(b.c)|a|+(c.a)|b|.
    Ω=2 atan2(det,X) is strictly decreasing in X for det>0.
    """
    if determinant <= 0:
        raise ValueError('Positive determinant required')
    a,b,c = vectors
    norms = [sqrt_interval(sum((square(v) for v in row), Interval.point(0)))
             for row in vectors]
    dot = lambda u,v: sum((x*y for x,y in zip(u,v)), Interval.point(0))
    X = norms[0]*norms[1]*norms[2] + dot(a,b)*norms[2] + dot(b,c)*norms[0] + dot(c,a)*norms[1]
    p = pi_interval()
    if X.lo > 0:
        lo = 2*atan_point(determinant/X.hi).lo
        hi = 2*atan_point(determinant/X.lo).hi
    elif X.hi < 0:
        lo = 2*p.lo - 2*atan_point(determinant/(-X.hi)).hi
        hi = 2*p.hi - 2*atan_point(determinant/(-X.lo)).lo
    else:
        lo = p.lo - 2*atan_point(X.hi/determinant).hi
        hi = p.hi - 2*atan_point(X.lo/determinant).lo
    return Interval(max(Q(0), lo), min(2*p.hi, hi))


def rectangle_coefficient(rect, receiver_box, height):
    """Enclose Ω/(4π) uniformly for every receiver in an axis-aligned box.

    rect=(sx0,sx1,sy0,sy1); receiver_box=(rx0,rx1,ry0,ry1).
    Exact degeneracies give zero; reversed intervals are invalid.
    """
    sx0,sx1,sy0,sy1 = map(number, rect)
    rx0,rx1,ry0,ry1 = map(number, receiver_box)
    h = number(height)
    if sx0 > sx1 or sy0 > sy1 or rx0 > rx1 or ry0 > ry1 or h <= 0:
        raise ValueError('Geometry precondition')
    if sx0 == sx1 or sy0 == sy1:
        return Interval.point(0)
    vertex = lambda x,y: (Interval(x-rx1,x-rx0), Interval(y-ry1,y-ry0), Interval.point(h))
    a,b,c,d = [vertex(x,y) for x,y in ((sx0,sy0),(sx1,sy0),(sx1,sy1),(sx0,sy1))]
    determinant = (sx1-sx0)*(sy1-sy0)*h
    omega = _triangle_angle((a,b,c),determinant) + _triangle_angle((a,c,d),determinant)
    value = omega/(4*pi_interval())
    return Interval(max(Q(0),value.lo),min(Q(1,2),value.hi))


def radial_integral_coefficient(rect, receiver_box, height):
    """Second independent coarse enclosure by positive area integration."""
    sx0,sx1,sy0,sy1 = map(number,rect)
    rx0,rx1,ry0,ry1 = map(number,receiver_box)
    h = number(height)
    if sx0>sx1 or sy0>sy1 or rx0>rx1 or ry0>ry1 or h<=0:
        raise ValueError('Geometry precondition')
    area=(sx1-sx0)*(sy1-sy0)
    if not area:return Interval.point(0)
    dx=max(Q(0),sx0-rx1,rx0-sx1);dy=max(Q(0),sy0-ry1,ry0-sy1)
    fx=max(abs(x-y) for x in (sx0,sx1) for y in (rx0,rx1))
    fy=max(abs(x-y) for x in (sy0,sy1) for y in (ry0,ry1))
    near=dx*dx+dy*dy+h*h;far=fx*fx+fy*fy+h*h
    p=pi_interval()
    lo=area*h/(4*p.hi*far*sqrt_point(far).hi)
    hi=area*h/(4*p.lo*near*sqrt_point(near).lo)
    return Interval(max(Q(0),lo),min(Q(1,2),hi))


@dataclass(frozen=True)
class Source:
    rect: tuple
    height: Q
    density: Q
    birth: Q
    expiry: Q

    def __post_init__(self):
        object.__setattr__(self,'rect',tuple(map(number,self.rect)))
        for k in ('height','density','birth','expiry'):
            object.__setattr__(self,k,number(getattr(self,k)))
        if len(self.rect)!=4 or self.rect[0]>self.rect[1] or self.rect[2]>self.rect[3] or self.height<=0 or self.density<0 or self.birth>self.expiry:
            raise ValueError('Source precondition')

    def active(self,t):
        return self.birth <= t < self.expiry


@dataclass(frozen=True)
class Leg:
    start: Q
    end: Q
    p0: tuple
    p1: tuple
    kind: str='ROAD'

    def __post_init__(self):
        object.__setattr__(self,'start',number(self.start));object.__setattr__(self,'end',number(self.end))
        object.__setattr__(self,'p0',tuple(map(number,self.p0)));object.__setattr__(self,'p1',tuple(map(number,self.p1)))
        if self.start>self.end or len(self.p0)!=2 or len(self.p1)!=2 or (self.start==self.end and self.p0!=self.p1):
            raise ValueError('Leg precondition')

    def point(self,t):
        if not self.start<=t<=self.end:raise ValueError('Time outside leg')
        if self.end==self.start:return self.p0
        u=(t-self.start)/(self.end-self.start)
        return tuple(a+(b-a)*u for a,b in zip(self.p0,self.p1))


def flux_at(sources, point, t):
    x,y=map(number,point); t=number(t)
    value=Interval.point(0)
    for source in sources:
        if source.active(t):value=value+rectangle_coefficient(source.rect,(x,x,y,y),source.height)*source.density
    return value


def _slab(leg,a,b,active):
    pa,pb=leg.point(a),leg.point(b)
    box=(min(pa[0],pb[0]),max(pa[0],pb[0]),min(pa[1],pb[1]),max(pa[1],pb[1]))
    flux=Interval.point(0)
    for source in active:
        flux=flux+rectangle_coefficient(source.rect,box,source.height)*source.density
    # All active phases are constant on the open interval. Supremum bounds are
    # valid even if an expiry endpoint itself excludes that source.
    return flux,flux*(b-a)


def bound_trajectory(sources, legs, incurred=0, *, max_slabs=1024,
                     dose_tolerance=Q(1,10**8), peak_tolerance=Q(1,10**8), wall_s=60):
    """Reference peak/dose enclosure; incomplete refinement remains enclosed.

    Source activity is event-split exactly. `converged` describes requested
    enclosure width, not validity: capped intervals are still outward bounds.
    A source-empty time interval is represented exactly as zero.
    """
    sources=tuple(sources);legs=tuple(legs);incurred=number(incurred)
    if incurred<0 or not legs or max_slabs<1 or wall_s<=0:raise ValueError('Trajectory settings')
    for i,leg in enumerate(legs):
        if i and (legs[i-1].end!=leg.start or legs[i-1].p1!=leg.p0):raise ValueError('Discontinuous trajectory')
    started=time.monotonic();records={};counter=0;peak_lower=Q(0);sampled_points=0
    def point_check(leg,t):
        nonlocal peak_lower,sampled_points
        v=flux_at(sources,leg.point(t),t);peak_lower=max(peak_lower,v.lo);sampled_points+=1
        return v.hi
    point_peak_upper=Q(0)
    def add(leg,a,b,active):
        nonlocal counter
        flux,dose=_slab(leg,a,b,active)
        middle=(a+b)/2;point_check(leg,middle)
        records[counter]=(leg,a,b,active,flux,dose);counter+=1
    for leg in legs:
        cuts=sorted({leg.start,leg.end,*[x for s in sources for x in (s.birth,s.expiry) if leg.start<x<leg.end]})
        for t in cuts:point_peak_upper=max(point_peak_upper,point_check(leg,t))
        for a,b in zip(cuts,cuts[1:]):
            active=tuple(s for s in sources if s.active((a+b)/2))
            add(leg,a,b,active)
    cap=None
    while True:
        dose=Interval.point(incurred)
        for row in records.values():dose=dose+row[5]
        peak_upper=max([point_peak_upper,*[r[4].hi for r in records.values()]])
        peak=Interval(peak_lower,peak_upper)
        if dose.width<=number(dose_tolerance) and peak.width<=number(peak_tolerance):break
        if len(records)>=max_slabs:cap='SLAB_CAP';break
        if time.monotonic()-started>=wall_s:cap='WALL_CAP';break
        choices=[(r[5].width+r[4].width*(r[2]-r[1]),k) for k,r in records.items() if r[0].p0!=r[0].p1 and r[1]<r[2]]
        if not choices:cap='NO_MOVING_SLABS';break
        _,key=max(choices);leg,a,b,active,_,_=records.pop(key);m=(a+b)/2
        add(leg,a,m,active);add(leg,m,b,active)
    return {'dose':dose,'peak':peak,'converged':cap is None,'cap':cap,'slabs':len(records),'sampled_points':sampled_points,'elapsed_s':time.monotonic()-started,'scope':'Declared finite-source solid-angle model; exact represented inputs; no physical validation'}


def compare(candidate,reference):
    """Sufficient containment or proven separation; overlap is inconclusive."""
    a,b=map(number,candidate)
    if a>b:raise ValueError('Candidate interval reversed')
    if b<reference.lo or a>reference.hi:return 'PROVEN_DISJOINT'
    if a<=reference.lo and b>=reference.hi:return 'PROVED_CONTAINS_REFERENCE'
    return 'INCONCLUSIVE_OVERLAP'


def encode(value):
    if isinstance(value,Q):return str(value)
    if isinstance(value,Interval):return {'lower':str(value.lo),'upper':str(value.hi),'width':str(value.width)}
    if isinstance(value,dict):return {str(k):encode(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [encode(v) for v in value]
    return value
