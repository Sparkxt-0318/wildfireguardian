"""Test A record script: flux plate in front of a BUNSEN BURNER (the only heat source permitted for test A).

Refuses to run unless --risk-assessment points to an existing scan/PDF of the adult supervisor's signed risk
assessment and --supervisor NAME is given; both go into trial.json. See protocols/A_flux_plate.md.

Run kinds (timed protocol; the script counts down and marks each phase at "NOW"):
- exposure: background (burner shielded/away) -> exposure (burner at the marked distance) -> cooldown tail.
- cooldown: heat (plate heated by the burner at close range, as allowed by the risk assessment) -> cooldown
  (burner removed, gas off, nobody touches the plate). Feeds crossing.flux.fit_cooldown in the analysis.

Flux-disc stop: the copper disc sits on printed PETG tabs. The run STOPS and warns ("STOP: flux disc at X C >= 70 C
(PETG tabs)") as soon as the disc reads >= 70 C (crossing.yaml flux.disc_max_c, user-set), or when no valid disc
temperature arrived for > 2 s (missing / faulted tc_plate); trial.json then has stop_reason DISC_OVER_70C /
DISC_TEMP_UNKNOWN and the script exits 3. Start far, step closer between runs; heat cool-down runs only to about
60 C. The guard stops the recording, not the burner: shield the burner / turn the gas off when it fires.

Usage (from apps/crossing):
  .venv/bin/python -m field_tests.a_flux_record --risk-assessment ~/ra_signed.pdf --supervisor "A. Adult" \
      --sheet field_tests/sheets/A_inputs.yaml --kind exposure --distance-m 0.15 --repeat 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "field_tests"

from field_tests import common, recordkit  # noqa: E402

HEAT_SOURCE = "Bunsen burner (test A uses a Bunsen burner only; no other flame or heater)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Test A: flux plate vs Bunsen burner (record one run)")
    common.add_risk_args(p, "required")
    p.add_argument("--sheet", required=True, help="filled-in A_inputs.yaml (gas flow, flame size, chi, ...)")
    p.add_argument("--kind", choices=("exposure", "cooldown"), required=True)
    p.add_argument("--distance-m", type=float, help="burner axis to plate front face (exposure runs)")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--pi", default=common.DEFAULT_PI_URL, help="unit WebSocket URL")
    p.add_argument("--background-s", type=float, default=60.0)
    p.add_argument("--exposure-s", type=float, default=180.0)
    p.add_argument("--heat-s", type=float, default=120.0, help="cooldown runs: heating phase length")
    p.add_argument("--cooldown-s", type=float, default=300.0)
    p.add_argument("--operator", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--out", default=str(common.RECORDS / "A"))
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    gate = common.gate_or_exit(args)                     # refuses before anything else happens
    sheet_path = Path(args.sheet)
    if not sheet_path.is_file():
        print("refusing to run: sheet not found: %s" % sheet_path, file=sys.stderr)
        return 2
    import yaml
    sheet = yaml.safe_load(sheet_path.read_text()) or {}
    if args.kind == "exposure" and not (args.distance_m and args.distance_m > 0):
        print("refusing to run: --distance-m > 0 is required for an exposure run", file=sys.stderr)
        return 2
    stamp = common.utc_stamp()
    run_id = ("A_exposure_d%.3f_r%d_%s" % (args.distance_m, args.repeat, stamp) if args.kind == "exposure"
              else "A_cooldown_r%d_%s" % (args.repeat, stamp))
    trial = common.base_meta("A", argv)
    trial.update({"run_id": run_id, "kind": args.kind, "distance_m": args.distance_m, "repeat": args.repeat,
                  "heat_source": HEAT_SOURCE, "sheet": sheet, "sheet_path": str(sheet_path.resolve()),
                  "operator": args.operator, "notes": args.notes, "simulated": False, "pi_url": args.pi})
    trial.update(gate)
    print("TEST A - heat source: %s" % HEAT_SOURCE)
    print("Supervisor: %s   risk assessment: %s" % (gate["supervisor"], gate["risk_assessment_path"]))
    if args.kind == "exposure":
        phases = [("background", args.background_s,
                   "Burner lit but SHIELDED / away. Plate in position at %.3f m. Nobody moves." % args.distance_m),
                  ("exposure", args.exposure_s, "REMOVE the shield / place the burner on the distance mark"),
                  ("cooldown", args.cooldown_s, "SHIELD / move the burner away. Leave the plate alone")]
    else:
        phases = [("heat", args.heat_s, "Heat the plate with the burner at the close-range mark"),
                  ("cooldown", args.cooldown_s, "Move the burner away and turn the gas OFF. Do not touch the plate")]
    run_dir = Path(args.out) / run_id
    print("Recording to %s (type a note + Enter for an operator mark, q to stop)" % run_dir)
    print("Flux-disc stop at %.0f C (PETG tabs): the run stops and warns at that disc temperature or when the disc "
          "temperature is missing for > 2 s." % common.disc_max_c())
    recordkit.record_run(args.pi, run_dir, trial, phases, needs_plate=True)
    return recordkit.report_end(trial, run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
