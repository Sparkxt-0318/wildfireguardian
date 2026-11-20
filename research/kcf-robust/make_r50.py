"""Central reach curve R50(h) per class: research/kcf-margin's own calibration (calibrate.load, class_mask, by_fire,
reach.conformal_R) at alpha 0.5 on its committed reach table, fire set all28, h 5 and 8. Forecast input, no routing
result is used. Writes r50.json.
    python3 research/kcf-robust/make_r50.py
"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
M = HERE.parent / "kcf-margin"
sys.path.insert(0, str(M))
import calibrate as C  # noqa: E402
from reach import conformal_R  # noqa: E402

df = C.load(M / "derived")
out = {}
for cls in ("all", "quiet", "slow", "running"):
    for h in (5, 8):
        dh = df[df.h == h]
        sc = C.by_fire(dh[C.class_mask(dh, cls)])
        for al in (0.5, 0.1):
            R, _, n = conformal_R(list(sc.values()), al, C.DRAWS)
            out.setdefault(cls, {})["R%d_a%s" % (h, al)] = round(R, 4)
            out[cls]["n_fires"] = n
print(json.dumps(out, indent=1))
(HERE / "r50.json").write_text(json.dumps({"source": "research/kcf-margin calibrate.py + reach.conformal_R, all28, draws 2000, seed 20261116",
                                           "km": out}, indent=1))
