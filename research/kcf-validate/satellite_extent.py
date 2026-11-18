"""Source 3 (PROTOCOL.md section 2 + amendment 1): Sentinel-2 burned/burning extent at 2025-03-24 02:17:30 UTC versus the model's
reached area at that time. Usage: python3 -I satellite_extent.py S2_DIR OUT_DIR
Counts, not scores: every number carries n. Nothing is tuned."""
from __future__ import annotations

import hashlib, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "research/kcf-replay"))
import measured_arms as MA  # noqa: E402

INVALID_SCL = (0, 1, 3, 6, 8, 9, 10, 11)
THR = (0.10, 0.27)
BURN_FRAC, MIN_VALID = 0.25, 0.50
X0, Y0, RES, W, H = 1085250.0, 1845375.0, 375.0, 237, 79  # Choi KFS_01 lattice, north-up, row 0 = north
NPIX = (RES / 20.0) ** 2
T_S = datetime(2025, 3, 24, 2, 17, 30, tzinfo=timezone.utc)
SCENES = {"52SDF": ("S2B_52SDF_20250314_0_L2A", "S2B_52SDF_20250324_0_L2A"),
          "52SEF": ("S2B_52SEF_20250314_0_L2A", "S2B_52SEF_20250324_0_L2A")}


def read(path, bounds):
    with rasterio.open(path) as s:
        w = from_bounds(*bounds, transform=s.transform).round_offsets().round_lengths()
        return s.read(1, window=w), s.window_transform(w), s.crs


def tile_stats(d, pre, post):
    """Per-cell (n_valid, n_burn[thr] for raw and offset maps) on the lattice, from one tile."""
    with rasterio.open(d / f"{pre}_B8A.tif") as s:
        epsg = s.crs.to_epsg()
    tr = Transformer.from_crs(5179, epsg, always_xy=True)
    xs = [X0, X0 + W * RES, X0, X0 + W * RES]; ys = [Y0, Y0, Y0 - H * RES, Y0 - H * RES]
    ux, uy = tr.transform(xs, ys)
    bounds = (min(ux) - 200, min(uy) - 200, max(ux) + 200, max(uy) + 200)
    a = {}
    for scene in (pre, post):
        for b in ("B8A", "B12", "SCL"):
            arr, t, crs = read(d / f"{scene}_{b}.tif", bounds)
            a[(scene, b)] = (arr, t)
    shp = {v[0].shape for v in a.values()}
    assert len(shp) == 1, shp  # 20 m bands on one grid
    t = a[(pre, "B8A")][1]
    r, c = np.indices(next(iter(shp)))
    px, py = rasterio.transform.xy(t, r.ravel(), c.ravel(), offset="center")
    to5179 = Transformer.from_crs(epsg, 5179, always_xy=True)
    X, Y = to5179.transform(np.asarray(px), np.asarray(py))
    col = np.floor((X - X0) / RES).astype(int); row = np.floor((Y0 - Y) / RES).astype(int)
    inside = (col >= 0) & (col < W) & (row >= 0) & (row < H)
    idx = (row * W + col)[inside]
    out = {}
    for mode in ("raw", "offset"):
        def nbr(scene):
            b8 = a[(scene, "B8A")][0].astype(float); b12 = a[(scene, "B12")][0].astype(float)
            scl = a[(scene, "SCL")][0]
            ok = ~np.isin(scl, INVALID_SCL) & (b8 > 0) & (b12 > 0)
            if mode == "offset":
                b8 = (b8 - 1000.0) / 10000.0; b12 = (b12 - 1000.0) / 10000.0
                ok &= (b8 > 0) & (b12 > 0)
            with np.errstate(invalid="ignore", divide="ignore"):
                return (b8 - b12) / (b8 + b12), ok
        n0, ok0 = nbr(pre); n1, ok1 = nbr(post)
        ok = (ok0 & ok1).ravel()[inside]
        dn = (n0 - n1).ravel()[inside]
        nv = np.bincount(idx, weights=ok.astype(float), minlength=H * W)
        res = {"n_valid": nv}
        for th in THR:
            res[th] = np.bincount(idx, weights=(ok & (dn >= th)).astype(float), minlength=H * W)
        out[mode] = res
    out["n_inside"] = np.bincount(idx, minlength=H * W).astype(float)
    return out


