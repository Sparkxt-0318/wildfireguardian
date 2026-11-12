import sys,numpy as np
sys.path.insert(0,sys.argv[1])
from fpp import cellular_automaton, first_passage
from gate1 import SIZE, regimes
init=np.zeros((SIZE,SIZE),bool); init[19:22,19:22]=True
name=sys.argv[2]; n=2000
spec=regimes()[name]; K,T=spec["K"],spec["T"]; hours=np.arange(1,T+1,dtype=float)
for s in [11,12,13]:
    c,arr=first_passage(K,init,hours,n_samples=n,seed=s,keep_arrivals=n)
    ref=((arr<=T)&~init).sum(axis=(1,2)).mean()
    _,th=cellular_automaton(K,init,hours,n_samples=n,seed=1000+s,return_totals=True,dt=1.0)
    _,tq=cellular_automaton(K,init,hours,n_samples=n,seed=2000+s,return_totals=True,dt=1.0,half_step=True)
    h,q=th[-1].mean(),tq[-1].mean()
    print(name,s,f"fp {ref:.2f} hourly {h:.2f} half {q:.2f} share {(q-h)/(ref-h):.3f}",flush=True)
