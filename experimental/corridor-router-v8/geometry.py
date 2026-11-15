"""Independent geometric, time and heat checks on native seconds and coordinates.
No search, checker, or cost code is imported from any benchmark arm.
"""
from collections import defaultdict, deque
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path
import heapq, json, math
import numpy as np
from solid_angle import arithmetic,rectangle_upper_nano

def read(p):
    return json.loads(Path(p).read_bytes())

def clip(a,b,box):
    lo,hi=F(0),F(1)
    for x,y,left,right in zip(a,b,(box[0],box[2]),(box[1],box[3])):
        if x==y:
            if not left<=x<=right:return None
        else:
            f,g=sorted(((left-x)/(y-x),(right-x)/(y-x)))
            lo=max(lo,f);hi=min(hi,g)
    return (lo,hi) if lo<=hi else None

class World:
    def __init__(self,graph_path,packet):
        g=read(graph_path); m=read(Path(packet)/'NATIVE_METADATA.json')
        self.nodes={n['id']:n for n in g['nodes']}
        self.xy={k:(F(n['x']),F(n['y'])) for k,n in self.nodes.items()}
        self.edges={e['id']:e for e in g['edges']}
        self.turns=set(map(tuple,g['forbidden_turns']))
        self.adj=defaultdict(list);self.reverse=defaultdict(list)
        for e in self.edges.values():
            self.adj[e['u']].append((e['v'],e['travel_ticks'],e['id']))
            self.reverse[e['v']].append((e['u'],e['travel_ticks']))
        self.members=m['construction']['scenario_ids']; cfg=m['construction']['assumptions']
        tr=m['affine_transform']; self.size=int(tr[0]);self.x0=int(tr[2]);self.y0=int(tr[5])
        assert self.x0==tr[2] and self.y0==tr[5]
        assert tr[0]==self.size==-tr[4] and tr[1]==tr[3]==0 and g['crs']==m['crs'] and g['revision']==m['graph_revision']
        self.h,self.w=m['shape']
        a=np.load(Path(packet)/'constructed_arrays.npz')
        seen=a['current_active']; ig=a['ignition_time_s'];self.valid=np.all(a['native_hourly_valid'],axis=1)
        dur=F(cfg['burning_duration_s']);R=F(cfg['initial_remaining_s'])
        # Cross-check the starting state, crop and new ignitions against the pre-routing export.
        full_path=Path(packet)/'FULL.npz'
        if full_path.exists():
            with np.load(full_path) as original:
                aff=original['affine'];dx=(tr[2]-aff[2])/tr[0];dy=(tr[5]-aff[5])/tr[4]
                assert int(dx)==dx and int(dy)==dy
                h,w=self.h,self.w; crop=(slice(int(dy),int(dy)+h),slice(int(dx),int(dx)+w))
                assert np.array_equal(original['valid'][:,:,crop[0],crop[1]],a['native_hourly_valid'])
                assert np.array_equal(original['ignition_time_s'][:,crop[0],crop[1]],ig)
                reached=original['initial_burned'][crop];ts=original['last_detection_unix'][crop];cutoff=float(original['cutoff_unix'])
                assert np.all(np.isfinite(ts[reached])) and np.all(ts[reached]<=cutoff)
                left=np.where(reached,np.maximum(0,float(dur)-(cutoff-ts)),0.)
                assert np.array_equal(left>0,seen) and np.isclose(left.max(),float(R),atol=1e-10,rtol=0)
        assert not np.any(seen&np.isfinite(ig))
        self.rects=[];self.periods=[];self.arrays=[];self.union=defaultdict(set)
        for j in range(4):
            rlist=[];times=[];exp=a[f'member{j}__extinction_breakpoint_s']
            for r,c in zip(*np.nonzero(seen|np.isfinite(ig[j]))):
                r=int(r);c=int(c);birth=F(0) if seen[r,c] else F(float(ig[j,r,c])); exact=R if seen[r,c] else birth+dur
                # Constructor rounds the right endpoint outward. Preserve the artifact's actual activity interval.
                end=R if seen[r,c] else F(float(exp[r,c]))
                assert end>=exact and float(end-exact)<=1e-8 and birth<end
                rlist.append(self.box(r,c));times.append((birth,end));self.union[r,c].add((birth,end))
            self.rects.append(rlist);self.periods.append(times)
            self.arrays.append((np.array(rlist,dtype=np.int64).reshape((-1,4)),np.array([math.floor(a) for a,b in times],dtype=np.int64),np.array([math.ceil(b) for a,b in times],dtype=np.int64)))
        val=math.prod(F(cfg[k]) for k in ['fuel_load_kg_m2','consumed_fraction','heat_of_combustion_j_kg','radiative_fraction','atmospheric_transmissivity'])/dur/1000
        self.flux_nano=math.ceil(val*10**9)
        self._event_sets=[{k for pair in v for k in pair} for v in self.periods]
        self.z=int(cfg['emission_height_m']-cfg['receiver_height_m']);assert self.z>0 and self.z==cfg['emission_height_m']-cfg['receiver_height_m']
        self._segments={};self._blocks={};self._static={}
    def box(self,r,c):
        d=self.size;x=self.x0+c*d;y=self.y0-r*d;return (x,x+d,y-d,y)
    def cells(self,u,v):
        key=(u,v)
        if key in self._segments:return self._segments[key]
        a,b=self.xy[u],self.xy[v];cols=sorted([math.floor((x-self.x0)/self.size) for x in [a[0],b[0]]]);rs=sorted([math.floor((self.y0-y)/self.size) for y in [a[1],b[1]]])
        result=[]
        for r in range(rs[0]-1,rs[1]+2):
            for c in range(cols[0]-1,cols[1]+2):
                box=self.box(r,c); cut=clip(a,b,box)
                if cut is None:continue
                left,right=cut;mid=(left+right)/2; q=(a[0]+(b[0]-a[0])*mid,a[1]+(b[1]-a[1])*mid)
                inside=bool(box[0]<q[0]<box[1] and box[2]<q[1]<box[3])
                result.append((r,c,left,right,inside))
        self._segments[key]=result
        return result
    def blocked(self,u,v,dt):
        key=(u,v,dt)
        if key in self._blocks:return self._blocks[key]
        # Necessary only: discard boundary-only flame contacts, forbid integer departures
        # strictly inside the time interval enabling an encounter in a cell interior.
        # The resulting network is an optimistic relaxation of the accepted route grammar.
        blocks=[]
        for r,c,a,b,inside in self.cells(u,v):
            if not inside:continue
            for t,s in self.union.get((r,c),()):
                low=math.floor(t-dt*b)+1; high=math.ceil(s-dt*a)
                if low<high:blocks.append((low,high))
        result=[]
        for l,r in sorted(blocks):
            if result and result[-1][1]>=l:result[-1]=(result[-1][0],max(result[-1][1],r))
            else:result.append((l,r))
        self._blocks[key]=result
        return result
    def static(self,dest):
        if dest in self._static:return self._static[dest]
        ds={dest:0};q=[(0,dest)]
        while q:
            d,v=heapq.heappop(q)
            if ds[v]!=d:continue
            for w,k in self.reverse[v]:
                nd=d+k
                if nd<ds.get(w,math.inf):ds[w]=nd;heapq.heappush(q,(nd,w))
        self._static[dest]=ds;return ds
    def flux(self,a,b,t,u,j):
        rect,birth,end=self.arrays[j]
        active=(birth<=math.ceil(u))&(end>=math.floor(t))
        if not active.any():return 0
        xmin,xmax=math.floor(min(a[0],b[0])),math.ceil(max(a[0],b[0]))
        ymin,ymax=math.floor(min(a[1],b[1])),math.ceil(max(a[1],b[1]))
        boxes=rect[active]
        dx=np.maximum(0,np.maximum(boxes[:,0]-xmax,xmin-boxes[:,1]));dy=np.maximum(0,np.maximum(boxes[:,2]-ymax,ymin-boxes[:,3]))
        z=np.maximum(self.z,np.maximum(dx,dy));k=self.flux_nano; d=self.size; top=k*d*d*self.z
        assert top<2**62 and z.max()<50000
        den=12*z**3
        # pi>3, Euclidean range >= max(h,dx,dy), hemisphere solid angle <=2*pi.
        f=np.minimum((k+1)//2,(top+den-1)//den)
        total=int(f.sum());assert total<=len(f)*(k+1)
        return total+1+math.ceil((self.flux_nano+1)/(2*10**8))

def refined_flux(W,a,b,t,u,member,tiling,active_override=None):
    # Tighten the product upper bound by subdividing the at-most 32 nearest active
    # sources. All other sources retain the original whole-cell bound.
    rect,birth,end=W.arrays[member]; active=active_override if active_override is not None else (birth<=math.ceil(u))&(end>=math.floor(t))
    if not active.any():return 0
    boxes=rect[active];d=W.size;h=W.z;k=W.flux_nano
    xl,xr=math.floor(min(a[0],b[0])),math.ceil(max(a[0],b[0]));yl,yr=math.floor(min(a[1],b[1])),math.ceil(max(a[1],b[1]))
    def bounds(z,side):
        dx=np.maximum(0,np.maximum(z[:,0]-xr,xl-z[:,1]));dy=np.maximum(0,np.maximum(z[:,2]-yr,yl-z[:,3]))
        sq=dx**2+dy**2+h*h;root=np.sqrt(sq).astype(np.int64);root-=(root**2>sq)
        assert np.all(root**2<=sq) and np.all((root+1)**2>sq)
        den=12*root**3;v=k*side*side*h
        assert den.max()<2**62 and v<2**62
        return np.minimum((k+1)//2,(v+den-1)//den)
    coarse=bounds(boxes,d);ix=np.argsort(coarse)[-32:];n=tiling
    if n<0:
        assert arithmetic() is not None
        scale=-n;sxl=math.floor(min(a[0],b[0])*scale);sxr=math.ceil(max(a[0],b[0])*scale)
        syl=math.floor(min(a[1],b[1])*scale);syr=math.ceil(max(a[1],b[1])*scale)
        for j in np.flatnonzero(coarse>100):
            coarse[j]=min(int(coarse[j]),rectangle_upper_nano(boxes[j],sxl,sxr,syl,syr,h,k,scale))
        return int(coarse.sum())+1+math.ceil((k+1)/(2*10**8))
    assert d%n==0;s=d//n
    offsets=np.array([(j*s,j*s,i*s,i*s) for j in range(n) for i in range(n)],np.int64)
    bb=boxes[ix].copy();bb[:,1]=bb[:,0]+s;bb[:,3]=bb[:,2]+s
    small=(bb[:,None,:]+offsets[None,:,:]).reshape(-1,4)
    coarse[ix]=np.minimum(coarse[ix],bounds(small,s).reshape(len(ix),-1).sum(axis=1))
    return int(coarse.sum())+1+math.ceil((k+1)/(2*10**8))
def witness(W,req,route):
    t=req['departure'];loc=req['position']['node'];prev=req['incoming_edge'];last_arrival=True
    seg=[]
    for l in route['legs']:
        assert int(t)==t==l['start'] and int(l['end'])==l['end'] and t<l['end']
        if l['kind']=='EDGE':
            e=W.edges[l['edge']];assert e['u']==loc and (prev,e['id']) not in W.turns and e['travel_ticks']==l['end']-t and l.get('from_fraction',0)==0 and l.get('to_fraction',1)==1
            nex=e['v'];prev=e['id'];last_arrival=True
        else:
            assert l['kind']=='WAIT' and W.nodes[loc]['waitable'] and l['node']==loc
            nex=loc;last_arrival=False
        seg.append((loc,nex,int(t),int(l['end'])));t=int(l['end']);loc=nex
    assert last_arrival and t==route['arrival'] and loc==route['destination']
    d,=[d for d in req['destinations'] if d['node']==loc]
    assert any(lo<=t and t+d['dwell']<=hi for lo,hi in d['open_intervals']) and t+d['dwell']<=req['horizon']
    assert int(d['dwell'])==d['dwell'];seg.append((loc,loc,int(t),int(t+d['dwell'])));missing=set();used=set();hits=set()
    for u,v,t,s in seg:
        for r,c,l,q,_ in W.cells(u,v):
            t0=t+(s-t)*l;t1=t+(s-t)*q
            for hour in range(min(len(W.valid)-1,math.floor(t0/3600)),min(len(W.valid)-1,math.floor(t1/3600))+1):
                used.add((hour,r,c))
                if not (0<=r<W.h and 0<=c<W.w and W.valid[hour,r,c]):missing.add((hour,r,c))
            for low,high in W.union.get((r,c),()):
                if t1>=low and t0<high:hits.add((r,c))
    peaks=[];doses=[]
    for i,member in enumerate(W.members):
        p=0;dose=0
        for u,v,t,s in seg:
            f=W.flux(W.xy[u],W.xy[v],t,s,i);p=max(p,f);dose+=f*(s-t)
        if not hits and (F(dose,10**9)+F(req['incurred'][member])>F(req['budgets']['dose'][member]) or F(p,10**9)>F(req['budgets']['peak'])):
            # Sharpen only enclosures which have not already proved the threshold.
            # An exact source-free wait can share a graph cell with a powerful future emitter.
            stages=[(35,45,5)]
            if arithmetic() is not None:stages.extend([(5,4,-4),(.75,1,-4)])
            else:stages.extend([(8,8,25),(4,3,75)])
            for distance,seconds,tiles in stages:
                p=0;dose=F(0)
                breaks=sorted({moment for period in W.periods[i] for moment in period})
                import bisect
                states={}
                for u,v,t,s in seg:
                    a,b=W.xy[u],W.xy[v];length=max(float(abs(x-y)) for x,y in zip(a,b))
                    n=max(1,math.ceil(length/distance),math.ceil((s-t)/seconds))
                    points=sorted({F(j,n) for j in range(n+1)}|{(moment-t)/(s-t) for moment in breaks if t<moment<s})
                    for l,r in zip(points,points[1:]):
                        x=tuple(a0+(b0-a0)*l for a0,b0 in zip(a,b));y=tuple(a0+(b0-a0)*r for a0,b0 in zip(a,b))
                        ta=t+(s-t)*l;tb=t+(s-t)*r;mid=(ta+tb)/2;slot=bisect.bisect_right(breaks,mid)
                        if slot not in states:states[slot]=np.array([lo<=mid<hi for lo,hi in W.periods[i]],dtype=bool)
                        val=refined_flux(W,x,y,ta,tb,i,tiles,states[slot]);p=max(p,val);dose+=val*(tb-ta)
                        # Isolated boundary flux can affect peak but never integral dose.
                        if tb in W._event_sets[i]:
                            p=max(p,refined_flux(W,y,y,tb,tb,i,5))
                dose=math.ceil(dose)
                if F(dose,10**9)+F(req['incurred'][member])<=F(req['budgets']['dose'][member]) and F(p,10**9)<=F(req['budgets']['peak']):break
        peaks.append(p);doses.append(dose)
    ok=not hits and all(F(peaks[i],10**9)<=F(req['budgets']['peak']) and F(doses[i],10**9)+F(req['incurred'][m])<=F(req['budgets']['dose'][m]) for i,m in enumerate(W.members))
    return dict(verified_feasible=ok,arrival=route['arrival'],legs=len(route['legs']),dwell=d['dwell'],occupied_cell_hours=len(used),unsupported_cell_hours=len(missing),flame_contact_cells=len(hits),peak_upper_kw_m2=[k/1e9 for k in peaks],dose_upper_kj_m2=[k/1e9 for k in doses])

def first_clear(t,intervals):
    for l,r in intervals:
        if t<l:break
        if t<r:t=r
    return t

def relaxed_bound(W,req,arrival=None,work_limit=30000):
    """Independent lower bound. Waiting is free at every node and ignores hazards.
    Forbid only contacts entailed by traversal of cell interiors; drop dose, forbidden
    turns and the newly-arrived rule. All legal journeys thus remain in the relaxation.
    Stop at first feasible relaxed arrival, label expiration, or stated work limit.
    """
    dep=int(req['departure']);source=req['position']['node'];target,=req['destinations'];z=target['node'];dwell=target['dwell'];smax=int(req['horizon'])-dwell
    lim=min(smax,int(arrival)-1) if arrival is not None else smax
    ds=W.static(z);earliest=dep+ds.get(source,math.inf)
    def destination_slot(t,blocks):
        for a,b in sorted(target['open_intervals']):
            q=first_clear(max(int(t),int(a)),blocks)
            if q+dwell<=b and q<=smax:return q
        return math.inf
    def proved(reason,exp=0):return dict(certified=True,method=reason,processed=exp)
    if earliest>lim:return proved('travel-time potential or horizon')
    earliest=destination_slot(earliest,W.blocked(z,z,dwell))
    if earliest>lim:return proved('necessary destination occupancy and static travel bound')
    distances={source:dep};pq=[(dep+ds[source],dep,source)];popped=0
    while pq:
        score,t,n=heapq.heappop(pq)
        if distances[n]!=t:continue
        if score>lim:break
        if n==z:
            result=destination_slot(t,W.blocked(z,z,dwell))
            if result>lim:return proved('optimistic time-dependent graph plus destination',popped)
            return dict(certified=False,method='optimistic feasible path; lower bound only',absolute_lower_bound=result,processed=popped)
        popped+=1
        if popped>work_limit:return dict(certified=False,method='independent exploration work limit',processed=popped,absolute_lower_bound=score)
        for v,dt,_ in W.adj[n]:
            if t+dt+ds.get(v,math.inf)>lim:continue
            next_t=first_clear(t,W.blocked(n,v,dt))+dt
            if next_t+ds[v]<=lim and next_t<distances.get(v,math.inf):
                distances[v]=next_t;heapq.heappush(pq,(next_t+ds[v],next_t,v))
    return proved('optimistic full reachable set exhausted before horizon or witness arrival',popped)

def lattice_bound(W,req,arrival=None,limit=240000):
    """Exact integer bitsets for an optimistic permitted-turn, permitted-wait contact relaxation.
    Time is discrete; shifts implement legal timed travel. Long labels close equal-time revisits.
    Each iteration propagates only new bits. Waiting cannot constitute a new destination arrival.
    """
    dep=int(req['departure']);s=req['position']['node'];d,=req['destinations'];z=d['node'];dwell=d['dwell'];hi=int(req['horizon'])-dwell
    if arrival is not None:hi=min(hi,int(arrival)-1)
    if hi<dep:return dict(certified=True,method='lattice has no requested clock',processed=0)
    D=W.static(z); hw=(1<<(hi+1))-1
    def clock_range(a,b):
        lo=max(0,int(a));h=min(hi+1,int(b));return ((1<<(h-lo))-1)<<lo if h>lo else 0
    @lru_cache(None)
    def allowed(u,v,dt):
        vbits=hw
        for a,b in W.blocked(u,v,dt):vbits&=~clock_range(a,b)
        return vbits
    terminal=allowed(z,z,dwell)&sum_ranges([(a,b-dwell+1) for a,b in d['open_intervals']],clock_range)
    outspecial={a for a,b in W.turns}; state=lambda n,e:(n,e if e in outspecial else None)
    init=state(s,req['incoming_edge']);front=deque([init]);seen={init:1<<dep};pending={init:1<<dep};processed=0
    if s==z and terminal&(1<<dep):return dict(certified=False,method='initial state meets relaxed target',processed=0)
    while front:
        ident=front.popleft();n,inc=ident;move=pending.pop(ident);processed+=1
        if processed>limit:return dict(certified=False,method='lattice verification work limit',processed=processed)
        if D.get(n,hi+1)>hi:continue
        if W.nodes[n]['waitable']:
            permits=allowed(n,n,1);closed=move
            # Reach along allowed 1-second waiting transitions in O(log H) bitwise operations.
            stride=1; transit=permits
            while stride<=hi:
                old=closed;closed|=((closed&transit)<<stride)&hw
                if closed==old:break
                transit &= transit>>stride;stride*=2
            move=closed
        for v,dt,e in W.adj[n]:
            if (inc,e) in W.turns or v not in D:continue
            ceiling=hi-D[v]-dt
            if ceiling<dep:continue
            starts=move&clock_range(dep,ceiling+1)
            if not starts:continue
            reached=((starts&allowed(n,v,dt))<<dt)&hw
            if v==z and reached&terminal:return dict(certified=False,method='relaxed target reachable; no independent optimum/no-route certificate',processed=processed)
            st=state(v,e); unseen=reached&~seen.get(st,0)
            if unseen:
                seen[st]=seen.get(st,0)|unseen
                if st not in pending:pending[st]=0;front.append(st)
                pending[st]|=unseen
    return dict(certified=True,method='time-expanded permitted-turn/hold contact relaxation exhausted',processed=processed)

def sum_ranges(ranges,construct):
    result=0
    for a,b in ranges:result|=construct(a,b)
    return result
