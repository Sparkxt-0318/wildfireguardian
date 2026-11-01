"""E4 ablation on the SYNTHETIC dev instances where plans fall short: the LP bound with and without the free-space
rows and the trip cuts (all variants are valid bounds; the strengthenings can only lower it).

    .venv/bin/python program/benchlock.py --label e4-ablation -- \
        .venv/bin/python evacplan/experiments/E4-flow-bound/ablation.py [INSTANCE ...]

Writes ``ablation.csv`` next to this file. Dev instances only (rule 5)."""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from evacplan.instances import CACHE_DIR, load_entry, load_split
from evacplan.methods.flow_bound import E4FlowBound, flow_bound
from evacplan.reach import Reach

HERE = Path(__file__).resolve().parent
DEFAULT = ["SYNTHETIC-M-grid-t75-s107", "SYNTHETIC-M-geo-t75-s108"]
VARIANTS = (("plain", False, False), ("free_space", True, False), ("free_space+trip_cuts", True, True))


def main(argv: list[str]) -> int:
    wanted = argv or DEFAULT
    split = load_split()
    entries = {e.id: e for e in split.entries("dev")}
    out = []
    for iid in wanted:
        inst, ss = load_entry(entries[iid], CACHE_DIR)
        rh = Reach(inst, ss)
        delta, grouping = E4FlowBound().setting(inst)
        for name, fs, tc in VARIANTS:
            t0 = time.monotonic()
            b, info = flow_bound(inst, ss, reach=rh, delta_s=delta, grouping=grouping, free_space=fs, trip_cuts=tc,
                                 time_limit=900.0)
            row = {"instance": iid, "variant": name, "bound": b, "lp_value": info.get("dual_bound"),
                   "lp_status": info.get("lp_status"), "cols": (info.get("lp") or {}).get("cols"),
                   "seconds": round(time.monotonic() - t0, 1)}
            print(row, flush=True)
            out.append(row)
    with (HERE / "ablation.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
