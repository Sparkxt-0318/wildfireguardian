"""Environment-free baselines on the real NIROPS intervals (public data only).

Phase ``choose``: score dilation(k) for k in {1, 2, 4, 8} h per cell on the
full rectangles of the 2020 to 2022 fit fires and record the best k
(``dilation_choice.json``). Phase ``heldout``: score persistence and every
dilation on the held-out 2024 intervals, pooled, per fire and fire-paired.

Cells: every cell of the event rectangle outside the initial union (the
model-validity intersection used for the final comparison is applied later
and can only remove cells). Nothing here reads environmental data.

Usage: python research/forecast-v2/scripts/public_baselines.py {choose,heldout} --perimeters DIR --out DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "forecast"))
from wildfire import baselines as B  # noqa: E402
from wildfire.survival import consecutive_intervals  # noqa: E402

SPLIT = json.loads((HERE.parents[1] / "SPLIT.json").read_text())


def entries(perimeters: Path, events):
    fire, y, preds = [], [], {}
    for event in events:
        data = np.load(perimeters / event / "states.npz")
        times = list(pd.to_datetime(data["times"], utc=True))
        states = data["states"].astype(bool)
        for i, j, hours in consecutive_intervals(times, 48.0):
            cells = ~states[i]
            fire.append(np.full(int(cells.sum()), event))
            y.append(states[j][cells].astype(np.float64))
            preds.setdefault("persistence", []).append(np.zeros(int(cells.sum())))
            for k in B.DILATION_HOURS:
                preds.setdefault(f"dilation_{k}h", []).append(B.dilation(states[i], hours, k)[cells])
    return dict(fire=np.concatenate(fire), y=np.concatenate(y),
                predictions={k: np.concatenate(v) for k, v in preds.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["choose", "heldout"])
    parser.add_argument("--perimeters", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--choice", type=Path, default=None)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.phase == "choose":
        events = SPLIT["fit"]["us_perimeter_and_kriged"]
        data = entries(args.perimeters, events)
        scores = {k: float(np.mean((data["predictions"][f"dilation_{k}h"] - data["y"]) ** 2)) for k in B.DILATION_HOURS}
        choice = B.choose_dilation(scores)
        (args.out / "dilation_choice.json").write_text(json.dumps(dict(
            training_pooled_brier_full_rectangles=scores, best_hours_per_cell=choice, fit_events=events,
            entries=int(len(data["y"])), positives=int(data["y"].sum()),
            persistence_brier=float(np.mean(data["y"] ** 2)),
            note="chosen on the 2020 to 2022 fit fires only, full rectangles, intervals <= 48 h; no held-out data read"),
            indent=1) + "\n")
        print(json.dumps(dict(best=choice, scores=scores)))
        return
    choice = json.loads(args.choice.read_text())["best_hours_per_cell"]
    data = entries(args.perimeters, SPLIT["held_out"]["us_2024"])
    data["predictions"]["dilation_best"] = data["predictions"][f"dilation_{choice}h"]
    result = B.score_entries(data)
    result["best_hours_per_cell"] = choice
    result["scope"] = ("environment-free baselines on all initially unburned rectangle cells of the held-out 2024 "
                       "intervals; the final comparison uses the subset valid for every model")
    (args.out / "public_baselines_heldout.json").write_text(json.dumps(result, indent=1) + "\n")
    rows = []
    for model, record in result["models"].items():
        for fire, s in record["per_fire"].items():
            rows.append(dict(model=model, fire=fire, entries=s["entries"], positives=s["positives"],
                             brier=s["brier"], bss_vs_persistence=s["bss_vs_persistence"],
                             average_precision=s["average_precision"]))
    pd.DataFrame(rows).to_csv(args.out / "public_baselines_per_fire.csv", index=False)
    print(json.dumps({m: r["pooled"]["brier"] for m, r in result["models"].items()}))


if __name__ == "__main__":
    main()
