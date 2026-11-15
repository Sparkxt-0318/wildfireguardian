"""Exhaustive small clocks plus an independent rectangular-source enclosure for solver/dose.cpp."""
import ctypes as C
import json
import random
import sys
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from solid_angle import rectangle_upper_nano

lib = C.CDLL(str(BASE / 'dose.so'))
pointer = C.c_void_p
integer = C.c_int
long = C.c_int64
lib.mincost.argtypes = [integer] * 9 + [pointer] * 10 + [long, pointer, pointer, integer] + [pointer] * 4
lib.mincost.restype = long
for kernel in (lib.coefficients, lib.mean_coeff):
    kernel.argtypes = [integer, integer, pointer, pointer, long, long, long, pointer]
    kernel.restype = integer


def flat(values, scalar=integer):
    return (scalar * len(values))(*values)


def test_source_enclosures(rng):
    count = 0
    for side in (9, 25, 375):
        for index in range(60):
            sx, sy = 5500, 4500
            height = rng.randrange(2, 50)
            density = rng.randrange(1, 1000000000)
            radius = side * (7 if index % 2 else 2)
            x = 8 * (sx + rng.randrange(-radius, radius + 1)) + rng.randrange(8)
            y = 8 * (sy + rng.randrange(-radius, radius + 1)) + rng.randrange(8)
            dx = 0 if index % 6 == 0 else rng.randrange(-600, 601)
            dy = 0 if index % 6 == 0 else rng.randrange(-600, 601)
            start, end = (x,y), (x+dx,y+dy)
            rect = flat([min(x,x+dx)//8, -(-max(x,x+dx)//8),
                         min(y,y+dy)//8, -(-max(y,y+dy)//8)], long)
            line = flat([v//8 for v in (*start,*end)], long)
            source = flat([sx,sy], long)
            coarse, mean = flat([0], long), flat([0], long)
            assert lib.coefficients(1,1,rect,source,side,height,density,coarse) == 0
            assert lib.mean_coeff(1,1,line,source,side,height,density*1000,mean) == 0
            count += 1
            # Enclose each 1/16 of the road by rational endpoints at scale 128.
            # Enlarging the source around this entire receiver interval overestimates flux.
            upper = 0
            for k in range(16):
                xx = (16*x+k*dx,16*x+(k+1)*dx)
                yy = (16*y+k*dy,16*y+(k+1)*dy)
                upper += rectangle_upper_nano((sx,sx+side,sy,sy+side),min(xx),max(xx),
                                               min(yy),max(yy),height,density,scale=128)
            assert 0 <= coarse[0] <= Fraction(upper,16) and 0 <= mean[0] <= Fraction(upper,16)
    return count


def test_time_expansion(rng):
    counts = {'graphs':0, 'comparisons':0, 'feasible':0, 'infeasible':0,
              'at_exact_minimum':0, 'terminal_unreachable':0}
    for _ in range(240):
        n = rng.randrange(2,6)
        dep, horizon, dwell = rng.randrange(0,3), rng.randrange(7,12), rng.randrange(1,4)
        last = horizon - dwell
        adj = [[] for _ in range(n)]
        edges = []
        for u in range(n):
            for v in range(n):
                if rng.random() < .34 or v == u+1:
                    adj[u].append(len(edges))
                    edges.append((v,rng.randrange(1,4)))
        m = len(edges)
        states = edges + [(n-1, dwell)]
        step = rng.randrange(1,5)
        bins = horizon//step+1
        allowed_final = [rng.random() < .65 for t in range(last+1)]
        intervals = [[(a,a+rng.randrange(1,4)) for a in [rng.randrange(0,horizon)]]
                     if rng.random()<.32 else [] for _ in range(m)]
        rates = [[rng.randrange(0,4) for j in range(bins)] for edge in states]
        groups = [(rng.randrange(0,4), rng.randrange(4,horizon+1)) for _ in range(2)]
        base = [[rng.randrange(0,5) for g in groups] for edge in states]
        mean = [[x+rng.randrange(0,4) for x in row] for row in base]
        def cost(i,t):
            end = t+states[i][1]
            coarse = sum(rates[i][sec//step] for sec in range(t,end))
            assured = 0
            for j,(start,stop) in enumerate(groups):
                active = len(range(max(t,start),min(end,stop)))
                assured += active * (mean if active == end-t else base)[i][j]
            return max(assured,coarse)
        journeys = []
        def enumerate_paths(u,t,dose):
            if u == n-1 and allowed_final[t]:
                journeys.append((t,dose+cost(m,t)))
            for i in adj[u]:
                v,dt = edges[i]
                if t+dt<=last and all(t<a or t>=b for a,b in intervals[i]):
                    enumerate_paths(v,t+dt,dose+cost(i,t))
        enumerate_paths(0,dep,0)
        minimum = min((dose for t,dose in journeys),default=None)
        if minimum is None:
            counts['terminal_unreachable'] += 1
        levels = {0,rng.randrange(1,45),10000}
        if minimum is not None:
            levels.update([max(0,minimum-1),minimum,minimum+1])
        first = [sum(map(len,adj[:k])) for k in range(n+1)]
        off = [sum(map(len,intervals[:k])) for k in range(m+1)]
        starts = [a for seq in intervals for a,b in seq]; ends = [b for seq in intervals for a,b in seq]
        prefix = [[sum(row[:j])*step for j in range(bins)] for row in rates]
        collapse=lambda rows: [x for row in rows for x in row]
        inputs = [flat(first),flat([v for v,dt in edges]),flat([dt for v,dt in edges]),flat([0]*n),
                  flat(allowed_final),flat(collapse(rates),long),flat(collapse(prefix),long),flat(off),
                  flat(starts),flat(ends)]
        clocks = [flat([a for a,b in groups]),flat([b for a,b in groups]),
                  flat(collapse(base),long),flat(collapse(mean),long)]
        for budget in levels:
            count, arrival = long(0),integer(-1)
            value=lib.mincost(n,m,dep,last,0,n-1,dwell,step,bins,*inputs,budget,
                              C.byref(count),C.byref(arrival),len(groups),*clocks)
            clock = min((t for t,dose in journeys if dose<=budget),default=-1)
            assert value>=0 and arrival.value==clock and (value<=budget)==(clock>=0)
            if clock>=0:
                assert value==minimum
            counts['comparisons']+=1
            counts['feasible' if clock>=0 else 'infeasible']+=1
            counts['at_exact_minimum']+=int(budget==minimum)
        counts['graphs']+=1
    return counts


if __name__ == '__main__':
    rng = random.Random(27305)
    report = dict(seed=27305, spatial_enclosures=test_source_enclosures(rng), clocks=test_time_expansion(rng))
    print(json.dumps(report,indent=2))
