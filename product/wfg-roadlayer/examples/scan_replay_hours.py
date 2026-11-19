"""Run the tool on every hour of the 25 March 2025 replay (12:00-24:00 KST, both regions, MEASURED arm, 8 h) and print
one summary line per region-hour: how many villages are cut at the issue time, cut inside the horizon, not cut; how
many are flagged; the largest road-cut-to-fire gap. About 25 minutes on 4 cores. Results: examples/SCAN.md.

    python3 examples/scan_replay_hours.py [--workers N]
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent
sys.path.insert(0, str(PRODUCT))
from wfg_roadlayer import pipeline  # noqa: E402

FLAG = "flag: road cut before 'execute now'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int)
    a = ap.parse_args()
    total = Counter()
    print("| issue KST | region | cut at issue | cut inside 8 h | not cut | flag yes | flag cannot tell | largest gap (min, village) |")
    print("|---|---|---:|---:|---:|---:|---:|---|")
    with tempfile.TemporaryDirectory() as td:
        for region in ("uiseong_andong_2025", "yeongdeok_2025"):
            for h in range(3, 16):
                T = "2025-03-25T%02d:00:00Z" % h
                tif = Path(td) / ("r_%02d.tif" % h)
                if not tif.exists():
                    subprocess.run([sys.executable, str(HERE / "build_example_raster.py"), "--issue", T, "--out", str(tif)],
                                   check=True, capture_output=True)
                out = Path(td) / ("%s_%02d" % (region, h))
                pipeline.run(region_name=region, issue_time=T, raster=str(tif), as_of=T, out=out, workers=a.workers,
                             log=lambda *_: None)
                rows = list(csv.DictReader(open(out / "en" / ("villages_road_cut_%s.csv" % region), encoding="utf-8-sig")))
                c, best = Counter(), (-1, "")
                for r in rows:
                    if r["refusal reason"]:
                        continue
                    st = r["road status"]
                    c["at"] += st.startswith("already")
                    c["cut"] += st == "cut"
                    c["nc"] += st.startswith("not cut")
                    c["fy"] += r[FLAG] == "yes"
                    c["fu"] += r[FLAG] == "cannot tell"
                    g = r["minutes from road cut to fire arrival"]
                    if g[:1].isdigit() and int(g) > best[0]:
                        best = (int(g), r["village or facility"])
                total.update(c)
                print("| %02d:00 | %s | %d | %d | %d | %d | %d | %s |" % (h + 9, region, c["at"], c["cut"], c["nc"], c["fy"], c["fu"],
                                                                     "%d, %s" % best if best[0] >= 0 else "–"), flush=True)
    print("\nplace-hours: cut at issue %d, cut inside 8 h %d, not cut %d; flag yes %d, cannot tell %d" %
          (total["at"], total["cut"], total["nc"], total["fy"], total["fu"]))


if __name__ == "__main__":
    main()
