"""`python -m wfglink validate --suite ember|core|mismatch|coverage`.

ember: the "Become an ember" check (src/wfglink/ember/validate.py): synthetic phone scenes
with ground truth, then data/raw/ember_free.* and data/raw/ember_ruler.* when present.
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

SUITES = ("ember", "core", "mismatch", "coverage")
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


def run_ember(args: argparse.Namespace) -> int:
    from wfglink.config import load_config
    from wfglink.ember.validate import run_suite, summary_lines

    cfg = load_config(*(args.config or []), local=True)
    scenes = args.scenes.split(",") if args.scenes else None
    rep = run_suite(cfg, raw=args.raw, out=args.out, phones=args.phones, path_m=args.path_m, work_dir=args.work,
                    scenes=scenes, seconds=args.seconds, synthetic=not args.no_synthetic,
                    log=lambda m: print(m, file=sys.stderr, flush=True))
    for line in summary_lines(rep):
        print(line)
    print(f"-> {rep['report_path']}")
    return 0


def run_validate(args: argparse.Namespace) -> int:
    if args.suite == "ember":
        return run_ember(args)
    if args.suite in HELD_OUT and not args.final:
        print(f"The {args.suite} suite is held out: {HELD_OUT[args.suite]}, so it is never used for tuning and "
              "runs once, on the final method. If that is now, run it again with --final:\n"
              f"  python -m wfglink validate --suite {args.suite} --final", file=sys.stderr)
        return 2
    return subprocess.call(synthetic_command(args), cwd=str(PROJECT_ROOT))


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Options of the validate command (cli.py builds the parser with these)."""
    p.add_argument("--suite", required=True, choices=SUITES,
                   help="ember: phones (synthetic scenes, ember_free, ember_ruler); core, mismatch, coverage: synthetic")
    p.add_argument("--raw", default=None, help="ember: folder with ember_free.* and ember_ruler.* (default data/raw)")
    p.add_argument("--phones", type=int, default=1, help="ember: how many phones moved in ember_free (default 1)")
    p.add_argument("--path-m", type=float, default=1.0, help="ember: length of the ruler path in ember_ruler, m")
    p.add_argument("--out", default=None, help="ember: report file (default results/validation/ember_report.json)")
    p.add_argument("--work", default=None, help="ember: folder for the generated scenes (default data/synthetic/ember)")
    p.add_argument("--scenes", default=None, help="ember: only these synthetic scenes, comma separated")
    p.add_argument("--seconds", type=float, default=None, help="ember: length of each synthetic scene (quick look)")
    p.add_argument("--no-synthetic", action="store_true", help="ember: only the recordings")
    p.add_argument("--config", nargs="*", help="ember: extra YAML config files")
    p.add_argument("--final", action="store_true", help="mismatch, coverage: this is the final, held-out run")
    p.add_argument("--workers", type=int, default=None, help="synthetic suites: worker processes")
    p.add_argument("--tag", default="", help="synthetic suites: suffix of the results/runs folder")
    p.add_argument("--record", action="store_true", help="synthetic suites: record the numbers in NUMBERS.json")
    p.add_argument("--no-generate", action="store_true", help="synthetic suites: evaluate the clips already generated")
