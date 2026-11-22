import json, sys, numpy as np
sys.path.insert(0, sys.argv[1]); import cv_part_a as C
fold = int(sys.argv[2]); r = json.load(open(sys.argv[3])); cv = json.load(open(sys.argv[4]))
th_mine, th_c = r["thetas"], cv["thetas"][str(fold)]
print("fold", fold, "test", r["test"] == cv["folds"][fold], "| sims/hours", r["sims"], r["hours"])
for n in th_mine: print(f"  theta {n:14s} max|d| {np.max(np.abs(np.array(th_mine[n]) - np.array(th_c[n]))):.3g}")
bad = 0
for f in r["test"]:
    for n in ("plugin", "composite", "meanfield_nll", "mcem"):
        m = C.metrics(np.array(r["per_fire"][f][n]["p"]), np.array(r["per_fire"][f][n]["y"]), np.array(r["per_fire"][f][n]["dist"]))
        c = cv["per_fire"][f][n]
        same = m == c
        if not same:
            bad += 1; diff = {k: (m[k], c[k]) for k in m if m[k] != c[k]}; print("  DIFF", f, n, str(diff)[:300])
print("  per-fire metric blocks differing:", bad, "of", 4 * len(r["test"]))
