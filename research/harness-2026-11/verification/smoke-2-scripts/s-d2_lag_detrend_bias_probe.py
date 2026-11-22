"""Owen: iid-noise probe of the detrended lag-1 excess in lag_persistence_v2.py (run from S-D2/ at 6ae6dfea).
Usage: python s-d2_lag_detrend_bias_probe.py <displacement_mcem.json>
Replaces log_ratio with iid N(0,1) on the real fire/run structure; reports mean excess for raw, detrended (as coded:
detrend then permute) and detrended with the null 'permute then detrend'."""
import json, sys, numpy as np
sys.path.insert(0, '.')
import lag_persistence_v2 as L
d = json.load(open(sys.argv[1])); per = L.fire_series(d, np.random.default_rng(1), False)
fires = sorted(f for f in per if len(L.pairs_for(per[f], 1))); rng = np.random.default_rng(7)
def stat2(per, fires, rng):
    xs, ys = [], []
    for f in fires:
        s = per[f]; v = s['log_ratio'][rng.permutation(len(s['run']))]; v = L.detrend(v, s['index']); p = L.pairs_for(s, 1)
        xs.append(v[p]); ys.append(v[p + 1])
    return float(np.corrcoef(np.concatenate(xs), np.concatenate(ys))[0, 1])
for label in ('raw', 'detrended_as_coded', 'detrended_correct_null'):
    ex = []
    for _ in range(300):
        sim = {f: dict(per[f], log_ratio=rng.normal(size=len(per[f]['run']))) for f in fires}
        det = label != 'raw'
        o = L.stat(sim, fires, 'log_ratio', 1, det, False)
        nm = np.mean([stat2(sim, fires, rng) if label == 'detrended_correct_null' else L.stat(sim, fires, 'log_ratio', 1, det, False, rng) for _ in range(40)])
        ex.append(o - nm)
    print(label, 'mean excess %.3f sd %.3f' % (np.mean(ex), np.std(ex)))
