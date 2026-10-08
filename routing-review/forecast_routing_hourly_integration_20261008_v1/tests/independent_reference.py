"""Reviewer-written reference. No constructor, solver or delivery-checker imports.

Exact rational time integration over declared cell-center fields. This verifies
the finite routing contract; it does not establish continuous spatial heat or
real fire safety. Enumeration keeps every timed walk, without dominance.
"""
from bisect import bisect_right
from fractions import Fraction as F
from heapq import heappop, heappush
from itertools import count
from math import ceil, floor


def cell(graph, x, y):
    g = graph["grid"]
    col = floor((F(x) - F(g["x0"])) / F(g["resolution"]))
    row = floor((F(y) - F(g["y0"])) / F(g["resolution"]))
    if not (0 <= col < g["width"] and 0 <= row < g["height"]):
        raise ValueError("SPATIAL_COVERAGE")
    return row * g["width"] + col


def edge_spans(graph, edge, start, end, first=0, last=1):
    nodes = {n["id"]: n for n in graph["nodes"]}
    a, b = nodes[edge["u"]], nodes[edge["v"]]
    first, last, start, end = map(F, (first, last, start, end))
    grid = graph["grid"]
    cuts = {first, last}
    for axis, base, size in (("x", "x0", "width"), ("y", "y0", "height")):
        delta = F(b[axis]) - F(a[axis])
        if delta:
            for j in range(1, grid[size]):
                z = (F(grid[base]) + j * F(grid["resolution"]) - F(a[axis])) / delta
                if first < z < last:
                    cuts.add(z)
    def xy(z):
        return tuple(F(a[ax]) + z * (F(b[ax]) - F(a[ax])) for ax in ("x", "y"))
    def time(z):
        return start + (end-start)*(z-first)/(last-first)
    spans = []
    ordered = sorted(cuts)
    for z in ordered:
        spans.append((cell(graph, *xy(z)), time(z), time(z)))
    for left, right in zip(ordered, ordered[1:]):
        # Occupancy is closed: both adjacent interval closures are checked.
        spans.append((cell(graph, *xy((left+right)/2)), time(left), time(right)))
    return spans


def integrate(hazard, spans, incurred=None, include_dose=True):
    stats, codes = {}, set()
    for m in hazard["members"]:
        dose, peak = F((incurred or {}).get(m["id"], 0)), 0
        bp = list(map(F, m["breakpoints"]))
        for c, lo, hi in spans:
            lo, hi = F(lo), F(hi)
            if lo < bp[0] or hi > bp[-1] or hi < lo:
                codes.add("MISSING_SUPPORT")
                continue
            cuts = sorted({lo, hi} | {p for p in bp if lo < p < hi})
            for point in cuts:
                k = min(len(bp)-2, bisect_right(bp, point)-1)
                if not m["support"][k][c]:
                    codes.add("MISSING_SUPPORT")
                if m["flame"][k][c]:
                    codes.add("FLAME_CONTACT")
                peak = max(peak, m["flux"][k][c])
            if include_dose:
                for left, right in zip(cuts, cuts[1:]):
                    k = min(len(bp)-2, bisect_right(bp, left)-1)
                    if m["support"][k][c]:
                        dose += (right-left)*F(m["flux"][k][c])
        stats[m["id"]] = {"dose":dose, "peak":peak}
    return stats, codes


