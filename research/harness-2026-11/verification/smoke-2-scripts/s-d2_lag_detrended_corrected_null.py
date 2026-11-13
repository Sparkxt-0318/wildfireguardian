"""Owen: corrected null for the detrended lag-1 excess (permute within fire, THEN detrend), same pairs/metrics as lag_persistence_v2."""
import json,sys,numpy as np
sys.path.insert(0,'.')
import lag_persistence_v2 as L
d=json.load(open(sys.argv[1])); seed=20261112
for drop in (False,True):
  per=L.fire_series(d,np.random.default_rng(seed),drop)
  fires=sorted(f for f in per if len(L.pairs_for(per[f],1)))
  for metric in ('rank','log_ratio'):
    def obs_stat(fs): return L.stat(per,fs,metric,1,True,False)
    def null_stat(fs,rng):
      xs,ys=[],[]
      for f in fs:
        s=per[f]; v=s[metric][rng.permutation(len(s[metric]))]; v=L.detrend(v,s['index']); p=L.pairs_for(s,1); xs.append(v[p]); ys.append(v[p+1])
      return float(np.corrcoef(np.concatenate(xs),np.concatenate(ys))[0,1])
    rng=np.random.default_rng([seed,7,drop,metric=='rank'])
    o=obs_stat(fires); null=np.array([null_stat(fires,rng) for _ in range(2000)])
    ex=[]
    for _ in range(400):
      pick=[fires[i] for i in rng.integers(0,len(fires),len(fires))]
      ex.append(obs_stat(pick)-np.mean([null_stat(pick,rng) for _ in range(30)]))
    print(f"{'no_detached ' if drop else ''}{metric:9s} detrended lag1: r {o:.3f}  corrected null {null.mean():.3f}±{null.std():.3f}  excess {o-null.mean():+.3f}  CI [{np.percentile(ex,2.5):+.3f},{np.percentile(ex,97.5):+.3f}]  p {(1+(null>=o).sum())/(len(null)+1):.4f}")
