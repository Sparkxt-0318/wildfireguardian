"""C3: predicted flame length against published observations (PROTOCOL.md 8, amendment A4).

(i) ICFME crown fires, Stocks et al. (2004, Can. J. For. Res. 34:1548-1560): per-plot intensity I (kW/m) and spread
    rate R (m/s) as reported; flame fronts "commonly extended 25-40 m above the ground". Predicted: Thomas from the
    reported I (the published-intensity path), and the protocol chain from the reported R with this study's conifer
    fuel (the full-chain path). Pass per plot: within a factor 2 of the nearest end of 25-40 m.
(ii) Pine-litter surface fires: Nelson and Adkins (1986): flame length ~0.5 m in needle litter regardless of
    intensity, and proportional to I^0.5 when consumption > 0.5 kg/m2 (abstract). Range comparison only.
(iii) Grass and shrub: RxCADRE 2012 (Butler et al. 2016, Int. J. Wildland Fire 25:76-89): flame heights 0.3-1.8 m at
    0.10-0.48 m/s. Range comparison only (no paired fuel consumption obtained).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_radiation import fire, model  # noqa: E402
from kcf_radiation.protocol import BASELINE  # noqa: E402
from dataclasses import replace  # noqa: E402

ICFME = {"A": (77688, 0.937), "1": (48697, 0.588), "2": (13402, 0.263), "3": (36902, 0.405), "4": (53162, 0.743),
         "5": (48134, 0.482), "6": (46721, 0.600), "7": (93476, 1.153), "8a": (34321, 0.405), "8c": (76270, 0.900),
         "9": (89681, 1.163)}
OBS = (25.0, 40.0)


def factor_to_range(x, lo, hi):
    if lo <= x <= hi:
        return 1.0
    return x / hi if x > hi else lo / x


def main():
    rows = []
    for plot, (I, R) in ICFME.items():
        L_pub = float(fire.flame_length_thomas(I))
        rec = {"plot": plot, "I_reported": I, "R_m_s": R, "L_thomas_from_reported_I": round(L_pub, 1),
               "factor_pub": round(factor_to_range(L_pub, *OBS), 2)}
        for lev in ("low", "middle", "high"):
            r = model.Evaluator(replace(BASELINE, level=lev, thresholds=(7.0,))).cells(
                np.array([R]), np.array(["conifer"]), np.array([5.0]), np.array([40.0]), np.array([20.0]))
            rec["chain_%s_L" % lev] = round(float(r["L"][0]), 1)
            rec["chain_%s_H" % lev] = round(float(r["H"][0]), 1)
            rec["chain_%s_I" % lev] = round(float(r["I_total"][0]))
            rec["factor_chain_%s" % lev] = round(factor_to_range(float(r["L"][0]), *OBS), 2)
        rows.append(rec)
    pass_pub = all(r["factor_pub"] <= 2 for r in rows)
    pass_chain = all(r["factor_chain_middle"] <= 2 for r in rows)
    # (ii) pine litter: Byram at I where consumption ~0.5-1.1 kg/m2 and R 0.5-5 m/min
    litter = []
    for w in (0.5, 0.76, 1.1):
        for Rm in (0.5, 1.0, 2.0, 5.0):
            I = 18000 * w * Rm / 60
            litter.append({"w": w, "R_m_min": Rm, "I": round(I), "L_byram": round(float(fire.flame_length_byram(I)), 2)})
    # (iii) grass: protocol grass fuel at RxCADRE spread rates
    grass = []
    for lev, w in (("low", 0.09), ("middle", 0.25), ("high", 0.48)):
        for R in (0.10, 0.48):
            I = 18000 * w * R
            grass.append({"level": lev, "R_m_s": R, "I": round(I), "L_byram": round(float(fire.flame_length_byram(I)), 2)})
    out = {"icfme": rows, "icfme_observed_flame_height_m": OBS, "pass_published_intensity": pass_pub,
           "pass_full_chain_middle": pass_chain, "pass": pass_pub and pass_chain,
           "pine_litter_range": litter, "nelson_adkins_1986_note": "needle litter flame ~0.5 m regardless of intensity (abstract)",
           "grass_range": grass, "rxcadre_observed_flame_height_m": [0.3, 1.8]}
    (HERE / "data/c3_flames.json").write_text(json.dumps(out, indent=1))
    for r in rows:
        print(r)
    print("pass published-I:", pass_pub, " pass chain (middle):", pass_chain)
    print("litter Byram L range:", min(x["L_byram"] for x in litter), "-", max(x["L_byram"] for x in litter))
    print("grass Byram L range:", min(x["L_byram"] for x in grass), "-", max(x["L_byram"] for x in grass))


if __name__ == "__main__":
    main()
