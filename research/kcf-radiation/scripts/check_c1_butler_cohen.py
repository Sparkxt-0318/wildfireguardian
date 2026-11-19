"""C1: Butler and Cohen (1998) rule, safe distance ~ 4 x flame height at 7 kW/m2 on flat ground (PROTOCOL.md 8).

Their assumptions: flat vertical radiating sheet of height H and width W, emissivity 1, uniform flame temperature
(1200 K; one secondary source reports 900 C = 1173 K, both run), no atmospheric attenuation, flat ground.
Receiver: a vertical element facing the flame; heights 0 (ground) and H/2 are both given. The net-exchange variant
subtracts the receiver's own emission at 310 K (skin), as in a three-surface net-radiation model.

Output: data/c1_butler_cohen.json and a printed table of d(7)/H against W/H and H.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_radiation import radiation, viewfactor as vf  # noqa: E402

SIG = radiation.SIGMA_KW


def d_at(q, H, W, T, z, net=False):
    E = SIG * T ** 4
    q_eff = q + (SIG * 310.0 ** 4 if net else 0.0)  # net = E F - sigma T_s^4 (receiver sees cold surroundings)
    lo, hi = 0.01, 50 * H + 10 * W
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if E * vf.planar_mcguire(m, H, W, z) > q_eff:
            lo = m
        else:
            hi = m
    return hi


def main():
    out = {"rows": []}
    for T in (1173.0, 1200.0):
        for net in (False, True):
            for zname in ("ground", "mid"):
                for wr in (1, 2, 3, 4, 5, 10, 1e4):
                    ratios = []
                    for H in (2.0, 5.0, 10.0, 20.0):
                        z = 0.0 if zname == "ground" else H / 2
                        ratios.append(d_at(7.0, H, wr * H, T, z, net) / H)
                    out["rows"].append({"T_K": T, "net": net, "receiver": zname, "W_over_H": wr,
                                        "d7_over_H_for_H_2_5_10_20": [round(r, 3) for r in ratios],
                                        "spread_pct": round(100 * (max(ratios) - min(ratios)) / min(ratios), 3)})
    # width ratio at which d/H = 4 (T 1200, ground, incident)
    lo, hi = 0.5, 100.0
    for _ in range(100):
        m = math.sqrt(lo * hi)
        if d_at(7.0, 10.0, m * 10.0, 1200.0, 0.0) / 10.0 < 4.0:
            lo = m
        else:
            hi = m
    out["W_over_H_giving_4H_T1200_ground"] = round(hi, 3)
    # Amendment 1 (PROTOCOL): Butler and Cohen's geometry is a FIXED 20 m front (Butler 2014, Table 1), 1200 K, eps 1,
    # vertical flame; not a fixed width ratio. d(q*) / H against H at W = 20 m, and the published comparators:
    # Zarate et al. 2008 (W 20 m, 1200 K, tau 1): 3.8 H at 7 and 4.8 H at 4.7 kW/m2 (as reported by Butler 2014);
    # Rossi et al. 2011: 8 x flame length for W/L > 50.
    fixed = []
    for H in (1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0):
        r = {"H_m": H}
        for zname in ("ground", "mid"):
            z = 0.0 if zname == "ground" else H / 2
            for qq in (7.0, 4.7):
                r["d%g_over_H_%s" % (qq, zname)] = round(d_at(qq, H, 20.0, 1200.0, z) / H, 3)
        fixed.append(r)
    out["fixed_width_20m"] = fixed
    def fit(key, Hmax):
        xs = [r["H_m"] for r in fixed if r["H_m"] <= Hmax]
        ds = [r[key] * r["H_m"] for r in fixed if r["H_m"] <= Hmax]
        return round(sum(x * d for x, d in zip(xs, ds)) / sum(x * x for x in xs), 3)
    out["linear_fit_through_origin_d7_over_H"] = {"H<=%g" % h: fit("d7_over_H_ground", h) for h in (5, 10, 20, 30)}
    out["linear_fit_through_origin_d4.7_over_H"] = {"H<=%g" % h: fit("d4.7_over_H_ground", h) for h in (5, 10, 20, 30)}
    out["long_front_d7_over_L_vertical_1200K"] = round(d_at(7.0, 10.0, 1e5, 1200.0, 0.0) / 10.0, 3)
    p = HERE / "data/c1_butler_cohen.json"
    p.write_text(json.dumps(out, indent=1))
    for r in out["fixed_width_20m"]:
        print(r)
    print("fits d7/H", out["linear_fit_through_origin_d7_over_H"], "d4.7/H", out["linear_fit_through_origin_d4.7_over_H"])
    print("long front d7/L", out["long_front_d7_over_L_vertical_1200K"])
    print("W/H giving d = 4H (1200 K, ground receiver, incident):", out["W_over_H_giving_4H_T1200_ground"])


if __name__ == "__main__":
    main()
