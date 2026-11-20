"""Generate SIMULATED inputs for tests A-F and run every analysis on them, writing the outputs (CSV, PNG, Markdown
snippets) to field_tests/example_outputs/<test>/. Everything produced here is watermarked SIMULATED: it shows what
the analysis produces, not how the hardware behaves.

Usage (from apps/crossing):  .venv/bin/python -m field_tests.run_demo [--scratch DIR] [--out DIR] [--quick]
The simulated run directories go to --scratch (default: a temporary directory), not into the repository.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import (a_flux_analyse, b_radar_analyse, c_thermal_analyse, common, d_failsafe_analyse,  # noqa: E402
                         e_vehicle_analyse, f_housing_analyse, simulate)

README = """# Example outputs: SIMULATED

**Every file in this folder was produced from SIMULATED inputs** (`field_tests/simulate.py`), by
`python -m field_tests.run_demo`. They show the format of the CSV / PNG / Markdown that each analysis script writes.
They are not measurements, they say nothing about how the unit or the app behaves on hardware, and they must not be
copied into `apps/crossing/RESULTS.md` as results.

The simulators deliberately include failures (a Bunsen radiant fraction that differs from the sheet, flame effects
below the radar noise at long range, a near edge outside the camera's field of view, one test D fault (imu_disconnect,
latency set to 2.3-2.6 s for this demo only) that takes longer than 2 s to detect and so FAILS, a thermal_freeze
whose operator mark is seconds off and is timed from the received thermal frames instead, a radar that stops while
its heartbeat says ok, link dropouts, and one test A cool-down run heated too hard that the record scripts' flux-disc
guard stops at 70 C: `A_cooldown_r3_SIM_overheated`, stop_reason DISC_OVER_70C, reported as "STOPPED: disc 70 C")
so that every "report failures as measured" path of the analysis is exercised. The copper flux disc sits on printed
PETG tabs: every record script stops a run at a disc temperature >= 70 C (user-set) and the simulated A and F runs
pass through that same guard.

| Folder | Test | Snippet |
|---|---|---|
| A_flux | flux plate vs Bunsen burner | A_flux/A_results.md |
| B_radar | radar, corner reflector, nothing / flame / smoke / mist | B_radar/B_results.md |
| C_thermal | thermal near-edge distance vs tape | C_thermal/C_results.md |
| D_failsafe | fault to CLOSED timing | D_failsafe/D_results.md |
| E_vehicle | 30-minute drive | E_vehicle/E_results.md |
| F_housing | water spray and hot-air gun | F_housing/F_results.md |

`wfgvu.synth` present when generated: %s. It is used only by the test B interop test
(`simulate.synth_b_nothing`); these example outputs come from `field_tests/simulate.py`.
"""

# Test D demo only: one fault detected too late, so D_results.md shows a FAIL row (the README above says so).
DEMO_D_LATENCY = {"imu_disconnect": (2.3, 2.6)}


def run(out, scratch, quick: bool = False, echo=print) -> dict:
    out = Path(out)
    scratch = Path(scratch)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    synth = importlib.util.find_spec("wfgvu.synth") is not None
    res = {}
    echo("A: simulating ...")
    simulate.sim_a(scratch / "A", distances=(0.10, 0.20, 0.40) if quick else (0.10, 0.15, 0.20, 0.30, 0.40),
                   repeats=2 if quick else 3, n_cooldown=1 if quick else 2)
    res["A"] = a_flux_analyse.analyse(scratch / "A", out / "A_flux")
    echo("B: simulating ...")
    simulate.sim_b(scratch / "B", distances=(2.0, 5.0) if quick else (2.0, 3.0, 4.0, 5.0),
                   duration_s=15.0 if quick else 30.0)
    res["B"] = b_radar_analyse.analyse(scratch / "B", out / "B_radar", echo=echo)
    echo("C: simulating ...")
    simulate.sim_c(scratch / "C", distances=(3.0, 8.0, 15.0) if quick else (3.0, 5.0, 8.0, 11.0, 15.0),
                   n_frames=4 if quick else 8)
    res["C"] = c_thermal_analyse.analyse(scratch / "C", out / "C_thermal")
    echo("D: simulating ...")
    d = simulate.sim_d(scratch / "D", latency=DEMO_D_LATENCY)
    res["D"] = d_failsafe_analyse.analyse(out / "D_failsafe", run_dir=d)
    echo("E: simulating ...")
    e = simulate.sim_e(scratch / "E", duration_s=240.0 if quick else 1800.0)
    res["E"] = e_vehicle_analyse.analyse(out / "E_vehicle", [str(e["pi"])], str(e["laptop"]))
    echo("F: simulating ...")
    f = simulate.sim_f(scratch / "F", scale=0.2 if quick else 1.0)
    res["F"] = f_housing_analyse.analyse(out / "F_housing", str(f["laptop"]), str(f["pi"]))
    (out / "README.md").write_text(README % ("yes" if synth else "no"))
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="SIMULATED demo of every field-test analysis")
    p.add_argument("--out", default=str(common.EXAMPLES))
    p.add_argument("--scratch", default=os.path.join(tempfile.gettempdir(), "wfg_field_tests_sim"))
    p.add_argument("--quick", action="store_true")
    a = p.parse_args(argv)
    run(a.out, a.scratch, a.quick)
    print("SIMULATED example outputs written to %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
