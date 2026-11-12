"""DOMINANCE_RULE §1 premises for the four G2c missions (Mira ledger 106 N1, §2 (iii)): the kit's ContactSources and the
relaxation's ContactModel + graph grid use the same grid cells, members and flame law.

- grid: every graph cell (south-up row gr, col c) rectangle vs the REPORT affine rectangle of native row H-1-gr, exact
  rationals (the kit's ContactSources.from_case places sources with REPORT native_metadata.affine_transform);
- members: ContactModel.ids vs REPORT rows[0].request.incurred keys vs the npz member axis;
- law: ContactModel T, R vs REPORT burning_duration_s, initial_remaining_s.
Usage (repo root, F-3.2 PYTHONPATH): python research/harness-2026-11/F-3.2/xcheck/g2c_premises.py > OUT.json
"""
import hashlib
import json
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from p1_check import routable_contact_model  # noqa: E402

D = "data/routing/"
CASES = [("hongseong_2023", "20230402T070000Z"), ("miryang_2022", "20220601T080000Z")]


def check(region, start):
    pk = Path(D + "latest_inputs_try02/packets/%s/%s" % (region, start)); gp = Path(D + "graphs/%s/graph.json" % region)
    g = json.loads(gp.read_text())["grid"]; rep = json.loads((pk / "REPORT.json").read_text())
    aff = [F(x) for x in rep["native_metadata"]["affine_transform"]]
    with np.load(pk / "constructed_arrays.npz", allow_pickle=False) as z:
        S, H, W = z["ignition_time_s"].shape
    res, x0, y0 = F(g["resolution"]), F(g["x0"]), F(g["y0"])
    grid_ok = (int(g["width"]), int(g["height"])) == (W, H) and aff == [res, F(0), x0, F(0), -res, y0 + H * res]
    bad = 0
    for gr in range(H):
        r = H - 1 - gr
        for c in range(W):
            gx = (x0 + c * res, x0 + (c + 1) * res); gy = (y0 + gr * res, y0 + (gr + 1) * res)
            kx = sorted([aff[2] + aff[0] * c + aff[1] * r, aff[2] + aff[0] * (c + 1) + aff[1] * (r + 1)])
            ky = sorted([aff[5] + aff[3] * c + aff[4] * r, aff[5] + aff[3] * (c + 1) + aff[4] * (r + 1)])
            bad += (tuple(kx) != gx) or (tuple(ky) != gy)
    m = routable_contact_model(str(pk))
    kit_ids = list(rep["rows"][0]["request"]["incurred"]); ass = rep["native_metadata"]["construction"]["assumptions"]
    return dict(region=region, start=start, graph_sha256=hashlib.sha256(gp.read_bytes()).hexdigest(),
                report_sha256=hashlib.sha256((pk / "REPORT.json").read_bytes()).hexdigest(),
                npz_sha256=hashlib.sha256((pk / "constructed_arrays.npz").read_bytes()).hexdigest(),
                grid={"graph": g, "packet_shape": [S, H, W], "report_affine": rep["native_metadata"]["affine_transform"]},
                grid_aligned=grid_ok, cells_checked=H * W, cell_rectangle_mismatches=bad,
                members={"kit_ids_from_REPORT": len(kit_ids), "npz_members": S, "ContactModel_ids": len(m.ids),
                         "identical_ordered": m.ids == kit_ids},
                member_set_equal=(m.ids == kit_ids and len(m.events) == S == len(kit_ids)),
                law={"T_kit": str(F(ass["burning_duration_s"])), "T_model": str(m.T),
                     "R_kit": str(F(ass["initial_remaining_s"])), "R_model": str(m.R)},
                flame_law_equal=(m.T == F(ass["burning_duration_s"]) and m.R == F(ass["initial_remaining_s"])))


if __name__ == "__main__":
    print(json.dumps([check(*c) for c in CASES], indent=1))
