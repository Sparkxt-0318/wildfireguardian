"""DEVELOPMENT-ONLY: why does the frozen logistic beat d4_wind in the 4 km band? (orchestrator request)

Data: cohort R only (US2024, already exposed), with dist_m from derive_dist.py.
No untouched fire is used.

Predictors are fit leave-one-fire-out (LOFO) on R: fit on 5 fires, predict the 6th.
Each uses the same negative subsampling (5%, inverse-weighted) as the frozen logistic.
  lofo_dist     features log1p(d), d/hours, log(hours), with d = min(dist cells, 40);
                these are the frozen logistic's distance and hours features
  lofo_d4recal  logit(p_d4_wind) alone: recalibrates d4 and adds no information
  lofo_hybrid   logit(p_d4_wind) plus the three distance and hours features
Also scored: the frozen logistic, d4_wind_seed0 and persistence.
Everything is scored by sd9bench inside dist_m <= 4 km, with paired whole-fire
intervals against the frozen logistic (10,000 draws, seed 20261030).
Wind, slope and biome are NOT available from committed files, so a true
ablation of those features is out of scope here.

  python logistic_dev.py --dist DIR --out LOGISTIC_DEV.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sd9bench.entries import Entries  # noqa: E402
from sd9bench.score import core  # noqa: E402

CELL_M, MAXD, BAND_M, NEG_FRAC, SEED = 375.0, 40.0, 4000.0, 0.05, 0


def features(dist_m, hours, p_d4, kind):
    d = np.minimum(dist_m / CELL_M, MAXD)
    base = [np.log1p(d), d / np.maximum(hours, 1e-9), np.log(hours)]
    lg = np.log(np.clip(p_d4, 1e-6, 1 - 1e-6) / (1 - np.clip(p_d4, 1e-6, 1 - 1e-6)))
    cols = {"dist": base, "d4recal": [lg], "hybrid": [lg] + base}[kind]
    return np.stack(cols, axis=1)


def fit(x, y, rng):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    keep = (y == 1) | (rng.random(len(y)) < NEG_FRAC)
    w = np.where(y[keep] == 1, 1.0, 1.0 / NEG_FRAC)
    sc = StandardScaler().fit(x[keep])
    m = LogisticRegression(C=1.0, max_iter=2000, random_state=SEED).fit(sc.transform(x[keep]), y[keep], sample_weight=w)
    return sc, m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    data = {}
    for path in sorted(args.dist.glob("*.npz")):
        with np.load(path, allow_pickle=False) as z:
            data[path.stem] = dict(y=z["y"].astype(int), dist=z["dist_m"], hours=z["hours"][z["interval"]],
                                   interval=z["interval"], d4=z["p_d4_wind_seed0"].astype(float),
                                   logistic=z["p_logistic"].astype(float), persistence=z["p_persistence"].astype(float))
    fires = sorted(data)
    preds = {k: {} for k in ("lofo_dist", "lofo_d4recal", "lofo_hybrid")}
    coefs = {k: {} for k in preds}
    for held in fires:
        train = [f for f in fires if f != held]
        for kind in ("dist", "d4recal", "hybrid"):
            x = np.concatenate([features(data[f]["dist"], data[f]["hours"], data[f]["d4"], kind) for f in train])
            y = np.concatenate([data[f]["y"] for f in train])
            sc, m = fit(x, y, np.random.default_rng(SEED))
            xt = features(data[held]["dist"], data[held]["hours"], data[held]["d4"], kind)
            preds["lofo_" + kind][held] = m.predict_proba(sc.transform(xt))[:, 1]
            coefs["lofo_" + kind][held] = m.coef_[0].round(4).tolist()
    band = {f: data[f]["dist"] <= BAND_M for f in fires}

    def cat(fn):
        return np.concatenate([fn(f)[band[f]] for f in fires])

    entries = Entries(
        fire=cat(lambda f: np.full(len(data[f]["y"]), f)), interval=cat(lambda f: data[f]["interval"]),
        hours=cat(lambda f: data[f]["hours"]), y=cat(lambda f: data[f]["y"].astype(float)),
        predictions={"logistic": cat(lambda f: data[f]["logistic"]), "d4_wind_seed0": cat(lambda f: data[f]["d4"]),
                     "persistence": cat(lambda f: data[f]["persistence"]),
                     **{k: cat(lambda f, k=k: preds[k][f]) for k in preds}},
    )
    scored = core(entries, references=("logistic",))
    out = dict(
        label="DEVELOPMENT-ONLY on exposed cohort R; LOFO fits; 4 km band; not a confirmatory result",
        band_m=BAND_M, entries=scored["entries"], positives=scored["positives"],
        pooled_brier={k: v["pooled"]["brier"] for k, v in scored["models"].items()},
        pooled_average_precision={k: v["pooled"]["average_precision"] for k, v in scored["models"].items()},
        lowest_bin={k: {kk: v["pooled"]["lowest_bin"][kk] for kk in ("count", "mean_prediction", "observed_frequency")}
                    for k, v in scored["models"].items()},
        low_probability_bins={k: v["pooled"]["low_probability_bins"] for k, v in scored["models"].items()},
        vs_logistic={k: dict(point=v["point_difference"], interval=v["percentile_95_interval"],
                             fires_favouring=v["fires_favouring_candidate"],
                             equal_fire=v["equal_fire"]["point_difference"],
                             equal_fire_interval=v["equal_fire"]["percentile_95_interval"],
                             per_fire=v["per_fire_difference"])
                     for k, v in scored["paired"].items() if k.endswith("__vs__logistic")},
        frozen_logistic_standardized_coefficients=json.loads(
            (Path(__file__).resolve().parents[4] / "forecast/runs/20261030_perimeter_trained/execution_v3/baselines/logistic.json").read_text()),
        lofo_standardized_coefficients=coefs,
    )
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"pooled_brier": out["pooled_brier"], "ap": out["pooled_average_precision"], "lowest_bin": out["lowest_bin"],
                      "vs_logistic": {k: {kk: vv for kk, vv in v.items() if kk != "per_fire"} for k, v in out["vs_logistic"].items()}},
                     indent=1))


if __name__ == "__main__":
    main()
