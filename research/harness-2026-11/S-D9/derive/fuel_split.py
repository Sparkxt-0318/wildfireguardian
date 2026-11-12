"""DEVELOPMENT-ONLY (Iris part a): are d4's tail positives on non-burnable fuel?

Uses Daniel's rebuilt US2024 static layers (daniel/data-fetch 7d430806, us2024_static/*_static.npz, on the
forecast-v2 rectangles). FBFM40 codes 91-99 (urban, snow/ice, agriculture, water, barren) are non-burnable.
Positives in the 4 km band are split into tail (d4 p < 1e-5) and non-tail; for each group the script reports
the non-burnable share, the share of each FBFM40 group, and the share with all static layers valid.
NOTE: these are rebuilt layers. Slope and tree cover differ in bytes from the archive (A1 item 14);
FBFM40 comes from LANDFIRE 2016, as in the archive build.
  python fuel_split.py --dist DIR --static DIR --out FUEL_SPLIT.json
"""
import argparse
import json
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--dist", required=True, type=Path)
ap.add_argument("--static", required=True, type=Path)
ap.add_argument("--out", required=True, type=Path)
a = ap.parse_args()
groups = {"tail": [], "nontail": []}
per_fire = {}
valid = {"tail": [], "nontail": []}
for path in sorted(a.dist.glob("*.npz")):
    z = np.load(path, allow_pickle=False)
    s = np.load(a.static / f"{path.stem}_static.npz", allow_pickle=False)
    fb = s["fbfm40"]
    allv = s["all_static_valid"]
    m = (z["y"] == 1) & (z["dist_m"] <= 4000)
    r, c, p = z["row"][m], z["col"][m], z["p_d4_wind_seed0"][m]
    per_fire[path.stem] = {}
    for name, use in (("tail", p < 1e-5), ("nontail", p >= 1e-5)):
        groups[name].append(fb[r[use], c[use]])
        codes = fb[r[use], c[use]]
        per_fire[path.stem][name] = dict(positives=int(codes.size),
                                         nonburnable=int(((codes >= 91) & (codes <= 99)).sum()))
        valid[name].append(allv[r[use], c[use]])


def fam(code):
    code = int(code)
    if 91 <= code <= 99:
        return "nonburnable_9x"
    return {10: "grass_10x", 12: "grass_shrub_12x", 14: "shrub_14x", 16: "timber_understory_16x",
            18: "timber_litter_18x", 20: "slash_20x"}.get(code // 10, f"other_{code}")


out = dict(label="DEVELOPMENT-ONLY on exposed cohort R, 4 km band, rebuilt static layers (daniel/data-fetch 7d430806)")
for name in groups:
    codes = np.concatenate(groups[name])
    v = np.concatenate(valid[name])
    fams = [fam(x) for x in codes]
    uniq = sorted(set(fams))
    out[name] = dict(positives=int(codes.size),
                     nonburnable_share=float(np.mean([f == "nonburnable_9x" for f in fams])),
                     all_static_valid_share=float(v.mean()),
                     family_shares={u: float(np.mean([f == u for f in fams])) for u in uniq},
                     top_codes={int(k): int(n) for k, n in zip(*np.unique(codes, return_counts=True))})
out["per_fire"] = per_fire
a.out.write_text(json.dumps(out, indent=1) + "\n")
for f, v in per_fire.items():
    print(f[:22], {k: (x["nonburnable"], x["positives"]) for k, x in v.items()})
for name in groups:
    print(name, {k: out[name][k] for k in ("positives", "nonburnable_share", "all_static_valid_share")})
    print("  ", out[name]["family_shares"])
