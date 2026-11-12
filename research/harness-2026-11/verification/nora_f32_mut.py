"""Nora targeted mutations: C4-only goal injection (instance AC edit), wait-unblock (WB edit), edge-unblock (EB edit)."""
import sys, random, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from nora_f32_reach import parse, norm, sub

def cert(text):
    tk = text.split('END_INSTANCE',1)[1].split(); i = 0
    def nx():
        nonlocal i; i += 1; return tk[i-1]
    def ni(): return int(nx())
    def ivl():
        m = ni(); return [(ni(), ni()) for _ in range(m)]
    assert nx()=='CLAIM'; c=nx(); T = ni() if c=='ROUTE' else None
    assert nx()=='WITNESS'
    for _ in range(ni()): nx(); ni(); ni(); ni()
    assert nx()=='CERT'; T2=ni(); k=ni(); C={}
    for _ in range(k):
        s=ni(); C[s]=(ivl(), ivl())
    return T2, C

def ser_ivl(v): return f"{len(v)}" + ''.join(f" {a} {b}" for a,b in v)
def ser_instance(I):
    L=['WFGC 1','INSTANCE',f"V {I['V']} E {I['E']}",f"DEP {I['dep']} HOR {I['H']} ORIGIN {I['origin']} START {I['s0']}",'EDGES']
    L+= [f"{a} {b} {c}" for a,b,c in I['edges']]
    L.append('WAITABLE '+str(len(I['waitable']))+''.join(f' {n}' for n in sorted(I['waitable'])))
    L.append('FORBID '+str(len(I['F']))+''.join(f' {s} {j}' for s,j in sorted(I['F'])))
    for key in ('EB','WB','AC'):
        recs=[(n,v) for n,v in sorted(I[key].items()) if v or key=='AC']
        L.append(f'{key} {len(recs)}'); L+= [f'{n} {ser_ivl(v)}' for n,v in recs]
    L.append('END_INSTANCE')
    return '\n'.join(L)+'\n'
def inside(v,t): return any(a<=t<=b for a,b in v)

def run(chk, path):
    p=subprocess.run(chk+[str(path)],capture_output=True,text=True); return p.stdout.strip()

if __name__=='__main__':
    d=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(exist_ok=True)
    C_CHK=[sys.argv[3]]; PY_CHK=[sys.executable, sys.argv[4]]
    rnd=random.Random(20261112); tally={}
    for f in sorted(d.glob('*.wfgc')):
        txt=f.read_text(); I=parse(txt); T,C=cert(txt); rest=txt[txt.index('CLAIM'):]
        # round-trip sanity: re-serialised unmutated instance must still be accepted
        base=ser_instance(I)+rest
        (out/'rt.wfgc').write_text(base)
        assert run(C_CHK,out/'rt.wfgc').startswith('ACCEPT') and run(PY_CHK,out/'rt.wfgc').startswith('ACCEPT'), f
        E=I['E']; head=[e[1] for e in I['edges']]; tail=[e[0] for e in I['edges']]; D=[e[2] for e in I['edges']]
        hd=lambda s: I['origin'] if s==E else head[s]
        lim=min(I['H'],T-1)
        muts=[]
        # M_C4: inject acceptance at an admitted second < T
        cand=[(s,t) for s,(R,A) in C.items() for a,b in A for t in (a,b) if t<=lim]
        if cand:
            s,t=rnd.choice(cand); J=parse(txt); n=hd(s); J['AC'][n]=norm(J['AC'].get(n,[])+[(t,t)]); muts.append(('C4_inject_accept',J))
        # M_WB: unblock a wait second that cuts a reachable run
        cand=[(s,w) for s,(R,A) in C.items() if hd(s) in I['waitable'] for a,b in R for w in [b] if w+1<=lim and inside(I['WB'].get(hd(s),[]),w)]
        if cand:
            s,w=rnd.choice(cand); J=parse(txt); n=hd(s); J['WB'][n]=sub(J['WB'][n],[(w,w)]); muts.append(('WB_unblock',J))
        # M_EB: unblock an edge departure second that is reachable and whose arrival is not admitted
        cand=[]
        outj={}
        for j in range(E): outj.setdefault(tail[j],[]).append(j)
        for s,(R,A) in C.items():
            for j in outj.get(hd(s),[]):
                if (s,j) in I['F'] or j not in I['EB']: continue
                Aj=C.get(j,([],[]))[1]
                for a,b in I['EB'].get(j,[]):
                    for t in range(a,min(b,a+50)+1):
                        if inside(R,t) and t+D[j]<=lim and not inside(Aj,t+D[j]): cand.append((j,t))
            if len(cand)>200: break
        if cand:
            j,t=rnd.choice(cand); J=parse(txt); J['EB'][j]=sub(J['EB'][j],[(t,t)]); muts.append(('EB_unblock',J))
        for name,J in muts:
            p=out/f'{f.stem}.{name}.wfgc'; p.write_text(ser_instance(J)+rest)
            rc,rp=run(C_CHK,p),run(PY_CHK,p)
            ok=rc.startswith('REJECT') and rp.startswith('REJECT')
            tally.setdefault(name,[0,0]); tally[name][0]+=1; tally[name][1]+=ok
            print(f.stem,name,'| c:',rc,'| py:',rp,'|','OK' if ok else '*** NOT REJECTED ***',flush=True)
    print('TALLY', tally)
