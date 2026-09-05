#!/usr/bin/env python
"""Is directional signal present in the LABELS at all?

Session 10 follow-up, task 5. Arm C and Arm D both modify FEATURES. Neither
touches the target. If a positive label is "this cell was newly detected as
burnt by the next overpass", and overpasses are 6-16 h apart on a 500 m grid,
then a fire advancing anisotropically still fills cells in many directions
within one step. Head-versus-flank asymmetry could be integrated out by
construction — in which case no wind feature, however well resolved, can
recover direction, and both nulls are explained upstream of the features.

This measures that on the existing labels. It changes no model, no target and
no Arm A artifact. It is a data-geometry analysis, not a new arm.

Per fire, per label step k -> k+1:

* bearings of every newly-burnt cell, in TWO reference frames:
  - CENTROID: from the centroid of the previous footprint. This is the fire's
    direction of travel and is what "anisotropy" means physically.
  - PERIMETER: from the NEAREST previously-active cell. This is exactly the
    frame `wind_alignment` uses, so it is the one the model actually sees.
* circular concentration R = |mean unit vector| in each frame. R -> 1 is a
  single direction; R -> 0 is isotropic growth. Circular variance is 1 - R.
* advance ratio: p90(|along dominant|) / p90(|across dominant|), centroid frame.
* the ERA5 wind bearing at the step's start, and the angular difference.

Then, across steps: how R varies with step duration, and the circular
correlation (Jammalamadaka-Sarma) between observed bearing and wind bearing,
per fire and pooled.

    python scripts/label_geometry.py --write

Writes docs/label_geometry.json and docs/figures/label_geometry_<fire>.png.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

OUT_JSON = REPO / "docs" / "label_geometry.json"
FIGDIR = REPO / "docs" / "figures"

#: A step with fewer new cells than this cannot support a stable bearing
#: distribution. Reported, never silently dropped.
MIN_NEW_CELLS = 5


def _unit_stats(east: np.ndarray, north: np.ndarray) -> tuple[float, float]:
    """Return (R, mean_bearing_deg) for a set of displacement vectors.

    R is the resultant length of the unit vectors: 1 = perfectly aligned,
    0 = isotropic. Bearing is compass degrees the growth points TOWARD, using
    the same atan2(east, north) convention as ``weather.wind_toward_deg``.
    """
    norm = np.hypot(east, north)
    keep = norm > 1e-9
    if not keep.any():
        return float("nan"), float("nan")
    ux, uy = east[keep] / norm[keep], north[keep] / norm[keep]
    mx, my = float(ux.mean()), float(uy.mean())
    R = float(np.hypot(mx, my))
    bearing = float((np.degrees(np.arctan2(mx, my)) + 360.0) % 360.0)
    return R, bearing


def _ang_diff(a: float, b: float) -> float:
    """Smallest absolute angular difference in degrees, 0-180."""
    d = abs((a - b + 180.0) % 360.0 - 180.0)
    return float(d)


def circ_corr(alpha_deg: list[float], beta_deg: list[float]) -> float | None:
    """Jammalamadaka-Sarma circular correlation coefficient."""
    a = np.radians(np.asarray(alpha_deg, dtype=float))
    b = np.radians(np.asarray(beta_deg, dtype=float))
    if len(a) < 3:
        return None
    abar = np.arctan2(np.sin(a).mean(), np.cos(a).mean())
    bbar = np.arctan2(np.sin(b).mean(), np.cos(b).mean())
    num = float(np.sum(np.sin(a - abar) * np.sin(b - bbar)))
    den = float(np.sqrt(np.sum(np.sin(a - abar) ** 2) * np.sum(np.sin(b - bbar) ** 2)))
    return None if den == 0 else num / den


def analyse_fire(fid: str) -> dict:
    from wildfireguardian.spread_v2 import data as datamod
    from wildfireguardian.spread_v2 import grid as gridmod
    from wildfireguardian.spread_v2.weather import weather_series_from_event
    from scipy.ndimage import distance_transform_edt

    ev = datamod.load_event(fid)
    g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=gridmod.DEFAULT_CELL_M)
    snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=90.0)
    ws = weather_series_from_event(ev)
    cs = g.cell_size_m

    steps: list[dict] = []
    for k in range(len(snaps) - 1):
        cur, nxt = snaps[k], snaps[k + 1]
        active = cur.cumulative_mask
        new = nxt.cumulative_mask & ~active
        dt_h = (nxt.time - cur.time).total_seconds() / 3600.0
        n_new = int(new.sum())
        rec = {"step": k, "dt_hours": round(dt_h, 3), "n_new_cells": n_new,
               "n_active_cells": int(active.sum()), "usable": False}
        if n_new < MIN_NEW_CELLS or not active.any():
            rec["reason_unusable"] = (
                f"n_new_cells={n_new} < {MIN_NEW_CELLS}" if n_new < MIN_NEW_CELLS
                else "no active footprint")
            steps.append(rec)
            continue

        rr, cc = np.nonzero(new)
        ar, ac = np.nonzero(active)
        c_r, c_c = float(ar.mean()), float(ac.mean())

        # CENTROID frame — the fire's direction of travel.
        e_cen = (cc - c_c) * cs
        n_cen = (c_r - rr) * cs
        R_cen, bear_cen = _unit_stats(e_cen, n_cen)

        # PERIMETER frame — the frame wind_alignment is computed in.
        _, (sr, sc) = distance_transform_edt(~active, return_indices=True)
        e_per = (cc - sc[rr, cc]) * cs
        n_per = (sr[rr, cc] - rr) * cs
        R_per, bear_per = _unit_stats(e_per, n_per)

        # Advance along vs across the dominant bearing (centroid frame).
        th = np.radians(bear_cen)
        ux, uy = np.sin(th), np.cos(th)          # bearing -> (east, north)
        along = e_cen * ux + n_cen * uy
        across = e_cen * (-uy) + n_cen * ux
        p90_along = float(np.percentile(np.abs(along), 90))
        p90_across = float(np.percentile(np.abs(across), 90))
        ratio = (p90_along / p90_across) if p90_across > 1e-9 else None

        rec.update({
            "usable": True,
            "R_centroid": round(R_cen, 6),
            "circular_variance_centroid": round(1.0 - R_cen, 6),
            "bearing_centroid_deg": round(bear_cen, 2),
            "R_perimeter": round(R_per, 6),
            "circular_variance_perimeter": round(1.0 - R_per, 6),
            "bearing_perimeter_deg": round(bear_per, 2),
            "advance_p90_along_m": round(p90_along, 1),
            "advance_p90_across_m": round(p90_across, 1),
            "advance_ratio_along_over_across": round(ratio, 4) if ratio else None,
        })
        if ws is not None:
            wx = ws.at(cur.time)
            rec["wind_toward_deg"] = round(float(wx["wind_toward_deg"]), 2)
            rec["wind_speed_ms"] = round(float(wx["wind_speed_ms"]), 3)
            rec["angle_obs_minus_wind_deg"] = round(
                _ang_diff(bear_cen, float(wx["wind_toward_deg"])), 2)
        steps.append(rec)

    usable = [s for s in steps if s["usable"]]
    out = {
        "fire_id": fid,
        "n_overpasses": len(snaps),
        "n_steps": len(steps),
        "n_usable_steps": len(usable),
        "min_new_cells_threshold": MIN_NEW_CELLS,
        "steps": steps,
    }
    if usable:
        Rc = np.array([s["R_centroid"] for s in usable], dtype=float)
        Rp = np.array([s["R_perimeter"] for s in usable], dtype=float)
        dt = np.array([s["dt_hours"] for s in usable], dtype=float)
        ratios = [s["advance_ratio_along_over_across"] for s in usable
                  if s["advance_ratio_along_over_across"]]
        out["summary"] = {
            "R_centroid_mean": round(float(Rc.mean()), 6),
            "R_centroid_sd": round(float(Rc.std(ddof=1)), 6) if len(Rc) > 1 else None,
            "R_centroid_min": round(float(Rc.min()), 6),
            "R_centroid_max": round(float(Rc.max()), 6),
            "R_perimeter_mean": round(float(Rp.mean()), 6),
            "R_perimeter_sd": round(float(Rp.std(ddof=1)), 6) if len(Rp) > 1 else None,
            "advance_ratio_mean": round(float(np.mean(ratios)), 4) if ratios else None,
            "dt_hours_mean": round(float(dt.mean()), 3),
            "corr_R_centroid_vs_dt": (
                round(float(np.corrcoef(Rc, dt)[0, 1]), 4)
                if len(Rc) > 2 and Rc.std() > 0 and dt.std() > 0 else None),
        }
        # Step-to-step persistence of the dominant bearing. This separates two
        # very different claims: "the labels have a direction" and "that
        # direction can be predicted from the previous step". Arm D's
        # obs_alignment assumed the second; only the first is established by R.
        consec = [(a, b) for a, b in zip(usable[:-1], usable[1:])
                  if b["step"] == a["step"] + 1]
        if len(consec) >= 3:
            out["summary"]["bearing_persistence_circ_corr"] = (
                lambda v: round(v, 4) if v is not None else None)(
                circ_corr([a["bearing_centroid_deg"] for a, _ in consec],
                          [b["bearing_centroid_deg"] for _, b in consec]))
        if consec:
            out["summary"]["mean_abs_bearing_change_deg"] = round(float(np.mean(
                [_ang_diff(a["bearing_centroid_deg"], b["bearing_centroid_deg"])
                 for a, b in consec])), 2)
            out["summary"]["n_consecutive_step_pairs"] = len(consec)

        withwind = [s for s in usable if "wind_toward_deg" in s]
        if len(withwind) >= 3:
            out["summary"]["circ_corr_obs_vs_wind"] = (
                lambda v: round(v, 4) if v is not None else None)(
                circ_corr([s["bearing_centroid_deg"] for s in withwind],
                          [s["wind_toward_deg"] for s in withwind]))
            out["summary"]["mean_abs_angle_obs_minus_wind_deg"] = round(
                float(np.mean([s["angle_obs_minus_wind_deg"] for s in withwind])), 2)
            out["summary"]["n_steps_with_wind"] = len(withwind)
    return out


def make_figure(fire: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    usable = [s for s in fire["steps"] if s["usable"]]
    fig = plt.figure(figsize=(11, 3.6))
    fig.suptitle(f"Label geometry — {fire['fire_id']}  "
                 f"({fire['n_usable_steps']}/{fire['n_steps']} usable steps)",
                 fontsize=11)

    ax1 = fig.add_subplot(1, 3, 1, projection="polar")
    ax1.set_theta_zero_location("N")
    ax1.set_theta_direction(-1)
    if usable:
        th = np.radians([s["bearing_centroid_deg"] for s in usable])
        r = [s["R_centroid"] for s in usable]
        ax1.scatter(th, r, s=26, alpha=0.75, label="observed")
        wind = [s for s in usable if "wind_toward_deg" in s]
        if wind:
            ax1.scatter(np.radians([s["wind_toward_deg"] for s in wind]),
                        [s["R_centroid"] for s in wind],
                        s=26, alpha=0.75, marker="x", label="ERA5 wind")
        ax1.legend(loc="upper right", bbox_to_anchor=(1.28, 1.14), fontsize=7)
    ax1.set_ylim(0, 1)
    ax1.set_title("bearing vs R", fontsize=9, pad=14)

    ax2 = fig.add_subplot(1, 3, 2)
    if usable:
        ax2.scatter([s["dt_hours"] for s in usable],
                    [s["R_centroid"] for s in usable], s=28, label="centroid")
        ax2.scatter([s["dt_hours"] for s in usable],
                    [s["R_perimeter"] for s in usable], s=28, marker="^",
                    alpha=0.7, label="perimeter")
        ax2.legend(fontsize=7)
    ax2.set_xlabel("step duration (h)", fontsize=8)
    ax2.set_ylabel("R (1 = one direction, 0 = isotropic)", fontsize=8)
    ax2.set_ylim(0, 1)
    ax2.axhline(0.5, ls=":", lw=0.8, color="grey")
    ax2.set_title("anisotropy vs step duration", fontsize=9)
    ax2.tick_params(labelsize=7)

    ax3 = fig.add_subplot(1, 3, 3)
    wind = [s for s in usable if "angle_obs_minus_wind_deg" in s]
    if wind:
        ax3.scatter([s["dt_hours"] for s in wind],
                    [s["angle_obs_minus_wind_deg"] for s in wind], s=28, color="tab:red")
        ax3.axhline(90, ls="--", lw=0.9, color="grey")
        ax3.text(0.02, 0.92, "90° = unrelated", transform=ax3.transAxes, fontsize=7,
                 color="grey")
    ax3.set_ylim(0, 180)
    ax3.set_xlabel("step duration (h)", fontsize=8)
    ax3.set_ylabel("|observed − ERA5 wind| (°)", fontsize=8)
    ax3.set_title("observed bearing vs wind bearing", fontsize=9)
    ax3.tick_params(labelsize=7)

    fig.tight_layout(rect=(0, 0, 1, 0.92))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    committed = json.loads(
        (REPO / "data/processed/spread_v2_lofo.json").read_text(encoding="utf-8"))
    fires = sorted(committed["per_fire_auc"])

    per_fire = [analyse_fire(f) for f in fires]

    pooled_obs, pooled_wind, all_R, all_dt = [], [], [], []
    for f in per_fire:
        for s in f["steps"]:
            if not s["usable"]:
                continue
            all_R.append(s["R_centroid"])
            all_dt.append(s["dt_hours"])
            if "wind_toward_deg" in s:
                pooled_obs.append(s["bearing_centroid_deg"])
                pooled_wind.append(s["wind_toward_deg"])

    fold_cc = {f["fire_id"]: f.get("summary", {}).get("circ_corr_obs_vs_wind")
               for f in per_fire}
    cc_vals = [v for v in fold_cc.values() if v is not None]

    # Pooled bearing persistence, over consecutive step pairs within each fire.
    pers_a, pers_b, dchange = [], [], []
    for f in per_fire:
        us = [s for s in f["steps"] if s["usable"]]
        for a, b in zip(us[:-1], us[1:]):
            if b["step"] != a["step"] + 1:
                continue
            pers_a.append(a["bearing_centroid_deg"])
            pers_b.append(b["bearing_centroid_deg"])
            dchange.append(abs((a["bearing_centroid_deg"]
                                - b["bearing_centroid_deg"] + 180) % 360 - 180))
    fold_pers = {f["fire_id"]: f.get("summary", {}).get("bearing_persistence_circ_corr")
                 for f in per_fire}
    pers_vals = [v for v in fold_pers.values() if v is not None]
    payload = {
        "schema_version": 1,
        "title": "Label geometry — is directional signal present in the target?",
        "provenance": "derived",
        "arm": "A_disclosure",
        "generated_by": "scripts/label_geometry.py",
        "what_this_measures": (
            "The angular structure of the LABELS themselves. No model, target or "
            "Arm A artifact is modified."
        ),
        "min_new_cells_threshold": MIN_NEW_CELLS,
        "pooled": {
            "n_usable_steps": len(all_R),
            "R_centroid_mean": round(float(np.mean(all_R)), 6) if all_R else None,
            "R_centroid_sd": round(float(np.std(all_R, ddof=1)), 6) if len(all_R) > 1 else None,
            "corr_R_vs_dt_hours": (
                round(float(np.corrcoef(all_R, all_dt)[0, 1]), 4)
                if len(all_R) > 2 else None),
            "circ_corr_obs_vs_wind": (
                lambda v: round(v, 4) if v is not None else None)(
                circ_corr(pooled_obs, pooled_wind)),
            "n_steps_with_wind": len(pooled_obs),
            "mean_abs_angle_obs_minus_wind_deg": round(
                float(np.mean([abs((a - b + 180) % 360 - 180)
                               for a, b in zip(pooled_obs, pooled_wind)])), 2)
            if pooled_obs else None,
        },
        "fold_circ_corr": fold_cc,
        "fold_circ_corr_spread": {
            "n_folds_with_value": len(cc_vals),
            "mean": round(float(np.mean(cc_vals)), 4) if cc_vals else None,
            "sd": round(float(np.std(cc_vals, ddof=1)), 4) if len(cc_vals) > 1 else None,
            "min": round(float(np.min(cc_vals)), 4) if cc_vals else None,
            "max": round(float(np.max(cc_vals)), 4) if cc_vals else None,
        },
        "bearing_persistence": {
            "what": ("Circular correlation between the dominant bearing at step k "
                     "and at step k+1. 'The labels have a direction' and 'that "
                     "direction is predictable from the previous step' are "
                     "different claims; R establishes only the first, and Arm D's "
                     "obs_alignment needed the second."),
            "n_consecutive_step_pairs": len(pers_a),
            "pooled_circ_corr": (lambda v: round(v, 4) if v is not None else None)(
                circ_corr(pers_a, pers_b)),
            "mean_abs_bearing_change_deg": round(float(np.mean(dchange)), 2)
            if dchange else None,
            "per_fold": fold_pers,
            "fold_spread": {
                "n_folds_with_value": len(pers_vals),
                "mean": round(float(np.mean(pers_vals)), 4) if pers_vals else None,
                "sd": round(float(np.std(pers_vals, ddof=1)), 4)
                if len(pers_vals) > 1 else None,
            },
        },
        "fires": per_fire,
    }

    if args.write:
        OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        for f in per_fire:
            make_figure(f, FIGDIR / f"label_geometry_{f['fire_id']}.png")
        print(f"wrote {OUT_JSON.relative_to(REPO)} and {len(per_fire)} figures")

    for f in per_fire:
        s = f.get("summary", {})
        print(f"  {f['fire_id']:24s} usable={f['n_usable_steps']:>3}/{f['n_steps']:<3} "
              f"R_cen={s.get('R_centroid_mean')} sd={s.get('R_centroid_sd')} "
              f"R_per={s.get('R_perimeter_mean')} "
              f"ratio={s.get('advance_ratio_mean')} "
              f"cc_wind={s.get('circ_corr_obs_vs_wind')}")
    print(f"\n  POOLED {json.dumps(payload['pooled'], indent=2)}")
    print(f"  FOLD SPREAD {json.dumps(payload['fold_circ_corr_spread'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
