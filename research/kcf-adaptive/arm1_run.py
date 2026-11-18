"""Arm 1 runner: adapt and predict every window of one or more fires (PROTOCOL.md 2.3, 2.7).

Modes:
  real      the method
  scramble  L2: for each target window, everything at or after its issue time is replaced before the
            method runs (target and later labels, later cut-off states, later environment snapshots)
  --leak    L3 positive control: the target window is added to its own history (LEAKY, NOT A RESULT)

    python arm1_run.py --env ENVDIR --set P4 --mode real --out WORK/arm1/P4_real [--fires ...] [--leak]
"""
import argparse
import copy
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

import tta
from cases import history_for, load_windows


class EnvStore:
    """Cut-off-hour environment snapshots [19, H, W] built by build_env.py: ENVDIR/<event>.npz."""

    def __init__(self, root: Path):
        self.root, self._z = Path(root), {}

    def at(self, event: str, hour: pd.Timestamp) -> np.ndarray:
        if event not in self._z:
            z = np.load(self.root / f"{event}.npz", allow_pickle=False)
            self._z[event] = ({str(h): i for i, h in enumerate(z["hours"])}, z["env"])
        idx, env = self._z[event]
        return env[idx[pd.Timestamp(hour).isoformat()]]


def scrambled_fire(ws, target, rng):
    """Copy of the fire's windows with everything at or after the target's issue time replaced."""
    out = []
    for w in ws:
        v = copy.copy(w)
        if w.endpoint > target.cutoff:                       # outcome not yet known at the issue time
            v.y = rng.integers(0, 2, size=len(w.y)).astype(np.int8)
        if w.cutoff > target.cutoff:                         # a later window: its state is in the future too
            n = len(w.row)
            flat = rng.choice(w.shape[0] * w.shape[1], size=n, replace=False)
            v.row, v.col = np.divmod(np.sort(flat), w.shape[1])
            v.case_id = w.case_id + "_scr"
        out.append(v)
    return out, out[[w.case_id for w in ws].index(target.case_id)]


def run_fire(event, ws, model, which, mode, leak, env, seed):
    rows, out = [], {}
    noise = np.random.default_rng(seed + 1)
    for i, w in enumerate(ws):
        t0 = time.time()
        fire, target = ws, w
        if mode == "scramble":
            fire, target = scrambled_fire(ws, w, np.random.default_rng([seed, i]))
        hid_cache = {}

        def hidden_of(v, T=w.cutoff):
            if v.case_id not in hid_cache:
                e = env.at(v.event, v.weather_hour)
                if mode == "scramble" and v.weather_hour > T:
                    e = noise.normal(size=e.shape).astype(e.dtype)      # weather after the issue time: noise
                    e[5:] = 0; e[5] = 1                                  # keep a valid one-hot biome
                hid_cache[v.case_id] = model.hidden(e)
            return hid_cache[v.case_id]

        hist = history_for(fire, target, _leak_target=leak)
        theta = tta.adapt(model, which, hist, hidden_of)
        p = tta.predict(model, theta, target, hidden_of)
        vec = tta.theta_vector(theta, which)
        out[f"p_{w.case_id}"] = p
        out[f"theta_{w.case_id}"] = vec
        rows.append(dict(event=event, case_id=w.case_id, cutoff=str(w.cutoff), hours=w.hours,
                         history=len(hist) - int(leak), seconds=time.time() - t0,
                         **{f"dmix{k}": float(vec[j]) for j, k in enumerate((3, 5, 7, 9))},
                         theta_norm=float(np.linalg.norm(vec))))
        print(f"{event} {i + 1}/{len(ws)} hist {len(hist)} {rows[-1]['seconds']:.1f}s dmix {np.round(vec[:4], 3)}", flush=True)
    return rows, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, type=Path)
    ap.add_argument("--set", required=True, choices=tta.SETS)
    ap.add_argument("--mode", required=True, choices=("real", "scramble"))
    ap.add_argument("--leak", action="store_true")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--fires", nargs="*")
    ap.add_argument("--seed", type=int, default=20261118)
    ap.add_argument("--penalty", type=float, default=tta.PENALTY, help="frozen value 0.01; others are sensitivity runs")
    a = ap.parse_args()
    torch.set_num_threads(1)
    tta.PENALTY = a.penalty
    a.out.mkdir(parents=True, exist_ok=True)
    fires = load_windows()
    model = tta.C651Model()
    env = EnvStore(a.env)
    for event, ws in fires.items():
        if a.fires and event not in a.fires:
            continue
        if (a.out / f"{event}.npz").exists():
            continue
        rows, out = run_fire(event, ws, model, a.set, a.mode, a.leak, env, a.seed)
        np.savez_compressed(a.out / f"{event}.npz", **out)
        pd.DataFrame(rows).to_csv(a.out / f"{event}.csv", index=False)


if __name__ == "__main__":
    main()
