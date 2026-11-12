"""d4_wind_recal (A1 §3): a one-feature logistic recalibration of d4_wind_rebuilt, fit IN-SAMPLE on the §3.1 training
data (fit-23 + part a) from d4_wind_rebuilt's own predictions there; frozen by SHA before part c opens.
THE FIT IS HELD until the ruling is pinned in #155. Details as proposed by Victor (a)-(d), accepted by Iris with five
implementation points; identical to S-D9 derive/logistic_dev.py on Main:
  (a) negative subsample 0.05, weight 1/0.05 = 20: ONE uniform per training entry (positives included),
      keep = (y == 1) | (rng.random(N) < 0.05), rng = np.random.default_rng(0), drawn ONCE over all entries
      concatenated by fire id (string sort), then interval index, then row-major cell order (the producer files'
      order). The entry count N and sha256 of the concatenated y bytes are recorded BEFORE the draw.
  (b) training entries: the full-rectangle producer files of score_parta.py, not band-limited, all §3.1 intervals.
      [Crop: see --crop; the reading of "crop as in training" is pending Victor's answer; default none.]
  (c) p cast to float64, then clipped to [1e-6, 1 - 1e-6] before the logit; the same clip at prediction.
  (d) StandardScaler fit UNWEIGHTED on the kept subsample; LogisticRegression(C=1.0, max_iter=2000, random_state=0)
      fit on the kept subsample with sample_weight (1 for positives, 20 for kept negatives).
The coefficient file (scaler mean/scale, slope, intercept) and its sha256 are committed before any refit output is
used and before any part-c access; numpy and sklearn versions are pinned in the receipt.

    fit:    python recal_parta.py fit   --d4-dir D4_PRODUCER --events TRAIN_EVENTS_final.txt --out RECAL_DIR
    apply:  python recal_parta.py apply --recal RECAL_DIR/recal.pkl --d4-dir D4_PRODUCER --out PRODUCER_DIR
On the part-a development table it is IN-SAMPLE TWICE OVER (the refit and the recal both saw these fires).
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
    return np.log(p / (1 - p))  # same expression as S-D9 derive/logistic_dev.py


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
    ap.add_argument("--crop", choices=("none", "training"), default="none")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "fit":
        import sklearn
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        if a.crop != "none":
            raise SystemExit("crop reading not yet ruled; only --crop none is implemented")
        events = sorted({e.strip() for e in a.events.read_text().splitlines() if e.strip()})  # fire id string sort
        xs, ys, used = [], [], []
        for ev in events:
            f = a.d4_dir / f"{ev}.npz"
            if not f.exists():
                used.append(dict(event=ev, missing=True))
                continue
            z = np.load(f, allow_pickle=False)
            order = np.lexsort((z["col"], z["row"], z["interval"]))  # interval, then row-major cell
            y = z["y"][order].astype(np.int64)
            xs.append(logit(z["p_d4_wind_rebuilt"][order], a.clip))
            ys.append(y)
            used.append(dict(event=ev, sha256=sha(f), cells=int(len(y)), already_sorted=bool(np.all(order == np.arange(len(order))))))
        x, y = np.concatenate(xs)[:, None], np.concatenate(ys)
        pre = dict(N=int(len(y)), positives=int(y.sum()), y_sha256=hashlib.sha256(y.astype(np.int8).tobytes()).hexdigest())
        rng = np.random.default_rng(a.seed)
        keep = (y == 1) | (rng.random(len(y)) < a.negative_fraction)
        xk, yk = x[keep], y[keep]
        w = np.where(yk == 1, 1.0, 1.0 / a.negative_fraction)
        scaler = StandardScaler().fit(xk)
        model = LogisticRegression(C=1.0, max_iter=2000, random_state=a.seed).fit(scaler.transform(xk), yk, sample_weight=w)
        (a.out / "recal.pkl").write_bytes(pickle.dumps(dict(scaler=scaler, model=model, clip=a.clip)))
        coef = dict(scaler_mean=float(scaler.mean_[0]), scaler_scale=float(scaler.scale_[0]),
                    slope=float(model.coef_[0, 0]), intercept=float(model.intercept_[0]), clip=a.clip)
        (a.out / "RECAL_COEFFICIENTS.json").write_text(json.dumps(coef, indent=1) + "\n")
        rec = dict(notice=NOTICE, rule="A1 §3 d4_wind_recal; Victor (a)-(d), Iris points 1-5; pinned in #155",
                   negative_fraction=a.negative_fraction, clip=a.clip, seed=a.seed, crop=a.crop,
                   events_sha256=sha(a.events), before_draw=pre, kept=int(keep.sum()), kept_positives=int(yk.sum()),
                   coefficients=coef, coefficients_sha256=sha(a.out / "RECAL_COEFFICIENTS.json"),
                   recal_pkl_sha256=sha(a.out / "recal.pkl"), script_sha256=sha(__file__),
                   versions=dict(numpy=np.__version__, sklearn=sklearn.__version__), inputs=used)
        (a.out / "RECAL_RECEIPT.json").write_text(json.dumps(rec, indent=1) + "\n")
        print(json.dumps(dict(before_draw=pre, kept=rec["kept"], coefficients=coef)))
    else:
        fitted = pickle.loads(a.recal.read_bytes())
        per_fire = {}
        for f in sorted(a.d4_dir.glob("*.npz")):
            z = dict(np.load(f, allow_pickle=False))
            x = logit(z.pop("p_d4_wind_rebuilt"), fitted["clip"])[:, None]  # float64 cast, same clip
            q = fitted["model"].predict_proba(fitted["scaler"].transform(x))[:, 1].astype(np.float32)
            np.savez_compressed(a.out / f.name, **z, p_d4_wind_recal=q)
            per_fire[f.stem] = dict(cells=int(len(q)), sha256=sha(a.out / f.name))
        (a.out / "SCORE_PARTA_RECEIPT.json").write_text(json.dumps(dict(
            notice=NOTICE, names=["d4_wind_recal"], recal_sha256=sha(a.recal), d4_dir=str(a.d4_dir),
            script_sha256=sha(__file__), per_fire=per_fire), indent=1) + "\n")
        print(json.dumps(dict(fires=len(per_fire))))


if __name__ == "__main__":
    main()
