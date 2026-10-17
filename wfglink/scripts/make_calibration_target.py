#!/usr/bin/env python3
"""Write the printed A4 calibration target for `python -m wfglink calibrate`.

    python scripts/make_calibration_target.py         # booth/ember/calibration_target_A4.pdf and .png

A4 landscape, four ArUco markers (4x4_50, ids 0 to 3) at known positions, a 100 mm line to
check the print scale, and "print at 100 percent" in Korean and English
(src/wfglink/ember/target.py). Print it at 100 percent (actual size, no "fit to page"),
check the line with a ruler, and keep the sheet flat (tape it to a board).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wfglink.ember.target import TARGET_PDF, TARGET_PNG, write_target  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdf", default=str(TARGET_PDF), help="PDF path (default booth/ember/calibration_target_A4.pdf)")
    ap.add_argument("--png", default=str(TARGET_PNG), help="PNG preview path")
    args = ap.parse_args()
    out = write_target(args.pdf, args.png)
    print(f"{out['pdf']} and {out.get('png')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
