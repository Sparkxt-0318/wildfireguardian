"""Turn-aware integer-clock reachability on reversible native road corridors."""
from collections import defaultdict
from heapq import heappop, heappush
from math import ceil, floor, inf
from time import perf_counter

from corridor_events import temporal_bound


def check_deadline(deadline):
    if perf_counter() >= deadline:
        raise TimeoutError("CORRIDOR_STAGE_BUDGET")


def bits(start, stop):
    """Integer ticks in [start, stop)."""
    start = max(0, start)
    if stop <= start:
        return 0
    return ((1 << (stop-start))-1) << start


def point_allowed(periods, duration, last):
    """Starts whose closed stationary occupancy misses every half-open fire interval."""
    permitted = bits(0, last+1)
    for begin, end in periods:
        permitted &= ~bits(ceil(begin-duration), min(last+1, ceil(end)))
    return permitted


def terminal_ticks(q, contact):
    dest, = q['destinations']
    stay = int(dest['dwell'])
    last = int(q['horizon'])-stay
    openings = 0
    for begin, end in dest['open_intervals']:
        openings |= bits(max(int(q['departure']),ceil(begin)), min(last,floor(end-stay))+1)
    return openings & point_allowed(contact.get(dest['node'],()),stay,last)


def saturate(arrivals, unit_clear, ceiling):
    """Close a set under any number of legal successive one-tick waits."""
    safe = unit_clear
    stride = 1
    while stride <= ceiling:
        extra = ((arrivals & safe) << stride) & ((1 << (ceiling+1))-1)
        enlarged = arrivals | extra
        if enlarged == arrivals:
            return arrivals
        arrivals = enlarged
        safe &= safe >> stride
        stride *= 2
    return arrivals


def lower_distances(compiled, target):
    incoming = defaultdict(list)
    for k, part in enumerate(compiled.parts):
        u = compiled.index.edges[part[0]]['u']
        incoming[compiled.ends[k]].append((u, compiled.cost[k], k))
    d = {target:0}
    queue = [(0,target)]
    while queue:
        t,node = heappop(queue)
        if d.get(node) != t:
            continue
        for u,dt,_ in incoming.get(node,()):
            value = t+dt
            if value < d.get(u,inf):
                d[u] = value
                heappush(queue,(value,u))
    return d,incoming


