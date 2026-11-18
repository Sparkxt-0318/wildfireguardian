#!/usr/bin/env python3
"""Assemble numbers.json from the derived files. Every number in RESULTS.md and the note is printed from it.

    python3 make_numbers.py --nwp NWP_DIR --out numbers.json
"""
import argparse
import json
from pathlib import Path

from rules import A_CAL, RUN_KM

HERE = Path(__file__).resolve().parent
D = HERE / "derived"


def fetch_summary(p):
    if not p.exists():
        return None
    last = {}
    for l in open(p):
        r = json.loads(l)
        last[r["cycle"]] = r
    rows = [last[k] for k in sorted(last)]
    miss = [r["cycle"] for r in rows if r["missing"]]
    return dict(cycles=len(rows), first_cycle=rows[0]["cycle"], last_cycle=rows[-1]["cycle"],
                gigabytes=round(sum(r["bytes"] for r in rows) / 1e9, 2),
                fetched_utc=[min(r["fetched_utc"] for r in rows), max(r["fetched_utc"] for r in rows)],
                cycles_with_missing=len(miss), first_missing=miss[:1], last_missing=miss[-1:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nwp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    an = json.load(open(D / "analysis.json"))
    out = dict(meta=dict(
        protocol_commit="9802a32", amendment_1_commit="556f842",
        question="Does forecast wind at 850 hPa warn of a fast run earlier or more reliably than the surface-gust rule?",
        run_hour="issue hour with 5 h reach > %.2f km" % RUN_KM,
        rules={"G": "forecast gust >= 20 m/s at two consecutive hourly valid times in the next 8 h (max of 4 lattice points)",
               "G-obs": "KMA ASOS gust >= 20 m/s in the hour ending at the issue hour, station within 50 km (KFS_01 only, PARTIAL)",
               "A-cal": f"forecast 850 hPa wind, 8 h window maximum > {A_CAL} m/s (California calibration, kcf-abstain tau)",
               "A25": "the same >= 25 m/s", "A30": "the same >= 30 m/s", "A+G": "A-cal or G",
               "A-match": "secondary: 850 hPa threshold with the same number of burden point-days as G"},
        forecast="issued GFS 0.25 deg, cycles 00/06/12/18 UTC, assumed available 5 h after the cycle, valid hours t+1..t+8",
        labels="MEASURED = computed here or reused from a committed file; ASSUMED = input, proxy or simplification; "
               "PARTIAL = G-obs on four stations for one fire; COARSE = S5; NOT RUN = not computed",
        reproduction_check=json.load(open(D / "reproduction_check.json")),
        fetch={k: fetch_summary(Path(a.nwp) / f"{k}_KOR" / "log.jsonl") for k in ("gfs", "ifs", "gefs")}))
    out.update(an)
    for name, f in (("second_model_ifs", "ifs_crosscheck.json"), ("height", "height.json"), ("S5_coarse", "coarse_s5.json")):
        out[name] = json.load(open(D / f)) if (D / f).exists() else "NOT DONE"
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    print("wrote", a.out, round(Path(a.out).stat().st_size / 1e3), "kB")


if __name__ == "__main__":
    main()
