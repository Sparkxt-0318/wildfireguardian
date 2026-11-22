"""Independent verifier: WIDENED_GRAPH_RULE P2/P3 on one packet pair, own code. argv: v37 /2 packet dir, padded packet dir, N"""
import json, sys, numpy as np
A, B, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
ha, hb = json.load(open(A + '/HAZARD.json')), json.load(open(B + '/HAZARD.json'))
ga, gb = ha['grid'], hb['grid']; W0, H0, W1, H1 = ga['width'], ga['height'], gb['width'], gb['height']
print('grids', ga, gb)
r = np.arange(H0)[:, None]; c = np.arange(W0)[None, :]
idx = ((r + N) * W1 + (c + N)).ravel()                      # old flat (row from south) -> new flat
pad = np.ones(W1 * H1, bool); pad[idx] = False
res = {}
for ma, mb in zip(ha['members'], hb['members']):
    ba, bb = ma['breakpoints'], mb['breakpoints']; res['breakpoints_equal'] = ba == bb
    fa, fb = np.array(ma['flame'], bool), np.array(mb['flame'], bool)
    res['flame_export_equal'] = bool(np.array_equal(fa, fb[:, idx])); res['flame_padding_any'] = int(fb[:, pad].sum())
    xa, xb = np.array(ma['flux'], float), np.array(mb['flux'], float)
    d = np.abs(xa - xb[:, idx]); rel = d / np.maximum(np.abs(xa), 1e-300)
    res['flux_max_abs'] = float(d.max()); res['flux_max_rel'] = float(rel[d > 0].max()) if (d > 0).any() else 0.0
    res['flux_A1_fail'] = int(((d > 1e-12) & (rel > 1e-9)).sum())
    res['flux_padding_max'] = float(xb[:, pad].max())
    sb = np.array(mb['support'], bool); res['support_false_is_padding'] = bool(np.array_equal(~sb.all(0), pad)) if sb.ndim == 2 else bool(np.array_equal(~sb, pad))
    res['ids_differ'] = ma['id'] != mb['id']
for k in ('valid_until', 'valid_from', 'dt'):
    res[k + '_equal'] = ha.get(k) == hb.get(k)
z = np.load(B + '/constructed_arrays.npz'); s = np.asarray(z['support']); res['npz_support_false'] = int((~s.astype(bool)).sum()) // s.shape[0]
sa = json.load(open(A + '/BUILD_SUMMARY.json')); sb_ = json.load(open(B + '/BUILD_SUMMARY.json'))
for k in ('enclosure', 'initial_remaining_s', 'initial_remaining_exact', 'present_fire_cells'):
    res[k + '_equal'] = sa.get(k) == sb_.get(k)
    if sa.get(k) != sb_.get(k): res[k] = (sa.get(k), sb_.get(k))
print(json.dumps(res, indent=0))
