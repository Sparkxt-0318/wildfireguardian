"""C4: spread in safe distance on representative cells (PROTOCOL.md 8): flame temperature 1090 / 1200 / 1400 K, view
factor planar / tilted / worst angle / cylinder, fuel low / middle / high, transmissivity on / off.

Representative cells (median conditions of the Uiseong 2025 reconstruction at arrival: U10 4 m/s, RH 46 %, 8.7 C):
* conifer, R = 30 m/min (crown fire at middle fuel);
* conifer, R = 3 m/min (surface fire at middle fuel);
* grass, R = 14 m/min (the Uiseong median spread rate).
"""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_radiation import model  # noqa: E402
from kcf_radiation.protocol import BASELINE  # noqa: E402

CELLS = {"conifer_crown_30m_min": ("conifer", 0.5), "conifer_surface_3m_min": ("conifer", 0.05),
         "grass_14m_min": ("grass", 14 / 60)}


def main():
    out = {}
    for cname, (g, R) in CELLS.items():
        rows = []
        for level, T, kind, tau in itertools.product(("low", "middle", "high"), (1090.0, 1200.0, 1400.0),
                                                     ("planar", "tilted", "tilted_max", "cylinder"), (True, False)):
            st = replace(BASELINE, level=level, T_flame_K=T, vf_kind=kind, transmissivity=tau)
            r = model.Evaluator(st).cells(np.array([R]), np.array([g]), np.array([4.0]), np.array([46.0]), np.array([8.7]))
            rows.append({"level": level, "T": T, "vf": kind, "tau": tau, "crown": bool(r["crown"][0]),
                         "L": round(float(r["L"][0]), 2), "H": round(float(r["H"][0]), 2),
                         **{"d%g" % q: round(float(r["dstar_%g" % q][0]), 1) for q in (7.0, 4.7, 2.5)}})
        base = next(x for x in rows if x["level"] == "middle" and x["T"] == 1200 and x["vf"] == "tilted" and x["tau"])
        summ = {"baseline": base}
        for q in ("d7", "d4.7", "d2.5"):
            v = [x[q] for x in rows]
            summ[q + "_min_max"] = [min(v), max(v)]
            for factor, key in (("T", "T"), ("vf", "vf"), ("level", "level"), ("tau", "tau")):
                sub = [x[q] for x in rows if all(x[k] == base[k] for k in ("level", "T", "vf", "tau") if k != key)]
                summ["%s_by_%s" % (q, factor)] = [min(sub), max(sub)]
        out[cname] = {"summary": summ, "rows": rows}
        print(cname, json.dumps(summ))
    (HERE / "data/c4_sensitivity.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
