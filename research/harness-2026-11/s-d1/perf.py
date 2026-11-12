"""Per-trajectory wall time and peak RSS: first-passage sampler vs the real hourly rollout.

The hourly arm runs the forecast's own ``wildfire.rollout.simulate`` (torch, CPU) with a stub
predictor that applies a fixed kernel field through ``wildfire.models.new_burn_probability``,
so only the environment->kernel network is skipped (identical for both arms, done once).
Each arm runs in a fresh subprocess; peak RSS is ru_maxrss of that process (includes the
interpreter, numpy/numba/torch imports), and an import-only baseline is reported too.

    python research/harness-2026-11/s-d1/perf.py [--n 2000] [--regime R3_heterogeneous9_static_wind]
"""
import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def arm(name, n, regime, batch):
    import numpy as np
    sys.path.insert(0, str(HERE))
    from gate1 import SIZE, regimes
    spec = regimes()[regime]
    K, T = spec["K"][:1], spec["T"]  # static kernels (first segment) for both arms
    init = np.zeros((SIZE, SIZE), bool)
    init[19:22, 19:22] = True
    hours = [float(T)]
    if name == "baseline_imports":
        import torch  # noqa: F401
        from fpp import first_passage  # noqa: F401
        sys.path.insert(0, str(REPO / "forecast"))
        import wildfire.rollout  # noqa: F401
        return dict(seconds=0.0)
    if name == "fpp":
        import torch  # noqa: F401  (same imports as the other arm)
        from fpp import first_passage
        first_passage(K[:, :, :8, :8], init[16:24, 16:24], [1.0], n_samples=2, seed=0)  # JIT/cache load
        t0 = time.perf_counter()
        c, _ = first_passage(K, init, hours, n_samples=n, seed=1)
        sec = time.perf_counter() - t0
        return dict(seconds=sec, mean_new=float(c[0].sum() / n))
    if name == "hourly_rollout":
        import torch
        torch.set_num_threads(1)
        sys.path.insert(0, str(REPO / "forecast"))
        from wildfire.models import new_burn_probability
        from wildfire.rollout import simulate
        kern = torch.tensor(K[0], dtype=torch.float32)

        class Stub(torch.nn.Module):
            channel_names = ("x",)

            def forward(self, states, environment, *, channel_names, burned_area_valid,
                        feature_valid, dt_hours, boundary):
                return new_burn_probability(states, kern.expand(states.shape[0], -1, -1, -1),
                                            dt_hours=dt_hours, burned_area_valid=burned_area_valid,
                                            boundary=boundary)

        b = torch.tensor(init, dtype=torch.float32)[None]
        env = torch.zeros((1, SIZE, SIZE))
        args = dict(channel_names=("x",), burned_area_valid=torch.ones_like(b, dtype=torch.bool),
                    feature_valid=torch.ones_like(env, dtype=torch.bool), hours=hours,
                    n_samples=n, seed=1, trajectory_batch_size=batch, boundary="zero")
        t0 = time.perf_counter()
        out = simulate(Stub(), b, env, **args)
        sec = time.perf_counter() - t0
        p = out[0]["details"].probability
        return dict(seconds=sec, mean_new=float(torch.nan_to_num(p).sum()))
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--regime", default="R3_heterogeneous9_static_wind")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--child", default=None)
    args = ap.parse_args()
    if args.child:
        res = arm(args.child, args.n, args.regime, args.batch)
        res["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print(json.dumps(res))
        return
    out = dict(n=args.n, regime=args.regime, trajectory_batch_size=args.batch,
               threads="numba single thread; torch.set_num_threads(1)", arms={})
    for name in ("baseline_imports", "fpp", "hourly_rollout"):
        r = subprocess.run([sys.executable, __file__, "--child", name, "--n", str(args.n),
                            "--regime", args.regime, "--batch", str(args.batch)],
                           capture_output=True, text=True, check=True)
        res = json.loads(r.stdout.strip().splitlines()[-1])
        res["ms_per_trajectory"] = 1000 * res["seconds"] / args.n
        out["arms"][name] = res
        print(name, res, flush=True)
    (HERE / f"RESULTS_perf_{args.regime}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
