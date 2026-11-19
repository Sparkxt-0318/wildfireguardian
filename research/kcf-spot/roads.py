"""Step 4 road layer and step 5 test 3 (PROTOCOL sections 5 and 6.3).

Road layer: for every road cell of the two wfg-roadlayer regions (375 m, EPSG:5179) and every 25 March 2025 issue hour
(KST 00-23, the detection product's issue hours), P(lit by a spot before the main front within h), h = 1..8, from the
frozen fit (25 March fold; KFS_01 out of the fit), with the burned set at the issue hour from the detection product.
Zones P >= 0.10 / 0.30 / 0.50.

Test 3: official KEC closures of 25 March (kcf-validate) and reported local-road controls (kcf-roadcut) whose road can
be located by route number. Section cells are approximated by route number inside the region grids (stated per row).

    python roads.py --geom WORK/geom --fit derived/fit.json --wind derived/era5_wind.csv.gz --out derived
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
from tests_geom import CK, spot_P  # noqa: E402

T0 = pd.Timestamp("2025-03-22 00:00")
CELL = 375.0
REGIONS = ("uiseong_andong_2025", "yeongdeok_2025")
FIXED_C = None   # read from derived/tests.json (test 1 calibration)

CLOSURES = [  # id, KST, source, region, route, part, note
    ("KEC-0015", "2025-03-25 00:15", "KEC official", "uiseong_andong_2025", "55", "all", "중앙선 의성IC~남안동JC: all route-55 cells in grid"),
    ("KEC-1530", "2025-03-25 15:30", "KEC official", "uiseong_andong_2025", "30", "east_of_jc", "서산영덕선 안동JC~청송IC: route-30 cells east of the 30/55 junction"),
    ("KEC-1558", "2025-03-25 15:58", "KEC official", "uiseong_andong_2025", "30", "all", "서산영덕선 서의성IC~청송IC: all route-30 cells in grid"),
    ("KEC-1800", "2025-03-25 18:00", "KEC official", "uiseong_andong_2025", "55", "all", "중앙선 의성IC~예천IC: all route-55 cells in grid"),
    ("KEC-2126", "2025-03-25 21:26", "KEC official", "uiseong_andong_2025", "55", "all", "중앙선 의성IC~풍기IC: all route-55 cells in grid"),
    ("RD10", "2025-03-25 18:25", "REPORTED (kcf-roadcut)", "yeongdeok_2025", "34", "all", "황장재 통행제한: all route-34 cells in the 영덕 grid"),
    ("RD11", "2025-03-25 18:58", "REPORTED (kcf-roadcut)", "yeongdeok_2025", "34", "all", "국도34 구미~황장: all route-34 cells in the 영덕 grid"),
    ("RD12", "2025-03-25 19:04", "REPORTED (kcf-roadcut)", "yeongdeok_2025", "911", "all", "지품면 도계→영양: route-911 cells in the 영덕 grid"),
    ("RD9", "2025-03-25 19:09", "REPORTED (kcf-roadcut)", "yeongdeok_2025", "911", "all", "지방도911 황장리~화매리: route-911 cells in the 영덕 grid"),
]


class Region:
    def __init__(self, name):
        g = json.load(open(REPO / f"data/routing/graphs/{name}/graph.json"))
        gr = g["grid"]
        self.name, self.x0, self.y0, self.res, self.W, self.H = name, gr["x0"], gr["y0"], gr["resolution"], gr["width"], gr["height"]
        self.edges = g["edges"]
        w = pd.read_csv(REPO / f"product/wfg-roadlayer/data/edges/{name}_ways.csv.gz", dtype={"ref": str})
        self.refs = {int(r.source_way): set(str(r.ref).split(";")) if isinstance(r.ref, str) else set() for r in w.itertuples()}
        self.cells = sorted({int(s["cell"]) for e in self.edges for s in e["segments"]})

    def centre(self, c):
        r, k = divmod(np.asarray(c), self.W)
        return self.x0 + (k + 0.5) * self.res, self.y0 + (r + 0.5) * self.res

    def route_cells(self, ref):
        return sorted({int(s["cell"]) for e in self.edges if ref in self.refs.get(e["source_way"], ()) for s in e["segments"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geom", required=True); ap.add_argument("--fit", required=True)
    ap.add_argument("--wind", required=True); ap.add_argument("--tests", default=str(HERE / "derived/tests.json"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    A = np.load(Path(a.geom) / "det_A.npy")
    meta = json.load(open(Path(a.geom) / "det_meta.json"))
    beta = np.array(json.load(open(a.fit))["kr_folds"]["DET:KFS_01"])
    fixed_c = [t for t in json.load(open(a.tests))["test1"] if t["arm"] == "FIXED"][0]["c_km"]
    hrs = pd.read_csv(REPO / "research/kcf-abstain/derived/hours.csv.gz", low_memory=False,
                      usecols=["fire", "product", "t_utc", "gust_ms"])
    hrs = hrs[(hrs.fire == "KFS_01") & (hrs["product"] == "DET")].copy()
    hrs["t_utc"] = pd.to_datetime(hrs.t_utc)
    wind = pd.read_csv(a.wind); wind["t_utc"] = pd.to_datetime(wind.t_utc)
    wd = wind[wind.fire == "KFS_01"].set_index("t_utc").era5_dir_deg
    regs = {r: Region(r) for r in REGIONS}
    # product indices of every road cell
    rc = {}
    for r, R in regs.items():
        x, y = R.centre(R.cells)
        rr = np.floor((meta["y1"] - y) / CELL).astype(int); cc = np.floor((x - meta["x0"]) / CELL).astype(int)
        ok = (rr >= 0) & (rr < A.shape[0]) & (cc >= 0) & (cc < A.shape[1])
        rc[r] = (np.array(R.cells)[ok], rr[ok], cc[ok])
    rows, Pstore, Dstore = [], {}, {}
    for _, h in hrs.iterrows():
        t = (h.t_utc - T0).total_seconds() / 3600
        known = A <= t
        dist = ndimage.distance_transform_edt(~known) * CK
        Ph = {k: spot_P(beta, known, float(h.gust_ms), float(wd.get(h.t_utc, np.nan)), h=k, mask_out=known) for k in range(1, 9)}
        Pstore[h.t_utc], Dstore[h.t_utc] = Ph, dist
        kst = h.t_utc + pd.Timedelta(hours=9)
        for r, (cells, rr, cc) in rc.items():
            arr = A[rr, cc] - t
            for i, c in enumerate(cells):
                p5, p8 = Ph[5][rr[i], cc[i]], Ph[8][rr[i], cc[i]]
                rows.append(dict(region=r, cell=int(c), issue_kst=str(kst), gust_ms=float(h.gust_ms),
                                 front_arrival_h=float(arr[i]) if np.isfinite(arr[i]) else np.inf,
                                 dist_front_km=float(dist[rr[i], cc[i]]), P1=float(Ph[1][rr[i], cc[i]]), P5=float(p5),
                                 P8=float(p8), zone8=("50%" if p8 >= 0.5 else "30%" if p8 >= 0.3 else "10%" if p8 >= 0.1 else "")))
    lay = pd.DataFrame(rows)
    lay.to_csv(Path(a.out) / "roadlayer_spot_20250325.csv.gz", index=False)
    summ = lay.groupby("issue_kst").agg(road_cells=("cell", "size"), P8_max=("P8", "max"), P5_max=("P5", "max"),
                                        zone10=("zone8", lambda z: int((z != "").sum())))
    summ.to_csv(Path(a.out) / "roadlayer_spot_20250325_summary.csv")
    # ---------------- test 3
    out = []
    for cid, kst_s, src, region, ref, part, note in CLOSURES:
        R = regs[region]
        cells = R.route_cells(ref)
        if part == "east_of_jc":
            j55 = np.array(R.centre(R.route_cells("55"))).T
            c30 = np.array(R.centre(cells)).T
            dj = np.min(np.hypot(c30[:, None, 0] - j55[None, :, 0], c30[:, None, 1] - j55[None, :, 1]), axis=1)
            xj = c30[np.argmin(dj), 0]
            cells = [c for c, (x, _) in zip(cells, c30) if x >= xj]
        x, y = R.centre(cells)
        rr = np.floor((meta["y1"] - y) / CELL).astype(int); cc = np.floor((x - meta["x0"]) / CELL).astype(int)
        ok = (rr >= 0) & (rr < A.shape[0]) & (cc >= 0) & (cc < A.shape[1])
        rr, cc = rr[ok], cc[ok]
        tc_utc = pd.Timestamp(kst_s) - pd.Timedelta(hours=9)
        tci = (tc_utc - T0).total_seconds() / 3600
        reached = bool((A[rr, cc] <= tci).any())
        first_arr = A[rr, cc].min()
        row = dict(id=cid, closure_kst=kst_s, source=src, region=region, section=note, n_cells=int(len(rr)),
                   front_reached_by_closure=reached,
                   first_front_arrival_kst=str(T0 + pd.Timedelta(hours=float(first_arr)) + pd.Timedelta(hours=9)) if np.isfinite(first_arr) else "not reached")
        issues = [t for t in Pstore if t <= tc_utc]
        if not issues:
            row["status"] = "no issue hour of the detection product at or before the closure"
        else:
            T = max(issues)
            hh = int(min(8, max(1, np.ceil((tc_utc - T).total_seconds() / 3600))))
            P = Pstore[T][hh][rr, cc]
            dd = Dstore[T][rr, cc]
            row.update(issue_kst=str(T + pd.Timedelta(hours=9)), h=hh, P_max=float(P.max()),
                       in_zone10=bool((P >= 0.10).any()), in_fixed_buffer=bool((dd <= fixed_c).any()),
                       nearest_front_km=float(dd.min()), fixed_c_km=fixed_c)
        out.append(row)
    t3 = pd.DataFrame(out)
    t3.to_csv(Path(a.out) / "test3_closures.csv", index=False)
    print(summ.to_string())
    print(t3.to_string())


if __name__ == "__main__":
    main()
