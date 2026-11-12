import numpy as np,glob
data=[dict(np.load(f)) for f in sorted(glob.glob('dist/*.npz'))]
for pred in ("p_d4_wind_seed0","p_c651_mc"):
  for floor,drop in ((1e-12,False),(1e-20,False),(1e-30,False),(1e-12,True)):
    sl=[]
    for z in data:
        p=z[pred].astype(float);d=z['dist_m'];iv=z['interval']
        for k in np.unique(iv):
            m=(iv==k)&(d<=4000);b=np.floor(d[m]/375).astype(int);med=[]
            for bb in range(1,11):
                s=b==bb
                if s.sum()>=5:
                    v=np.median(p[m][s])
                    if drop and v<=1e-12: continue
                    med.append((bb,np.log10(max(v,floor))))
            if len(med)>=3:
                x,y=np.array(med).T; sl.append(np.polyfit(x,y,1)[0])
    q=np.quantile(sl,[.1,.5,.9]); print(pred,f"floor {floor:g} drop_floored={drop} n={len(sl)} factor q10/50/90",np.round(10**q,4))
