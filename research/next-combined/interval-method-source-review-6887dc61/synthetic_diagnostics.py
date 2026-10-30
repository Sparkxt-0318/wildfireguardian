"""Tiny invented pooled diagnostic controls, no actual study reads/imports."""
import json
from math import isclose, log
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score


BINS = np.linspace(0.0, 1.0, 11)
FLOOR = 1e-7


def auc_groups(fires, multiplicity):
    groups = {}
    for f, rows in enumerate(fires):
        for y, p in rows:
            a, b = groups.get(p, (0, 0))
            groups[p] = a + multiplicity[f] * y, b + multiplicity[f] * (1-y)
    positives = sum(a for a, _ in groups.values())
    negatives = sum(b for _, b in groups.values())
    if positives == 0 or negatives == 0:
        return None
    below = 0
    numerator = 0
    for p in sorted(groups):
        a, b = groups[p]
        numerator += a * (below + b / 2)
        below += b
    return numerator / (positives * negatives)


def scores_literal(rows):
    y, p = (np.array(v, dtype=float) for v in zip(*rows))
    index = np.clip(np.digitize(p, BINS[1:-1], right=False), 0, 9)
    ece = sum(abs(float(p[index == b].sum())-float(y[index == b].sum())) for b in range(10)) / len(y)
    clipped = np.clip(p, FLOOR, 1-FLOOR)
    return dict(brier=float(np.mean((p-y)**2)), ece=ece,
                clipped_nll=float(np.mean(-(y*np.log(clipped)+(1-y)*np.log1p(-clipped)))))


fires = [[(1, .1), (0, .1)], [(0, .9), (0, 0.), (0, 1.)],
         [(1, .3), (1, 1.)], [(1, 0.), (0, .9), (0, .3)]]
vectors = [(4,0,0,0),(0,4,0,0),(0,0,4,0),(0,0,0,4),(1,1,1,1),(2,0,2,0),(0,2,1,1)]
per_fire = []
for rows in fires:
    y, p = (np.array(v,dtype=float) for v in zip(*rows))
    index = np.clip(np.digitize(p,BINS[1:-1],right=False),0,9)
    q = np.clip(p,FLOOR,1-FLOOR)
    per_fire.append(dict(n=len(y), sse=float(((p-y)**2).sum()),
                         loss=float(-(y*np.log(q)+(1-y)*np.log1p(-q)).sum()),
                         bins=[(float(p[index == b].sum()),float(y[index == b].sum())) for b in range(10)]))
checks = []
flat = [row for fire in fires for row in fire]
y, p = (np.array(v,dtype=float) for v in zip(*flat))
for m in vectors:
    literal = [row for f, fire in enumerate(fires) for _ in range(m[f]) for row in fire]
    expected = scores_literal(literal)
    n = sum(k * f["n"] for k, f in zip(m,per_fire))
    pooled = dict(brier=sum(k*f["sse"] for k,f in zip(m,per_fire))/n,
                  clipped_nll=sum(k*f["loss"] for k,f in zip(m,per_fire))/n,
                  ece=sum(abs(sum(k*(f["bins"][b][0]-f["bins"][b][1]) for k,f in zip(m,per_fire)))
                          for b in range(10))/n)
    assert all(isclose(pooled[k],expected[k],rel_tol=0,abs_tol=3e-15) for k in pooled)
    value = auc_groups(fires,m)
    ly, lp = (np.array(v,dtype=float) for v in zip(*literal))
    if value is None:
        assert len(set(ly)) == 1
        auc_status = "UNAVAILABLE_ABSENT_CLASS"
    else:
        weights = np.array([m[f] for f,fire in enumerate(fires) for _ in fire])
        assert isclose(value,roc_auc_score(ly,lp),rel_tol=0,abs_tol=2e-15)
        assert isclose(value,roc_auc_score(y,p,sample_weight=weights),rel_tol=0,abs_tol=2e-15)
        auc_status = "PASS_LITERAL_AND_WEIGHTED_SKLEARN"
    checks.append(dict(multiplicity=m,status="PASS",auc=auc_status,
                       brier_ece_clipped_nll="PASS_POOLED_SUFFICIENT_STATISTICS_VS_LITERAL"))
assert np.digitize([0., .1, 1.],BINS[1:-1],right=False).tolist() == [0,1,9]
assert auc_groups([[(1,.5),(0,.5)]],(1,)) == .5
assert isclose(scores_literal([(1,0.)])["clipped_nll"],-log(FLOOR),rel_tol=0,abs_tol=1e-14)
out = dict(status="PASS",cohort_draw_checks=len(checks),checks=checks,
           boundary_controls=["ten_equal_width_bins_boundary_rule","AUC_exact_ties_half_credit","clipped_NLL_epsilon"],
           scope="Only ten invented entries over four invented fires; no actual data/models/outputs")
Path(__file__).with_name("SYNTHETIC_DIAGNOSTIC_CONTROLS.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(dict(status=out["status"],cohort_draw_checks=len(checks),boundary_controls=3)))
