"""Owen: independent brute force from DESIGN.md's problem statement vs fbase.solve_exact / solve_ten."""
import sys, random
sys.path.insert(0, sys.argv[1])
from fbase import Instance, solve_exact, replay, instance_text
try:
    from fbase_ten import solve_ten, parse as ten_parse
except Exception: solve_ten=None
def ivs(rng,H,k):
    pts=sorted(rng.sample(range(0,H+1),min(2*k,H+1)))
    out=[(pts[i],pts[i+1]) for i in range(0,len(pts)-1,2)]
    return out
def mine(inst):
    # state set per second; edge move admitted; wait not admitted
    def inn(l,t): return any(a<=t<=b for a,b in l)
    if inst.hd(inst.s0) in inst.AC and inn(inst.AC[inst.hd(inst.s0)],inst.dep): return ("ROUTE",inst.dep)
    reach={inst.dep:{inst.s0}}; best=None
    for t in range(inst.dep,inst.H+1):
        for s in reach.get(t,()):
            n=inst.hd(s)
            if n in inst.waitable and not inn(inst.WB.get(n,[]),t) and t+1<=inst.H: reach.setdefault(t+1,set()).add(s)
            for j in range(inst.nE):
                if inst.tail[j]!=n or (s,j) in inst.forbid or inn(inst.EB.get(j,[]),t) or t+inst.D[j]>inst.H: continue
                a=t+inst.D[j]; reach.setdefault(a,set()).add(j)
                if inst.head[j] in inst.AC and inn(inst.AC[inst.head[j]],a): best=a if best is None else min(best,a)
    return ("ROUTE",best) if best is not None else ("NO_ROUTE",None)
rng=random.Random(int(sys.argv[2])); bad=0; N=int(sys.argv[3]); routes=0; tenbad=0; tenn=0
for it in range(N):
    nV=rng.randint(2,6); nE=rng.randint(1,10); H=rng.randint(3,30)
    tail=[rng.randrange(nV) for _ in range(nE)]; head=[rng.randrange(nV) for _ in range(nE)]
    D=[rng.randint(1,4) for _ in range(nE)]
    origin=rng.randrange(nV)
    inst=Instance(nV=nV,nE=nE,dep=rng.randint(0,3),H=H,origin=origin,s0=nE,tail=tail,head=head,D=D,
        waitable={v for v in range(nV) if rng.random()<0.5},
        forbid={(s,j) for s in range(nE+1) for j in range(nE) if rng.random()<0.15},
        EB={j:ivs(rng,H,rng.randint(0,2)) for j in range(nE) if rng.random()<0.6},
        WB={v:ivs(rng,H,rng.randint(0,2)) for v in range(nV) if rng.random()<0.5},
        AC={v:ivs(rng,H,rng.randint(1,2)) for v in rng.sample(range(nV),rng.randint(1,2))})
    inst.EB={k:v for k,v in inst.EB.items() if v}; inst.WB={k:v for k,v in inst.WB.items() if v}; inst.AC={k:v for k,v in inst.AC.items() if v}
    if not inst.AC: continue
    ref=mine(inst); c,T,w=solve_exact(inst)
    routes+=ref[0]=="ROUTE"
    if (c,T)!=ref: bad+=1; print("MISMATCH",it,ref,(c,T)) if bad<4 else None
    elif c=="ROUTE":
        try: ok=replay(inst,w,T)
        except Exception as e: ok=f"EXC {e}"
        if ok is False: print("replay?",it,ok) if bad<4 else None
    if solve_ten is not None:
        try:
            r=solve_ten(ten_parse(instance_text(inst))); tenn+=1
            if (r[0],r[1])!=ref: tenbad+=1
        except Exception as e:
            if tenn==0 and it<3: print("ten call failed:",e)
print(f"N={N} exact mismatches={bad} routes={routes} ten_checked={tenn} ten_mismatches={tenbad}")
