"""Test E record script (laptop side): keep a laptop copy of the unit stream during the 30-minute drive.

The Pi records its own full-rate session (hardware/vehicle-unit/records/<session_id>/; copy it to the laptop
afterwards with scp/rsync). This script records what reached the laptop plus the receipt times (rx.jsonl.gz),
which the analysis needs for link dropouts. The crossing app with its research log may run at the same time (it is
a separate WebSocket client). No fire in test E. See protocols/E_vehicle.md.

Usage (from apps/crossing):
  .venv/bin/python -m field_tests.e_vehicle_record --duration-s 1800 --vehicle "car, magnet roof mount"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common, recordkit  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test E: laptop copy of the unit stream during the drive")
    p.add_argument("--duration-s", type=float, default=1800.0)
    p.add_argument("--vehicle", default="")
    p.add_argument("--route", default="")
    p.add_argument("--driver", default="")
    p.add_argument("--operator", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--pi", default=common.DEFAULT_PI_URL)
    p.add_argument("--out", default=str(common.RECORDS / "E"))
    a = p.parse_args(argv)
    run_id = "E_drive_%s" % common.utc_stamp()
    trial = common.base_meta("E", argv)
    trial.update({"run_id": run_id, "vehicle": a.vehicle, "route": a.route, "driver": a.driver,
                  "operator": a.operator, "notes": a.notes, "simulated": False, "pi_url": a.pi,
                  "duration_s": a.duration_s})
    phases = [("drive", a.duration_s, "Start driving the planned route (laptop operator is NOT the driver)")]
    run_dir = Path(a.out) / run_id
    print("TEST E - recording to %s. Type a note + Enter to mark an event (tunnel, bump, stop)." % run_dir)
    recordkit.record_run(a.pi, run_dir, trial, phases)
    print("Done: %s\nNow copy the Pi session (records/<session_id>/) next to it and run e_vehicle_analyse." % run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
