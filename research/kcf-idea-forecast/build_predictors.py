"""Hop factor F and reach predictors X1 (10% rule, wind run) and X2 (10% rule x hop factor). Inputs only: no reach is read.

    python3 build_predictors.py ERA5.csv.gz DEM_DIR OUT.csv.gz [--kr]

Frozen parameters are in params.json (see IDEA.md / TEST.md). One row per fire and hour stamp, per parameter set.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import terrain

P = json.loads((Path(__file__).resolve().parent / "params.json").read_text())
NDIR = 16


def factor_table(z, sets, need):
    """need: set of (dirbin, Ubin, rbin). Returns dict (setname, dirbin, Ubin, rbin) -> F."""
    out = {}
    for d in sorted({k[0] for k in need}):
        zr = terrain.rotate_to_wind(z, d * 360.0 / NDIR)
        for name, s in sets.items():
            jumps = {}
            for (dd, ub, rb) in sorted(k for k in need if k[0] == d):
                U = float(ub); r = rb / 10.0
                if U <= 0 or r <= 0:
                    out[(name, d, ub, rb)] = 1.0; continue
                if ub not in jumps:
                    jumps[ub] = terrain.landing(zr, s["w_t"] / U, s["z0"], int(s["t_b"] * U / terrain.CELL))
                j = jumps[ub]
                out[(name, d, ub, rb)] = 1.0 if not j.any() else max(1.0, terrain.speedup(zr, j, r, s["t_i"], U))
    return out


def main():
    era, demdir, outp = sys.argv[1:4]
    kr = "--kr" in sys.argv
    e = pd.read_csv(era, parse_dates=["t"])
    if kr:   # fire-wide series: max over the five points per hour; direction from the point with the largest U100
        i = e.groupby("t").wind_speed_100m.idxmax()
        d = e.loc[i, ["t", "wind_direction_100m"]].set_index("t")
        m = e.groupby("t")[["wind_speed_10m", "wind_speed_100m", "wind_gusts_10m"]].max()
        e = m.join(d).reset_index(); e.insert(0, "fire", "Gyeongbuk")
    e["dirbin"] = (np.round(((e.wind_direction_100m + 180.0) % 360) / (360.0 / NDIR)).astype(int)) % NDIR
    c = P["c"]
    rows = []
    for fire, s in e.groupby("fire"):
        z = np.load(Path(demdir) / (fire.replace(" ", "_").replace("/", "_") + ".npz"))["z"].astype(float)
        s = s.copy()
        for name, ps in P["sets"].items():
            ucol = ps.get("u_crest", "wind_speed_100m")
            s["ub_" + name] = np.round(s[ucol]).astype(int)
        s["rb"] = np.round(c * s.wind_speed_10m * 10).astype(int)
        for name, ps in P["sets"].items():
            need = set(zip(s.dirbin, s["ub_" + name], s.rb))
            tab = factor_table(z, {name: ps}, need)
            s["F_" + name] = [tab[(name, a, b, r)] for a, b, r in zip(s.dirbin, s["ub_" + name], s.rb)]
        rows.append(s); print(fire, len(s), {n: round(float(s["F_" + n].max()), 2) for n in P["sets"]}, flush=True)
    pd.concat(rows).to_csv(outp, index=False)


if __name__ == "__main__":
    main()
