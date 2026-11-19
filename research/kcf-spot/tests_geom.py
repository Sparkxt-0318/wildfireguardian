"""Step 5 geometry (PROTOCOL section 6): for every fire and eligible issue hour at 5 h lead, the reach S (kcf-margin
rule, product burned set K_t, components > 5 km excluded), the area curve, and for a grid of spot-layer thresholds p
the residual reach S'_p (largest distance of reach cells outside the zone P >= p) and the zone's area by distance.
Also the ORACLE reach with observed spot-born cells removed (test 4a).

Products: GOFER (California), Choi kriged raster (Korea), FIRMS VIIRS + Himawari detection product (25 March, built
by kcf-margin/score_gyeongbuk.py). The spot layer is computed from what was observed by the issue hour (B_obs:
GOFER + VIIRS in California, VIIRS in Korea, the detection product on 25 March), with the frozen fit (derived/fit.json).

    python tests_geom.py --work WORK --choi DATA/choi/x --wind derived/era5_wind.csv.gz --fit derived/fit.json --out WORK/geom
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "research/kcf-margin"))
import spotlib as S  # noqa: E402
from reach import component_reach  # noqa: E402

ABSTAIN = REPO / "research/kcf-abstain/derived/hours.csv.gz"
CELL = 375.0
CK = 0.375
NB = 160                       # 60 km cap in 0.375 km bins
LEAD = 5
P_GRID = np.array([0.5, 0.3, 0.1, 0.03, 0.01, 3e-3, 1e-3, 3e-4, 1e-4])


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def spot_P(beta, Bobs, U, wdir, h=LEAD, mask_out=None):
    """Per-cell P(lit by a spot within h) from the frozen fit; 0 outside the fitted distance range."""
    d, ind = ndimage.distance_transform_edt(~Bobs, return_indices=True)
    x = d * CK
    H, W = Bobs.shape
    rr, cc = np.mgrid[0:H, 0:W]
    ok = (~Bobs) & (x >= 0.375) & (x < 15.0)
    if mask_out is not None:
        ok &= ~mask_out
    P = np.zeros(Bobs.shape)
    if not ok.any() or not np.isfinite(U) or not np.isfinite(wdir):
        return P
    b = S.bearing_deg(rr[ok] - ind[0][ok], cc[ok] - ind[1][ok])
    a = S.angle_to_downwind(b, wdir)
    lx = np.log(x[ok])
    eta = beta[0] + beta[1] * lx + beta[2] * U + beta[3] * U * lx + beta[4] * np.log(h) + beta[5] * np.cos(np.radians(a))
    P[ok] = -np.expm1(-np.exp(np.clip(eta, -30, 5)))
    return P


def hist(dist, m):
    idx = np.ceil(dist[m] / CK - 1e-9).astype(np.int64)
    idx = idx[(idx >= 1) & (idx <= NB)]
    return np.bincount(idx - 1, minlength=NB).astype(np.float32)


def hour_rows(fire, region, A, Bobs_of, spotborn, hours, epoch, beta, wind):
    """A: product arrival in integer hours since epoch (inf = never). Bobs_of(t) -> bool grid."""
    rows, curves, zones = [], [], []
    w = wind[wind.fire == fire].set_index("t_utc")
    last = np.nanmax(np.where(np.isfinite(A), A, np.nan))
    first = np.nanmin(np.where(np.isfinite(A), A, np.nan))
    prev, dist = None, None
    for _, hr in hours.iterrows():
        tu = pd.Timestamp(hr.t_utc)
        t = int(round((tu - epoch).total_seconds() / 3600))
        if t - first < 3 or t + LEAD > last:
            continue
        known = A <= t
        if not known.any():
            continue
        n = int(known.sum())
        if n != prev:
            dist = ndimage.distance_transform_edt(~known) * CK
            prev = n
        new = (A > t) & (A <= t + LEAD)
        rr_, _, R = component_reach(known, new, (5.0,), dist=dist)
        Sx = rr_[5.0]
        wd = w["era5_dir_deg"].get(tu.floor("h"), np.nan)
        P = spot_P(beta, Bobs_of(t), float(hr.gust_ms), wd, mask_out=known)
        Zs, Sp = [], []
        for p in P_GRID:
            Z = P >= p
            m = R & ~Z
            Sp.append(float(dist[m].max()) if m.any() else 0.0)
            Zs.append(hist(dist, Z & ~known))
        m0 = R & ~spotborn if spotborn is not None else None
        rows.append(dict(fire=fire, region=region, t_utc=str(tu), t_idx=t, S=Sx,
                         S_nospot=(float(dist[m0].max()) if m0.any() else 0.0) if m0 is not None else np.nan,
                         reach_cells=int(R.sum()), spot_cells_in_reach=int((R & spotborn).sum()) if spotborn is not None else -1,
                         gust=float(hr.gust_ms), wdir=wd, Pmax=float(P.max()), kst_hour=(tu + pd.Timedelta(hours=9)).hour,
                         **{f"Sp_{i}": v for i, v in enumerate(Sp)}))
        curves.append(np.cumsum(hist(dist, ~known & (dist > 0))))
        zones.append(np.stack(Zs))
    return rows, curves, zones


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--choi", required=True)
    ap.add_argument("--wind", required=True); ap.add_argument("--fit", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--only", default="CA,KR,DET")
    ap.add_argument("--part", default=None)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fit = json.load(open(a.fit))
    hrs = pd.read_csv(ABSTAIN, low_memory=False, usecols=["fire", "product", "t_utc", "gust_ms"])
    hrs = hrs[hrs.gust_ms.notna()]
    wind = pd.read_csv(a.wind); wind["t_utc"] = pd.to_datetime(wind.t_utc)
    jobs = []
    regions = a.only.split(",")
    if "CA" in regions:
        jobs += [("CA", p) for p in sorted((Path(a.work) / "CA").glob("*.npz"))]
    if "KR" in regions:
        kr = sorted(hrs[hrs["product"] == "CHOI"].fire.unique())
        jobs += [("KR", Path(a.work) / "KR" / f"{f}.npz") for f in kr if f.startswith("KFS")]
    if "DET" in regions:
        jobs.append(("DET", Path(a.work) / "DET" / "KFS_01.npz"))
    if a.part:
        i, n = (int(x) for x in a.part.split("/"))
        jobs = jobs[i::n]
    for region, p in jobs:
        z = np.load(p)
        fire = p.stem
        epoch = pd.Timestamp(str(z["epoch"]))
        first = z["first"].astype(float)
        lab = z["label"]
        spotborn = (lab == S.SPOT) | (lab == S.GROWTH)
        if region == "CA":
            beta = np.array(fit["ca_fit"]["beta"])
            A = z["gofer_A"].astype(float)
            Bobs_of = lambda t, first=first: first <= t
            hours = hrs[(hrs.fire == fire) & (hrs["product"] == "GOFER")]
        elif region == "KR":
            beta = np.array(fit["kr_folds"][fire])
            import rasterio
            with rasterio.open(Path(a.choi) / "rasters_kr" / f"{fire}_pswt_ok_toa.tif") as ds:
                toa = ds.read(1, masked=True).filled(np.nan).astype(float)
                tf = ds.transform
                t0 = pd.Timestamp(ds.tags()["t0_utc"])
            off = (t0 - epoch).total_seconds() / 3600
            A = np.full(first.shape, np.inf)
            r0 = int(round((float(z["y1"]) - tf.f) / CELL)); c0 = int(round((tf.c - float(z["x0"])) / CELL))
            sub = np.where(np.isfinite(toa), np.ceil(toa + off - 1e-9), np.inf)
            A[r0:r0 + toa.shape[0], c0:c0 + toa.shape[1]] = sub
            Bobs_of = lambda t, first=first: first <= t
            hours = hrs[(hrs.fire == fire) & (hrs["product"] == "CHOI")]
        else:
            beta = np.array(fit["kr_folds"]["DET:KFS_01"])
            sk = _load(REPO / "research/kcf-margin/score_gyeongbuk.py", "score_gyeongbuk")
            Ad, _, meta = sk.build_arrival(str(REPO / "research/harness-2026-11/data-fetch/small/firms"),
                                           str(REPO / "research/harness-2026-11/data-fetch-2/ahi_kfs01"))
            A = np.where(Ad == np.iinfo(np.int32).max, np.inf, Ad.astype(float))
            epoch = sk.T0
            # observed spot-born cells of this folder's DET run, mapped onto the product grid
            sb = np.zeros(A.shape, bool)
            r0 = int(round((meta["y1"] - float(z["y1"])) / CELL)); c0 = int(round((float(z["x0"]) - meta["x0"]) / CELL))
            rr, cc = np.nonzero(spotborn)
            ok = (rr + r0 >= 0) & (rr + r0 < A.shape[0]) & (cc + c0 >= 0) & (cc + c0 < A.shape[1])
            sb[rr[ok] + r0, cc[ok] + c0] = True
            spotborn = sb
            Bobs_of = lambda t, A=A: A <= t
            hours = hrs[(hrs.fire == "KFS_01") & (hrs["product"] == "DET")]
            np.save(out / "det_A.npy", A)
            json.dump({k: float(v) for k, v in meta.items() if np.isscalar(v)}, open(out / "det_meta.json", "w"))
        rows, curves, zones = hour_rows(fire, region, A, Bobs_of, spotborn, hours, epoch, beta, wind)
        tag = f"{region}_{fire}".replace(" ", "_")
        pd.DataFrame(rows).to_csv(out / f"{tag}.csv", index=False)
        np.savez_compressed(out / f"{tag}.npz", curves=np.array(curves, np.float32).reshape(-1, NB),
                            zones=np.array(zones, np.float32).reshape(-1, len(P_GRID), NB))
        print(region, fire, len(rows), "hours", flush=True)


if __name__ == "__main__":
    main()
