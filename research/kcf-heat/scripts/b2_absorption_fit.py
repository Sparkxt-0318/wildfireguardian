"""Diagnostic for B.2: how much gray absorption makes the voxel sum match FDS's own radiometers?

    python scripts/b2_absorption_fit.py HRRPUV_1S.npz B2.json

Voxel sum (chi * HRRPUV, isotropic) with Beer-Lambert attenuation exp(-(kf * L_flame + ka * r)) on each voxel-to-
receiver ray: L_flame = path length inside cells with HRRPUV > 1 kW/m3 (48-point ray sampling), r = ray length.
Grid search over kf (flame-zone absorption) and ka (path absorption). This is a FIT used to interpret FDS's result, not a
model of the fire: it says what optical depth the FDS radiation field behaves as if it had.
"""
import json
import sys

import numpy as np

XR = {"RAD_X080": 80.0, "RAD_X090": 90.0, "RAD_X102": 102.0, "RAD_X105": 105.0, "RAD_X108": 108.0}


def main(vol, b2):
    z = np.load(vol); h = z["hrrpuv_kw_m3"]; t = z["time_s"]; x = z["x_m"]; y = z["y_m"]; zz = z["z_m"]
    b = json.load(open(b2)); chi = b["radiant_fraction"]; samples = b["samples"][::2]
    X0, Y0 = x[0] - 0.5, y[0] - 0.5
    Zc, Yc, Xc = np.meshgrid(zz, y, x, indexing="ij")

    def flux(hk, rec, kf, ka, nseg=48):
        m = hk > 1.0
        xs, ys, zs, hs = Xc[m], Yc[m], Zc[m], hk[m]
        rx, ry, rz = xs - rec[0], ys - rec[1], zs - rec[2]; r2 = rx * rx + ry * ry + rz * rz; r = np.sqrt(r2)
        cos = np.clip(-rx / r, 0, None)
        s = (np.arange(nseg) + 0.5) / nseg
        px = xs[:, None] + (rec[0] - xs)[:, None] * s; py = ys[:, None] + (rec[1] - ys)[:, None] * s
        pz = zs[:, None] + (rec[2] - zs)[:, None] * s
        ix = np.clip(np.floor(px - X0).astype(int), 0, len(x) - 1); iy = np.clip(np.floor(py - Y0).astype(int), 0, len(y) - 1)
        iz = np.clip(np.floor(pz).astype(int), 0, len(zz) - 1)
        lf = (hk[iz, iy, ix] > 1.0).mean(axis=1) * r
        return float((chi * hs * cos / (4 * np.pi * r2) * np.exp(-(kf * lf + ka * r))).sum())

    fds = np.array([s["fds"] for s in samples]); d = np.array([s["d"] for s in samples])
    out = []
    for kf in (0.0, 0.3, 0.6, 1.0):
        for ka in (0.0, 0.03, 0.06):
            q = np.array([flux(h[int(np.argmin(abs(t - s["t"])))].astype(float), (XR[s["device"]], 0.0, 1.5), kf, ka) for s in samples])
            lr = np.log(q / fds)
            out.append({"kappa_flame_per_m": kf, "kappa_path_per_m": ka, "geomean_model_over_fds": float(np.exp(lr.mean())),
                        "d_lt_8": float(np.exp(lr[d < 8].mean())), "d_ge_20": float(np.exp(lr[d >= 20].mean())),
                        "rms_log": float(np.sqrt((lr ** 2).mean())), "n": int(len(samples))})
            print(json.dumps(out[-1]), flush=True)
    best = min(out, key=lambda r: r["rms_log"])
    print("best", json.dumps(best))


if __name__ == "__main__":
    main(*sys.argv[1:3])
