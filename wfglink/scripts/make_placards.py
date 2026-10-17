#!/usr/bin/env python3
"""Write the A5 booth placards (Korean and English) into booth/placards/.

    python scripts/make_placards.py                      # all of them
    python scripts/make_placards.py --card ember_page    # only the ember page's QR card

sensor_ko/en ("This is the sensor", for the dashcam stand), limits_ko/en (the limits card)
and, when booth.ember_page_url is set (configs/booth_local.yaml or configs/default.yaml),
ember_page_ko/en (the ember page's address as a large QR code, for the standing spot), each
as a print-ready PDF and a PNG preview (src/wfglink/render/placards.py). Run it again after
any change to the limits in src/wfglink/ui/i18n.py, and after publishing the ember page.
--url gives the address on the command line instead.
Print at 100 % (actual size) on A5, or on A4 at 100 % and trim.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wfglink.render.placards import OUT_DIR, make_placards  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(OUT_DIR), help="output folder (default booth/placards)")
    ap.add_argument("--lang", nargs="+", default=["ko", "en"], choices=["ko", "en"])
    ap.add_argument("--card", nargs="+", choices=["sensor", "limits", "ember_page"],
                    help="default: sensor and limits, and ember_page when the page's address is set")
    ap.add_argument("--url", help="the ember page's address (default booth.ember_page_url)")
    args = ap.parse_args()
    url = args.url
    if url is None:
        from wfglink.config import load_config

        url = str((load_config(local=True).get("booth") or {}).get("ember_page_url") or "")
    url = url.strip()
    cards = args.card or (["sensor", "limits"] + (["ember_page"] if url else []))
    if "ember_page" in cards and not url:
        print("make_placards: the ember_page card needs the page's address: set booth.ember_page_url in "
              "configs/booth_local.yaml (or give --url)", file=sys.stderr)
        return 2
    for r in make_placards(args.out, tuple(args.lang), tuple(cards), url=url):
        print(f"{r['pdf']} and .png: body type {r['body_mm']:.1f} mm")
    if not url:
        print("ember_page card not made: booth.ember_page_url is empty (set it after publishing the page)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
