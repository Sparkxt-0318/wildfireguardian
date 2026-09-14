#!/usr/bin/env python
"""NH-062 — settle it in one command, from anywhere, on any shell.

Answers the one open question in docs/auto/NEEDS_HUMAN.md NH-062: is the ERA5 time index
NANOSECOND resolution? ``WeatherSeries.at`` resolves a time with
``self.time.view("int64") - when.value``; ``Timestamp.value`` is always nanoseconds while
``view("int64")`` is the index's OWN resolution, so on a datetime64[us] or [s] index every
comparison goes one way and the lookup silently returns the LAST sample in the series.

Deliberately does its own path setup from ``__file__`` rather than from the working
directory, and takes no arguments. The repository lives under a path with SPACES in it
(「Korea Code Fair」), which is exactly where a shell one-liner with a bare relative `src`
falls over.

    python scripts/nh062_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

FIRE = "yeongdeok_2025"


def main() -> int:
    print(f"repo         : {REPO}")
    print(f"python       : {sys.executable}")
    print(f"python ver   : {sys.version.split()[0]}")

    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        print(f"\nSTOP: {exc}.  This interpreter does not have the project's dependencies.")
        print("Use the project venv, e.g.:")
        print(f'    "{REPO}/.auto/venv/bin/python" "{REPO}/scripts/nh062_check.py"')
        print("  (create it first with:  bash scripts/auto/bootstrap.sh )")
        return 2
    print(f"pandas       : {pd.__version__}")
    try:
        import xarray
        print(f"xarray       : {xarray.__version__}")
    except ImportError:
        print("xarray       : MISSING (needed to open the ERA5 file)")

    from wildfireguardian.spread_v2 import data
    from wildfireguardian.spread_v2.weather import weather_series_from_event

    # ⚠ find_data_dir() RETURNS None when it finds nothing; it does not raise. Checking
    # only for an exception here let the failure fall through to a bare traceback the
    # first time this script was run — which is the whole thing it exists to avoid.
    d = None
    try:
        d = data.find_data_dir()
    except Exception as exc:  # noqa: BLE001
        print(f"FIRMS bundle : lookup raised {type(exc).__name__}: {exc}")
    if d is None:
        print("FIRMS bundle : NOT FOUND")
        print("\nSTOP: the FIRMS/ERA5 bundle is not on this machine.")
        print(f"Looked under {REPO / 'data/raw'} (and $WFG_FIRMS_DIR if set).")
        print("data/raw/** is git-ignored, so it exists only where you unzipped it.")
        print("If the bundle lives elsewhere, point at it and re-run:")
        print('    export WFG_FIRMS_DIR="/path/to/firms_data"')
        return 2

    ev = data.load_event(FIRE)
    ws = weather_series_from_event(ev)
    if ws is None:
        print(f"\nSTOP: {FIRE} has no usable ERA5 ({ev.era5_path}).")
        return 2

    idx = ws.time
    print(f"\nERA5 time dtype : {idx.dtype}      <-- THIS IS THE ANSWER")
    print(f"samples         : {len(idx)}  from {idx[0]}  to {idx[-1]}")

    # Prove it end to end rather than reasoning from the dtype: ask at() for a time whose
    # correct answer is known, and see whether it returns the last sample.
    if len(idx) >= 3:
        target = idx[1]
        picked_val = ws.at(target)["temp_c"]
        last_val = float(ws.temp_c[-1])
        first_ok = abs(picked_val - float(ws.temp_c[1])) < 1e-9
        print(f"\nat(time[1]) returned temp_c={picked_val:.4f}; "
              f"time[1] is {float(ws.temp_c[1]):.4f}, last sample is {last_val:.4f}")
        if first_ok:
            print("\nVERDICT: at() resolves CORRECTLY.  ->  NH-062 option A is free:")
            print("         harden the two view(\"int64\") idioms, re-run make verify and the")
            print("         baseline, and expect every number unchanged.")
        else:
            print("\n⚠ VERDICT: at() returned the WRONG sample — the resolution bug is LIVE.")
            print("         Every committed spread field was driven by the wrong weather.")
            print("         -> NH-062 option B. Do not fix this quietly: numbers will move.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
