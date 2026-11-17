"""Test C record script: thermal camera near-edge distance at set distances and tilts (no flame; a heated panel
standing on the ground is the near-edge stand-in). See protocols/C_thermal.md and sheets/C_inputs.yaml.

Each run records the thermal frames (wire rate, 4 Hz) and the IMU while the panel's bottom edge is at the
tape-measured distance and the camera body is tilted by the nominal angle (wedge).

Usage (from apps/crossing):
  .venv/bin/python -m field_tests.c_thermal_record --sheet field_tests/sheets/C_inputs.yaml \
      --distance-m 8 --tilt-deg 5 --repeat 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common, recordkit  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test C: thermal near-edge distance (record one run)")
    p.add_argument("--sheet", required=True)
    p.add_argument("--distance-m", type=float, required=True, help="TRUE distance (tape) to the panel bottom edge")
    p.add_argument("--tilt-deg", type=float, required=True, help="nominal wedge tilt of the camera body")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--duration-s", type=float, default=10.0)
    p.add_argument("--pi", default=common.DEFAULT_PI_URL)
    p.add_argument("--operator", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--out", default=str(common.RECORDS / "C"))
    args = p.parse_args(argv)
    sp = Path(args.sheet)
    if not sp.is_file():
        print("refusing to run: sheet not found: %s" % sp, file=sys.stderr)
        return 2
    import yaml
    sheet = yaml.safe_load(sp.read_text()) or {}
    if not args.distance_m > 0:
        print("refusing to run: --distance-m must be > 0", file=sys.stderr)
        return 2
    run_id = "C_d%.2f_tilt%+.1f_r%d_%s" % (args.distance_m, args.tilt_deg, args.repeat, common.utc_stamp())
    trial = common.base_meta("C", argv)
    trial.update({"run_id": run_id, "distance_m": args.distance_m, "tilt_deg": args.tilt_deg,
                  "tilt_axis": sheet.get("tilt_axis", "pitch"), "repeat": args.repeat, "sheet": sheet,
                  "operator": args.operator, "notes": args.notes, "simulated": False, "pi_url": args.pi})
    phases = [("hold", args.duration_s, "Panel bottom edge at %.2f m, camera tilted %+.1f deg: HOLD STILL"
               % (args.distance_m, args.tilt_deg))]
    run_dir = Path(args.out) / run_id
    print("TEST C - recording to %s" % run_dir)
    recordkit.record_run(args.pi, run_dir, trial, phases)
    print("Done: %s" % run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
