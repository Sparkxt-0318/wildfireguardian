"""Diagnostic for check (b), CO: are the cell-minutes outside 3 standard errors the ones reached by few paths?

Run like perpath_export.py (pipeline on the path):  python diag_co_check.py --v1 export_6h --out export_v2
Writes export_v2/diag_co_check.json. No criterion is evaluated.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import perpath_export as E


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--v1", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); v1 = Path(a.v1)
    from wildfire import monte_carlo_hazards as mch
    initial, spread, factory = E.setup(6)
    cap = []
    orig = mch._window_exposure
    def capture(*args, **kw):
        cap.append((args, kw))   # one call for all six hours, as in v1/v2: the same source set in every hour
    mch._window_exposure = capture
    try:
        spread.calculate_hazards(hours_later=list(range(6)), initial_activity=initial, physical_factory=factory,
                                 ignition_timing="uniform_within_step", timing_seed=E.SEED, time_step_s=60.,
                                 batch_size=E.BATCH_PIPELINE, activity_mode="probability_map")
    finally:
        mch._window_exposure = orig
    pw = E.PathWeights(cap); P = pw.n
    edges = np.r_[np.arange(0., 3600., 60.), 3600.]
    out = {}
    for name, key, scale in (("co", "co_mg_m3", 1.), ("radiant", "q_rad_kw_m2", 1000.)):
        rows = []
        for h in range(6):
            phys = cap[h][0][6]
            s = q = cnt = None
            mw = np.zeros((60, len(pw.source)))
            for b0 in range(0, P, 32):
                paths = np.arange(b0, min(P, b0 + 32))
                w = pw.weights(paths, h, edges)
                mw += w.sum(axis=0)
                rad, co = E.fields(phys, w, edges)
                x = (co if name == "co" else rad).reshape(len(paths), 60, -1)
                s = x.sum(0) if s is None else s + x.sum(0)
                q = (x ** 2).sum(0) if q is None else q + (x ** 2).sum(0)
                cnt = (x > 0).sum(0) if cnt is None else cnt + (x > 0).sum(0)
            mean = s / P
            se = np.sqrt(np.maximum(q / P - mean ** 2, 0.) / (P - 1))
            v = np.load(v1 / ("hour_%02d.npz" % h))[key].reshape(60, -1) * scale
            # the field of the mean weights: linear, so it must equal the mean field exactly
            from wildfire.hazards import HazardTimeline
            tl = HazardTimeline(phys.receiver_grid, phys.receiver_shape, edges, [1.], {"source": "diag"})
            f = phys.fields_from_activity((mw / P)[None], tl, quantities=("radiant", "co"))
            fm = f.lower_bounds[name][0].reshape(60, -1)
            rows.append((mean, se, cnt, v, float(np.max(np.abs(fm - mean)))))
        mean, se, cnt, v = (np.concatenate([r[i] for r in rows]) for i in range(4))
        pos = se > 0
        within = np.abs(mean - v) <= 3 * se
        buckets = {}
        for lo, hi in ((1, 4), (5, 19), (20, 99), (100, 10 ** 6)):
            m = pos & (cnt >= lo) & (cnt <= hi)
            buckets["%d-%s paths" % (lo, hi if hi < 10 ** 6 else "")] = {
                "cell_minutes": int(m.sum()), "share_within_3_se": float(within[m].mean()) if m.any() else None}
        out[name] = {"linearity_mean_field_vs_field_of_mean_weights_max_abs": max(r[4] for r in rows),
                     "by_number_of_paths_reaching_the_cell_minute": buckets,
                     "share_within_3_se_all": float(within[pos].mean())}
    # weights split by source kind: cells burning at the cutoff (sampled draws per path; analytic in v1) and new cells
    act_all = None
    import wildfire.monte_carlo_hazards as M
    wk = {}
    for h in range(6):
        sup = cap[h][0][5]
        act, _ = M._path_active_probability(cap[h][0][2], sup, edges, hour=h, ignition_timing="uniform_within_step")
        s = q = None
        for b0 in range(0, P, 64):
            w = pw.weights(np.arange(b0, min(P, b0 + 64)), h, edges)
            s = w.sum(0) if s is None else s + w.sum(0)
            q = (w ** 2).sum(0) if q is None else q + (w ** 2).sum(0)
        mw = s / P
        sw = np.sqrt(np.maximum(q / P - mw ** 2, 0.) / (P - 1))
        for kind, m in (("burning_at_cutoff", pw.old), ("new", ~pw.old)):
            d = (mw - act)[:, m]
            e = sw[:, m]
            r = wk.setdefault(kind, {"sources": int(m.sum()), "sum_mean_weights": [], "sum_v1_weights": [],
                                     "share_within_3_se": []})
            r["sum_mean_weights"].append(float(mw[:, m].sum()))
            r["sum_v1_weights"].append(float(act[:, m].sum()))
            r["share_within_3_se"].append(float(np.mean(np.abs(d[e > 0]) <= 3 * e[e > 0])) if (e > 0).any() else None)
    out["weights_by_source_kind"] = wk
    Path(a.out, "diag_co_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
