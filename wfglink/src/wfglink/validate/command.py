"""`python -m wfglink validate --suite led|core|mismatch|coverage`.

led: the dashcam LED turntable test, room test and night drive (validate/led_suite.py).
core, mismatch, coverage: the synthetic suites, generated and evaluated by scripts/run_suite.py
(run as a subprocess, so its own options and records behave exactly as when it runs alone).
mismatch and coverage are held out (plan 4.1): they supply the headline numbers and the
interval coverage, so they must never be used for tuning, and they run only with --final.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

from wfglink import PROJECT_ROOT

SUITES = ("led", "core", "mismatch", "coverage")
HELD_OUT = {
    "mismatch": "it supplies the headline numbers (plan 4.1)",
    "coverage": "it measures the interval coverage of the counts (plan 4.1)",
}


def synthetic_command(args: argparse.Namespace) -> list[str]:
    """The scripts/run_suite.py command line for a synthetic suite."""
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "run_suite.py"), args.suite]
    if args.workers:
        cmd += ["--workers", str(args.workers)]
    if args.tag:
        cmd += ["--tag", args.tag]
    if args.record:
        cmd.append("--record")
    if args.no_generate:
        cmd.append("--no-generate")
    return cmd


def run_validate(args: argparse.Namespace) -> int:
    if args.suite == "led":
        from wfglink.config import load_config
        from wfglink.validate.led_suite import run_led_suite

        code, _ = run_led_suite(args.raw, args.notes, args.out, load_config(*(args.config or [])),
                                max_seconds=args.max_seconds)
        return code
    if args.suite in HELD_OUT and not args.final:
        print(f"The {args.suite} suite is held out: {HELD_OUT[args.suite]}, so it is never used for tuning and "
              "runs once, on the final method. If that is now, run it again with --final:\n"
              f"  python -m wfglink validate --suite {args.suite} --final", file=sys.stderr)
        return 2
    return subprocess.call(synthetic_command(args), cwd=str(PROJECT_ROOT))


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Options of the validate command (cli.py builds the parser with these)."""
    p.add_argument("--suite", required=True, choices=SUITES,
                   help="led: dashcam LED turntable, room test and night drive; core, mismatch, coverage: synthetic")
    p.add_argument("--raw", default=None, help="led: folder with the recordings (default data/raw)")
    p.add_argument("--notes", default=None, help="led: notes file (default <raw>/led_notes.yaml)")
    p.add_argument("--out", default=None, help="led: report file (default results/validation/led_report.json)")
    p.add_argument("--max-seconds", type=float, default=None,
                   help="led: analyse at most this many seconds of each recording (quick look)")
    p.add_argument("--config", nargs="*", help="led: extra YAML config files")
    p.add_argument("--final", action="store_true", help="mismatch, coverage: this is the final, held-out run")
    p.add_argument("--workers", type=int, default=None, help="synthetic suites: worker processes")
    p.add_argument("--tag", default="", help="synthetic suites: suffix of the results/runs folder")
    p.add_argument("--record", action="store_true", help="synthetic suites: record the numbers in NUMBERS.json")
    p.add_argument("--no-generate", action="store_true", help="synthetic suites: evaluate the clips already generated")
