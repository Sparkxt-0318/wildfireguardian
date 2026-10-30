"""Directed Decimal enclosures of the polygon edge-angle formula.

Every algebraic operation is rounded outwards. Decimal sqrt is correctly
rounded, so adjacent Decimal numbers enclose it. atan uses half-angle range
reduction and an alternating Taylor series with an explicit next-term tail.
Machin's identity encloses pi. Precision increases until a directed binary64
lower approximation has a certified relative enclosure width below 2**-55.
There is no coordinate cutoff and no unverified libm accuracy allowance.
"""
from __future__ import annotations

from decimal import Context,Decimal,ROUND_FLOOR,ROUND_CEILING
from fractions import Fraction as F
import math
import numpy as np
from .isochrone import UnsupportedGeometry


class _Retry(Exception):pass


class _Arithmetic:
    def __init__(self,precision):
        self.down=Context(prec=precision,rounding=ROUND_FLOOR)
        self.up=Context(prec=precision,rounding=ROUND_CEILING)
        self.target=Decimal(1).scaleb(-precision+10)
        self.pi=None

    def __call__(self,value):
        if isinstance(value,_I):return value
        if isinstance(value,F):
            numerator=Decimal(value.numerator);denominator=Decimal(value.denominator)
            return _I(self,self.down.divide(numerator,denominator),self.up.divide(numerator,denominator))
        value=Decimal(value)
        return _I(self,value,value)


class _I:
    __slots__=("a","lo","hi")
    def __init__(self,a,lo,hi):self.a,self.lo,self.hi=a,lo,hi
    def __add__(self,other):
        b=self.a(other);return _I(self.a,self.a.down.add(self.lo,b.lo),self.a.up.add(self.hi,b.hi))
    __radd__=__add__
    def __neg__(self):return _I(self.a,self.hi.copy_negate(),self.lo.copy_negate())
    def __sub__(self,other):return self+-self.a(other)
    def __rsub__(self,other):return self.a(other)+-self
    def __mul__(self,other):
        b=self.a(other);pairs=[(x,y) for x in (self.lo,self.hi) for y in (b.lo,b.hi)]
        return _I(self.a,min(self.a.down.multiply(x,y) for x,y in pairs),max(self.a.up.multiply(x,y) for x,y in pairs))
    __rmul__=__mul__
    def __truediv__(self,other):
        b=self.a(other)
        if b.lo<=0<=b.hi:raise _Retry()
        pairs=[(x,y) for x in (self.lo,self.hi) for y in (b.lo,b.hi)]
        return _I(self.a,min(self.a.down.divide(x,y) for x,y in pairs),max(self.a.up.divide(x,y) for x,y in pairs))
    def square(self):
        lo=Decimal(0) if self.lo<=0<=self.hi else min(self.a.down.multiply(x,x) for x in (self.lo,self.hi))
        hi=max(self.a.up.multiply(x,x) for x in (self.lo,self.hi))
        return _I(self.a,lo,hi)
    def sqrt(self):
        if self.lo<0:raise _Retry()
        low=self.a.down.sqrt(self.lo);high=self.a.up.sqrt(self.hi)
        return _I(self.a,Decimal(0) if not low else low.next_minus(self.a.down),high.next_plus(self.a.up))


def _dot(a,b):return sum((x*y for x,y in zip(a,b)),a[0].a(0))
def _norm(a):return sum((v.square() for v in a),a[0].a(0)).sqrt()
def _cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def _fdot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))
def _fcross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def _sub(a,b):return [x-y for x,y in zip(a,b)]


def _atan_unit(a,z):
    # Three half-angle reductions put 0<=z<=1 inside the rapidly converging
    # Taylor domain. Its exact remainder is bounded by the next term.
    for _ in range(3):z=z/(1+(1+z.square()).sqrt())
    z2=z.square();power=z;total=a(0);n=0
    while True:
        term=power/(2*n+1);total=total+term if n%2==0 else total-term
        power=power*z2
        tail=a.up.divide(power.hi,Decimal(2*n+3))
        if tail<a.target:
            return (total+_I(a,tail.copy_negate(),tail))*8
        n+=1


def _pi(a):
    if a.pi is None:a.pi=16*_atan_unit(a,a(F(1,5)))-4*_atan_unit(a,a(F(1,239)))
    return a.pi


def _atan2_scalar(a,y,x):
    if not y:
        return _pi(a) if x<0 else a(0)
    if not x:return _pi(a)/2
    ax=x.copy_abs()
    theta=_atan_unit(a,a(y)/a(ax)) if y<=ax else _pi(a)/2-_atan_unit(a,a(ax)/a(y))
    return theta if x>0 else _pi(a)-theta


def _atan2(a,y,x):
    if y.lo<0:raise _Retry()
    low=_atan2_scalar(a,y.lo if x.hi>=0 else y.hi,x.hi).lo
    high=_atan2_scalar(a,y.hi if x.lo>=0 else y.lo,x.lo).hi
    return _I(a,low,high)


