import json, numpy as np
d = json.load(open(__import__("sys").argv[1])); pf = d["per_fire"]; names = ["plugin", "composite", "meanfield_nll", "mcem"]
fl = list(pf)
print("fires", len(fl), "| folds cover", sorted(sum(d["folds"], [])) == sorted(fl))
for n in names:
    c = sum(pf[f][n]["cells"] for f in fl); b = sum(pf[f][n]["brier"] * pf[f][n]["cells"] for f in fl) / c
    bel = sum(pf[f][n]["pos_below_1_1024"] for f in fl)
    prof = {k: round(sum(pf[f][n]["profile"][k]["pred"] for f in fl), 1) for k in ("0-1km", "1-2km", "2-4km")}
    obs = {k: sum(pf[f][n]["profile"][k]["obs"] for f in fl) for k in ("0-1km", "1-2km", "2-4km")}
    P = d["pooled"][n]
    print(f"{n:14s} brier {b:.10f} (json {P['brier']:.10f}) cells {c} below1/1024 {bel} (json {P['pos_below_1_1024']}) pred {prof} obs {obs}")
# bootstrap: same scheme, independent code; fires in per_fire key order (as in the script)
rng = np.random.default_rng(20261030); draws = rng  # sequential per comparison as in the script
for n in ("plugin", "composite", "meanfield_nll"):
    se = np.array([pf[f][n]["brier"] * pf[f][n]["cells"] for f in fl]); sm = np.array([pf[f]["mcem"]["brier"] * pf[f]["mcem"]["cells"] for f in fl])
    nc = np.array([pf[f]["mcem"]["cells"] for f in fl]); idx = rng.integers(0, len(fl), (10000, len(fl)))
    v = (sm[idx].sum(1) - se[idx].sum(1)) / nc[idx].sum(1)
    j = d["brier_diff_vs_mcem"][f"mcem_minus_{n}"]
    print(f"mcem-{n}: point {(sm.sum()-se.sum())/nc.sum():+.6f} ci [{np.percentile(v,2.5):+.6f}, {np.percentile(v,97.5):+.6f}] better {sum(pf[f]['mcem']['brier'] < pf[f][n]['brier'] for f in fl)}/25 | json {j}")
