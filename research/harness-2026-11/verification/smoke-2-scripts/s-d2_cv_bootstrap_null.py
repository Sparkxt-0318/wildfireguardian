import json, numpy as np
d = json.load(open(__import__("sys").argv[1])); pf = d["per_fire"]; fl = list(pf)
rng = np.random.default_rng(7)
for n in ("plugin", "meanfield_nll", "composite"):
    diff = np.array([(pf[f]["mcem"]["brier"] - pf[f][n]["brier"]) * pf[f]["mcem"]["cells"] for f in fl])
    nc = np.array([pf[f]["mcem"]["cells"] for f in fl], float)
    rej = 0; R = 1000
    for _ in range(R):   # exchangeability null: each fire's paired difference sign-flipped at random
        dd = diff * rng.choice([-1.0, 1.0], len(fl))
        idx = rng.integers(0, len(fl), (2000, len(fl)))
        v = dd[idx].sum(1) / nc[idx].sum(1)
        lo, hi = np.percentile(v, [2.5, 97.5]); rej += (lo > 0) or (hi < 0)
    # sign-flip randomisation test p for the observed pooled difference
    obs = diff.sum() / nc.sum(); null = np.array([(diff * rng.choice([-1.0, 1.0], len(fl))).sum() / nc.sum() for _ in range(20000)])
    print(f"mcem-{n}: bootstrap CI excludes 0 under null in {rej/R:.3f} of {R} (nominal 0.05); sign-flip p (two-sided) = {np.mean(np.abs(null) >= abs(obs)):.4f}")
