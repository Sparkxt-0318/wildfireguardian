from heapq import heappop, heappush
from itertools import count
from time import monotonic

def road_cost(route):
    return sum(l['end']-l['start'] for l in route['legs'] if l['kind']=='EDGE')

def least_driving(world,q,arrival,incumbent_cost,deadline,limit):
    target,=q['destinations']
    z=target['node'];source=q['position']['node'];dep=q['departure'];dwell=target['dwell']
    dist=world.static(z);base=dist.get(source,float('inf'))
    assert dep<=arrival and arrival+dwell<=q['horizon'] and any(a<=arrival and arrival+dwell<=b for a,b in target['open_intervals'])
    if base>=incumbent_cost:
        assert base==incumbent_cost
        return 'STATIC_BOUND',None,0
    def permitted(u,v,start,duration):
        return all(start<lo or start>=hi for lo,hi in world.blocked(u,v,duration))
    # The state for arrival is distinct from remaining in place at a destination.
    root=(source,q['incoming_edge'],dep,True)
    seq=count();heap=[(base,0,next(seq),root)]
    best={root:0};parents={}
    while heap:
        f,cost,_,state=heappop(heap)
        if cost!=best[state]:continue
        if monotonic()>=deadline or len(best)>limit:return 'WORK_LIMIT',None,len(best)
        u,inc,t,fresh=state
        if t==arrival and u==z and fresh and permitted(u,u,t,dwell):
            steps=[];node=state
            while node!=root:
                prev,eid=parents[node]
                steps.append((eid,prev[0],prev[2],node[2]));node=prev
            legs=[]
            for edge,at,a,b in reversed(steps):
                if edge is None:
                    if legs and legs[-1]['kind']=='WAIT' and legs[-1]['end']==a:legs[-1]['end']=b
                    else:legs.append(dict(kind='WAIT',node=at,start=a,end=b))
                else:legs.append(dict(kind='EDGE',edge=edge,start=a,end=b))
            route=dict(legs=legs,destination=z,arrival=arrival)
            assert road_cost(route)==cost<incumbent_cost
            return 'RELAXED_MINIMUM',route,len(best)
        if t>=arrival:continue
        def put(v,edge,duration,moving):
            arrival_tick=t+duration;used=cost+(duration if moving else 0);d=dist.get(v,float('inf'))
            if arrival_tick+d>arrival or used+d>=incumbent_cost:return
            successor=(v,edge if moving else inc,arrival_tick,moving)
            if used>=best.get(successor,float('inf')) or not permitted(u,v,t,duration):return
            best[successor]=used;parents[successor]=(state,edge if moving else None)
            heappush(heap,(used+d,used,next(seq),successor))
        for v,dt,edge in world.adj.get(u,()):
            if (inc,edge) not in world.turns:put(v,edge,dt,True)
        if world.nodes[u]['waitable']:put(u,None,1,False)
    return 'EXHAUSTED',None,len(best)
