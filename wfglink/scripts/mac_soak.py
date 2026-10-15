#!/usr/bin/env python3
"""Overnight booth soak on the Mac, with a PASS or FAIL report at the end.

    python scripts/mac_soak.py --hours 8                     # from wfglink/ (sitting 2)
    python scripts/mac_soak.py --hours 8 -- --lang en        # options after -- go to booth/booth.sh
    python scripts/mac_soak.py --hours 0.1 -- --synthetic    # a six minute trial on generated video

It runs the booth exactly as on the day (bash booth/booth.sh: the playlist in a loop,
fullscreen, restarted after a crash or hang, the Mac kept awake) for the given hours,
copies logs/heartbeat.json into a CSV every --every seconds, prints a progress line every
10 minutes, and at the end (or on Ctrl-C) stops the booth and prints the report: paint fps
against its floors, memory growth in MB per hour, restarts and hangs from logs/booth.log,
analysis stalls and errors (rules: src/wfglink/soak.py; floors: soak: in configs/default.yaml).

Files: logs/soak/<date-time>/soak.csv, soak_report.json, soak_meta.json and supervisor.txt.
The exit code is 0 for PASS, 1 for FAIL. If the soak was cut off before its report (the Mac
restarted), `python -m wfglink.soak logs/soak/<date-time>` analyses what was sampled.

It re-runs itself with wfglink/.venv/bin/python (or $WFG_PY) when started with another Python.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ensure_venv() -> None:
    """Re-execute with the project's Python unless this already is it."""
    target = Path(os.environ.get("WFG_PY") or ROOT / ".venv" / "bin" / "python")
    if Path(sys.prefix).resolve() == target.parent.parent.resolve() or os.environ.get("WFG_SOAK_REEXEC"):
        return
    if not target.exists():
        print(f"mac_soak.py: {target} not found. Run ./scripts/setup_mac.sh once (from the wfglink folder).",
              file=sys.stderr)
        raise SystemExit(2)
    os.environ["WFG_SOAK_REEXEC"] = "1"
    os.execv(str(target), [str(target), str(Path(__file__).resolve()), *sys.argv[1:]])


def main(argv: list[str]) -> int:
    import argparse
    import datetime as dt

    sys.path.insert(0, str(ROOT / "src"))
    from wfglink.soak import format_report, run_soak, soak_config

    own, booth_args = (argv[:argv.index("--")], argv[argv.index("--") + 1:]) if "--" in argv else (argv, [])
    sc = soak_config()
    ap = argparse.ArgumentParser(prog="python scripts/mac_soak.py", description=__doc__.split("\n")[0],
                                 epilog="Options after -- go to booth/booth.sh (python -m wfglink live options).")
    ap.add_argument("--hours", type=float, default=8.0, help="soak length in hours (default 8)")
    ap.add_argument("--every", type=float, default=float(sc.get("every_s", 60)),
                    help="seconds between heartbeat samples (default: soak.every_s)")
    ap.add_argument("--out", default=None, help="folder for the CSV and the report (default: soak.out_dir/<date-time>)")
    args = ap.parse_args(own)
    if args.hours <= 0 or args.every <= 0:
        ap.error("--hours and --every must be positive")
    out = Path(args.out) if args.out else ROOT / sc.get("out_dir", "logs/soak") / dt.datetime.now().strftime("%Y%m%d-%H%M")
    os.chdir(ROOT)
    report = run_soak(args.hours, ["bash", str(ROOT / "booth" / "booth.sh"), *booth_args], out, every_s=args.every,
                      sc=sc, cwd=ROOT)
    print()
    print(format_report(report))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    _ensure_venv()
    sys.exit(main(sys.argv[1:]))
