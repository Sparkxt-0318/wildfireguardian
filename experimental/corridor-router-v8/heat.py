"""Necessary lower bound on integrated radiation over all directed road journeys."""
import ctypes as ct
import heapq,math
from pathlib import Path
from fractions import Fraction as F
import numpy as np
from collections import defaultdict

def distances(adj,start):
    d={start:0};heap=[(0,start)]
    while heap:
        t,u=heapq.heappop(heap)
        if d[u]!=t:continue
        for v,dt in adj[u]:
            b=t+dt
            if b<d.get(v,math.inf):d[v]=b;heapq.heappush(heap,(b,v))
    return d

def certify(graph,q,packet,step=30,contact=None,points=None,tight=False):
    import json
    p=Path(packet);m=json.loads((p/'NATIVE_METADATA.json').read_text())
    cfg=m['construction']['assumptions'];members=m['construction']['scenario_ids']
    s=q['position']['node'];dest,=q['destinations'];z=dest['node'];dwell=int(dest['dwell']);horizon=int(q['horizon'])
    dep=int(q['departure']);last=horizon-dwell
    if not 0<=dep<=last<=3600:return None
    physical=['fuel_load_kg_m2','consumed_fraction','heat_of_combustion_j_kg','radiative_fraction','atmospheric_transmissivity']
    if len(set(members))!=len(members) or set(members)!=set(q['incurred']):return None
    if any(not math.isfinite(cfg[k]) or cfg[k]<0 for k in physical):return None
    if cfg['burning_duration_s']<=0 or step<=0 or int(step)!=step:return None
    duration=F(cfg['burning_duration_s']);density=math.floor(math.prod(F(cfg[k]) for k in physical)*10**9/(1000*duration))
    h=F(cfg['emission_height_m'])-F(cfg['receiver_height_m']);cell=F(graph['grid']['resolution'])
    if h.denominator!=1 or cell.denominator!=1:return None
    x0,top=F(m['affine_transform'][2]),F(m['affine_transform'][5])
    if any(x.denominator!=1 for x in [x0,top]):return None
    grid=graph['grid'];height,width=grid['height'],grid['width']
    if tuple(map(F,m['affine_transform']))!=(cell,0,F(grid['x0']),0,-cell,F(grid['y0'])+height*cell):return None
    if not (0<h<=1000 and 0<cell<=1000 and 0<=density<=10**10):return None
    x0,top,cell,h=(int(v*2) for v in (x0,top,cell,h))
    adj=defaultdict(list);rev=defaultdict(list);edgeinfo=defaultdict(list)
    for e in graph['edges']:
        u,v=e['u'],e['v'];dt=e['travel_ticks']
        if type(dt)!=int or dt<=0:return None
        adj[u].append((v,dt));rev[v].append((u,dt));edgeinfo[u].append(e)
    a=distances(adj,s);d=distances(rev,z);nnames=[u for u in a if a[u]+d.get(u,math.inf)<=last-dep]
    si={n:i for i,n in enumerate(nnames)}
    if s not in si or z not in si:return None
    if len(si)*(last-dep+1)>90000000:return None
    edges=[];native=[];first=[]; nodes={n['id']:n for n in graph['nodes']}
    for u in nnames:
        first.append(len(edges))
        for e in edgeinfo[u]:
            v,dt=e['v'],e['travel_ticks']
            if v in si and a[u]+dt+d[v]<=last-dep:
                edges.append((u,v,dt));native.append(e)
        if nodes[u]['waitable']:edges.append((u,u,1));native.append(None)
    first.append(len(edges))
    raw=[(min(nodes[u]['x'],nodes[v]['x']),max(nodes[u]['x'],nodes[v]['x']),min(nodes[u]['y'],nodes[v]['y']),max(nodes[u]['y'],nodes[v]['y'])) for u,v,dt in edges+[(z,z,dwell)]]
    coord=np.array([(math.floor(2*x),math.ceil(2*X),math.floor(2*y),math.ceil(2*Y)) for x,X,y,Y in raw],dtype=np.int64)
    # Share spatial coefficients for exact duplicate receiver boxes, including reversed roads.
    coords,lookup=np.unique(coord,axis=0,return_inverse=True)
    coords=np.ascontiguousarray(coords);pbuf=lambda a:ct.c_void_p(a.ctypes.data)
    lib=ct.CDLL(str(Path(__file__).with_name('dose.so')))
    lib.coefficients.argtypes=[ct.c_int,ct.c_int,ct.c_void_p,ct.c_void_p,ct.c_longlong,ct.c_longlong,ct.c_longlong,ct.c_void_p]
    lib.mincost.argtypes=[ct.c_int]*9+[ct.c_void_p]*10+[ct.c_longlong,ct.c_void_p,ct.c_void_p,ct.c_int]+[ct.c_void_p]*4;lib.mincost.restype=ct.c_longlong
    def ints(vals):return np.array(vals,np.int32)
    first=ints(first);to=ints([si[v] for u,v,t in edges]);dt=ints([t for u,v,t in edges]);reverse=ints([d[n] for n in nnames])
    goal=ints([any(l<=t and t+dwell<=r for l,r in dest['open_intervals']) for t in range(last+1)])
    # A subset of each raw movement's closed flames suffices for the optimistic bound.
    blocks=[[] for _ in edges]
    if contact is not None and points is not None:
        from types import SimpleNamespace
        from corridor_events import make_entry_sets
        native_ids=[i for i,e in enumerate(native) if e is not None and any(seg['cell'] in contact for seg in e['segments'])]
        if native_ids:
            slim=SimpleNamespace(index=SimpleNamespace(edges=native),parts=[(i,) for i in native_ids])
            entries,_=make_entry_sets(graph,slim,contact,horizon)
            for i,spans in zip(native_ids,entries):blocks[i]=spans
        for i,((u,v,t),e) in enumerate(zip(edges,native)):
            if e is None:blocks[i]=[(math.ceil(l-1),math.ceil(r)) for l,r in points.get(u,())]
        for l,r in points.get(z,()):
            goal[max(0,math.ceil(l-dwell)):max(0,math.ceil(r))]=0
    offsets=ints(np.cumsum([0]+[len(b) for b in blocks]))
    begins=ints([a for b in blocks for a,_ in b]);ends=ints([z for b in blocks for _,z in b])
    with np.load(p/'constructed_arrays.npz') as arr:active=arr['current_active']; ign=arr['ignition_time_s']
    if active.dtype!=bool or active.shape!=(height,width) or ign.shape!=(len(members),height,width):return None
    rr,cc=np.nonzero(active|np.isfinite(ign).any(axis=0));boxes=np.ascontiguousarray(np.column_stack((x0+cell*cc,top-cell*(rr+1))),dtype=np.int64)
    if len(coords)*len(boxes)>12000000:return None
    # Absolute geometric flux upper bound of one rectangle is density/2. This loose
    # guard also bounds all subsequent nonnegative int64 sums and time integrals.
    if ((density+1)*max(1,len(boxes))*(horizon+1))>2**56:return None
    if np.any(np.abs(coords)>100000000) or np.any(np.abs(boxes)>100000000):return None
    coef=np.zeros((len(coords),len(boxes)),np.int64)
    if lib.coefficients(len(coords),len(boxes),pbuf(coords),pbuf(boxes),cell,h,density,pbuf(coef)):return None
    # Reduce once over the common old sources. New sources need only the nonempty columns of each member.
    initial=active[rr,cc];init_rate=coef[:,initial].sum(axis=1)
    if np.any(coef.sum(axis=1)>2**58//(horizon+1)):return None
    ts=np.arange(horizon//step+1)*step;bins=len(ts);end=math.floor(F(cfg['initial_remaining_s']))
    if (len(edges)+1)*bins>12000000:return None
    improved=None
    if tight:
        def line(u,v):
            xy=lambda n:(math.floor(2*nodes[n]['x']),math.floor(2*nodes[n]['y']))
            a,b=sorted([xy(u),xy(v)])
            return (*a,*b)
        lns,find=np.unique(np.array([line(u,v) for u,v,dt in edges+[(z,z,dwell)]],np.int64),axis=0,return_inverse=True)
        lns=np.ascontiguousarray(lns);imp=np.zeros((len(lns),len(boxes)),np.int64)
        lib.mean_coeff.argtypes=lib.coefficients.argtypes
        density_p=math.floor(math.prod(F(cfg[k]) for k in physical)*10**12/(1000*duration))
        if lib.mean_coeff(len(lns),len(boxes),pbuf(lns),pbuf(boxes),cell,h,density_p,pbuf(imp)):return None
        improved=imp[find]
    states=[];earliest=[]
    for j,member in enumerate(members):
        budget=math.floor((F(q['budgets']['dose'][member])-F(q['incurred'][member]))*10**9)
        rate=init_rate[:,None]*(ts+step<=end)[None,:]
        new=np.flatnonzero(~initial & np.isfinite(ign[j,rr,cc]))
        for col in new:
            birth=F(float(ign[j,rr[col],cc[col]]));end_j=math.floor(birth+duration)
            on=(ts>=math.ceil(birth)) & (ts+step<=end_j)
            rate[:,on]+=coef[:,col,None]
        rate=np.ascontiguousarray(rate[lookup]);prefix=np.zeros_like(rate);prefix[:,1:]=np.cumsum(rate[:,:-1]*step,axis=1)
        ng=0;clock1=ints([]);clock2=ints([]);base=np.empty(0,np.int64);mean=base
        if improved is not None:
            groups=defaultdict(list);groups[(0,end)]=list(np.flatnonzero(initial))
            for col in new:
                birth=F(float(ign[j,rr[col],cc[col]]))
                groups[(math.ceil(birth),math.floor(birth+duration))].append(col)
            ng=len(groups);clock1=ints([a for a,b in groups]);clock2=ints([b for a,b in groups])
            base=np.ascontiguousarray(np.column_stack([coef[:,cols].sum(axis=1)[lookup] for cols in groups.values()]))
            mean=np.ascontiguousarray(np.maximum(base,np.column_stack([improved[:,cols].sum(axis=1) for cols in groups.values()])))
            if np.any(mean.sum(axis=1)>2**58//(horizon+1)):return None
        visits=ct.c_longlong(0);arrive=ct.c_int(-1)
        lower=lib.mincost(len(si),len(edges),dep,last,si[s],si[z],dwell,step,bins,*map(pbuf,[first,to,dt,reverse,goal,rate,prefix,offsets,begins,ends]),budget,ct.byref(visits),ct.byref(arrive),ng,*map(pbuf,[clock1,clock2,base,mean]))
        if lower<0:return None
        earliest.append(arrive.value);states.append([member,lower,budget,visits.value,arrive.value])
        if lower>budget:
            return dict(proved=True,member=member,minimum_terminal_lower_nano=lower if lower<2**60 else None,budget_nano=budget,work=states,bin_s=step,tight=tight)
    return dict(proved=False,work=states,earliest_lower=max(earliest))
