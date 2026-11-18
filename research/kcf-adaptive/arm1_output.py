"""Arm 1-F: OUTPUT-LEVEL adaptation of the committed c651 mean-field probabilities (PROTOCOL 2.4, item 4).

No weights change. p' = 1 - (1 - p)^c, one number c per window, fitted on the fire's own earlier windows only.
This is not the requested weight-level test; it shows what a one-number rate correction buys.

    python arm1_output.py --out derived/arm1_output.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

from cases import HELDOUT, KOREAN, history_for, load_windows, paired_bootstrap, summarise

PENALTY, S_MAX = 0.01, 5.0
SOURCE = "p_c651_meanfield"


def rescale(p, s):
    return -np.expm1(np.exp(s) * np.log1p(-np.clip(p, 0.0, 1 - 1e-12)))


def fit_c(hist, leak_free=True):
    """ln c minimising the mean window Brier over `hist` plus the frozen penalty."""
    if not hist:
        return 0.0
    data = [(w.committed[SOURCE], w.y.astype(float)) for w in hist]

    def loss(s):
        return float(np.mean([np.mean((rescale(p, s) - y) ** 2) for p, y in data])) + PENALTY * s * s

    r = minimize_scalar(loss, bounds=(-S_MAX, S_MAX), method="bounded", options=dict(xatol=1e-10))
    return float(r.x)


def run(root, leak=False):
    fires = load_windows(root)
    rows, cols = [], dict(fire=[], y=[], adapted=[], unadapted=[], mc=[], has_history=[])
    for ev, ws in fires.items():
        for w in ws:
            hist = history_for(ws, w, _leak_target=leak)
            s = fit_c(hist)
            p = w.committed[SOURCE]
            cols["fire"].append(np.full(len(w.y), ev)); cols["y"].append(w.y.astype(float))
            cols["adapted"].append(rescale(p, s)); cols["unadapted"].append(p); cols["mc"].append(w.committed["p_c651_mc"])
            n_hist = len(hist) - (1 if leak else 0)
            cols["has_history"].append(np.full(len(w.y), n_hist > 0))
            rows.append(dict(event=ev, case_id=w.case_id, cutoff=str(w.cutoff), hours=w.hours, history=n_hist,
                             ln_c=s, c=float(np.exp(s)), positives=int(w.y.sum()), cells=int(len(w.y))))
    c = {k: np.concatenate(v) for k, v in cols.items()}
    return rows, c


def report(c, mask=None):
    m = np.ones(len(c["y"]), bool) if mask is None else mask
    preds = dict(adapted_output_level=c["adapted"][m], c651_meanfield_committed=c["unadapted"][m],
                 c651_mc_committed=c["mc"][m], persistence=np.zeros(int(m.sum())))
    s = summarise(c["fire"][m], c["y"][m], preds)
    se, n = s.pop("_se"), s.pop("_n")
    s["paired_brier_difference"] = {
        "adapted_minus_c651_meanfield": paired_bootstrap(se["adapted_output_level"], se["c651_meanfield_committed"], n),
        "adapted_minus_persistence": paired_bootstrap(se["adapted_output_level"], se["persistence"], n),
        "c651_meanfield_minus_persistence": paired_bootstrap(se["c651_meanfield_committed"], se["persistence"], n),
        "c651_mc_minus_persistence": paired_bootstrap(se["c651_mc_committed"], se["persistence"], n)}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = dict(label="OUTPUT-LEVEL adaptation of committed c651 mean-field probabilities; not the weight-level test",
               source=SOURCE, penalty=PENALTY)
    rows, c = run(HELDOUT)
    out["us2024"] = dict(windows=rows, all_windows=report(c), windows_with_history=report(c, c["has_history"]))
    rows_l, c_l = run(HELDOUT, leak=True)
    out["us2024_LEAKY_NOT_A_RESULT"] = dict(note="target window added to its own history (positive control)",
                                           brier=float(np.mean((c_l["adapted"] - c_l["y"]) ** 2)))
    rows_k, ck = run(KOREAN)
    out["korea2025_descriptive"] = dict(windows=rows_k, all_windows=report(ck) if ck["y"].sum() else None)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    for name in ("all_windows", "windows_with_history"):
        r = out["us2024"][name]
        print(name, r["entries"], r["positives"])
        for k, v in r["models"].items():
            print(f"  {k:28s} brier {v['brier']:.7f}  sum p / burned {v['calibration']['sum_p_over_burned']:.3f}  "
                  f"exp miss {v['flagging']['expected_miss_rate']:.3f}  ece {v['calibration']['ece']:.5f}")
        for k, v in r["paired_brier_difference"].items():
            print(f"  {k:38s} {v['point']:+.7f} [{v['ci95'][0]:+.7f}, {v['ci95'][1]:+.7f}] fires favouring {v['fires_favouring_a']}/6")
    print("LEAKY (not a result) brier", out["us2024_LEAKY_NOT_A_RESULT"]["brier"])
    lc = np.array([r["ln_c"] for r in rows if r["history"]])
    print("ln c quartiles", np.quantile(lc, [0, .25, .5, .75, 1]).round(3))


if __name__ == "__main__":
    main()
