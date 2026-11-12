"""Preflight for every refit command (S-D9 A1 §3.1/§3.2): FAIL unless the interpreter and installed packages
equal the pins in requirements-refit.txt (plus torch 2.5.1 and Python 3.12).

The pins are load-bearing, not cosmetic (Owen, verdict on 81dc7c2): under pandas 3.1.1 / numpy 2.5.4 the
UNMODIFIED forecast/wildfire/prepare.py fails at line 946 (``assert current_utc == expected_utc``), so a run in
another environment is not the recorded recipe. This is a separate script so the A1-pinned wrappers
(run_pipeline_rebuilt.py 264deaea…, run_c651_recipe.py 3e99f479…, write_receipt_addendum.py 54b0f957…) keep
their bytes. Run it with the SAME interpreter immediately before each wrapper command; with --out it writes
REFIT_ENV_CHECK.json (into the run directory, beside the receipt) and exits non-zero on any mismatch.

    V/bin/python research/harness-2026-11/s-d1/refit/check_refit_env.py --out RUN_DIR && V/bin/python ...wrapper...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTRA = {"torch": "2.5.1"}
PYTHON = "3.12"


def pins():
    out = {}
    for line in (HERE / "requirements-refit.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, ver = line.split("==")
            out[name.strip()] = ver.strip()
    return {**out, **EXTRA}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    found, bad = {}, []
    for name, want in pins().items():
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            have = None
        found[name] = have
        if have is None or have.split("+", 1)[0] != want:
            bad.append(f"{name}: want {want}, have {have}")
    py = platform.python_version()
    if not py.startswith(PYTHON + "."):
        bad.append(f"python: want {PYTHON}.x, have {py}")
    report = dict(schema="s-d1.refit-env-check/1", ok=not bad, mismatches=bad, python=py, executable=sys.executable,
                  packages=found, requirements_sha256=hashlib.sha256((HERE / "requirements-refit.txt").read_bytes()).hexdigest())
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "REFIT_ENV_CHECK.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report))
    if bad:
        raise SystemExit("REFIT ENVIRONMENT MISMATCH (pins are load-bearing): " + "; ".join(bad))


if __name__ == "__main__":
    main()
