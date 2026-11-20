"""Test B record script: aluminium corner reflector at 2, 3, 4 or 5 m in front of the radar, one condition per run:
nothing / flame / smoke (smoke only, no flame) / mist (water mist). See protocols/B_radar.md.

The flame AND smoke conditions refuse to run unless --risk-assessment points to an existing scan/PDF of the signed
risk assessment and --supervisor NAME is given (both stored in trial.json): a smouldering smoke source still burns
(protocols/B_radar.md, Safety). Other conditions record them if given.
Flame source: as approved in the signed risk assessment; the analysis assumes a Bunsen-size flame. The flame
condition needs --flame-kind bunsen|other (stored as trial.json `flame_kind` and `bunsen_burner`); the analysis
flags every non-Bunsen flame run. The free-text --flame-source is recorded, never matched.

Flux-disc stop (recordkit.DiscGuard): any run stops and warns when the flux disc (PETG tabs) reads >= 70 C; flame
and smoke runs also stop when the disc temperature is missing / faulted for > 2 s during condition_on.

Run roles: `baseline` (nothing in the path; the analysis builds crossing.radar_flame.RadarBaseline from it) and
`trial` (pre -> condition_on -> condition_off, timed).

Usage (from apps/crossing):
  .venv/bin/python -m field_tests.b_radar_record --distance-m 3 --condition nothing --role baseline
  .venv/bin/python -m field_tests.b_radar_record --distance-m 3 --condition flame --repeat 1 \
      --flame-kind bunsen --flame-source "Bunsen burner, air hole closed" --risk-assessment ~/ra.pdf \
      --supervisor "A. Adult"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common, recordkit  # noqa: E402

CONDITIONS = ("nothing", "flame", "smoke", "mist")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Test B: radar vs corner reflector under four conditions")
    p.add_argument("--distance-m", type=float, required=True, help="radar face to reflector apex (2, 3, 4 or 5 m)")
    p.add_argument("--condition", choices=CONDITIONS, required=True)
    p.add_argument("--role", choices=("trial", "baseline"), default="trial")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--flame-distance-m", type=float, help="radar to the flame/smoke/mist on the line of sight "
                                                          "(default: half the reflector distance)")
    p.add_argument("--flame-source", default="", help="required for the flame condition (what burns, its size)")
    p.add_argument("--flame-kind", choices=("bunsen", "other"),
                   help="required for the flame condition: 'bunsen' (the source the analysis assumes) or 'other' "
                        "(as approved in the signed risk assessment; flagged by the analysis)")
    p.add_argument("--smoke-source", default="", help="smoke condition: what makes the smoke (no flame in view)")
    p.add_argument("--mist-source", default="", help="mist condition: nozzle / sprayer and water flow")
    p.add_argument("--reflector", default="aluminium trihedral corner reflector, edge ___ mm")
    common.add_risk_args(p, "required for --condition flame and --condition smoke")
    p.add_argument("--pre-s", type=float, default=10.0)
    p.add_argument("--duration-s", type=float, default=30.0)
    p.add_argument("--post-s", type=float, default=10.0)
    p.add_argument("--pi", default=common.DEFAULT_PI_URL)
    p.add_argument("--operator", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--out", default=str(common.RECORDS / "B"))
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    gate = {}
    if args.condition in ("flame", "smoke"):         # a smouldering smoke source still burns: same gate
        gate = common.gate_or_exit(args)
        if args.condition == "flame" and not args.flame_source.strip():
            print("refusing to run: --flame-source is required for the flame condition", file=sys.stderr)
            return 2
        if args.condition == "flame" and not args.flame_kind:
            print("refusing to run: --flame-kind bunsen|other is required for the flame condition", file=sys.stderr)
            return 2
    elif args.risk_assessment or args.supervisor:
        gate = common.gate_or_exit(args)
    if args.role == "baseline" and args.condition != "nothing":
        print("refusing to run: a baseline run must use --condition nothing", file=sys.stderr)
        return 2
    if not args.distance_m > 0:
        print("refusing to run: --distance-m must be > 0", file=sys.stderr)
        return 2
    fd = args.flame_distance_m if args.flame_distance_m else args.distance_m / 2.0
    run_id = "B_d%.1f_%s_%s_r%d_%s" % (args.distance_m, args.condition, args.role, args.repeat, common.utc_stamp())
    trial = common.base_meta("B", argv)
    trial.update({"run_id": run_id, "distance_m": args.distance_m, "condition": args.condition, "role": args.role,
                  "repeat": args.repeat, "flame_distance_m": fd, "flame_source": args.flame_source,
                  "flame_kind": args.flame_kind if args.condition == "flame" else None,
                  "bunsen_burner": (args.flame_kind == "bunsen") if args.condition == "flame" else None,
                  "smoke_source": args.smoke_source, "mist_source": args.mist_source, "reflector": args.reflector,
                  "operator": args.operator, "notes": args.notes, "simulated": False, "pi_url": args.pi})
    trial.update(gate)
    if args.role == "baseline":
        phases = [("baseline", args.duration_s, "Nothing in the path. Nobody moves inside the radar view")]
    else:
        what = {"nothing": "Nothing (control run): keep the path clear",
                "flame": "Light / place the flame on the mark at %.2f m" % fd,
                "smoke": "Start the smoke at %.2f m (NO flame in view)" % fd,
                "mist": "Start the water mist at %.2f m" % fd}[args.condition]
        phases = [("pre", args.pre_s, "Path clear, condition OFF"),
                  ("condition_on", args.duration_s, what),
                  ("condition_off", args.post_s, "Condition OFF / remove it")]
    run_dir = Path(args.out) / run_id
    print("TEST B - %s at %.1f m (%s). Recording to %s" % (args.condition, args.distance_m, args.role, run_dir))
    recordkit.record_run(args.pi, run_dir, trial, phases,
                         plate_phases=("condition_on",) if args.condition in ("flame", "smoke") else None)
    return recordkit.report_end(trial, run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
