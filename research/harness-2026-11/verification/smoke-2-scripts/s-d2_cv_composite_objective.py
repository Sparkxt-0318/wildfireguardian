import sys, json, numpy as np, scipy
from pathlib import Path
sys.path.insert(0, sys.argv[1]); import cv_part_a as C, real_bracket_fit as F
cv = json.load(open(sys.argv[2])); fold = 2
train = [f for f in sum(cv["folds"], []) if f not in cv["folds"][fold]]
fires = [F.load_fire(Path(sys.argv[3]) / f"{f}.npz", 240.0, 0) for f in train]
objs = [C._composite_objective(p, o) for p, o in fires]
def f(th):
    v = [o(np.asarray(th, float)) for o in objs]; return sum(x[0] for x in v), np.sum([x[1] for x in v], axis=0)
mine = json.load(open(sys.argv[4])); mine = np.asarray(mine.get("theta", mine), float)
comm = np.asarray(cv["thetas"]["2"]["composite"], float); x0 = np.full(len(comm), 0.02)
for name, th in (("pinned-env solution", mine), ("committed (floor) solution", comm), ("start x0=0.02", x0)):
    val, g = f(th); print(f"numpy {np.__version__} scipy {scipy.__version__} | {name:28s} objective {val:.6g}  |grad| {np.linalg.norm(g):.3g}  finite {np.isfinite(val)}")