def witness(graph, hazard, request, legs, destination):
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    dests = {d["node"]: d for d in request["destinations"]}
    now, pos, incoming, admission = request["departure"], request["position"].copy(), request["incoming_edge"], True
    spans = []
    if "edge" in pos and pos["fraction"] == 1:
        incoming, pos = pos["edge"], {"node": edges[pos["edge"]]["v"]}
    if "node" in pos:
        spans.append((cell(graph, nodes[pos["node"]]["x"],nodes[pos["node"]]["y"]),now,now))
    else:
        e = edges[pos["edge"]]
        spans += edge_spans(graph,e,now,now,pos["fraction"],1)[:1]
    for index, leg in enumerate(legs):
        if leg["start"] != now or leg["end"] <= now or leg["end"] > request["horizon"]:
            return {"ok":False,"codes":["ROUTE_TIME"]}
        if (F(leg["end"])-F(now))/F(hazard["dt"]) != int((F(leg["end"])-F(now))/F(hazard["dt"])):
            return {"ok":False,"codes":["ROUTE_LATTICE"]}
        if leg["kind"] == "WAIT":
            if "node" not in pos or leg["node"] != pos["node"] or not nodes[pos["node"]]["waitable"]:
                return {"ok":False,"codes":["ILLEGAL_WAIT"]}
            n=nodes[pos["node"]]
            spans.append((cell(graph,n["x"],n["y"]),now,leg["end"]))
            admission=False
        elif leg["kind"] == "EDGE":
            e=edges[leg["edge"]]
            first,last=leg["from_fraction"],leg["to_fraction"]
            if not 0 <= first < last == 1:
                return {"ok":False,"codes":["ROUTE_FRACTION"]}
            if "edge" in pos:
                old=edges[pos["edge"]]
                forward=e["id"]==old["id"] and first==pos["fraction"]
                reverse=graph["mid_edge_reversal"] and old.get("reverse_edge")==e["id"] and F(first)==1-F(pos["fraction"])
                if index != 0 or not (forward or reverse):
                    return {"ok":False,"codes":["PARTIAL_POSITION"]}
            elif e["u"] != pos["node"] or first != 0:
                return {"ok":False,"codes":["ROUTE_CONTINUITY"]}
            if incoming is not None and [incoming,e["id"]] in graph["forbidden_turns"]:
                return {"ok":False,"codes":["FORBIDDEN_TURN"]}
            duration=ceil(F(e["travel_ticks"])*(1-F(first)))*F(hazard["dt"])
            if F(leg["end"])-F(now) != duration:
                return {"ok":False,"codes":["ROUTE_DURATION"]}
            spans += edge_spans(graph,e,now,leg["end"],first,last)
            pos,incoming,admission={"node":e["v"]},e["id"],True
        else:
            return {"ok":False,"codes":["ROUTE_KIND"]}
        now=leg["end"]
    if pos != {"node":destination} or destination not in dests or not admission:
        return {"ok":False,"codes":["DESTINATION_ADMISSION"]}
    d=dests[destination]
    finish=now+d["dwell"]
    if finish > request["horizon"] or not any(lo <= now and finish <= hi for lo,hi in d["open_intervals"]):
        return {"ok":False,"codes":["DESTINATION_DWELL"]}
    stats,codes=integrate(hazard,spans,request["incurred"])
    n=nodes[destination]
    dwell,dcodes=integrate(hazard,[(cell(graph,n["x"],n["y"]),now,finish)],include_dose=request["exposure_scope"]=="including_dwell")
    codes |= dcodes
    for mid,s in stats.items():
        s["dose"] += dwell[mid]["dose"]
        s["peak"]=max(s["peak"],dwell[mid]["peak"])
        if s["dose"] > F(request["budgets"]["dose"][mid]): codes.add("DOSE_BUDGET")
        if s["peak"] > request["budgets"]["peak"]: codes.add("PEAK_BUDGET")
    return {"ok":not codes,"codes":sorted(codes),"arrival":now,"per_member":{k:{"dose":float(v["dose"]),"peak":v["peak"]} for k,v in stats.items()}}


