#!/usr/bin/env python
"""Session 19 — how long after the report does GK2A first see the fire?

Korea's wildfire detection is almost entirely human. GK2A scans the Peninsula
every 2 minutes, so cadence is not the constraint — sensitivity is. This
measures, for the fires in the training set that the archive covers, the delay
between the recorded 발생일시 and the first infrared anomaly GK2A can resolve.

    python scripts/gk2a_detection.py --fire yeongdeok_2025
    python scripts/gk2a_detection.py --control          # no-fire false alarms
    python scripts/gk2a_detection.py --collect

⚠⚠ THE REFERENCE TIME IS A REPORT TIME, NOT AN IGNITION TIME.
``docs/data_provenance/fire_manifest.json`` records 발생일시 as the fire's
``start``. For a fire found by an eyewitness — and 99 % of Korean fire reports
are eyewitness reports — that timestamp is *derived from the report itself*.
So every delay below is **detection relative to report**, not detection relative
to ignition. The true ignition is earlier by an unknown amount, which means the
delays here are LOWER BOUNDS on the satellite's lag behind the actual fire, and
they cannot be read as "the satellite was X minutes slow". This caveat travels
with every number this script produces and is repeated in the artifact.

THE DETECTOR, AND WHY ITS THRESHOLD IS NOT TUNED
------------------------------------------------
The mid-infrared / window contrast is what every operational fire product is
built on: a flaming front is far brighter at 3.8 μm than at 11 μm, while clouds
and warm ground are not. Channels here are GK2A ``sw038`` (3.8 μm) and
``ir112`` (11.2 μm), the closest AMI pair to the 3.9/11 μm convention.

A CONTEXTUAL test is used rather than a fixed cutoff, because a fixed cutoff is
exactly where tuning hides. Daytime solar reflection alone lifts the background
contrast to +6…+8 K over Korea (measured, §Phase 0), so any fixed number would
have to be picked against the data it is then applied to. Instead each candidate
pixel is compared with its own surroundings at that same minute:

    flag  <=>  BT₃.₈ > mean_bg(BT₃.₈) + K·sd_bg(BT₃.₈)
          and  ΔT    > mean_bg(ΔT)    + K·sd_bg(ΔT)
          and  ΔT    > DELTA_FLOOR_K

with **K = 4 fixed before any fire was examined**, the conventional choice in
this algorithm family, and a small absolute floor so a numerically tiny
background sd cannot manufacture a detection. The floor and K are NOT adjusted
afterwards: ``--control`` measures the false-alarm rate at these same settings
over fire-free periods, which is what makes the choice checkable instead of
merely asserted. A detector with an unmeasured false-alarm rate is not a
detector.

⚠ THE BACKGROUND IS CONTAMINATED, AND BOTH ESTIMATORS ARE THEREFORE REPORTED.
The 영덕 and 의성·안동 fires ignited on the same day **66 km apart** — inside
each other's 30–80 km background annulus. Measured consequence: 의성 burning at
ΔT ≈ 67 K lifts 영덕's annulus standard deviation to ≈ 4 K, so the 4σ bar climbs
past 20 K and no plausible fire could ever clear it. A clean Korean night scene
has ΔT median 1.13 K and sd 0.49 K, which is what the annulus should look like.

So each step records the mean/sd background AS DECLARED and, beside it, a
**robust** background — median and 1.4826·MAD, the estimator this algorithm
family uses for exactly this reason (Giglio et al. 2003). The robust pair is
read as primary because the defect it repairs was demonstrated, not suspected;
the declared pair is kept in every record so the change is visible rather than
quietly substituted. **K stays 4 for both.** Neither was chosen after seeing a
detection.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.detection.gk2a import (      # noqa: E402
    MIR_CHANNEL, TIR_CHANNEL, geos_latlon, read_granule, s3_key)

BASE = "https://noaa-gk2a-pds.s3.amazonaws.com/"
CACHE = Path("/tmp/gk2a_cache")
OUT = REPO / "data" / "processed" / "detection"

#: Contextual threshold, in background standard deviations. FIXED A PRIORI.
K_SIGMA = 4.0
#: Absolute floor on the contrast, so a near-zero background sd cannot invent a
#: detection out of numerical noise.
DELTA_FLOOR_K = 3.0
#: Pixels within this radius of the ignition point are candidates.
TARGET_RADIUS_KM = 15.0
#: Background annulus. Far enough out not to contain the fire, close enough to
#: share illumination, view angle and airmass with it.
BG_INNER_KM, BG_OUTER_KM = 30.0, 80.0
#: ir112 colder than this at the target is taken as cloud over the fire. A
#: DIAGNOSTIC, never a filter — an obscured fire is reported as obscured.
CLOUD_BT_K = 273.0

#: Search window around the reference time, in hours. Chosen for budget, and
#: stated: a fire not seen within 8 h of its report is already far slower than
#: the human report this is compared against.
WINDOW_BEFORE_H, WINDOW_AFTER_H = 2.0, 8.0
STEP_MIN = 2                      # native LA cadence

#: The no-fire control runs over the SAME extent and the SAME clock window this
#: many days earlier, so season, solar geometry, terrain and coastline are held
#: fixed and only the fire is removed. 14 days is far enough that no smouldering
#: remains and close enough that the sun has barely moved.
CONTROL_DAYS_BEFORE = 14


def fires() -> dict:
    man = json.loads((REPO / "docs" / "data_provenance" /
                      "fire_manifest.json").read_text(encoding="utf-8"))
    return {f["id"]: f for f in man["fires"]}


def _fetch(ch: str, when: dt.datetime) -> Path | None:
    key = s3_key(ch, when)
    p = CACHE / os.path.basename(key)
    if p.exists() and p.stat().st_size > 0:
        return p
    try:
        with urllib.request.urlopen(BASE + key, timeout=90) as r:
            b = r.read()
    except Exception:                                        # noqa: BLE001
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b)
    return p


def _masks(lat, lon, ign_lat, ign_lon):
    km = np.hypot((lat - ign_lat) * 111.0,
                  (lon - ign_lon) * 111.0 * np.cos(np.radians(ign_lat)))
    return (km <= TARGET_RADIUS_KM,
            (km >= BG_INNER_KM) & (km <= BG_OUTER_KM), km)


def analyse_step(when: dt.datetime, ign_lat: float, ign_lon: float,
                 geom: dict) -> dict | None:
    pm, pt = _fetch(MIR_CHANNEL, when), _fetch(TIR_CHANNEL, when)
    if pm is None or pt is None:
        return None
    try:
        mir, tir = read_granule(pm), read_granule(pt)
    except Exception as exc:                                 # noqa: BLE001
        return {"time": when.isoformat(), "error": f"{type(exc).__name__}: {exc}"}

    if "target" not in geom:
        lat, lon = geos_latlon(tir.attrs, tir.bt.shape)
        t, b, _ = _masks(lat, lon, ign_lat, ign_lon)
        geom["target"], geom["bg"] = t, b
    tgt, bg = geom["target"], geom["bg"]

    delta = mir.bt - tir.bt
    good = (mir.quality == 0) & (tir.quality == 0) & np.isfinite(delta)
    bgm, tgm = bg & good, tgt & good
    if bgm.sum() < 50 or tgm.sum() < 1:
        return {"time": when.isoformat(), "error": "insufficient valid pixels"}

    mu_m, sd_m = float(mir.bt[bgm].mean()), float(mir.bt[bgm].std(ddof=1))
    mu_d, sd_d = float(delta[bgm].mean()), float(delta[bgm].std(ddof=1))

    def _robust(a):
        med = float(np.median(a))
        return med, 1.4826 * float(np.median(np.abs(a - med)))

    rmu_m, rsd_m = _robust(mir.bt[bgm])
    rmu_d, rsd_d = _robust(delta[bgm])

    def _flag(m_mu, m_sd, d_mu, d_sd):
        return (tgm
                & (mir.bt > m_mu + K_SIGMA * m_sd)
                & (delta > d_mu + K_SIGMA * d_sd)
                & (delta > DELTA_FLOOR_K))

    hit_decl = _flag(mu_m, sd_m, mu_d, sd_d)
    hit = _flag(rmu_m, rsd_m, rmu_d, rsd_d)          # primary: robust
    n_hit = int(hit.sum())

    tir_t = tir.bt[tgm]
    rec = {
        "time": when.isoformat(),
        "n_flagged": n_hit,                       # robust background (primary)
        "n_flagged_declared_bg": int(hit_decl.sum()),
        "bg_mir_mean_k": round(mu_m, 3), "bg_mir_sd_k": round(sd_m, 3),
        "bg_delta_mean_k": round(mu_d, 3), "bg_delta_sd_k": round(sd_d, 3),
        "bg_mir_median_k": round(rmu_m, 3), "bg_mir_mad_sd_k": round(rsd_m, 3),
        "bg_delta_median_k": round(rmu_d, 3), "bg_delta_mad_sd_k": round(rsd_d, 3),
        "target_delta_max_k": round(float(delta[tgm].max()), 3),
        "target_mir_max_k": round(float(mir.bt[tgm].max()), 3),
        "target_tir_median_k": round(float(np.median(tir_t)), 3),
        "target_frac_below_cloud_bt": round(float((tir_t < CLOUD_BT_K).mean()), 4),
        "n_target_px": int(tgm.sum()), "n_bg_px": int(bgm.sum()),
    }
    if n_hit:
        rec["hit_delta_max_k"] = round(float(delta[hit].max()), 3)
        rec["hit_mir_max_k"] = round(float(mir.bt[hit].max()), 3)
    for p in (pm, pt):                    # keep the cache bounded
        try:
            p.unlink()
        except OSError:
            pass
    return rec


def scan(label: str, ign_lat: float, ign_lon: float, t0: dt.datetime,
         before_h: float, after_h: float) -> dict:
    steps = [t0 - dt.timedelta(hours=before_h) + dt.timedelta(minutes=STEP_MIN * i)
             for i in range(int((before_h + after_h) * 60 // STEP_MIN) + 1)]
    cache_p = OUT / "steps" / f"{label}.json"
    cache_p.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if cache_p.exists():
        done = {r["time"]: r for r in json.loads(cache_p.read_text())["steps"]}

    todo = [s for s in steps if s.isoformat() not in done]
    geom: dict = {}
    # Prefetch in parallel, then analyse serially — the network is the cost.
    for i in range(0, len(todo), 24):
        chunk = todo[i:i + 24]
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            list(ex.map(lambda w: (_fetch(MIR_CHANNEL, w), _fetch(TIR_CHANNEL, w)),
                        chunk))
        for w in chunk:
            r = analyse_step(w, ign_lat, ign_lon, geom)
            if r is not None:
                done[w.isoformat()] = r
        cache_p.write_text(json.dumps(
            {"label": label, "reference_time_utc": t0.isoformat(),
             "ignition": [ign_lon, ign_lat],
             "steps": [done[k] for k in sorted(done)]}, indent=1) + "\n",
            encoding="utf-8")
        print(f"    {min(i+24, len(todo))}/{len(todo)} steps", flush=True)
    return {"label": label, "n_steps": len(done),
            "steps": [done[k] for k in sorted(done)]}


#: Flaming-front temperatures the sub-pixel area estimate is bracketed over.
#: A single value would state a precision this method does not have.
FLAME_T_K = (600.0, 750.0, 900.0)
#: GK2A LA infrared pixel: 2 km nominal, so 4 km² of ground per pixel.
PIXEL_AREA_KM2 = 4.0


def _planck_wn(T: float, lam_um: float) -> float:
    """Planck radiance at wavenumber, W·m⁻²·sr⁻¹·(m⁻¹)⁻¹."""
    h, c, k = 6.62606957e-34, 299792458.0, 1.3806488e-23
    nu = 1.0 / (lam_um * 1e-6)
    return 2 * h * c**2 * nu**3 / (np.expm1(h * c * nu / (k * T)))


def sub_pixel_area(mir_bt: float, bg_bt: float, lam_um: float = 3.8) -> dict:
    """Fire area inside one pixel, from the MIR radiance excess (Dozier 1981).

    Treats the pixel as two components — a fraction ``p`` at flaming temperature
    ``Tf`` and the remainder at the background temperature — and solves the
    single MIR equation for ``p`` with ``Tf`` ASSUMED:

        B(mir_bt) = p·B(Tf) + (1-p)·B(bg_bt)

    ⚠ This is an order-of-magnitude estimate and nothing more. ``Tf`` is not
    measured, the two-component model ignores smouldering and the mixed
    emissivity of a real front, and ``p`` varies by roughly a factor of three
    across the plausible ``Tf`` range — which is why the range is reported
    rather than a single number.
    """
    obs, bg = _planck_wn(mir_bt, lam_um), _planck_wn(bg_bt, lam_um)
    out = {}
    for tf in FLAME_T_K:
        p = (obs - bg) / (_planck_wn(tf, lam_um) - bg)
        out[f"Tf_{int(tf)}K"] = {
            "fire_fraction": round(float(p), 8),
            "fire_area_km2": round(float(p * PIXEL_AREA_KM2), 6),
            "fire_area_ha": round(float(p * PIXEL_AREA_KM2 * 100.0), 4),
        }
    return out


def _first_hit(steps: list[dict]) -> dict | None:
    for s in steps:
        if s.get("n_flagged", 0) > 0:
            return s
    return None


def collect() -> dict:
    man = fires()
    firms = json.loads((OUT / "firms_first_detection.json").read_text(
        encoding="utf-8")) if (OUT / "firms_first_detection.json").exists() else {}

    per_fire, controls = {}, {}
    for p in sorted((OUT / "steps").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        label = d["label"]
        t0 = dt.datetime.fromisoformat(d["reference_time_utc"])
        steps = d["steps"]
        n_flag_steps = sum(1 for s in steps if s.get("n_flagged", 0) > 0)
        rec = {"n_steps": len(steps), "n_steps_flagged": n_flag_steps,
               "reference_time_utc": d["reference_time_utc"],
               "window_min": [
                   round((dt.datetime.fromisoformat(steps[0]["time"]) - t0)
                         .total_seconds() / 60),
                   round((dt.datetime.fromisoformat(steps[-1]["time"]) - t0)
                         .total_seconds() / 60)] if steps else None}
        if label.startswith("control_"):
            controls[label] = rec
            continue

        hit = _first_hit(steps)
        if hit:
            th = dt.datetime.fromisoformat(hit["time"])
            rec |= {
                "detected": True,
                "first_detection_utc": hit["time"],
                "delay_min": round((th - t0).total_seconds() / 60),
                "n_pixels": hit["n_flagged"],
                "delta_bt_k": hit["hit_delta_max_k"],
                "mir_bt_k": hit["hit_mir_max_k"],
                "bg_delta_median_k": hit["bg_delta_median_k"],
                "bg_delta_mad_sd_k": hit["bg_delta_mad_sd_k"],
                "threshold_delta_k": round(hit["bg_delta_median_k"]
                                           + K_SIGMA * hit["bg_delta_mad_sd_k"], 3),
                "target_tir_median_k": hit["target_tir_median_k"],
                "target_frac_below_cloud_bt": hit["target_frac_below_cloud_bt"],
                "sub_pixel_area": sub_pixel_area(hit["hit_mir_max_k"],
                                                 hit["bg_mir_median_k"]),
                "first_detection_declared_bg_min": next(
                    (round((dt.datetime.fromisoformat(s["time"]) - t0)
                           .total_seconds() / 60)
                     for s in steps if s.get("n_flagged_declared_bg", 0) > 0), None),
            }
        else:
            best = max(steps, key=lambda s: s.get("target_delta_max_k", -9e9))
            rec |= {
                "detected": False,
                "best_target_delta_k": best.get("target_delta_max_k"),
                "threshold_at_best_k": round(best["bg_delta_median_k"]
                                             + K_SIGMA * best["bg_delta_mad_sd_k"], 3),
                "note": "no pixel cleared the contextual threshold in this window",
            }
        rec["firms"] = firms.get(label)
        per_fire[label] = rec

    n_ctrl_steps = sum(c["n_steps"] for c in controls.values())
    n_ctrl_flag = sum(c["n_steps_flagged"] for c in controls.values())
    out = {
        "what": ("First GK2A infrared anomaly at each fire, relative to the "
                 "RECORDED 발생일시 — which is a REPORT time, not an observed "
                 "ignition. Every delay here is detection-relative-to-report."),
        "detector": {
            "channels": [f"{MIR_CHANNEL} (3.8 um)", f"{TIR_CHANNEL} (11.2 um)"],
            "k_sigma": K_SIGMA, "delta_floor_k": DELTA_FLOOR_K,
            "target_radius_km": TARGET_RADIUS_KM,
            "background_annulus_km": [BG_INNER_KM, BG_OUTER_KM],
            "background_estimator": "median + 1.4826*MAD (primary); mean + sd "
                                    "also recorded per step",
            "cadence_min": STEP_MIN,
        },
        "per_fire": per_fire,
        "false_alarms": {
            "design": (f"same extent and same clock window "
                       f"{CONTROL_DAYS_BEFORE} days before each fire"),
            "n_sites": len(controls),
            "n_steps": n_ctrl_steps,
            "n_steps_with_a_flagged_pixel": n_ctrl_flag,
            "false_alarm_rate_per_step": (round(n_ctrl_flag / n_ctrl_steps, 6)
                                          if n_ctrl_steps else None),
            "per_site": controls,
        },
    }
    (OUT / "gk2a_detection_floor.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"per_fire": {k: {kk: v[kk] for kk in v
                                       if kk not in ("sub_pixel_area",)}
                                   for k, v in per_fire.items()},
                      "false_alarms": {k: v for k, v in out["false_alarms"].items()
                                       if k != "per_site"}},
                     indent=2, ensure_ascii=False))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--fire")
    ap.add_argument("--control", help="fire id: same extent, no-fire period")
    ap.add_argument("--control-days-before", type=int, default=CONTROL_DAYS_BEFORE)
    ap.add_argument("--before", type=float, default=WINDOW_BEFORE_H)
    ap.add_argument("--after", type=float, default=WINDOW_AFTER_H)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if a.control:
        f = fires()[a.control]
        t0 = dt.datetime.fromisoformat(f["start"]).astimezone(dt.timezone.utc)
        t0 = t0.replace(tzinfo=None) - dt.timedelta(days=a.control_days_before)
        t0 -= dt.timedelta(minutes=t0.minute % STEP_MIN, seconds=t0.second)
        lon, lat = f["ignition"]
        label = f"control_{a.control}"
        print(f"  CONTROL {a.control}: {a.control_days_before} days before the "
              f"fire, same extent, same clock window -> {t0}Z", flush=True)
        r = scan(label, lat, lon, t0, a.before, a.after)
        n_flag = sum(1 for s in r["steps"] if s.get("n_flagged", 0) > 0)
        print(f"  {r['n_steps']} steps, {n_flag} with a flagged pixel")
        return 0

    if a.fire:
        f = fires()[a.fire]
        t0 = dt.datetime.fromisoformat(f["start"]).astimezone(dt.timezone.utc)
        t0 = t0.replace(tzinfo=None)
        t0 -= dt.timedelta(minutes=t0.minute % STEP_MIN, seconds=t0.second)
        lon, lat = f["ignition"]
        print(f"  {a.fire}: reference {f['start']} = {t0}Z (REPORT time), "
              f"ignition ({lat}, {lon})", flush=True)
        r = scan(a.fire, lat, lon, t0, a.before, a.after)
        print(f"  {r['n_steps']} steps analysed")
    if a.collect:
        collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
