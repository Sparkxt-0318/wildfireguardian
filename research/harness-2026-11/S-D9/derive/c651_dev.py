"""DEVELOPMENT-ONLY (Iris experiment 2, orchestrator request): c651_mc against perimeter-trained models
on full-rectangle perimeter labels (cohort R, US2024, already exposed).

c651_mc was trained only on interior patches of final kriged footprints (A1 §4.1, prepare.py:862-883).
d4_wind_seed0 and the frozen logistic were trained on perimeter states. This script asks whether c651 is
worse off-footprint, using only committed forecast-v2 entry files plus dist_m from derive_dist.py.

Populations (all full-rectangle, A1 §4.1):
  full_domain    every scored entry
  band_4km       dist_m <= 4,000 m (A1 primary band)
  off_footprint  cells outside the fire's FINAL mapped union. These never burn (y = 0), so Brier = mean p^2.
                 The final union is (complement of the last interval's scored cells) | (its positives), as in
                 enclosure.py; the last interval is checked to have the latest cutoff.
  on_footprint   cells inside the final mapped union.
Paired differences are whole-fire bootstrap 95% intervals (10,000 draws, seed 20261030; 6 fires), computed
by sd9bench core() where positives exist, and by the same resampling of per-fire squared-error sums for
off_footprint.

c651_mc caveat (Owen): its marginals come from 1,024 trajectories, so p is a multiple of 1/1024 and many
are exact Monte Carlo zeros. Its tail is reported only against the 1/1024 floor; no decay slope is fitted.

  python c651_dev.py --dist DIR --heldout DIR --out C651_DEV.json
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

MODELS = ("c651_mc", "d4_wind_seed0", "logistic", "persistence")
REFS = ("persistence", "d4_wind_seed0", "logistic")
BAND_M, DRAWS, SEED, FLOOR = 4000.0, 10000, 20261030, 1.0 / 1024


def final_union(z, shape):
    t1 = [str(t) for t in z["t1"]]
    from datetime import datetime
    stamps = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in t1]
    last = max(range(len(stamps)), key=stamps.__getitem__)
    if last != int(z["interval"].max()):
        raise ValueError("last interval index is not the latest cutoff")
    m = z["interval"] == last
    union = np.ones(shape, bool)
    union[z["row"][m], z["col"][m]] = False
    pos = m & (z["y"] == 1)
    union[z["row"][pos], z["col"][pos]] = True
    return union


def tail(y, p):
    use = p < 1e-3
    zero = p == 0
    return dict(
        exact_zero_share=float(zero.mean()), exact_zero_positives=int(y[zero].sum()),
        positives_below_1_over_1024=int(y[p < FLOOR].sum()), share_of_positives_below_1_over_1024=float(y[p < FLOOR].sum() / y.sum()) if y.sum() else None,
        lowest_bin_0_1e3=dict(count=int(use.sum()), positives=int(y[use].sum()),
                              mean_p=float(p[use].mean()) if use.any() else None,
                              observed=float(y[use].mean()) if use.any() else None,
                              gap=float(abs(p[use].mean() - y[use].mean())) if use.any() else None))


def summarise(scored, y, preds):
    out = dict(entries=scored["entries"], positives=scored["positives"],
               pooled={k: {kk: v["pooled"][kk] for kk in ("brier", "average_precision", "positives_below_1_over_1024")}
                       for k, v in scored["models"].items()},
               paired={k: dict(point=v["point_difference"], interval=v["percentile_95_interval"],
                               fires_favouring_candidate=v["fires_favouring_candidate"],
                               per_fire=v["per_fire_difference"])
                       for k, v in scored["paired"].items() if k.split("__vs__")[0] != k.split("__vs__")[1]},
               tail={k: tail(y, preds[k]) for k in preds})
    return out


def off_footprint(per_fire):
    fires = sorted(per_fire)
    rng = np.random.default_rng(SEED)
    sampled = rng.integers(0, len(fires), size=(DRAWS, len(fires)))
    sq = {m: np.array([np.sum(per_fire[f][m] ** 2) for f in fires]) for m in MODELS}
    n = np.array([len(per_fire[f][MODELS[0]]) for f in fires], float)
    out = dict(entries=int(n.sum()), positives=0,
               pooled_brier={m: float(sq[m].sum() / n.sum()) for m in MODELS},
               mean_p={m: float(sum(per_fire[f][m].sum() for f in fires) / n.sum()) for m in MODELS},
               share_p_ge_0_01={m: float(sum((per_fire[f][m] >= 0.01).sum() for f in fires) / n.sum()) for m in MODELS},
               per_fire_brier={m: {f: float(sq[m][i] / n[i]) for i, f in enumerate(fires)} for m in MODELS},
               paired={})
    for a in MODELS:
        for b in REFS:
            if a == b:
                continue
            point = (sq[a].sum() - sq[b].sum()) / n.sum()
            boot = (sq[a][sampled].sum(1) - sq[b][sampled].sum(1)) / n[sampled].sum(1)
            out["paired"][f"{a}__vs__{b}"] = dict(point=float(point),
                                                  interval=np.quantile(boot, [.025, .975]).tolist(),
                                                  fires_favouring_candidate=int((sq[a] / n < sq[b] / n).sum()))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--heldout", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    shapes = {}
    for f in (args.heldout / "cases").glob("*.json"):
        c = json.loads(f.read_text())
        shapes.setdefault(c["case"]["event"], tuple(c["rectangle"]))
    cols = dict(fire=[], interval=[], hours=[], y=[], dist=[], onfp=[], **{m: [] for m in MODELS})
    off = {}
    for path in sorted(args.dist.glob("*.npz")):
        ev = path.stem
        with np.load(path, allow_pickle=False) as z:
            union = final_union(z, shapes[ev])
            on = union[z["row"], z["col"]]
            y = z["y"].astype(float)
            if y[~on].any():
                raise ValueError(f"{ev}: a positive lies outside the final union")
            cols["fire"].append(np.full(len(y), ev)); cols["interval"].append(z["interval"])
            cols["hours"].append(z["hours"][z["interval"]]); cols["y"].append(y)
            cols["dist"].append(z["dist_m"]); cols["onfp"].append(on)
            for m in MODELS:
                cols[m].append(z[f"p_{m}"].astype(float))
            off[ev] = {m: z[f"p_{m}"].astype(float)[~on] for m in MODELS}
    c = {k: np.concatenate(v) for k, v in cols.items()}
    preds = {m: c[m] for m in MODELS}
    all_e = Entries(fire=c["fire"], interval=c["interval"], hours=c["hours"], y=c["y"], predictions=preds,
                    population="full_rectangle")
    out = dict(label="DEVELOPMENT-ONLY on exposed cohort R (US2024, full-rectangle perimeter labels); not a confirmatory result",
               population="full_rectangle", draws=DRAWS, seed=SEED, mc_floor=FLOOR,
               c651_caveat="c651_mc marginals are multiples of 1/1024; exact zeros are Monte Carlo zeros; no decay slope fitted",
               decomposition_note=("on_footprint and off_footprint split cells by the FINAL mapped union, which is hindsight. "
                                   "They are a diagnostic decomposition of the full-rectangle score, not populations for a "
                                   "decision; on_footprint alone is hindsight-conditioned (A1 §4.1)."))
    for name, mask in (("full_domain", np.ones(len(c["y"]), bool)), ("band_4km", c["dist"] <= BAND_M),
                       ("on_footprint", c["onfp"])):
        sub = all_e.subset(mask)
        out[name] = summarise(core(sub, references=REFS, draws=DRAWS, seed=SEED), sub.y, sub.predictions)
    out["off_footprint"] = off_footprint(off)
    out["off_footprint_share_of_entries"] = float((~c["onfp"]).mean())
    out["band_4km_off_footprint_share"] = float((~c["onfp"][c["dist"] <= BAND_M]).mean())
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    for k in ("full_domain", "band_4km", "on_footprint"):
        print(k, out[k]["entries"], out[k]["positives"], json.dumps({m: round(v["brier"], 7) for m, v in out[k]["pooled"].items()}))
        for pk, pv in out[k]["paired"].items():
            if pk.startswith("c651") or pk == "d4_wind_seed0__vs__persistence":
                print("  ", pk, round(pv["point"], 7), [round(x, 7) for x in pv["interval"]], pv["fires_favouring_candidate"])
    o = out["off_footprint"]
    print("off_footprint", o["entries"], json.dumps({m: round(v, 7) for m, v in o["pooled_brier"].items()}))
    print("  mean_p", json.dumps({m: round(v, 6) for m, v in o["mean_p"].items()}), "p>=0.01", o["share_p_ge_0_01"])
    for pk, pv in o["paired"].items():
        print("  ", pk, round(pv["point"], 7), [round(x, 7) for x in pv["interval"]], pv["fires_favouring_candidate"])
    print("tail band", json.dumps(out["band_4km"]["tail"], indent=0))


if __name__ == "__main__":
    main()
