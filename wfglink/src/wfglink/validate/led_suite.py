"""The LED suite: `python -m wfglink validate --suite led` on the dashcam recordings (plan 4.4).

Reads data/raw (names and led_notes.yaml: see validate/dashcam.py), analyses every recording
found with the date stamp masked, prints one line per clip (LEDs tracked, median speed error,
or the counts per minute of the room test and the night drive) and one summary line, and
writes results/validation/led_report.json with stills in led_stills/ next to it:

- <clip>_mask.jpg for every clip: a frame (LED clips: the brightest value of each pixel, so
  the rings show) with the date-stamp mask outlined in cyan and the fitted rings in green;
- led_ruler_full.png and led_ruler_centre_2x.png: the sharpest ruler frame, for reading the
  ruler by eye (the result goes into the notes as ruler_px_per_mm).

The goal (plan 4.4) is a median absolute speed error of at most validate.led.goal_median_error_pct
over the tracks of both speeds; PASS or MISS is a result, so the exit code is 0 whenever the
suite ran, and 2 when inputs are missing or the notes need fixing.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import rel, run_record
from wfglink.validate.dashcam import (NOTES_NAME, REQUIRED, ROLES, SPEEDS, VIDEO_EXTS, boxes_px,
                                      compare_with_notes, files_cfg, find_recordings, load_notes, omega_from_notes,
                                      probe_file, stamp_boxes, write_mask_still, write_ruler_stills)
from wfglink.validate.drive import false_tracks_per_minute, room_check
from wfglink.validate.led import _led_cfg, analyse_led_clip, metric_check

SPEED_ROLES = ("led_33rpm", "led_45rpm")


def _ellipses(rings: list[dict[str, Any]]) -> list:
    return [((e[0], e[1]), (e[2], e[3]), e[4]) for e in (r["ellipse_px"] for r in rings)]


def rings_under_mask(rings: list[dict[str, Any]], boxes, size: list[int] | None) -> list[int]:
    """Indices (1 = smallest) of rings that pass through a masked box."""
    if not rings or not boxes or not size:
        return []
    w, h = size
    hit = []
    phi = np.linspace(0, 2 * math.pi, 72, endpoint=False)
    for k, r in enumerate(rings):
        ex, ey, ea, eb, ang = r["ellipse_px"]
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        u, v = 0.5 * ea * np.cos(phi), 0.5 * eb * np.sin(phi)
        x, y = ex + u * c - v * s, ey + u * s + v * c
        if any(np.any((x >= x0) & (x < x1) & (y >= y0) & (y < y1)) for x0, y0, x1, y1 in boxes_px(boxes, w, h)):
            hit.append(k + 1)
    return hit


def _fmt(v: float | None, spec: str = ".2f", unit: str = "") -> str:
    return "n/a" if v is None else f"{v:{spec}}{unit}"


def run_led_suite(raw_dir: str | Path | None = None, notes_path: str | Path | None = None,
                  out_path: str | Path | None = None, cfg: dict | None = None, max_seconds: float | None = None,
                  echo: Callable[[str], Any] = print) -> tuple[int, dict[str, Any]]:
    """Run the suite; returns (exit code, report). Prints as it goes through echo."""
    cfg = cfg or load_config()
    fc, lc = files_cfg(cfg), _led_cfg(cfg)
    raw = Path(raw_dir) if raw_dir else PROJECT_ROOT / fc["raw_dir"]
    notes_file = Path(notes_path) if notes_path else raw / NOTES_NAME
    out = Path(out_path) if out_path else PROJECT_ROOT / fc["report"]

    # Inputs ----------------------------------------------------------------------------------
    missing: list[str] = []
    if not raw.is_dir():
        missing.append(f"{rel(raw)}: folder not found (scripts/setup_mac.sh creates data/raw)")
    recs, problems, ignored = find_recordings(raw)
    missing += problems
    for role in REQUIRED:
        if role not in recs and not any(p.startswith(role + ":") for p in problems):
            missing.append(f"{role}: no file {role}.<ext>, or parts {role}_a.<ext>, {role}_b.<ext>, ... "
                           f"(<ext> one of {' '.join(VIDEO_EXTS)})")
    notes, note_errors, warnings = load_notes(notes_file, cfg)
    missing += note_errors
    probes: dict[str, dict[str, Any]] = {}
    for rec in recs.values():
        for p in rec.files:
            probes[p.name] = probe_file(p)
            if "error" in probes[p.name]:
                missing.append(f"{p.name}: cannot be opened as a video ({probes[p.name]['error']}). A file the "
                               "dashcam was writing when it lost power is often unreadable: leave it out and rename "
                               "the other parts so the letters have no gap")
    if missing:
        echo(f"Cannot run the LED suite. Fix these in {rel(raw)}, then run it again:")
        for m in missing:
            echo(f"  - {m}")
        for m in ignored:
            echo(f"  note: {m}")
        return 2, {"missing": missing, "ignored": ignored}
    for rec in recs.values():
        warnings += compare_with_notes(rec.role, {p.name: probes[p.name] for p in rec.files}, notes, cfg)
    warnings += ignored

    boxes = stamp_boxes(notes["date_stamp"], cfg)
    stills = out.parent / fc["stills_dir"]
    led_secs = lc["max_seconds"] if max_seconds is None else max_seconds
    scene_secs = fc["scene_max_seconds"] if max_seconds is None else max_seconds
    stamp_text = "off" if not boxes else f"{notes['date_stamp']} (masked)"
    echo(f"LED suite on {rel(raw)} with {notes_file.name}: dashcam {notes['dashcam_model']}, "
         f"{notes['resolution'][0]}x{notes['resolution'][1]} at {notes['fps']:g} fps, date stamp {stamp_text}")
    for role in ROLES:
        rec = recs.get(role)
        if rec is None:
            echo(f"  {role:<12} not found" + ("" if role in REQUIRED else " (optional)"))
            continue
        pr = probes[rec.files[0].name]
        dur = sum(probes[p.name].get("duration_s") or 0 for p in rec.files)
        echo(f"  {role:<12} {rec.label}: {pr['width']}x{pr['height']} {pr['codec']} {_fmt(pr.get('fps'), 'g')} fps, "
             f"{dur:.0f} s")
    for w in warnings:
        echo(f"warning: {w}")

    # Analysis ---------------------------------------------------------------------------------
    clips: dict[str, Any] = {}
    for role in SPEED_ROLES:
        if role not in recs:
            continue
        rec = recs[role]
        omega = omega_from_notes(notes, role)
        echo(f"{role}: analysing {len(rec.files)} file(s), up to {led_secs:g} s ...")
        images: dict[str, Any] = {}
        res = analyse_led_clip(rec.files, omega, cfg, boxes, still="max", max_seconds=led_secs, images=images)
        res["truth"] = {"turns_timed": notes["turns_timed"], "time_s": notes[f"time_{SPEEDS[role][0]}rpm_s"],
                        "omega_rad_s": round(omega, 5), "rpm": round(60 * omega / (2 * math.pi), 3)}
        res["metric"] = metric_check(res.get("rings", []), notes["led_radius_mm"], omega, cfg,
                                     notes.get("ruler_px_per_mm"))
        _finish_led(role, res, images, boxes, stills, cfg, lc, echo)
        clips[role] = res

    if "led_ruler" in recs:
        rec = recs["led_ruler"]
        omega = omega_from_notes(notes, "led_ruler")
        echo(f"led_ruler: analysing {len(rec.files)} file(s), up to {led_secs:g} s ...")
        images = {}
        res = analyse_led_clip(rec.files, omega, cfg, boxes, still="sharp", max_seconds=led_secs, images=images)
        res["truth"] = ({"ruler_rpm": notes["ruler_rpm"], "omega_rad_s": round(omega, 5)} if omega else
                        {"status": "no speed truth: ruler_rpm is not 33 or 45 in the notes"})
        if notes.get("ruler_rpm") == 0 and not res.get("rings"):
            res["problem"] = (f"turntable stopped (ruler_rpm 0), so there are no rings to fit; "
                              f"{res.get('tracks_static', 0)} static lights tracked")
        if images.get("still") is not None:
            res["ruler_stills"] = {k: rel(v) for k, v in write_ruler_stills(images["still"], stills, "led_ruler").items()}
        if omega and res.get("rings"):
            res["metric"] = metric_check(res["rings"], notes["led_radius_mm"], omega, cfg, notes.get("ruler_px_per_mm"))
        _finish_led("led_ruler", res, images, boxes, stills, cfg, lc, echo)
        if "ruler_stills" in res:
            echo(f"  ruler stills for reading by eye: {res['ruler_stills']['full']}, {res['ruler_stills']['centre_2x']}")
        clips["led_ruler"] = res

    if "room_test" in recs:
        rec = recs["room_test"]
        echo(f"room_test: analysing {len(rec.files)} file(s) ...")
        images = {}
        res = room_check(rec.files, cfg, scene_secs, boxes, images=images)
        res["probe"] = probes[rec.files[0].name]
        if images.get("still") is not None:
            res["still"] = rel(write_mask_still(images["still"], boxes, stills / "room_test_mask.jpg", cfg,
                                                rings=_ellipses(res["led_rings"]), title="room_test"))
        tm, pr = res["timing"], res["probe"]
        echo(f"room_test: {pr['width']}x{pr['height']} {pr['codec']}, {_fmt(pr.get('fps'), 'g')} fps declared, "
             f"{_fmt(tm.get('fps_measured'))} measured, {100 * tm.get('irregular_interval_fraction', 0):.1f} % irregular "
             f"frame intervals, {tm.get('repeated_frames', 0)} repeated frames; per minute: "
             f"{_fmt(res.get('detections_per_min'), '.1f')} detections, {_fmt(res.get('moving_tracks_per_min'))} moving "
             f"tracks, {_fmt(res.get('gate_crossings_per_min'))} gate crossings; LED rings found: {len(res['led_rings'])}")
        for w in res.get("warnings", []) + ([tm["warning"]] if tm.get("warning") else []):
            echo(f"  warning: {w}")
        clips["room_test"] = res

    if "night_drive" in recs:
        rec = recs["night_drive"]
        echo(f"night_drive: analysing {len(rec.files)} file(s) ...")
        images = {}
        res = false_tracks_per_minute(rec.files, cfg, scene_secs, boxes, images=images)
        if images.get("still") is not None:
            res["still"] = rel(write_mask_still(images["still"], boxes, stills / "night_drive_mask.jpg", cfg,
                                                title="night_drive"))
        echo(f"night_drive: {res['minutes']:.1f} min; false counts per minute: "
             f"{_fmt(res.get('false_gate_counts_per_min'))} gate crossings, {_fmt(res.get('false_tracks_per_min'))} "
             f"moving tracks ({_fmt(res.get('detections_per_min'), '.1f')} detections per minute)")
        for w in res.get("warnings", []) + ([res["timing"]["warning"]] if res["timing"].get("warning") else []):
            echo(f"  warning: {w}")
        clips["night_drive"] = res

    # Summary ------------------------------------------------------------------------------------
    errs = [e for role in SPEED_ROLES for e in clips.get(role, {}).get("track_errors_pct", [])]
    summary: dict[str, Any] = {"goal_median_abs_error_pct": lc["goal_pct"], "speeds": [r for r in SPEED_ROLES if r in clips],
                               "tracks": len(errs)}
    if errs:
        summary["median_abs_speed_error_pct"] = round(float(np.median(np.abs(errs))), 2)
        summary["median_speed_error_pct"] = round(float(np.median(errs)), 2)
        summary["status"] = "PASS" if summary["median_abs_speed_error_pct"] <= lc["goal_pct"] else "MISS"
        head = (f"median speed error {summary['median_abs_speed_error_pct']:.2f} % over {len(errs)} tracks at "
                f"{len(summary['speeds'])} speeds (goal at most {lc['goal_pct']:g} %): {summary['status']}")
    else:
        summary["status"] = "MISS"
        summary["reason"] = "no LED speed was measured"
        head = f"no LED speed was measured (goal at most {lc['goal_pct']:g} %): MISS"
    nd = clips.get("night_drive")
    if nd and nd.get("minutes"):
        summary["night_drive"] = {"minutes": nd["minutes"], "false_gate_counts_per_min": nd.get("false_gate_counts_per_min"),
                                  "false_tracks_per_min": nd.get("false_tracks_per_min")}
        tail = (f"night drive false counts per minute: {_fmt(nd.get('false_gate_counts_per_min'))} gate crossings, "
                f"{_fmt(nd.get('false_tracks_per_min'))} moving tracks")
    else:
        tail = "night drive: not recorded"
    echo(f"summary: {head}; {tail}")

    inputs = {p.name: p for rec in recs.values() for p in rec.files}
    report = {"suite": "led", "provenance": run_record("python -m wfglink validate --suite led", cfg, inputs=inputs),
              "raw_dir": rel(raw), "notes_file": rel(notes_file), "notes": notes, "warnings": warnings,
              "date_stamp": {"notes": notes["date_stamp"], "masked_boxes_frac": [list(b) for b in boxes]},
              "inputs": {role: {"parts": rec.parts, "files": [{"name": p.name, "bytes": p.stat().st_size,
                                                               **probes[p.name]} for p in rec.files]}
                         for role, rec in recs.items()},
              "clips": clips, "summary": summary,
              "notes_on_method": ["speed errors are per track: median over its points of measured over expected "
                                  "image speed, minus 1; expected = omega x the ring's ellipse radius at that point",
                                  "the summary pools the tracks of led_33rpm and led_45rpm only",
                                  "metric (mm/s) errors use the scale named in scale_source"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    echo(f"report: {rel(out)}")
    return 0, report


def _finish_led(role: str, res: dict[str, Any], images: dict, boxes, stills: Path, cfg: dict, lc: dict,
                echo: Callable[[str], Any]) -> None:
    """Still, mask warning and the printed lines of one LED clip."""
    rings = res.get("rings", [])
    if images.get("still") is not None:
        res["still"] = rel(write_mask_still(images["still"], boxes, stills / f"{role}_mask.jpg", cfg,
                                            rings=_ellipses(rings), title=role))
    under = rings_under_mask(rings, boxes, res.get("size_px"))
    if under:
        res.setdefault("warnings", []).append(
            f"ring {', '.join(map(str, under))} (1 = innermost) passes under the date-stamp mask, where nothing is "
            "detected; move the turntable or the dashcam so the LEDs stay clear of the stamp")
    line = f"{role}: LEDs tracked {res.get('n_rings', 0)} of {lc['n_leds']}"
    if "median_speed_error_pct" in res:
        line += (f", median speed error {res['median_speed_error_pct']:+.2f} % (absolute "
                 f"{res['median_abs_speed_error_pct']:.2f} %, {res['tracks_measured']} tracks)")
    elif res.get("problem"):
        line += f" ({res['problem']})"
    else:
        line += " (no speed truth for this clip)"
    echo(line)
    details = []
    m = res.get("metric") or {}
    if "median_error_pct" in m:
        spread = f", spread over rings {m['scale_spread_pct']:.1f} %" if m.get("scale_spread_pct") is not None else ""
        details.append(f"mm/s check {m['median_error_pct']:+.2f} % (scale {m['scale_px_per_mm']:.3f} px/mm from the "
                       f"{m['scale_source']}{spread})")
    elif m.get("status"):
        details.append(f"mm/s check: {m['status']}")
    if rings:
        details.append(f"axis ratio {min(r['axis_ratio'] for r in rings):.3f}")
    if res.get("omega_disagreement_pct") is not None:
        details.append(f"stopwatch versus video {res['omega_disagreement_pct']:+.2f} %")
    tm = res.get("timing", {})
    if tm.get("fps_measured"):
        details.append(f"{tm['fps_measured']:.2f} fps measured, {tm.get('repeated_frames', 0)} repeated frames")
    if details:
        echo("  " + "; ".join(details))
    for w in res.get("warnings", []) + ([m["warning"]] if m.get("warning") else []) + (
            [tm["warning"]] if tm.get("warning") else []):
        echo(f"  warning: {w}")
