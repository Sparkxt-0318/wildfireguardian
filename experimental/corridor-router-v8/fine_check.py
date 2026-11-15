"""Original roads and fire grid, checked by directed solid-angle brackets at radial extremal receiver positions."""
from fractions import Fraction as F
from collections import defaultdict
import math
import numpy as np
from functools import lru_cache
from solid_angle import corner

@lru_cache(200000)
def angle(x,y,side,z):
    a,b=x-side,x+side;c,d=y-side,y+side
    return max(0,corner(b,d,z,True)-corner(a,d,z,False)-corner(b,c,z,False)+corner(a,c,z,True))

def evaluate(w,q,rt,span=6,grid=4):
    """span meters per exact subleg; grid given in half meters and points rounded toward the source."""
    u=q['position']['node'];inc=q['incoming_edge'];t=q['departure'];fresh=True;legs=[]
    for leg in rt['legs']:
        end=leg['end'];assert t==leg['start'] and int(t)==t and int(end)==end and t<end
        if leg['kind']=='WAIT':
            assert leg['node']==u and w.nodes[u]['waitable'];v=u;fresh=False
        else:
            e=w.edges[leg['edge']];assert leg['kind']=='EDGE' and not (inc,e['id']) in w.turns and e['u']==u and e['travel_ticks']==end-t
            assert leg.get('from_fraction',0)==0 and leg.get('to_fraction',1)==1
            v=e['v'];inc=e['id'];fresh=True
        legs.append((u,v,t,end));u=v;t=end
    assert u==rt['destination'] and t==rt['arrival'] and fresh
    d,=[d for d in q['destinations'] if d['node']==u];end=t+d['dwell'];assert end<=q['horizon'] and any(a<=t and end<=b for a,b in d['open_intervals'])
    legs.append((u,u,t,end));used=set();missing=set();hits=set();intervals=[];locations=[]
    for u,v,a,b in legs:
        for r,c,lo,hi,_ in w.cells(u,v):
            p,q1=a+lo*(b-a),a+hi*(b-a)
            for hour in range(min(len(w.valid)-1,math.floor(p/3600)),min(len(w.valid)-1,math.floor(q1/3600))+1):
                used.add((hour,r,c))
                if not (0<=r<w.h and 0<=c<w.w and w.valid[hour,r,c]):missing.add((hour,r,c))
            if any(q1>=x and p<y for x,y in w.union.get((r,c),())):hits.add((r,c))
        xy=w.xy[u]; delta=tuple(vv-uu for uu,vv in zip(xy,w.xy[v]))
        n=max(1,math.ceil(max(map(abs,delta))/span))
        for j in range(n):
            ll=F(j,n);rr=F(j+1,n);t0=a+ll*(b-a);t1=a+rr*(b-a)
            aa=tuple(uu+x*ll for uu,x in zip(xy,delta));bb=tuple(uu+x*rr for uu,x in zip(xy,delta))
            locations.append((math.floor(20*min(aa[0],bb[0])),math.ceil(20*max(aa[0],bb[0])),math.floor(20*min(aa[1],bb[1])),math.ceil(20*max(aa[1],bb[1]))))
            intervals.append((t0,t1))
    x0,x1,y0,y1=np.array(locations,np.int64).T
    allboxes=set(box for member in w.rects for box in member);f={};side=w.size*10;k=w.flux_nano
    for a,b,c,d0 in sorted(allboxes):
        dx=np.maximum(0,np.maximum(x0-10*(a+b),10*(a+b)-x1)); dy=np.maximum(0,np.maximum(y0-10*(c+d0),10*(c+d0)-y1))
        # Use (8,16,32)m cells in successively more distant annuli for caching, round inward everywhere.
        size=grid*(1+(dx+dy>12000)+2*(dx+dy>30000)+4*(dx+dy>60000))
        dx=dx//size*size;dy=dy//size*size
        # m coordinates are doubled; negate/invert axis symmetry yields closeness upper enclosure.
        aa=np.minimum(dx,dy);bb=np.maximum(dx,dy);keys=aa*100000000+bb
        assert np.all(bb<100000000)
        uk,iv=np.unique(keys,return_inverse=True)
        upper=np.array([(k*angle(int(e//100000000),int(e%100000000),side,20*w.z)+4*3141592653*100-1)//(4*3141592653*100) for e in uk],np.int64)[iv]
        f[a,b,c,d0]=upper
    doses=[];peaks=[];penalty=1+math.ceil((k+1)/(2*10**8))
    for member in range(len(w.members)):
        grouped=defaultdict(list)
        for box,interval in zip(w.rects[member],w.periods[member]):grouped[interval].append(f[box])
        peak=np.zeros(len(intervals),np.int64);dose=F(0)
        for (a,b),powers in grouped.items():
            P=np.sum(powers,axis=0)
            gain=np.array([max(F(0),min(t1,b)-max(t0,a)) for t0,t1 in intervals],dtype=object)
            dose+=sum(g*int(p) for g,p in zip(gain,P) if g)
            peak+=P*np.array([aa<b and bb>=a for aa,bb in intervals])
        dose+=penalty*(legs[-1][3]-legs[0][2]);peak+=penalty
        doses.append(math.ceil(dose));peaks.append(int(peak.max()))
    ok=not hits and all(F(peaks[i],10**9)<=F(q['budgets']['peak']) and F(doses[i],10**9)+F(q['incurred'][m])<=F(q['budgets']['dose'][m]) for i,m in enumerate(w.members))
    return dict(verified_feasible=ok,arrival=rt['arrival'],legs=len(rt['legs']),dwell=d['dwell'],occupied_cell_hours=len(used),unsupported_cell_hours=len(missing),flame_contact_cells=len(hits),
        peak_upper_kw_m2=[k/1e9 for k in peaks],dose_upper_kj_m2=[k/1e9 for k in doses],dose_upper_nano=doses,span_m=span,snap_half_m=grid,method='directed solid-angle radial maxima')
