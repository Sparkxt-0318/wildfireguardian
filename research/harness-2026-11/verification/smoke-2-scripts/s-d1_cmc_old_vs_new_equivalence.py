import sys,numpy as np,importlib.util
sys.path.insert(0,sys.argv[1]); sys.path.insert(0,sys.argv[2] if len(sys.argv)>2 else 'oldfpp')  # dir holding ada7709 fpp.py renamed fpp_old.py
import fpp as new, fpp_old as old
rng=np.random.default_rng(0); bad=0
for trial,(k,S,H,hs,scale,edge) in enumerate([(5,2,20,[1.,2.5,4.],0.3,False),(3,1,16,[3.],1.0,True),(9,3,24,[0.5,2.,6.],0.15,False),(5,4,12,[1.,8.],2.0,True),(7,1,30,[5.],0.05,False)]):
    K=rng.uniform(0,scale,size=(S,k*k,H,H)); K[:,k*k//2]=0
    K*= rng.random(K.shape)<0.7   # sparse zeros -> non-positive offsets
    init=np.zeros((H,H),bool)
    if edge: init[0,:3]=True; init[H-1,H-1]=True
    else: init[H//2,H//2]=True
    for seed in (1,2):
        a=new.first_passage_cmc(K,init,hs,n_samples=40,seed=seed,seg_len=1.0 if trial!=3 else 0.5)
        b=old.first_passage_cmc(K,init,hs,n_samples=40,seed=seed,seg_len=1.0 if trial!=3 else 0.5)
        for key in a:
            if not np.array_equal(a[key],b[key]):
                d=np.abs(np.asarray(a[key])-np.asarray(b[key])).max(); print("DIFF",trial,seed,key,d); bad+=d>1e-12
        print(trial,seed,"plain mass",a["plain"].sum().round(2),"gap",np.round(a["gap_fraction"],4))
print("BAD",bad)
