"""Directed MPFR rounding for the integral over an enlarged horizontal emission rectangle."""
import ctypes as c
import ctypes.util,math
from functools import lru_cache
from pathlib import Path


class Variable(c.Structure):
    _fields_=[('precision',c.c_long),('sign',c.c_int),('exponent',c.c_long),('digits',c.POINTER(c.c_ulong))]


@lru_cache
def arithmetic():
    name=c.util.find_library('mpfr')
    if not name:
        name=next((str(p) for p in (Path('/opt/homebrew/opt/mpfr/lib/libmpfr.dylib'),Path('/usr/local/opt/mpfr/lib/libmpfr.dylib')) if p.is_file()),None)
    if not name:return None
    lib=c.CDLL(name);r=c.POINTER(Variable);i=c.c_int;v=c.c_long
    for key,p in dict(init2=[r,v],set_si=[r,v,i],sqrt=[r,r,i],mul_si=[r,r,v,i],div=[r,r,r,i],atan=[r,r,i],get_si=[r,i]).items():
        fun=getattr(lib,'mpfr_'+key);fun.argtypes=p;fun.restype=v if key=='get_si' else None if key=='init2' else i
    a,b=Variable(),Variable();aa,bb=c.pointer(a),c.pointer(b);lib.mpfr_init2(aa,112);lib.mpfr_init2(bb,112)
    return lib,aa,bb


@lru_cache(maxsize=250000)
def corner(x,y,h,upper):
    """Integer ceiling / floor of the angle scaled by 10^11, at worst one unit wider."""
    lib,den,num=arithmetic()
    rnd=2 if upper else 3 # MPFR_RNDU, MPFR_RNDD
    xy=x*y
    if not xy:return 0
    # For a positive numerator f=atan(xy/(h*sqrt(s))) decreases with sqrt(s).
    # For a negative numerator it increases, so reverse the denominator enclosure.
    denrnd=(3 if upper else 2) if xy>0 else rnd
    lib.mpfr_set_si(den,x*x+y*y+h*h,0)
    lib.mpfr_sqrt(den,den,denrnd);lib.mpfr_mul_si(den,den,h,denrnd)
    lib.mpfr_set_si(num,xy,0);lib.mpfr_div(num,num,den,rnd)
    lib.mpfr_atan(num,num,rnd);lib.mpfr_mul_si(num,num,10**11,rnd)
    return lib.mpfr_get_si(num,rnd)


def rectangle_upper_nano(box,xl,xr,yl,yr,h,emitter_nano,scale=1):
    x0,x1,y0,y1=map(int,box)
    x0*=scale;x1*=scale;y0*=scale;y1*=scale;h*=scale
    a,b=x0-xr,x1-xl;c,d=y0-yr,y1-yl
    # Every possible receiver-relative source rectangle lies in [a,b] × [c,d].
    # The positive kernel integrated over this enlarged rectangle is an upper bound.
    def angle_value(x,y,bound):
        g=math.gcd(x,y,h)
        return corner(x//g,y//g,h//g,bound)
    angle=angle_value(b,d,True)-angle_value(a,d,False)-angle_value(b,c,False)+angle_value(a,c,True)
    assert angle>=0
    # 3.141592653 < pi. corner() is scaled by 10^11, pi lower bound by 10^9.
    den=4*3141592653*100
    return (emitter_nano*angle+den-1)//den
