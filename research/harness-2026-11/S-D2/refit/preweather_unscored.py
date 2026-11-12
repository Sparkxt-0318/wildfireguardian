"""Pre-weather check for Victor: part-a new-burn cells that d2_bracket would NOT score, from perimeters alone.

Reproduces pipeline.perimeter_samples' interval and crop rules without weather:
- consecutive_intervals(times, 48 h) from wildfire.survival;
- score_mask = ~initial;
- crop to crop_box(initial) with pipeline MARGIN.

It does NOT apply Environment.available_at or kernel finiteness. Those need weather, and the post-weather count adds
them. Per interval, it counts:
- new = endpoint & ~initial, the latent arrivals d2_bracket samples (finding 1);
- unscored_in_crop = new & ~score_mask inside the crop. This is 0 by construction while score_mask = ~initial; it
  is reported as a check;
- outside_crop = new cells outside the crop. pipeline.cropped drops them entirely: they are neither latent nor
  scored, and they act as no sources.
Each states.npz is verified against PERIMETER_MANIFEST.json states_sha256 before use.

    python preweather_unscored.py --perimeters <parta_pool>/perimeters --out ../results/preweather_unscored.json

(pipeline layout: PERIMETER_MANIFEST.json beside the <id>/ directories, copied there from parta_pool/.)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from wildfire.survival import consecutive_intervals

REPO = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("pipeline", REPO / "research/forecast-v2/scripts/pipeline.py")
sys.path.insert(0, str(REPO / "research/forecast-v2/scripts"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--perimeters", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    man = json.loads((a.perimeters / "PERIMETER_MANIFEST.json").read_text())
    rows, totals = [], dict(intervals=0, new=0, unscored_in_crop=0, outside_crop=0)
    for ev in sorted(man["events"]):
        path = a.perimeters / ev / "states.npz"
        if hashlib.sha256(path.read_bytes()).hexdigest() != man["events"][ev]["states_sha256"]:
            raise ValueError(f"states sha mismatch: {ev}")
        d = np.load(path, allow_pickle=False)
        times = list(pd.to_datetime(d["times"], utc=True))
        states = d["states"].astype(bool)
        for i, j, hours in consecutive_intervals(times, 48.0):
            ini, end = states[i], states[j]
            new = end & ~ini
            r, c = P.crop_box(ini)
            inside = np.zeros_like(ini)
            inside[r, c] = True
            score = ~ini
            n_new = int(new.sum())
            u = int((new & inside & ~score).sum())
            o = int((new & ~inside).sum())
            rows.append(dict(event=ev, i=i, hours=hours, new=n_new, unscored_in_crop=u, outside_crop=o))
            totals["intervals"] += 1
            totals["new"] += n_new
            totals["unscored_in_crop"] += u
            totals["outside_crop"] += o
    df = pd.DataFrame(rows)
    per_int = (df.outside_crop / df.new.where(df.new > 0)).dropna()
    out = dict(command="python preweather_unscored.py " + " ".join(argv or sys.argv[1:]),
               manifest_sha256=hashlib.sha256((a.perimeters / "PERIMETER_MANIFEST.json").read_bytes()).hexdigest(),
               margin=P.MARGIN, events=len(man["events"]), totals=totals,
               share_outside_crop=totals["outside_crop"] / max(totals["new"], 1),
               share_unscored_in_crop=totals["unscored_in_crop"] / max(totals["new"], 1),
               intervals_with_any_outside=int((df.outside_crop > 0).sum()),
               per_interval_outside_share_median=float(per_int.median()) if len(per_int) else None,
               per_interval_outside_share_p90=float(per_int.quantile(0.9)) if len(per_int) else None,
               note="pre-weather: Environment.available_at and kernel finiteness not applied")
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
