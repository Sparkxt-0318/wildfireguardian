"""Test C analysis: near-edge distance error of the thermal camera at set distances and tilts.

Method (crossing.thermal + crossing.geometry + crossing.terrain, not re-implemented):
- mask = thermal.flame_mask(frame, t_detect_c) with the test threshold from the sheet (a heated panel stands in for
  the flame; its bottom edge on the ground stands in for the flame base).
- pose = geometry.CameraPose(camera_height_m, mount angles from the sheet); attitude = median IMU roll/pitch over
  the hold phase; ground = terrain.Profile.plane(ground_grade) from the surveyed test ground (slope_source
  "survey"; the DEM/IMU-plane choice of the app is not exercised here).
- near edge = geometry.near_edge(mask, model, pose, attitude, profile): along-ground distance to the lowest hot
  pixel's bottom edge, with its interval (+-0.5 px, +-0.5 deg pitch). Per run the median over up to 20 frames.
- The same is computed with the IMU ignored (attitude 0, 0) to show what the tilt correction is worth.
Error = estimate - tape distance (m) and relative error (%). `covered` = tape distance inside [d_lo, d_hi].

Assumptions: pinhole camera without distortion correction (TC001 lens distortion not calibrated); the tape distance
is measured to the same edge the camera sees; the panel's bottom edge reads above t_detect_c.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common  # noqa: E402
from field_tests.sessions import Run, find_runs, segment  # noqa: E402
from crossing import geometry, terrain, thermal  # noqa: E402


def camera_model(sheet: dict) -> thermal.CameraModel:
    c = sheet.get("camera") or {}
    return thermal.CameraModel(w=int(c.get("w", 256)), h=int(c.get("h", 192)), hfov_deg=float(c.get("hfov_deg", 56.0)),
                               vfov_deg=float(c.get("vfov_deg", 42.0)))


def analyse_run(run: Run, sheet: dict, max_frames: int = 20) -> dict:
    d_true = float(run.trial["distance_m"])
    row = {"run_id": run.run_id, "distance_m": d_true, "tilt_deg": float(run.trial.get("tilt_deg", 0.0)),
           "tilt_axis": run.trial.get("tilt_axis", sheet.get("tilt_axis", "pitch")),
           "repeat": run.trial.get("repeat"), "flag": ""}
    t0, t1 = run.mark_t("hold"), run.mark_t("end")
    frames = segment(run.readings("thermal"), t0, t1)
    imu = [m for m in segment(run.readings("imu"), t0, t1)
           if m["data"].get("pitch_deg") is not None and m["data"].get("roll_deg") is not None]
    if t0 is None:
        row["flag"] = "no hold mark"
        return row
    if not frames:
        row["flag"] = "no thermal frames in the hold phase"
        return row
    if not imu:
        row["flag"] = "no IMU attitude in the hold phase"
        return row
    att = geometry.Attitude(float(np.median([m["data"]["roll_deg"] for m in imu])),
                            float(np.median([m["data"]["pitch_deg"] for m in imu])))
    row["imu_roll_deg"], row["imu_pitch_deg"] = att.roll_deg, att.pitch_deg
    model = camera_model(sheet)
    pose = geometry.CameraPose(float(sheet.get("camera_height_m", 1.5)), float(sheet.get("mount_pitch_deg", 0.0)),
                               float(sheet.get("mount_roll_deg", 0.0)), float(sheet.get("mount_yaw_deg", 0.0)))
    s_max = max(40.0, 3.0 * d_true)
    profile = terrain.Profile.plane(float(sheet.get("ground_grade", 0.0)), s_max_m=s_max, ds=0.5, source="survey")
    thr = float(sheet.get("t_detect_c", 150.0))
    idx = np.unique(np.linspace(0, len(frames) - 1, min(max_frames, len(frames))).astype(int))
    ds, los, his, d0s, bad, cut = [], [], [], [], 0, 0
    for i in idx:
        try:
            temps = thermal.frame_from_reading(frames[i]["data"], frames[i]["t_mono"]).temps_k
        except Exception:  # noqa: BLE001
            bad += 1
            continue
        ok, why = thermal.validate_frame(temps, model)
        if not ok:
            bad += 1
            continue
        mask = thermal.flame_mask(temps, thr)
        ne = geometry.near_edge(mask, model, pose, att, profile)
        ne0 = geometry.near_edge(mask, model, pose, geometry.Attitude(0.0, 0.0), profile)
        if ne is None:
            bad += 1
            continue
        if ne.row >= model.h - 1 or getattr(ne, "base_cut_off", False):
            # Base cut off by the image: lowest hot pixel on the bottom row, or hot pixels in the outermost columns
            # at either side (crossing.geometry.near_edge `base_cut_off`, any reason). d_lo_m is then 0, which would
            # trivially "cover" the tape distance, and the estimate is only a bound: not used.
            cut += 1
            continue
        ds.append(ne.d_m); los.append(ne.d_lo_m); his.append(ne.d_hi_m)
        d0s.append(ne0.d_m if ne0 is not None else float("nan"))
    row.update({"n_frames": len(ds), "n_bad_frames": bad, "n_cut_off_frames": cut, "t_detect_c": thr,
                "d_min_visible_m": min_visible_distance(model, pose, att, float(sheet.get("ground_grade", 0.0)))})
    if not ds:
        if cut:
            row["flag"] = ("hot area touches the bottom image row in all %d frames: base below the field of view "
                           "(nearest visible ground about %s m), not observable" % (cut, common.fmt(
                               row["d_min_visible_m"], 1)))
        else:
            row["flag"] = ("no near edge in any frame (%d frame(s) with no pixel above %.0f C in view, or "
                           "invalid)" % (bad, thr))
        return row
    d = float(np.median(ds))
    row.update({"d_est_m": d, "d_lo_m": float(np.median(los)), "d_hi_m": float(np.median(his)),
                "d_frame_sd_m": float(np.std(ds, ddof=1)) if len(ds) > 1 else 0.0,
                "err_m": d - d_true, "err_pct": 100.0 * (d - d_true) / d_true})
    row["covered"] = bool(row["d_lo_m"] <= d_true <= row["d_hi_m"])
    d0 = float(np.nanmedian(d0s)) if np.isfinite(d0s).any() else float("nan")
    row.update({"d_no_imu_m": d0, "err_no_imu_pct": 100.0 * (d0 - d_true) / d_true if math.isfinite(d0)
                else float("nan")})
    if bad or cut:
        row["flag"] = "%d frame(s) without a near edge, %d with the base cut off by the image edge" % (bad, cut)
    return row


def min_visible_distance(model, pose, att, grade: float = 0.0) -> float:
    """Nearest ground distance (m) visible on the image centre column's bottom pixel edge (pinhole, flat or
    constant-grade ground). inf if the bottom of the image looks at or above the horizon."""
    ray = geometry.pixel_ray(model, pose, att, model.h - 0.5, model.ppx)
    if ray[0] <= 1e-9 or ray[2] >= grade * ray[0]:
        return float("inf")
    return float(pose.height_m / (grade - ray[2] / ray[0]))


def plan_coverage(rows: List[dict], sheet: dict) -> List[str]:
    """Gaps against the sheet plan (every distance x every tilt at least once), one line each."""
    dists, tilts = sheet.get("distances_m"), sheet.get("tilts_deg")
    if not dists or tilts is None:
        return ["plan: the sheet has no distances_m / tilts_deg, coverage not checked"]
    have = {(round(float(r["distance_m"]), 2), round(float(r["tilt_deg"]), 2)) for r in rows}
    return ["plan: %g m at tilt %+g deg not recorded" % (float(d), float(t)) for t in tilts for d in dists
            if (round(float(d), 2), round(float(t), 2)) not in have]


def analyse(runs_root, out, sheet: Optional[dict] = None) -> dict:
    runs = find_runs(runs_root, "C")
    if not runs:
        raise SystemExit("no test C runs under %s" % runs_root)
    out = common.out_dir(out)
    sim = common.is_simulated(*[r.simulated for r in runs])
    rows = [analyse_run(r, sheet or r.trial.get("sheet") or {}) for r in runs]
    rows.sort(key=lambda r: (r["tilt_deg"], r["distance_m"]))
    cols = ["run_id", "distance_m", "tilt_deg", "tilt_axis", "repeat", "imu_pitch_deg", "imu_roll_deg", "n_frames",
            "d_est_m", "d_lo_m", "d_hi_m", "d_frame_sd_m", "err_m", "err_pct", "covered", "d_no_imu_m",
            "err_no_imu_pct", "d_min_visible_m", "t_detect_c", "n_bad_frames", "n_cut_off_frames", "flag"]
    common.write_csv(out / "C_runs.csv", rows, cols, sim)
    _plot(out / "C_error_vs_distance.png", rows, sim)
    good = [r for r in rows if "err_pct" in r]
    flagged = [r for r in rows if r.get("flag")]
    s = common.summary([abs(r["err_pct"]) for r in good])
    s0 = common.summary([abs(r["err_no_imu_pct"]) for r in good])
    body = ["Heated panel (no flame) at %s m, tilts %s deg; threshold %s C; camera height %s m." % (
        ", ".join(sorted({"%g" % r["distance_m"] for r in rows}, key=float)),
        ", ".join(sorted({"%+g" % r["tilt_deg"] for r in rows}, key=float)),
        common.fmt(rows[0].get("t_detect_c"), 0), common.fmt((sheet or runs[0].trial.get("sheet") or {})
                                                            .get("camera_height_m"), 2)),
            "With IMU correction: |error| median %s %%, max %s %% (n = %d runs); interval covers the tape distance "
            "in %d of %d runs. Ignoring the IMU: |error| median %s %%, max %s %%." % (
                common.fmt(s["p50"], 1), common.fmt(s["max"], 1), s["n"], sum(1 for r in good if r["covered"]),
                len(good), common.fmt(s0["p50"], 1), common.fmt(s0["max"], 1)), "",
            common.md_table(rows, ["distance_m", "tilt_deg", "imu_pitch_deg", "d_est_m", "err_m", "err_pct",
                                   "d_lo_m", "d_hi_m", "covered", "err_no_imu_pct", "d_min_visible_m"],
                            ["tape (m)", "tilt (deg)", "IMU pitch", "estimate (m)", "error (m)", "error (%)",
                             "lo (m)", "hi (m)", "covered", "error, no IMU (%)", "nearest visible (m)"], nd=2)]
    if flagged:
        body += ["", "Flagged runs (as measured):"] + ["- %s: %s" % (r["run_id"], r["flag"]) for r in flagged]
    coverage = plan_coverage(rows, sheet or runs[0].trial.get("sheet") or {})
    body += ["", "Plan coverage (sheet distances x tilts): %s." % (
        "complete" if not coverage else "INCOMPLETE, protocol not completed")] + ["PROBLEM: " + c for c in coverage]
    body += ["", "A frame whose hot area is cut off by the image (lowest hot pixel on the bottom row, or hot pixels "
             "in the outermost columns at either side: crossing.geometry.near_edge base_cut_off) is not used: the "
             "base may be outside the field of view, the estimate would only be a bound and its interval would "
             "start at 0 m (trivially covering the tape distance).",
             "Flat surveyed ground; lens distortion not corrected; a panel edge is sharper than a real flame "
             "base. Files: C_runs.csv, C_error_vs_distance.png."]
    md = common.md_snippet("Test C - thermal near-edge distance vs tape", sim, body)
    (out / "C_results.md").write_text(md)
    return {"simulated": sim, "runs": rows, "markdown": md, "plan_problems": coverage}


def _plot(path, rows, sim):
    plt = common.pyplot()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 6.5), sharex=True)
    tilts = sorted({r["tilt_deg"] for r in rows})
    cm = plt.get_cmap("coolwarm")
    for i, tl in enumerate(tilts):
        rs = sorted([r for r in rows if r["tilt_deg"] == tl and "err_m" in r], key=lambda r: r["distance_m"])
        if not rs:
            continue
        c = cm(i / max(len(tilts) - 1, 1))
        x = [r["distance_m"] for r in rs]
        a1.errorbar(x, [r["err_m"] for r in rs], yerr=[[r["d_est_m"] - r["d_lo_m"] for r in rs],
                                                       [min(r["d_hi_m"] - r["d_est_m"], 50) for r in rs]],
                    fmt="o-", color=c, capsize=3, label="tilt %+g deg (IMU-corrected)" % tl)
        a2.plot(x, [r["err_pct"] for r in rs], "o-", color=c, label="tilt %+g deg" % tl)
        a2.plot(x, [r["err_no_imu_pct"] for r in rs], "x--", color=c, alpha=0.6, label="tilt %+g deg, IMU ignored" % tl)
    for a in (a1, a2):
        a.axhline(0, color="k", lw=0.8); a.grid(alpha=0.3)
    a1.set_ylabel("error (m), bars = interval"); a2.set_ylabel("error (%)"); a2.set_xlabel("tape distance (m)")
    a1.legend(fontsize=7); a2.legend(fontsize=6, ncol=2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    common.finish_figure(fig, path, "Test C: thermal near-edge distance error", sim)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test C analysis")
    p.add_argument("--runs", default=str(common.RECORDS / "C"))
    p.add_argument("--sheet", help="override the sheet stored in the runs")
    p.add_argument("--out", default=str(common.RECORDS / "C" / "analysis"))
    a = p.parse_args(argv)
    sheet = None
    if a.sheet:
        import yaml
        sheet = yaml.safe_load(Path(a.sheet).read_text())
    res = analyse(a.runs, a.out, sheet)
    print(res["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
