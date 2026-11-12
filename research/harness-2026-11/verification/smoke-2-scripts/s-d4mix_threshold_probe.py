import json,numpy as np,glob,collections
data={f.split('/')[-1][:-4]:dict(np.load(f)) for f in sorted(glob.glob('dist/*.npz'))}
r=json.load(open('precheck_mine.json'))
for pred in ("p_d4_wind_seed0","p_c651_mc"):
    allp=np.concatenate([z[pred].astype(float)[z['dist_m']<=4000] for z in data.values()])
    print(pred,"band cells",allp.size,"p<=1e-12:",(allp<=1e-12).mean().round(4),"p==0:",(allp==0).mean().round(4),"min",allp.min())
    # floored medians
    nfl=0;nb=0
    for z in data.values():
        p=z[pred].astype(float);d=z['dist_m'];iv=z['interval']
        for k in np.unique(iv):
            m=(iv==k)&(d<=4000);b=np.floor(d[m]/375).astype(int)
            for bb in range(1,11):
                s=b==bb
                if s.sum()>=5: nb+=1; nfl+= np.median(p[m][s])<=1e-12
    print("  bin medians at floor:",nfl,"/",nb)
    print("  top10 fires:",collections.Counter(x['fire'][:12] for x in r['predictors'][pred]['top10_tail_intervals']))
    for thr in (1e-4,1e-5,1e-6,1e-7):
        iv_t=[]
        for f,z in data.items():
            m=z['dist_m']<=4000;p=z[pred].astype(float)[m];y=z['y'][m];iv=z['interval'][m]
            t=(y==1)&(p<thr)
            for k in np.unique(iv): iv_t.append((f,int(t[iv==k].sum())))
        c=sorted([x[1] for x in iv_t],reverse=True);tot=sum(c)
        print(f"  thr {thr:g}: tail {tot} top10 share {sum(c[:10])/max(tot,1):.3f}")
    # leave-one-fire-out slope median
    print("  max_pos_dist at band edge share:",np.mean([x['max_pos_dist_m']>3900 for x in r['predictors'][pred]['top10_tail_intervals']]))