def cell_state(stats_by_tile, mode, th):
    """1 burned, 0 unburned, -1 not assessable. Per cell: the tile with more valid pixels."""
    nv = np.stack([s[mode]["n_valid"] for s in stats_by_tile]); nb = np.stack([s[mode][th] for s in stats_by_tile])
    k = nv.argmax(0)
    v = np.take_along_axis(nv, k[None], 0)[0]; b = np.take_along_axis(nb, k[None], 0)[0]
    st = np.full(H * W, -1, int)
    ass = v >= MIN_VALID * NPIX
    st[ass] = (b[ass] >= BURN_FRAC * v[ass]).astype(int)
    return st.reshape(H, W), (v / NPIX).reshape(H, W)


def load_discs():
    d = json.loads((REPO / "research/kcf-replay/fire_discs.json").read_text())["discs"]
    return [dict(x, t=datetime.fromisoformat(x["t_utc"])) for x in d]


def centres():
    cx = X0 + (np.arange(W) + 0.5) * RES; cy = Y0 - (np.arange(H) + 0.5) * RES
    return np.meshgrid(cx, cy)


def dist_to_discs(discs, CX, CY):
    d = np.full(CX.shape, np.inf)
    if not discs:
        return d
    Xd = np.array([x["x"] for x in discs]); Yd = np.array([x["y"] for x in discs]); Rd = np.array([x["r_m"] for x in discs])
    fx, fy = CX.ravel(), CY.ravel(); out = np.full(fx.shape, np.inf)
    for i in range(0, len(discs), 500):
        dd = np.sqrt((fx[:, None] - Xd[None, i:i + 500]) ** 2 + (fy[:, None] - Yd[None, i:i + 500]) ** 2) - Rd[None, i:i + 500]
        out = np.minimum(out, np.maximum(dd, 0).min(1))
    return out.reshape(CX.shape)


def confusion(model, sat, dom):
    m = model & dom; s = sat == 1
    ass = (sat >= 0) & dom
    hit = int((m & s & ass).sum()); miss = int((~m & s & ass).sum()); fa = int((m & ~s & ass).sum()); cn = int((~m & ~s & ass).sum())
    r = {"hit": hit, "miss": miss, "false_alarm": fa, "correct_negative": cn, "assessable": int(ass.sum()),
         "not_assessable_in_domain": int((dom & (sat < 0)).sum()), "satellite_burned": hit + miss, "model_reached": hit + fa}
    r["POD"] = hit / (hit + miss) if hit + miss else None
    r["FAR"] = fa / (hit + fa) if hit + fa else None
    r["CSI"] = hit / (hit + miss + fa) if hit + miss + fa else None
    return r


