"""Nora: independent F-3.2 checks. (1) own forward reachability on the .wfgc INSTANCE -> OPT; compare with CLAIM and
with CERT R/A (truncated). (2) targeted mutations (C4-only goal injection, wait-unblock, edge-unblock) fed to both checkers."""
import sys, glob, subprocess, random, bisect
from pathlib import Path

def parse(text):
    tk = text.split(); i = 0
    def nx():
        nonlocal i; i += 1; return tk[i-1]
    def ni(): return int(nx())
    def ivl():
        m = ni(); return [(ni(), ni()) for _ in range(m)]
    I = {}
    assert nx()=='WFGC' and nx()=='1' and nx()=='INSTANCE'
    nx(); I['V']=ni(); nx(); I['E']=ni(); nx(); I['dep']=ni(); nx(); I['H']=ni(); nx(); I['origin']=ni(); nx(); I['s0']=ni()
    assert nx()=='EDGES'; I['edges']=[(ni(),ni(),ni()) for _ in range(I['E'])]
    assert nx()=='WAITABLE'; I['waitable']=set(ni() for _ in range(ni()))
    assert nx()=='FORBID'; k=ni(); I['F']=set((ni(),ni()) for _ in range(k))
    for key in ('EB','WB','AC'):
        assert nx()==key; k=ni(); I[key]={}
        for _ in range(k):
            n=ni(); I[key][n]=ivl()
    assert nx()=='END_INSTANCE'
    return I

def norm(iv):
    iv=sorted(iv); out=[]
    for a,b in iv:
        if out and a<=out[-1][1]+1: out[-1]=(out[-1][0],max(out[-1][1],b))
        else: out.append((a,b))
    return out
def sub(a, b):  # a minus b; a, b sorted disjoint (two-pointer)
    out=[]; k=0; nb=len(b)
    for lo,hi in sorted(a):
        cur=lo
        while k<nb and b[k][1]<cur: k+=1
        m=k
        while m<nb and b[m][0]<=hi:
            x,y=b[m]
            if x>cur: out.append((cur,x-1))
            cur=max(cur,y+1)
            if cur>hi: break
            m+=1
        if cur<=hi: out.append((cur,hi))
    return out
def inter(a,b):
    out=[]
    for lo,hi in a:
        for x,y in b:
            l,h=max(lo,x),min(hi,y)
            if l<=h: out.append((l,h))
    return norm(out)

def reach(I):
    E,H,dep=I['E'],I['H'],I['dep']
    tail=[e[0] for e in I['edges']]; head=[e[1] for e in I['edges']]; D=[e[2] for e in I['edges']]
    hd=lambda s: I['origin'] if s==E else head[s]
    out={}
    for j,t in enumerate(tail): out.setdefault(t,[]).append(j)
    def comp(n, runs):   # waiting closure
        if n not in I['waitable']: return runs
        WB=I['WB'].get(n,[]); ends=[b for _,b in WB]; res=[]
        for lo,hi in runs:
            # extend hi to next blocked wait second >= hi (or H)
            k=bisect.bisect_left(ends,hi)
            e=min(H,max(WB[k][0],hi)) if k<len(WB) else H
            res.append((lo,max(hi,e)))
        return norm(res)
    R={}; A={}
    s0=I['s0']; A[s0]=[(dep,dep)]
    import heapq
    work=[]; cnt=0
    for lo,hi in comp(hd(s0), [(dep,dep)]): heapq.heappush(work,(lo,cnt,s0,lo,hi)); cnt+=1
    while work:
        _,_,s,lo,hi=heapq.heappop(work)
        new=sub([(lo,hi)], R.get(s,[]))
        if not new: continue
        R[s]=norm(R.get(s,[])+new)
        for j in out.get(hd(s),[]):
            if (s,j) in I['F']: continue
            dep_ok=sub([(lo,min(hi,H-D[j])) for lo,hi in new if lo<=min(hi,H-D[j])], I['EB'].get(j,[]))
            arr=[(x+D[j],y+D[j]) for x,y in dep_ok]
            if not arr: continue
            A[j]=norm(A.get(j,[])+arr)
            for lo2,hi2 in comp(head[j], arr):
                heapq.heappush(work,(lo2,cnt,j,lo2,hi2)); cnt+=1
    best=None
    for s,a in A.items():
        g=inter(a, I['AC'].get(hd(s),[]))
        if g and (best is None or g[0][0]<best): best=g[0][0]
    return R,A,best

if __name__=='__main__':
    d=Path(sys.argv[1]); cc=sys.argv[2]; py=sys.argv[3]
    files=sorted(d.glob('*.wfgc'), key=lambda p: p.stat().st_size)
    for f in files:
        txt=f.read_text(); I=parse(txt)
        claim=txt.split('CLAIM',1)[1].split()[:2]
        R,A,best=reach(I)
        exp = ('ROUTE',str(best)) if best is not None else ('NO_ROUTE',)
        ok = tuple(claim[:len(exp)])==exp if best is not None else claim[0]=='NO_ROUTE'
        print(f.name, 'claim', ' '.join(claim) if claim[0]=='ROUTE' else claim[0], '| own OPT', best, '|', 'AGREE' if ok else 'DISAGREE', flush=True)
