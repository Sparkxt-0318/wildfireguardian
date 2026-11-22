"""Driver: python3 -m kq.run_all STAGE   (STAGE = mid | lh | oat). Resumable; one gz JSON per (region, hour, stage)."""
import gzip, json, sys, time
from multiprocessing import Pool
from pathlib import Path
from . import run_real

import os
OUT = Path(os.environ.get("KQ_OUT") or Path(__file__).resolve().parents[1] / "results" / "work")


def todo(stage):
    jobs = []
    for rid in ["uiseong_andong_2025", "yeongdeok_2025"]:
        for hu in range(3, 16):
            if stage == "oat" and (rid, hu) not in run_real.CARD_CASES:
                continue
            jobs.append((rid, hu))
    return jobs


def work(a):
    stage, rid, hu = a
    fn = OUT / ("%s__%02d__%s.json.gz" % (rid, hu, stage))
    if fn.exists():
        return fn.name, 0
    pn = {"mid": ["MID"], "lh": ["LOW", "HIGH"], "oat": [k for k in run_real.PARAMS if k.startswith("OAT")]}[stage]
    pol = {"mid": "mid", "lh": "lh", "oat": "none"}[stage]
    res = run_real.job((rid, hu, pn, pol))
    tmp = fn.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        json.dump(res, f)
    tmp.rename(fn)
    return fn.name, res["wall_s"]


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    stage = sys.argv[1]
    jobs = [(stage, r, h) for r, h in todo(stage)]
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 4, maxtasksperchild=1) as p:
        for name, w in p.imap_unordered(work, jobs):
            print(time.strftime("%H:%M:%S"), name, w, flush=True)
