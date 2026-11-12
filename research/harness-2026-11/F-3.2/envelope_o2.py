"""O2 for F-DYN envelope packets: independent per-cell burning intervals from the raw bracket arrays.

Written from Leo's rule text (messages of 2026-11-12), WITHOUT reading fdyn/ignitions.py or fdyn/_packet_child.py.
Exact rationals of the stored binary64 values throughout:
  lo = firms_early arrival_h, hi = firms_constrained arrival_h (hours since t0; north-up rows), h = start − t0 in hours,
  T = 3970.4642815249267 s, Q = 300 s, floor_300(x) = 300·floor(x / 300) on seconds;
  b = floor_300(max(lo − h, 0)·3600);  e = floor_300(max(hi − h, 0)·3600) + T + Q;  half-open [b, e);
  kept iff lo, hi finite, b < H, (hi − h)·3600 > −T, and the cell is not export-burned
  (source_burned_area_valid ∧ source_burned_area == 1); present fire = heat__initial_active_burning_probability > 0
  on [0, R), R = the writer's scalar enclosure (NATIVE_METADATA).
Compared (i) per cell with HAZARD.json flame sets (differences classified: same starts and every end within 1 µs in
either direction = binary64 rounding of the end sum; anything else is an 'other' difference), and (ii) as integer instances: derive_instance on these intervals vs frontend.build_instance
on the HAZARD intervals, for the first N origins of the region's INSTANCE.json entry, departure 0.
Usage: python envelope_o2.py --leo WORKTREE --packet REL --start 20250325T110000Z --origins N
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import derive_instance as DI  # noqa: E402
import p1_check as P  # noqa: E402
from wfg_sipp.frontend import build_instance, prepared  # noqa: E402

T = F(3970.4642815249267)
Q = F(300)


def floor300(x: F) -> F:
    return 300 * F((x / 300).numerator // (x / 300).denominator)


def find(d, key):
    if isinstance(d, dict):
        for k, v in d.items():
            if k == key:
                return v
            r = find(v, key)
            if r is not None:
                return r
    elif isinstance(d, list):
        for v in d:
            r = find(v, key)
            if r is not None:
                return r
    return None


def independent_intervals(L, pk, start_tag, H, mode='exact'):
    lo = np.load(L / "variants/firms_early.npz")["arrival_h"]
    hi = np.load(L / "variants/firms_constrained.npz")["arrival_h"]
    t0 = datetime.fromisoformat(str(np.load(L / "variants/firms_early.npz")["t0_utc"]).replace("Z", "+00:00"))
    st = datetime.strptime(start_tag, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    h = F(int((st - t0).total_seconds()), 3600)
    ex = np.load(L / ("synthetic_exports/FORECAST_%s.npz" % start_tag), allow_pickle=False)
    burned = ex["source_burned_area_valid"] & (ex["source_burned_area"] == 1)
    present = ex["heat__initial_active_burning_probability"] > 0
    meta = json.loads((pk / "NATIVE_METADATA.json").read_text())
    R = find(meta, "R_max_s")
    R = F(float(R)) if R is not None else None
    Hn, W = lo.shape
    g = lambda r, c: (Hn - 1 - int(r)) * W + int(c)
    out, kept = {}, 0
    for r in range(Hn):
        for c in range(W):
            if burned[r, c] or not (np.isfinite(lo[r, c]) and np.isfinite(hi[r, c])):
                continue
            if mode == "float":   # the rule evaluated in binary64, as a float implementation would
                hf = float(h)
                xb = F(float(max(lo[r, c] - hf, 0.0) * 3600)); xe = F(float(max(hi[r, c] - hf, 0.0) * 3600))
                keep = (hi[r, c] - hf) * 3600 > -float(T)
            else:                 # exact rationals of the stored values
                L_, H_ = F(float(lo[r, c])), F(float(hi[r, c]))
                xb, xe = max(L_ - h, F(0)) * 3600, max(H_ - h, F(0)) * 3600
                keep = (H_ - h) * 3600 > -T
            b = floor300(xb)
            e = floor300(xe) + T + Q
            if b < H and keep:
                out.setdefault(g(r, c), []).append((b, e)); kept += 1
    if R is not None and R > 0:
        for r, c in zip(*np.nonzero(present)):
            out.setdefault(g(r, c), []).append((F(0), R))
    return out, dict(h=str(h), R=str(R), igniting_cells=kept, present_cells=int(present.sum()), export_burned=int(burned.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leo", required=True)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--origins", type=int, default=10)
    ap.add_argument("--mode", choices=["exact", "float"], default="exact")
    a = ap.parse_args()
    L = Path(a.leo) / "research/harness-2026-11/F-DYN/_data"
    pk = Path(a.leo) / a.packet
    region = pk.parent.name
    hz = json.loads((pk / "HAZARD.json").read_text())
    H = int(F(float(hz["valid_until"])))
    mine_raw, info = independent_intervals(L, pk, a.start, H, a.mode)
    info["mode"] = a.mode
    Hs = F(H)
    mine = {k: v for k, v in ((k, P.merge(v, F(0), Hs)) for k, v in mine_raw.items()) if v}
    haz = {k: v for k, v in P.from_hazard(hz, Hs).items() if v}
    diff = [k for k in set(mine) | set(haz) if mine.get(k) != haz.get(k)]
    # Same starts, every end within 1 us in EITHER direction: binary64 rounding of the end sum. (An earlier version
    # counted only HAZARD-later ends and so reported 0 differences when the float-mode run had 820 sub-us ones.)
    roundup = [k for k in diff if len(mine.get(k, [])) == len(haz.get(k, [])) and all(
        x0 == y0 and abs(y1 - x1) < F(1, 10**6) for (x0, x1), (y0, y1) in zip(mine[k], haz[k]))]
    later = sum(1 for k in roundup if any(y1 > x1 for (_, x1), (_, y1) in zip(mine[k], haz[k])))
    earlier = sum(1 for k in roundup if any(y1 < x1 for (_, x1), (_, y1) in zip(mine[k], haz[k])))
    maxdev = max((abs(y1 - x1) for k in roundup for (_, x1), (_, y1) in zip(mine[k], haz[k])), default=F(0))
    other = sorted(set(diff) - set(roundup))
    report = dict(packet=a.packet, **info, active_cells_mine=len(mine), active_cells_hazard=len(haz), differing_cells=len(diff),
                  end_within_1us=len(roundup), end_within_1us_hazard_later=later, end_within_1us_hazard_earlier=earlier,
                  end_within_1us_max_abs_s=float(maxdev), other_differences=len(other),
                  other_examples=[{"cell": k, "mine": [[str(x), str(y)] for x, y in mine.get(k, [])][:2],
                                   "hazard": [[str(x), str(y)] for x, y in haz.get(k, [])][:2]} for k in other[:5]])
    print(json.dumps({k: v for k, v in report.items() if k != "other_examples"}), flush=True)
    g = json.loads((L / "graphs_interim" / region / "graph.json").read_text())
    pg = prepared(g)
    inst = [i for i in json.loads((L / "INSTANCE.json").read_text())["instances"] if i["region"] == region and i["horizon_s"] == H][0]

    class HzModel:
        cell_intervals = haz
        supported = True
    n_eq = n = 0
    for o in inst["origins"][: a.origins]:
        req = {"position": {"node": o["entry_node"]}, "incoming_edge": None, "departure": 0, "horizon": H,
               "destinations": [{"node": d["node"], "dwell": d["dwell_s"], "open_intervals": [[0, H]]} for d in o["destinations"]]}
        i_h, _ = build_instance(g, req, HzModel, prepared_graph=pg)
        d = DI.compare_semantic(i_h, DI.derive(g, req, mine_raw))
        n += 1; n_eq += not d
        if d:
            print("INSTANCE DIFF", o["origin_id"], d[:2], flush=True)
    report.update(integer_instances_equal=n_eq, integer_instances_compared=n)
    print(json.dumps({"integer_instances_equal": n_eq, "of": n}))
    (HERE / "results" / ("envelope_o2_%s.json" % a.mode)).write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
