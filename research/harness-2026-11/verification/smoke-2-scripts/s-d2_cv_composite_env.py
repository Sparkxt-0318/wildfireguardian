import sys, json, numpy as np, scipy
from pathlib import Path
sys.path.insert(0, sys.argv[1]); import cv_part_a as C, real_bracket_fit as F
cv = json.load(open(sys.argv[2])); fold = int(sys.argv[3])
train = [f for f in sum(cv["folds"], []) if f not in cv["folds"][fold]]
fires = [F.load_fire(Path(sys.argv[4]) / f"{f}.npz", 240.0, 0) for f in train]
th = C.fit_composite(fires)
print("numpy", np.__version__, "scipy", scipy.__version__, "| fold", fold, "composite sum", float(np.sum(th)), "k0", float(th[0]))
