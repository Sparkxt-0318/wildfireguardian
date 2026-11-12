"""d4_wind_recal (A1 §3): a one-feature logistic recalibration of d4_wind_rebuilt, fit IN-SAMPLE on the §3.1 training
data (fit-23 + part a) from d4_wind_rebuilt's own predictions there, frozen by SHA before part c opens.
THE FIT IS HELD until the orchestrator rules on the three details A1 leaves open (Victor's proposal, 2026-11-12 16:06Z);
they are parameters here, with Victor's proposed values as defaults:
  (a) --negative-fraction 0.05 with inverse weights, the same rule and RNG draw order as `pipeline.py baselines`
      (rng = default_rng(seed); keep = y==1 | rng.random(n) < f; weights 1 / f on kept negatives);
  (b) population: the full-rectangle producer files of score_parta.py (A1 §4.1 rule 3), not the cropped training samples;
  (c) --clip 1e-6: p clipped to [clip, 1 - clip] before the logit.
Model: StandardScaler(sample_weight) + LogisticRegression(max_iter=3000, random_state=seed), as `pipeline.py baselines`.

    fit:    python recal_parta.py fit   --d4-dir D4_PRODUCER --events TRAIN_EVENTS_final.txt --out RECAL_DIR
    apply:  python recal_parta.py apply --recal RECAL_DIR/recal.pkl --d4-dir D4_PRODUCER --out PRODUCER_DIR
The apply step writes p_d4_wind_recal producer files (same entries as the d4 files) for merge_parta.py. On the part-a
development table it is IN-SAMPLE TWICE OVER (the refit and the recal both saw these fires).
"""
import argparse
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np

NOTICE = ("IN-SAMPLE TWICE OVER, DEVELOPMENT-ONLY: d4_wind_recal is fit on the same part-a/fit-23 fires as "
          "d4_wind_rebuilt; scores from these files are fit statistics.")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def logit(p, clip):
    p = np.clip(p.astype(np.float64), clip, 1 - clip)
    return np.log(p) - np.log1p(-p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("fit", "apply"))
    ap.add_argument("--d4-dir", type=Path, required=True)
    ap.add_argument("--events", type=Path)
    ap.add_argument("--recal", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--negative-fraction", type=float, default=0.05)
    ap.add_argument("--clip", type=float, default=1e-6)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "fit":
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        events = [e.strip() for e in a.events.read_text().splitlines() if e.strip()]
        rng = np.random.default_rng(a.seed)
        xs, ys, used = [], [], []
        for ev in events:  # list order, then file order: the draw order is fixed by the committed list
            f = a.d4_dir / f"{ev}.npz"
            if not f.exists():
                continue
            z = np.load(f, allow_pickle=False)
            y, p = z["y"].astype(int), z["p_d4_wind_rebuilt"]
            keep = (y == 1) | (rng.random(len(y)) < a.negative_fraction)
            xs.append(logit(p[keep], a.clip)[:, None])
            ys.append(y[keep])
            used.append(dict(event=ev, sha256=sha(f), cells=int(len(y)), kept=int(keep.sum())))
        x, y = np.concatenate(xs), np.concatenate(ys)
        w = np.where(y == 1, 1.0, 1.0 / a.negative_fraction)
        scaler = StandardScaler().fit(x, sample_weight=w)
        model = LogisticRegression(max_iter=3000, random_state=a.seed).fit(scaler.transform(x), y, sample_weight=w)
        (a.out / "recal.pkl").write_bytes(pickle.dumps(dict(scaler=scaler, model=model, clip=a.clip)))
        rec = dict(notice=NOTICE, rule="A1 §3 d4_wind_recal; details (a)-(c) per orchestrator ruling",
                   negative_fraction=a.negative_fraction, clip=a.clip, seed=a.seed, events_sha256=sha(a.events),
                   n_rows=int(len(y)), positives=int(y.sum()), coef=float(model.coef_[0, 0]),
                   intercept=float(model.intercept_[0]), scaler_mean=float(scaler.mean_[0]),
                   scaler_scale=float(scaler.scale_[0]), recal_pkl_sha256=sha(a.out / "recal.pkl"),
                   script_sha256=sha(__file__), inputs=used)
        (a.out / "RECAL_RECEIPT.json").write_text(json.dumps(rec, indent=1) + "\n")
        print(json.dumps({k: rec[k] for k in ("n_rows", "positives", "coef", "intercept", "recal_pkl_sha256")}))
    else:
        fitted = pickle.loads(a.recal.read_bytes())
        per_fire = {}
        for f in sorted(a.d4_dir.glob("*.npz")):
            z = dict(np.load(f, allow_pickle=False))
            x = logit(z.pop("p_d4_wind_rebuilt"), fitted["clip"])[:, None]
            q = fitted["model"].predict_proba(fitted["scaler"].transform(x))[:, 1].astype(np.float32)
            np.savez_compressed(a.out / f.name, **z, p_d4_wind_recal=q)
            per_fire[f.stem] = dict(cells=int(len(q)), sha256=sha(a.out / f.name))
        (a.out / "SCORE_PARTA_RECEIPT.json").write_text(json.dumps(dict(
            notice=NOTICE, names=["d4_wind_recal"], recal_sha256=sha(a.recal), d4_dir=str(a.d4_dir),
            script_sha256=sha(__file__), per_fire=per_fire), indent=1) + "\n")
        print(json.dumps(dict(fires=len(per_fire))))


if __name__ == "__main__":
    main()
