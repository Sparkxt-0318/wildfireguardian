"""Pinned (E3) vs unpinned (E1) side by side for every pooled number of the part-a fire-level CV.

Reads results/cv_part_a{,_pinned}.json and results/cv_baselines{,_pinned}.json and the
check_bounds verdicts; writes results/cv_pinned_vs_unpinned.json and .md.
Reporting only: no fitting, no randomness.  The E1 composite is INVALID (collapsed to the
1e-9 floor in folds 0,2,3,4) and is shown struck, for the record only.
Caveats on every number: covariate-free, homogeneous, 25 part-a fires incl. 4 H-dev, not the neural refit.
"""
import json
from pathlib import Path

R = Path("results")
cvU, cvP = (json.loads((R / f).read_text()) for f in ("cv_part_a.json", "cv_part_a_pinned.json"))
bU, bP = (json.loads((R / f).read_text()) for f in ("cv_baselines.json", "cv_baselines_pinned.json"))
cbP = json.loads((R / "check_bounds_pinned.json").read_text())["results"]
INVALID_E1 = {"composite"}

rows = []
def add(section, name, u, p, model=None):
    rows.append(dict(section=section, quantity=name, unpinned=u, pinned=p,
                     delta=None if (u is None or p is None) else p - u,
                     e1_invalid=model in INVALID_E1))

for m in cvP["pooled"]:
    for key in ("brier", "pred_area", "lowbin_gap", "lowbin_n", "pos_below_1e5", "pos_below_1_1024"):
        add("cv_part_a pooled", f"{m}.{key}", cvU["pooled"][m][key], cvP["pooled"][m][key], m)
    for band, v in cvP["pooled"][m]["profile"].items():
        add("cv_part_a pooled", f"{m}.pred_{band}", cvU["pooled"][m]["profile"][band]["pred"], v["pred"], m)
for c, v in cvP["brier_diff_vs_mcem"].items():
    m = c.split("_minus_")[1]
    u = cvU["brier_diff_vs_mcem"][c]
    add("brier_diff_vs_mcem", f"{c}.point", u["point"], v["point"], m)
    add("brier_diff_vs_mcem", f"{c}.ci95_lo", u["ci95"][0], v["ci95"][0], m)
    add("brier_diff_vs_mcem", f"{c}.ci95_hi", u["ci95"][1], v["ci95"][1], m)
    rows.append(dict(section="brier_diff_vs_mcem", quantity=f"{c}.mcem_better_fires", unpinned=u["mcem_better_fires"],
                pinned=v["mcem_better_fires"], delta=None, e1_invalid=m in INVALID_E1))
for m in bP["pooled"]:
    for key, val in bP["pooled"][m].items():
        if key.startswith("brier"):
            add("baselines pooled", f"{m}.{key}", bU["pooled"][m][key], val, m)
for c, v in bP["paired"].items():
    ms = set(c.split("_minus_"))
    u = bU["paired"].get(c)
    inv = bool(ms & INVALID_E1)
    if u is None:
        continue
    add("baselines paired", f"{c}.point", u["point"], v["point"]); rows[-1]["e1_invalid"] = inv
    add("baselines paired", f"{c}.ci95_lo", u["ci95"][0], v["ci95"][0]); rows[-1]["e1_invalid"] = inv
    add("baselines paired", f"{c}.ci95_hi", u["ci95"][1], v["ci95"][1]); rows[-1]["e1_invalid"] = inv
    bf = [k for k in v if k.endswith("fires")]
    for k in bf:
        rows.append(dict(section="baselines paired", quantity=f"{c}.{k}", unpinned=u[k], pinned=v[k], delta=None, e1_invalid=inv))

out = dict(env_unpinned=cvU.get("env", "E1: Python 3.13.18, numpy 2.1.3, scipy 1.14.1, pandas 2.2.3 (not recorded in file)"),
           env_pinned=cvP["env"], check_bounds_pinned={f: {e: x["verdict"] for e, x in v.items()} for f, v in cbP.items()},
           caveats="covariate-free, homogeneous, 25 part-a fires incl. 4 H-dev, not the neural refit",
           rows=rows)
(R / "cv_pinned_vs_unpinned.json").write_text(json.dumps(out, indent=1, default=str))

def fmt(x):
    if isinstance(x, float):
        return f"{x:.6g}"
    return str(x)
md = ["# Part-a fire-level CV: pinned (E3) vs unpinned (E1), every pooled number", "",
      "Caveats: covariate-free, homogeneous, 25 part-a fires incl. 4 H-dev, not the neural refit.",
      f"Pinned env: {cvP['env']}", "E1 composite is INVALID (floor collapse); its rows are struck and kept for the record only.",
      "check_bounds (pinned): " + "; ".join(f"fold {f}: " + ", ".join(f"{e} {x['verdict']}" for e, x in v.items()) for f, v in cbP.items()), ""]
sec = None
for r in rows:
    if r["section"] != sec:
        sec = r["section"]
        md += ["", f"## {sec}", "", "| quantity | unpinned E1 | pinned E3 | pinned − unpinned |", "|---|---|---|---|"]
    u = fmt(r["unpinned"]); u = f"~~{u}~~ (INVALID)" if r["e1_invalid"] else u
    md.append(f"| {r['quantity']} | {u} | {fmt(r['pinned'])} | {fmt(r['delta']) if r['delta'] is not None else ''} |")
(R / "cv_pinned_vs_unpinned.md").write_text("\n".join(md) + "\n")
print(f"{len(rows)} rows")