def exhaustive(graph,hazard,request,max_walks=100000):
    nodes={n["id"]:n for n in graph["nodes"]}
    edges={e["id"]:e for e in graph["edges"]}
    destinations={d["node"] for d in request["destinations"]}
    serial=count()
    initial=request["position"].copy()
    if "edge" in initial:
        raise ValueError("Reviewer tiny enumeration bounded to node starts; witnesses support mid-edge")
    queue=[(request["departure"],next(serial),initial["node"],request["incoming_edge"],True,[])]
    popped=0
    while queue:
        if popped >= max_walks: return {"status":"UNRESOLVED","arrival":None,"walks":popped}
        now,_,node,incoming,admission,legs=heappop(queue)
        popped += 1
        if admission and node in destinations:
            result=witness(graph,hazard,request,legs,node)
            if result["ok"]: return {**result,"status":"FEASIBLE","legs":legs,"destination":node,"walks":popped}
        if nodes[node]["waitable"] and now+hazard["dt"] <= request["horizon"]:
            end=now+hazard["dt"]
            wait={"kind":"WAIT","node":node,"start":now,"end":end}
            heappush(queue,(end,next(serial),node,incoming,False,legs+[wait]))
        for e in edges.values():
            if e["u"] != node or (incoming is not None and [incoming,e["id"]] in graph["forbidden_turns"]): continue
            end=now+e["travel_ticks"]*hazard["dt"]
            if end > request["horizon"]: continue
            leg={"kind":"EDGE","edge":e["id"],"start":now,"end":end,"from_fraction":0,"to_fraction":1}
            heappush(queue,(end,next(serial),e["v"],e["id"],True,legs+[leg]))
    full=all(all(all(row) for row in m["support"]) for m in hazard["members"])
    return {"status":"INFEASIBLE" if full else "UNSUPPORTED","arrival":None,"walks":popped}


def radiation_quadrature(active, transform, density, radiative_fraction, height, transmission=1.0, order=96):
    """Integrate h/(4*pi*r^3) over every source cell using Gauss-Legendre.

    This directly integrates point-source irradiance and shares no solid-angle
    implementation or FFT with the mentor or constructor.
    """
    import numpy as np
    x,w=np.polynomial.legendre.leggauss(order)
    u,v=np.meshgrid((x+1)/2,(x+1)/2,indexing="ij")
    weights=np.outer(w,w)/4
    a,b,c,d,e,f=transform
    area=abs(a*e-b*d)
    active=np.asarray(active)
    h,wid=active.shape
    out=np.zeros_like(active,dtype=float)
    density=np.broadcast_to(density,active.shape)
    rf=np.broadcast_to(radiative_fraction,active.shape)
    for rr in range(h):
        for cc in range(wid):
            rx=a*(cc+.5)+b*(rr+.5)+c
            ry=d*(cc+.5)+e*(rr+.5)+f
            for sr in range(h):
                for sc in range(wid):
                    if active[sr,sc] == 0: continue
                    sx=a*(sc+u)+b*(sr+v)+c
                    sy=d*(sc+u)+e*(sr+v)+f
                    kernel=height/(4*np.pi*((sx-rx)**2+(sy-ry)**2+height**2)**1.5)
                    out[rr,cc] += float(np.sum(kernel*weights))*area*active[sr,sc]*density[sr,sc]*rf[sr,sc]*transmission
    return out


def rectangular_source_sum(active, transform, density, radiative_fraction, height, receivers, transmission=1.0):
    """Independent rectangle antiderivative for axis-aligned large-grid checks.

    Uses four arctangent corner terms, not the delivered triangular solid-angle
    geometry or convolution. Sources are ground-area sheets, receivers points.
    """
    import numpy as np
    a,b,c,d,e,f=transform
    if b != 0 or d != 0:
        raise ValueError("Reference rectangle formula requires axis alignment")
    active=np.asarray(active)
    source_density=active*np.broadcast_to(density,active.shape)*np.broadcast_to(radiative_fraction,active.shape)
    rr,cc=np.indices(active.shape)
    lx=np.minimum(a*cc+c,a*(cc+1)+c)
    ux=np.maximum(a*cc+c,a*(cc+1)+c)
    ly=np.minimum(e*rr+f,e*(rr+1)+f)
    uy=np.maximum(e*rr+f,e*(rr+1)+f)
    def corner(x,y):
        return np.arctan2(x*y,height*np.sqrt(x*x+y*y+height*height))
    fields=[]
    for r,col in receivers:
        x=a*(col+.5)+c;y=e*(r+.5)+f
        solid=corner(ux-x,uy-y)-corner(lx-x,uy-y)-corner(ux-x,ly-y)+corner(lx-x,ly-y)
        fields.append(float(np.sum(source_density*solid)/(4*np.pi))*transmission)
    return np.asarray(fields)