def lower_float(value):
    """Binary64 directed conversion from an exact Fraction or Decimal."""
    exact=F(value)
    try:out=float(exact)
    except OverflowError as exc:raise UnsupportedGeometry("radiation total exceeds binary64 output range") from exc
    while F(out)>exact:out=float(np.nextafter(out,-math.inf))
    return max(0.,out)


def _normal(receiver):
    if isinstance(receiver,str) and receiver=="worst_case":return None
    if isinstance(receiver,str) and receiver.startswith("vertical_facing(") and receiver.endswith(")"):
        angle=float(receiver[len("vertical_facing("):-1]);normal=[math.cos(angle),math.sin(angle),0.]
    else:normal=list(receiver)
    if len(normal)!=3 or not all(math.isfinite(float(v)) for v in normal) or not any(normal):
        raise ValueError("finite nonzero receiver normal required")
    return [F(float(v)) for v in normal]


def polygon_factor(vertices,point,receiver="worst_case"):
    """Certified lower approximation to the same diffuse polygon formula.

    The old orientation-envelope branch remains one when the full-patch
    maximizing normal does not see every vertex. That branch is excluded by
    the cone condition required for the geometric far-field enclosure.
    """
    vertices=[[F(v) for v in row] for row in vertices];point=[F(v) for v in point]
    if len(vertices)<3 or any(len(row)!=3 for row in vertices) or len(point)!=3:raise ValueError("polygon [N,3] and point [3] required")
    normal=_normal(receiver)
    rays=[_sub(v,point) for v in vertices]
    plane=None
    for i in range(1,len(vertices)-1):
        candidate=_fcross(_sub(vertices[i],vertices[0]),_sub(vertices[i+1],vertices[0]))
        if any(candidate):plane=candidate;break
    if plane is None:return 0.
    if any(_fdot(plane,_sub(v,vertices[0])) for v in vertices):
        raise ValueError("polygon must be exactly planar; supply the declared parallelogram directly")
    for i in range(len(vertices)):
        turn=_fcross(_sub(vertices[(i+1)%len(vertices)],vertices[i]),_sub(vertices[(i+2)%len(vertices)],vertices[(i+1)%len(vertices)]))
        if _fdot(turn,plane)<0:raise ValueError("polygon must be convex with consistent vertex order")
    facing=_fdot(plane,rays[0])
    if not facing:
        signs=[_fdot(_fcross(_sub(b,a),_sub(point,a)),plane) for a,b in zip(vertices,vertices[1:]+vertices[:1])]
        if all(s>=0 for s in signs) or all(s<=0 for s in signs):raise ValueError("receiver intersects an emitting panel")
        return 0.
    if normal is not None:
        if not any(_fdot(ray,normal)>0 for ray in rays):return 0.
        clipped=[]
        for a,b in zip(vertices,vertices[1:]+vertices[:1]):
            da=_fdot(_sub(a,point),normal);db=_fdot(_sub(b,point),normal)
            if da>=0:clipped.append(a)
            if (da>=0)!=(db>=0):clipped.append([x+da/(da-db)*(y-x) for x,y in zip(a,b)])
        clipped=[v for i,v in enumerate(clipped) if i==0 or v!=clipped[i-1]]
        if len(clipped)>1 and clipped[0]==clipped[-1]:clipped.pop()
        if len(clipped)<3:return 0.
        vertices=clipped;rays=[_sub(v,point) for v in vertices]
    precision=48
    while True:
        a=_Arithmetic(precision)
        try:
            unit=[]
            for ray in rays:
                r=[a(v) for v in ray];radius=_norm(r)
                if radius.lo<=0:raise _Retry()
                unit.append([v/radius for v in r])
            moment=[a(0),a(0),a(0)]
            for index,(u,v) in enumerate(zip(unit,unit[1:]+unit[:1])):
                if not any(_fcross(rays[index],rays[(index+1)%len(rays)])):continue
                cross=_cross(u,v);length=_norm(cross)
                if length.lo<=0:raise _Retry()
                angle=_atan2(a,length,_dot(u,v))
                moment=[x+angle*c/length/2 for x,c in zip(moment,cross)]
            if facing<0:moment=[-v for v in moment]
            if normal is None:
                for ray in rays:
                    seen=_dot(moment,[a(v) for v in ray])
                    if seen.hi<0:return 1.
                    if seen.lo<0:raise _Retry()
                factor=_norm(moment)/_pi(a)
            else:
                n=[a(v) for v in normal]
                factor=_dot(moment,n)/_norm(n)/_pi(a)
            low=max(Decimal(0),factor.lo);high=min(Decimal(1),factor.hi)
            if high<low:raise _Retry()
            if low>0 and a.up.subtract(high,low)<=a.down.multiply(low,a(F(1,2**55)).lo):
                return lower_float(low)
        except _Retry:pass
        precision*=2
