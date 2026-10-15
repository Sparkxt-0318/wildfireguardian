#!/usr/bin/env python3
"""Write the A5 booth placards (Korean and English) into booth/placards/.

    python scripts/make_placards.py                      # all four, with the LED result if there is one
    python scripts/make_placards.py --led-report results/validation/led_report.json

sensor_ko/en ("This is the sensor", for the dashcam stand) and limits_ko/en (the limits
card), each as a print-ready PDF and a PNG preview (src/wfglink/render/placards.py). Run it
again after `python -m wfglink validate --suite led` so the sensor card prints the LED
median speed error, and after any change to the limits in src/wfglink/ui/i18n.py.
Print at 100 % (actual size) on A5, or on A4 at 100 % and trim.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wfglink.render.placards import LED_REPORT, OUT_DIR, make_placards  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(OUT_DIR), help="output folder (default booth/placards)")
    ap.add_argument("--led-report", default=str(LED_REPORT),
                    help="LED suite report; its median speed error goes on the sensor card when the file exists")
    ap.add_argument("--lang", nargs="+", default=["ko", "en"], choices=["ko", "en"])
    ap.add_argument("--card", nargs="+", default=["sensor", "limits"], choices=["sensor", "limits"])
    args = ap.parse_args()
    for r in make_placards(args.out, args.led_report, tuple(args.lang), tuple(args.card)):
        led = "; LED line printed" if r["led_line"] else ""
        print(f"{r['pdf']} and .png: body type {r['body_mm']:.1f} mm{led}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
