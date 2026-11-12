"""S-D4mix pre-check (no rollout): how does predicted probability fall with distance, and do a few fast
intervals hold most tail positives? DEVELOPMENT-ONLY, on the exposed US2024 cohort R.

Inputs: Victor's derive_dist.py output (one <fire>.npz per US2024 fire: the committed forecast-v2
heldout entry arrays plus dist_m; branch claude/s-d9-forecast-benchmark, research/harness-2026-11/S-D9/
derive/derive_dist.py). Predictors examined: p_d4_wind_seed0 and p_c651_mc (if present).

Per predictor:
  (1) decay: within each interval, median log10 p over distance bins of one cell (375 m) out to 4 km;
      the per-interval slope (least squares on bins with finite medians) in log10 units per cell,
      and the implied per-cell-hop factor 10^slope. Pooled quantiles across intervals.
  (2) tail concentration: tail = positives (y = 1) with p < 1e-5 in the 4 km band. Share of all tail
      positives held by the top 1, 3, 5 and 10 intervals; those intervals' hours, total positives,
      max positive distance and an "apparent speed" = max positive dist_m / hours.
  (3) for contrast, the same for positives with p >= 1e-5.

    python research/harness-2026-11/s-d4mix/precheck.py --dist-dir DIR [--out RESULTS_precheck.json]
"""
import argparse
import json
from pathlib import Path

import numpy as np

BAND_M = 4000.0
CELL = 375.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist-dir", required=True)
    ap.add_argument("--out", default=str(Path(__file__).with_name("RESULTS_precheck.json")))
    args = ap.parse_args()
    files = sorted(Path(args.dist_dir).glob("*.npz"))
    data = {f.stem: dict(np.load(f, allow_pickle=False)) for f in files}
    out = {"fires": list(data), "band_m": BAND_M, "predictors": {}}
    for pred in ("p_d4_wind_seed0", "p_c651_mc"):
        if not all(pred in z for z in data.values()):
            continue
        slopes, intervals = [], []
        for fire, z in data.items():
            iv, y, d, p, hours = z["interval"], z["y"], z["dist_m"], z[pred].astype(float), z["hours"]
            for k in np.unique(iv):
                m = (iv == k) & (d <= BAND_M)
                if not m.any():
                    continue
                pk, dk, yk = p[m], d[m], y[m]
                bins = np.floor(dk / CELL).astype(int)
                med = []
                for b in range(1, int(BAND_M // CELL) + 1):
                    sel = bins == b
                    if sel.sum() >= 5:
                        v = np.median(np.log10(np.maximum(pk[sel], 1e-12)))
                        med.append((b, v))
                if len(med) >= 3:
                    bb, vv = np.array(med).T
                    slopes.append(float(np.polyfit(bb, vv, 1)[0]))
                h = float(hours[k]) if hours.ndim and len(hours) > k else float("nan")
                tail = (yk == 1) & (pk < 1e-5)
                pos = yk == 1
                intervals.append(dict(fire=fire, interval=int(k), hours=h, positives=int(pos.sum()),
                                      tail_positives=int(tail.sum()),
                                      nontail_positives=int((pos & ~tail).sum()),
                                      max_pos_dist_m=float(dk[pos].max()) if pos.any() else 0.0,
                                      apparent_speed_m_per_h=float(dk[pos].max() / h) if pos.any() and h > 0 else 0.0))
        s = np.array(slopes)
        tot_tail = sum(x["tail_positives"] for x in intervals)
        tot_nt = sum(x["nontail_positives"] for x in intervals)
        ranked = sorted(intervals, key=lambda x: -x["tail_positives"])
        conc = {f"top{n}": float(sum(x["tail_positives"] for x in ranked[:n]) / max(tot_tail, 1)) for n in (1, 3, 5, 10)}
        ranked_nt = sorted(intervals, key=lambda x: -x["nontail_positives"])
        conc_nt = {f"top{n}": float(sum(x["nontail_positives"] for x in ranked_nt[:n]) / max(tot_nt, 1)) for n in (1, 3, 5, 10)}
        with_tail = [x for x in intervals if x["tail_positives"] > 0]
        without = [x for x in intervals if x["tail_positives"] == 0 and x["positives"] > 0]
        out["predictors"][pred] = dict(
            intervals=len(intervals), intervals_with_slope=len(s),
            log10_slope_per_cell_q10_q50_q90=[float(x) for x in np.quantile(s, [0.1, 0.5, 0.9])],
            per_cell_factor_q10_q50_q90=[float(10 ** x) for x in np.quantile(s, [0.1, 0.5, 0.9])],
            tail_positives=tot_tail, nontail_positives=tot_nt, intervals_with_tail=len(with_tail),
            tail_share_top_intervals=conc, nontail_share_top_intervals=conc_nt,
            apparent_speed_m_per_h_median_with_tail=float(np.median([x["apparent_speed_m_per_h"] for x in with_tail])) if with_tail else None,
            apparent_speed_m_per_h_median_without_tail=float(np.median([x["apparent_speed_m_per_h"] for x in without])) if without else None,
            hours_median_with_tail=float(np.median([x["hours"] for x in with_tail])) if with_tail else None,
            hours_median_without_tail=float(np.median([x["hours"] for x in without])) if without else None,
            top10_tail_intervals=ranked[:10])
        r = out["predictors"][pred]
        print(f"== {pred}: intervals {len(intervals)}; slope log10/cell q10/50/90 {np.round(r['log10_slope_per_cell_q10_q50_q90'], 3)}"
              f" (factor {np.round(r['per_cell_factor_q10_q50_q90'], 3)})")
        print(f"   tail positives {tot_tail} in {len(with_tail)} intervals; share in top1/3/5/10 {conc}; non-tail {conc_nt}")
        print(f"   apparent speed m/h median: with tail {r['apparent_speed_m_per_h_median_with_tail']}, without {r['apparent_speed_m_per_h_median_without_tail']};"
              f" hours median with/without tail {r['hours_median_with_tail']}/{r['hours_median_without_tail']}")
        for x in ranked[:5]:
            print("   ", x)
    Path(args.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
