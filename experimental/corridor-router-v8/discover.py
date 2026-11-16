"""Candidate discovery only. All distances, heat and time estimates below may only propose journeys."""
from collections import defaultdict
from pathlib import Path
import ctypes as ct
import heapq,json,math
import numpy as np
HERE=Path(__file__).resolve().parent

def times(adj,s):
    d={s:0};q=[(0,s)]
    while q:
        at,u=heapq.heappop(q)
        if d[u]!=at:continue
        for v,dt in adj[u]:
            b=at+dt
            if b<d.get(v,math.inf):d[v]=b;heapq.heappush(q,(b,v))
    return d

def find(graph,q,packet,weight=None,step=10,slack=1.):
    p=Path(packet);meta=json.loads((p/'NATIVE_METADATA.json').read_bytes());cfg=meta['construction']['assumptions'];members=meta['construction']['scenario_ids']
    s=q['position']['node'];d,=q['destinations'];z=d['node'];dwell=int(d['dwell']);dep=int(q['departure']);H=int(q['horizon']);last=H-dwell
    nodes={n['id']:n for n in graph['nodes']};adj=defaultdict(list);rev=defaultdict(list)
    for e in graph['edges']:
        u,v,dt=e['u'],e['v'],e['travel_ticks'];adj[u].append((v,dt));rev[v].append((u,dt))
    ds=times(adj,s);dz=times(rev,z);raw=[];by=defaultdict(list)
    for e in graph['edges']:
        u,v,dt=e['u'],e['v'],e['travel_ticks']
        if ds.get(u,math.inf)+dt+dz.get(v,math.inf)<=last-dep:
            by[u].append(len(raw));raw.append((u,v,dt,e['id']))
    for u in ds:
        if nodes[u]['waitable'] and ds[u]+1+dz.get(u,math.inf)<=last-dep:
            by[u].append(len(raw));raw.append((u,u,1,None))
    raw.append((z,z,dwell,None));end_geo=len(raw)-1
    coord=np.array([[nodes[u]['x'],nodes[u]['y'],nodes[v]['x'],nodes[v]['y']] for u,v,_,_ in raw])
    with np.load(p/'constructed_arrays.npz') as a:seen=a['current_active'];ig=a['ignition_time_s']
    rr,cc=np.nonzero(seen|np.isfinite(ig).any(axis=0));sz,x0,top=meta['affine_transform'][0],meta['affine_transform'][2],meta['affine_transform'][5]
    x=x0+cc*sz;y=top-(rr+1)*sz;initial=seen[rr,cc]
    h=cfg['emission_height_m']-cfg['receiver_height_m'];coef=math.prod(cfg[k] for k in ['fuel_load_kg_m2','consumed_fraction','heat_of_combustion_j_kg','radiative_fraction','atmospheric_transmissivity'])/(1000*cfg['burning_duration_s']*4*math.pi)
    ts=np.arange(0,H+1,step);bins=len(ts)
    # Normalized rates permit unequal remaining dose budgets.
    budgets=np.array([float(q['budgets']['dose'][m])-float(q['incurred'][m]) for m in members])
    if budgets.min()<=0:return None
    starts=[];lows=[];highs=[];rlist=[]
    birth=np.where(initial,0,ig[:,rr,cc]);death=np.where(initial,cfg['initial_remaining_s'],birth+cfg['burning_duration_s'])
    active=(ts[None,None,:]+step/2>=birth[:,:,None])&(ts[None,None,:]+step/2<death[:,:,None]); active=active.astype(float)
    locs,weights=np.polynomial.legendre.leggauss(5)
    for i in range(0,len(raw),96):
        rows=coord[i:i+96];ax=rows[:,0,None];ay=rows[:,1,None];dx=rows[:,2,None]-ax;dy=rows[:,3,None]-ay
        shape=(len(rows),len(x));f=np.zeros(shape)
        for a,b in zip(locs,weights):
            px=ax+(a+1)*dx/2;py=ay+(a+1)*dy/2
            def omega(X,Y):return np.arctan2(X*Y,h*np.sqrt(X**2+Y**2+h*h))
            X=x-px;Y=y-py
            f+=b*.5*coef*(omega(X+sz,Y+sz)+omega(X,Y)-omega(X+sz,Y)-omega(X,Y+sz))
        norm=np.array([f@ac/bu for ac,bu in zip(active,budgets)])
        rlist.append((norm.max(axis=0) if weight is None else np.average(norm,axis=0,weights=weight)).astype(np.float32))
        lo=np.zeros(shape);hi=np.ones(shape)
        for origin,delta,left in [(ax,dx,x),(ay,dy,y)]:
            slope=np.where(delta==0,1,delta)
            a=(left-origin)/slope;b=(left+sz-origin)/slope
            lo=np.maximum(lo,np.where(delta==0,np.where((origin<left)|(origin>left+sz),2.,0.),np.minimum(a,b)))
            hi=np.minimum(hi,np.where(delta==0,1.,np.maximum(a,b)))
        for j in range(len(rows)):
            starts.append(len(lows));dt=raw[i+j][2]
            for l in np.flatnonzero(lo[j]<=hi[j]):
                for t0,t1 in set(zip(birth[:,l],death[:,l])):
                    if np.isfinite(t0):
                        lows.append(math.ceil(t0-hi[j,l]*dt-1e-9));highs.append(math.ceil(t1-lo[j,l]*dt+1e-9))
    starts.append(len(lows));rates=np.concatenate(rlist);prefix=np.zeros_like(rates,dtype=float);prefix[:,1:]=np.cumsum(rates[:,:-1],axis=1,dtype=float)*step
    turns={tuple(pair) for pair in graph['forbidden_turns']};needed={a for a,b in turns}
    def state(u,e):return (u,e if e in needed else None)
    start=state(s,q['incoming_edge']);states=[start];si={start:0};head=[];to=[];geo=[]
    for u,inc in states:
        head.append(len(to))
        for g in by[u]:
            _,v,dt,eid=raw[g]
            if (inc,eid) in turns:continue
            nxt=state(v,eid) if eid is not None else (u,inc)
            if nxt not in si:si[nxt]=len(states);states.append(nxt)
            geo.append(g);to.append(si[nxt])
    head.append(len(to))
    lib=ct.CDLL(str(HERE/'walk.so'));lib.findwalk.argtypes=[ct.c_int]*9+[ct.c_void_p]*14+[ct.c_double,ct.c_int]+[ct.c_void_p]*3
    goal=[any(a<=t and t+dwell<=b for a,b in d['open_intervals']) for t in range(last+1)]
    ints=lambda L:np.array(L,dtype=np.int32)
    inputs=list(map(ints,[[u==z for u,_ in states],[x[3] is not None for x in raw],head,to,[raw[g][2] for g in geo],geo,[dz[u] for u,_ in states],goal]))+[rates,prefix]+list(map(ints,[starts,lows,highs]))
    lib.findwalk.argtypes=[ct.c_int]*9+[ct.c_void_p]*len(inputs)+[ct.c_double,ct.c_int]+[ct.c_void_p]*3
    out=np.zeros(H+2,dtype=np.int32);arr=ct.c_int(-1);dose=ct.c_double()
    ok=lib.findwalk(len(states),len(to),dep,last,0,0,dwell,bins,step,*(a.ctypes.data for a in inputs),slack,end_geo,out.ctypes.data,ct.byref(arr),ct.byref(dose))
    if ok or arr.value<0:return None
    legs=[];clock=dep
    for g in out[:np.where(out<0)[0][0]][::-1]:
        u,v,dt,eid=raw[g]
        if eid is not None:legs.append(dict(kind='EDGE',edge=eid,start=clock,end=clock+dt,from_fraction=0,to_fraction=1))
        elif legs and legs[-1]['kind']=='WAIT':legs[-1]['end']+=dt
        else:legs.append(dict(kind='WAIT',node=u,start=clock,end=clock+dt))
        clock+=dt
    return dict(legs=legs,arrival=clock,destination=z)