def search(compiled, forbidden, point_contact, req, deadline):
    """Return earliest relaxed witness, or None following complete impossibility proof."""
    check_deadline(deadline)
    depart = int(req['departure'])
    horizon = int(req['horizon'])
    z = req['destinations'][0]['node']
    origin = req['position']['node']
    terminal = terminal_ticks(req,point_contact)
    stats = {'algorithm':'legal_corridor_contact_lattice','exhausted':False,'label_batches':0,
             'clock_labels':0,'passes':0,'corridors':len(compiled.parts)}
    def absent(reason):
        stats.update(exhausted=True,reason=reason)
        return None,stats
    if not terminal:
        return absent('DESTINATION_STAY_HAS_NO_OPEN_CONTACT_FREE_TICK')
    optimistic,_ = temporal_bound(compiled,forbidden,req)
    check_deadline(deadline)
    if optimistic is None:
        return absent('UNREACHABLE_EVEN_WITH_UNRESTRICTED_BOUNDARY_WAITING')
    eligible = terminal & ~bits(0,int(optimistic))
    if not eligible:
        return absent('DESTINATION_WINDOW_PRECEDES_TRAVEL_LOWER_BOUND')
    low = (eligible & -eligible).bit_length()-1
    last = eligible.bit_length()-1
    stats.update(unrestricted_arrival_bound=low,latest_possible_arrival=last)
    reverse,incoming = lower_distances(compiled,z)
    initial = req.get('incoming_edge')
    first_edge = None if initial is None else compiled.index.by_id[initial]
    wait_clear = {}
    entry_clear = {}
    ceilings = (low,) if low==last else (low,last)
    def wait_at(node):
        if node not in wait_clear:
            wait_clear[node] = point_allowed(point_contact.get(node,()),1,horizon-1)
        return wait_clear[node]
    def can_enter(k):
        if k not in entry_clear:
            allowed = bits(depart,horizon+1)
            for a,b in forbidden[k]:
                allowed &= ~bits(int(a),int(b))
            entry_clear[k] = allowed
        return entry_clear[k]

    def solve(ceiling):
        check_deadline(deadline)
        stats['passes']+=1
        allowed_goal = eligible & bits(0,ceiling+1)
        # State -1 is the initial arrival. Every other state ends a physical movement.
        initial_bit=1<<depart
        reached={-1:initial_bit}
        pending={-1:initial_bit}
        keys={-1:depart+reverse.get(origin,inf)}
        queue=[(keys[-1],-1)]
        best=ceiling+1; success=None
        if origin==z and initial_bit & allowed_goal:
            best=depart;success=-1
        while queue:
            estimate,s = heappop(queue)
            if estimate != keys.get(s):continue
            if estimate>=best or estimate>ceiling:break
            del keys[s]
            times=pending.pop(s)
            stats['label_batches']+=1
            if stats['label_batches']%64==0:check_deadline(deadline)
            node=origin if s==-1 else compiled.ends[s]
            in_edge=first_edge if s==-1 else compiled.parts[s][-1]
            cap=min(ceiling,best-1)-reverse[node]
            times &= bits(0,cap+1)
            if not times:continue
            if node in compiled.index.waitable:
                times=saturate(times,wait_at(node),cap)
            for k in compiled.at.get(node,()):
                if in_edge is not None and not compiled.index.allowed(in_edge,compiled.parts[k][0]):
                    continue
                after=compiled.ends[k]; dt=compiled.cost[k]; tail=reverse.get(after)
                if tail is None or dt+tail>ceiling-depart:continue
                t=(times & can_enter(k) & bits(0,min(ceiling,best-1)-tail-dt+1))<<dt
                new=t & ~reached.get(k,0)
                if not new:continue
                reached[k]=reached.get(k,0)|new
                stats['clock_labels']+=new.bit_count()
                if after==z and (new & allowed_goal):
                    ok=new & allowed_goal
                    candidate=(ok & -ok).bit_length()-1
                    if candidate<best:
                        best=candidate;success=k
                estimate=(new & -new).bit_length()-1 + tail
                if estimate >= best:continue
                pending[k]=pending.get(k,0)|new
                if estimate<keys.get(k,inf):
                    keys[k]=estimate;heappush(queue,(estimate,k))
        if success is None:
            return None
        s=success; t=best; chunks=[]
        while s!=-1:
            check_deadline(deadline)
            path=compiled.parts[s]
            u=compiled.index.edges[path[0]]['u']
            e=t-compiled.cost[s]
            if not (can_enter(s) & (1<<e)):
                raise ArithmeticError('Invalid cached arrival')
            earliest=e
            if u in compiled.index.waitable:
                earliest=((~wait_at(u)) & bits(0,e)).bit_length()
            choices=[]
            if u==origin:
                choices.append((-1,first_edge))
            choices.extend((p,compiled.parts[p][-1]) for _,_,p in incoming.get(u,()))
            start_time=-1;pred=None
            for p,inc in choices:
                if inc is not None and not compiled.index.allowed(inc,path[0]):continue
                possible=reached.get(p,0)&bits(earliest,e+1)
                if possible and possible.bit_length()-1>start_time:
                    start_time=possible.bit_length()-1;pred=p
            if pred is None:
                raise ArithmeticError('Reachable clock has no predecessor')
            chunk=[]
            if start_time<e:
                chunk.append(dict(kind='WAIT',node=u,start=start_time,end=e))
            for j in path:
                edge=compiled.index.edges[j]; end=e+edge['travel_ticks']
                chunk.append(dict(kind='EDGE',edge=edge['id'],start=e,end=end,from_fraction=0,to_fraction=1))
                e=end
            if e!=t:raise ArithmeticError('Corridor traversal duration changed')
            chunks.append(chunk);s,t=pred,start_time
        if t!=depart:raise ArithmeticError('Reconstruction missed departure')
        return {'legs':[leg for c in reversed(chunks) for leg in c],'arrival':best,'destination':z}
    for ceiling in ceilings:
        route=solve(ceiling)
        if route is not None:
            stats.update(lower_bound_arrival=route['arrival'],wait_legs=sum(x['kind']=='WAIT' for x in route['legs']))
            return route,stats
    return absent('ALL_PERMITTED_ARRIVAL_TICKS_EXHAUSTED')
