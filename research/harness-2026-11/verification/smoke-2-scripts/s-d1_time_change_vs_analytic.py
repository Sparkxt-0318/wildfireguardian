import sys; sys.path.insert(0,sys.argv[1])
import numpy as np
from fpp import first_passage, time_change_arrivals
def Ginv(T,z):
    out=np.full(T.shape,np.inf); g=0.0; rem=np.isfinite(T).copy()
    for h in range(100000):
        zz=z[min(h,len(z)-1)]
        if zz>0:
            m=rem&(T<=g+zz); out[m]=h+(T[m]-g)/zz; rem&=~m
        g+=zz
        if (h>=len(z)-1 and zz==0) or not rem.any(): break
    return out
def run(z,horizon,sparse,edge,seed=0,H=10,W=11):
    rng=np.random.default_rng(seed)
    K=rng.uniform(0,0.3,size=(25,H,W)); K[12]=0
    if sparse: K*=rng.random(K.shape)<0.6
    init=np.zeros((H,W),bool); 
    if edge: init[0,3]=True
    else: init[H//2,W//2]=True
    _,base=first_passage(K,init,[1e6],n_samples=25,seed=seed,keep_arrivals=25)
    _,direct=first_passage(K[None]*np.asarray(z)[:,None,None,None],init,[horizon],n_samples=25,seed=seed,keep_arrivals=25)
    ex=Ginv(base,np.asarray(z,float)); ex=np.where(ex<=horizon,ex,np.inf)
    f=np.isfinite(ex); g=np.isfinite(direct)
    d=float(np.abs(np.where(f&g,direct-ex,0)).max())
    return int((f!=g).sum()), d
for z,hz in [([1.,2.,0.],8.),([1.,2.,0.],2.9),([1.,2.,0.5],8.),([2.,0.,0.,5.,1.],3.5),([2.,0.,0.,5.,1.],8.),([2.,1.,1.,5.,1.],3.5),([0.5,0.,3.,1.,8.,0.2],12.)]:
    for sparse in (False,True):
        for edge in (False,True):
            print(z,hz,"sparse" if sparse else "dense","edge" if edge else "centre", run(z,hz,sparse,edge))
