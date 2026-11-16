"""Geometry and fire-history parser for original road-level checks."""
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

from geometry import World, read


def make_world(graph,packet):
    w=World(graph,packet)
    cfg=read(Path(packet)/'REPORT.json')['native_metadata']['construction']['assumptions']
    from numpy import load,nonzero,isfinite
    W,H=w.w,w.h
    duration,remaining=map(F,(cfg['burning_duration_s'],cfg['initial_remaining_s']))
    real_union=defaultdict(set)
    with load(Path(packet)/'constructed_arrays.npz',allow_pickle=False) as a:
        act=a['current_active'];assert a['support'].all()
        for j,ign in enumerate(a['ignition_time_s']):
            real=[]
            for slot,(r,c) in enumerate(zip(*nonzero(act|isfinite(ign)))):
                r,c=int(r),int(c)
                birth=F(0) if act[r,c] else F(float(ign[r,c]))
                end=remaining if act[r,c] else birth+duration
                assert w.rects[j][slot]==w.box(r,c)
                lo,hi=w.periods[j][slot]; assert lo==birth and hi>=end and hi-end<F(1,10**8)
                real.append((birth,end));real_union[r,c].add((birth,end))
            w.periods[j]=real
    w._event_sets=[{t for p in member for t in p} for member in w.periods]
    w.union=real_union # Conservative outgoing flux-array enclosures can retain outward rounding.
    return w
