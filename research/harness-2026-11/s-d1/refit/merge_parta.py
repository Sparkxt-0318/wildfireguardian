"""Merge part-a producer directories into the sd9bench table (Victor 2026-11-12; entries.py contract): one
<fire>.npz per fire holding EVERY p_<name> on identical entries. IN-SAMPLE, DEVELOPMENT-ONLY.

Per fire: intersect entries on (t1, row, col) across all producers (the interval index is re-derived from the common
t1 list); assert y and dist_m identical on shared cells (fail otherwise); write interval, row, col, y, dist_m, t1,
hours, every p_<name>, meta_<name> (the notice, per predictor) and population="full_rectangle". Every output file must
carry the same set of p_ columns: a fire missing from any producer is dropped and logged. The receipt logs, per producer
and fire, the cells dropped by the intersection, and pins every input and output sha.

    python merge_parta.py --producers DIR1 DIR2 ... --out TABLE_DIR
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

NOTICE = "IN-SAMPLE, DEVELOPMENT-ONLY: part a is the refit training pool; scores from these files are fit statistics."


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def keys(z):
    t1 = z["t1"]
    return np.array([f"{t1[i]}|{r}|{c}" for i, r, c in zip(z["interval"], z["row"], z["col"])])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--producers", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    fires = [set(p.stem for p in d.glob("*.npz")) for d in a.producers]
    common_fires = sorted(set.intersection(*fires))
    log = dict(notice=NOTICE, producers=[str(d) for d in a.producers],
               producer_receipts={str(d): sha(d / "SCORE_PARTA_RECEIPT.json") for d in a.producers},
               fires_dropped_not_in_all={str(d): sorted(f - set(common_fires)) for d, f in zip(a.producers, fires)},
               per_fire={})
    for fire in common_fires:
        zs = [dict(np.load(d / f"{fire}.npz", allow_pickle=False)) for d in a.producers]
        ks = [keys(z) for z in zs]
        common = set(ks[0])
        for k in ks[1:]:
            common &= set(k)
        order = sorted(common, key=lambda s: (s.split("|")[0], int(s.split("|")[1]), int(s.split("|")[2])))
        pos = [{k: i for i, k in enumerate(kk)} for kk in ks]
        idx = [np.array([p[k] for k in order], dtype=np.int64) for p in pos]
        base = zs[0]
        y = base["y"][idx[0]]
        dist = base["dist_m"][idx[0]]
        for z, ii, d in zip(zs[1:], idx[1:], a.producers[1:]):
            if not np.array_equal(z["y"][ii], y) or not np.array_equal(z["dist_m"][ii], dist):
                raise SystemExit(f"y or dist_m differ on shared cells: {fire} ({d})")
        # Iris/Victor pin: recal columns may only appear on cells inside d4_wind_rebuilt's own producer support.
        has = [{k for k in z if k.startswith("p_")} for z in zs]
        recal_i = [i for i, h in enumerate(has) if h & {"p_d4_wind_recal", "p_d4_wind_recal_band"}]
        support_check = None
        if recal_i:
            d4_i = [i for i, h in enumerate(has) if "p_d4_wind_rebuilt" in h]
            if not d4_i:
                raise SystemExit(f"{fire}: recal present without the d4_wind_rebuilt producer")
            d4keys = set(ks[d4_i[0]])
            inside = sum(k in d4keys for k in order)
            if inside != len(order):
                raise SystemExit(f"{fire}: {len(order) - inside} merged cells outside d4_wind_rebuilt support")
            for i in recal_i:
                if set(ks[i]) != d4keys:
                    raise SystemExit(f"{fire}: recal producer entries differ from d4_wind_rebuilt entries")
            support_check = dict(merged_cells=len(order), inside_d4_support=inside, share=1.0)
        t1s = sorted({k.split("|")[0] for k in order})
        t1_index = {t: i for i, t in enumerate(t1s)}
        hours_by_t1 = {}
        for z in zs:
            for t, h in zip(z["t1"], z["hours"]):
                if hours_by_t1.setdefault(str(t), float(h)) != float(h):
                    raise SystemExit(f"hours differ for {fire} {t}")
        out = dict(interval=np.array([t1_index[k.split("|")[0]] for k in order], np.int64),
                   row=base["row"][idx[0]], col=base["col"][idx[0]], y=y, dist_m=dist,
                   t1=np.array(t1s), hours=np.array([hours_by_t1[t] for t in t1s]),
                   population=np.array("full_rectangle"))
        for z, ii in zip(zs, idx):
            for name in (k for k in z if k.startswith("p_")):
                if name in out:
                    raise SystemExit(f"duplicate predictor {name} in {fire}")
                out[name] = z[name][ii].astype(np.float32)
                out["meta_" + name[2:]] = np.array(json.dumps(dict(notice=NOTICE)))
        np.savez_compressed(a.out / f"{fire}.npz", **out)
        log["per_fire"][fire] = dict(shared_cells=len(order), positives=int(y.sum()),
                                     dropped_by_intersection={str(d): int(len(k) - len(order)) for d, k in zip(a.producers, ks)},
                                     recal_inside_d4_support=support_check,
                                     sha256=sha(a.out / f"{fire}.npz"))
    preds = {tuple(sorted(k for k in np.load(a.out / f"{f}.npz").files if k.startswith("p_"))) for f in common_fires}
    if len(preds) > 1:
        raise SystemExit("predictor sets differ across fires")
    log["predictors"] = list(next(iter(preds))) if preds else []
    (a.out / "MERGE_RECEIPT.json").write_text(json.dumps(log, indent=1) + "\n")
    print(json.dumps(dict(fires=len(common_fires), predictors=log["predictors"])))


if __name__ == "__main__":
    main()
