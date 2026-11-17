"""Test F record script: water spray and hot-air gun on the running unit (no flame). See protocols/F_housing.md.

Timed phases (durations adjustable): baseline -> spray -> dry -> hot_air_front -> hot_air_plate -> hot_air_probe ->
cool. The laptop copy of the stream is recorded with phase marks; the Pi records its own session too (copy it next
to the run afterwards for the analysis: unit-side gaps are then separated from Wi-Fi gaps). At the end the script
asks the checklist questions (water inside, radar window damage, plate) and stores the answers in trial.json.

Flux-disc stop (recordkit.DiscGuard): the hot air must not heat the flux disc (PETG tabs) to 70 C. The run stops
and warns at a disc reading >= 70 C (crossing.yaml flux.disc_max_c, user-set) at any time, and when the disc
temperature is missing / faulted for > 2 s during the hot-air and cool phases; trial.json records stop_reason and
the script exits 3 (the checklist is still asked).

Usage (from apps/crossing):
  .venv/bin/python -m field_tests.f_housing_record --operator "..." [--spray-s 300 --hot-front-s 240 ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common, recordkit  # noqa: E402

CHECKLIST = (("water_inside", "Open the lid: any water inside (paper towel test)? [yes/no + where]"),
             ("radome_damage", "Radar window (PETG, thinned to 1.2 mm) deformed, discoloured or cracked? [yes/no]"),
             ("window_damage", "Camera hole / lens wet, damaged or blocked? [yes/no]"),
             ("plate_ok", "Plate coating, PETG tabs under the disc and thermocouple intact? [yes/no]"),
             ("notes", "Anything else (smell, condensation, loose parts)?"))


PLATE_PHASES = ("hot_air_front", "hot_air_plate", "hot_air_probe", "cool")   # disc temperature needed here


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test F: water spray and hot-air gun (record)")
    p.add_argument("--baseline-s", type=float, default=120.0)
    p.add_argument("--spray-s", type=float, default=300.0)
    p.add_argument("--dry-s", type=float, default=60.0)
    p.add_argument("--hot-front-s", type=float, default=240.0)
    p.add_argument("--hot-plate-s", type=float, default=120.0)
    p.add_argument("--hot-probe-s", type=float, default=120.0)
    p.add_argument("--cool-s", type=float, default=60.0)
    p.add_argument("--hot-air-gun", default="", help="model and setting (temperature, distance from the face)")
    p.add_argument("--spray", default="", help="nozzle / hose and approximate flow")
    p.add_argument("--operator", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--no-checklist", action="store_true", help="skip the questions at the end")
    p.add_argument("--pi", default=common.DEFAULT_PI_URL)
    p.add_argument("--out", default=str(common.RECORDS / "F"))
    a = p.parse_args(argv)
    phases = [("baseline", a.baseline_s, "Unit running dry, nothing applied"),
              ("spray", a.spray_s, "Water spray ON, all faces, keep moving the nozzle"),
              ("dry", a.dry_s, "Spray OFF"),
              ("hot_air_front", a.hot_front_s, "Hot-air gun ON at the front face and shield (not the window)"),
              ("hot_air_plate", a.hot_plate_s, "Hot-air gun on the flux plate"),
              ("hot_air_probe", a.hot_probe_s, "Hot-air gun on the air probe"),
              ("cool", a.cool_s, "Hot-air gun OFF")]
    run_id = "F_housing_%s" % common.utc_stamp()
    trial = common.base_meta("F", argv)
    trial.update({"run_id": run_id, "phases": [[k, d, t] for k, d, t in phases], "hot_air_gun": a.hot_air_gun,
                  "spray": a.spray, "operator": a.operator, "notes": a.notes, "simulated": False, "pi_url": a.pi})
    run_dir = Path(a.out) / run_id
    print("TEST F - recording to %s (type a note + Enter for an operator mark)" % run_dir)
    recordkit.record_run(a.pi, run_dir, trial, phases, plate_phases=PLATE_PHASES)
    if not a.no_checklist and sys.stdin and sys.stdin.isatty():
        answers = {}
        for key, q in CHECKLIST:
            answers[key] = input(q + " ").strip()
        trial["checklist"] = answers
        common.write_json(run_dir / "trial.json", trial)
    rc = recordkit.report_end(trial, run_dir)
    print("Copy the Pi session next to it and run f_housing_analyse.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