def main(s2dir, outdir):
    s2dir, outdir = Path(s2dir), Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    stats = [tile_stats(s2dir, *SCENES[t]) for t in ("52SDF", "52SEF")]
    CX, CY = centres()
    toa = rasterio.open(REPO / "research/harness-2026-11/data-fetch/small/choi2026_kfs01/KFS_01_pswt_ok_toa.tif")
    assert toa.transform.c == X0 and toa.transform.f == Y0 and toa.shape == (H, W)
    TOA = toa.read(1).astype(float)
    t0 = datetime.fromisoformat(toa.tags()["t0_utc"].replace(" ", "T") + "+00:00")
    h_s = (T_S - t0).total_seconds() / 3600.0
    v1 = np.isfinite(TOA) & (TOA <= h_s)
    discs = load_discs()
    v2 = dist_to_discs([d for d in discs if d["t"] < T_S], CX, CY) == 0
    near_footprint = dist_to_discs([{"x": float(x), "y": float(y), "r_m": 0.0, "t": T_S} for x, y in zip(CX[np.isfinite(TOA)], CY[np.isfinite(TOA)])], CX, CY) <= 10000.0
    zones, info = {}, {}
    for H_h, T in ((8, datetime(2025, 3, 23, 18, 0, tzinfo=timezone.utc)), (5, datetime(2025, 3, 23, 21, 0, tzinfo=timezone.utc))):
        r5, r8, cls, inf = MA.curve("MEASURED", discs, T, H_h)
        R = r8 if H_h == 8 else r5
        known_T = [d for d in discs if d["t"] < T]
        dT = dist_to_discs(known_T, CX, CY)
        zones[H_h] = (dT <= R, dT, known_T)
        info[H_h] = {"T_utc": T.isoformat(), "class": cls, "R5_km": r5 / 1000, "R8_km": r8 / 1000, "R_used_km": R / 1000,
                     "discs_before_T": len(known_T), "zone_target_time_utc": (T + timedelta(hours=H_h)).isoformat()}
    res = {"label": "Model output on reconstructed inputs. Not what happened to people.",
           "protocol": "research/kcf-validate/PROTOCOL.md §2 + amendment 1", "t_S_utc": T_S.isoformat(),
           "choi_t0_utc": t0.isoformat(), "choi_hours_at_t_S": h_s,
           "scene_sha256": {l.split()[1]: l.split()[0] for l in (s2dir / "sha256.txt").read_text().splitlines()},
           "lattice": {"x0": X0, "y0": Y0, "res": RES, "cols": W, "rows": H}, "zones": info, "maps": {}}
    figdata = {}
    for mode in ("raw", "offset"):
        for th in THR:
            sat, valid = cell_state(stats, mode, th)
            key = f"{mode}_dnbr{th}"
            D1 = np.ones((H, W), bool); D2 = near_footprint
            ent = {"cells": H * W, "burned": int((sat == 1).sum()), "unburned": int((sat == 0).sum()), "not_assessable": int((sat < 0).sum()),
                   "burned_area_km2_375m_cells": float((sat == 1).sum() * RES * RES / 1e6)}
            for name, model in (("V1_Choi_toa", v1), ("V2_known_area_discs", v2), ("V3_MEASURED_8h_zone", zones[8][0]), ("V4_MEASURED_5h_zone", zones[5][0])):
                ent[name] = {"D1_all_assessable": confusion(model, sat, D1), "D2_within_10km_of_Choi_footprint": confusion(model, sat, D2)}
            for H_h in (8, 5):
                zone, dT, known_T = zones[H_h]
                newb = (sat == 1) & ~(dT == 0)
                dd = dT[newb]
                R = info[H_h]["R_used_km"] * 1000
                ent[f"coverage_newly_burned_{H_h}h"] = {
                    "n_burned_not_in_known_area_at_T": int(newb.sum()), "n_inside_zone": int((newb & zone).sum()),
                    "coverage": float((newb & zone).sum() / newb.sum()) if newb.sum() else None,
                    "dist_km_p10_p50_p90_max": [float(np.percentile(dd, q) / 1000) for q in (10, 50, 90)] + [float(dd.max() / 1000)] if dd.size else None,
                    "R_km": R / 1000, "n_beyond_R": int((newb & ~zone).sum())}
            res["maps"][key] = ent
            if mode == "raw" and th == 0.10:
                figdata = {"sat": sat, "v1": v1, "v2": v2, "v3": zones[8][0], "valid": valid}
    (outdir / "satellite_extent.json").write_text(json.dumps(res, indent=1))
    np.savez_compressed(outdir / "maps.npz", **{k: v for k, v in figdata.items()})
    print(json.dumps({k: res["maps"][k]["burned"] for k in res["maps"]}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
