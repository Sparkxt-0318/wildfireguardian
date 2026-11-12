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
Mode v31 (QUANT_v3_1_RULE.md @ f40e2af, from the rule text only): every floored time is an integer number of
milliseconds since t0. Cells flagged `timestamp_exact` in the variant file are recovered as round(arrival_h·3.6e6) and
asserted to lie within 1e-6 ms of that integer; all other cells are rounded to the nearest ms, half to even.
rel = arrival_ms − start_ms; b = floor_div(max(rlo, 0), 300000)·300 s; hi_rel = floor_div(max(rhi, 0), 300000)·300 s;
e = hi_rel + T + Q; kept iff b < H, rhi > −T·1000 (exact comparison) and not export-burned. Compared with INTEGER
equality: each HAZARD interval's start must equal b exactly and its end must imply the same integer hi_rel
(|e_hazard − (hi_rel + T + Q)| < 1 µs is reported as the binary64 representation of the same schedule).
Usage: python envelope_o2.py --leo WORKTREE --packet REL --start 20250325T110000Z --origins N [--mode exact|float|v31]
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


def independent_intervals(L, pk, start_tag, H, mode='exact', law='envelope'):
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
    if mode == "v31":
        if F(float(ex["contract__cell_duration_s"])) != T:
            raise SystemExit("export cell duration %r is not T" % float(ex["contract__cell_duration_s"]))
        return v31_intervals(L, pk, st, t0, burned, present, R, H, g, Hn, W, law)
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


def to_ms(arr, exact):
    """Integer ms of every finite cell (rule §1); timestamp-derived cells must be within 1e-6 ms of their integer."""
    out = np.zeros(arr.shape, dtype=object)
    worst = F(0)
    for r, c in zip(*np.nonzero(np.isfinite(arr))):
        x = F(float(arr[r, c])) * 3600000
        n = round(x)                                     # Fraction round(): nearest, half to even
        if exact[r, c]:
            worst = max(worst, abs(x - n))
            if abs(x - n) >= F(1, 10**6):
                raise SystemExit("timestamp_exact cell %d,%d is %s ms from an integer" % (r, c, float(abs(x - n))))
        out[r, c] = n
    return out, worst


def v31_intervals(L, pk, st, t0, burned, present, R, H, g, Hn, W, law="envelope"):
    """law 'envelope': births from lo = firms_early, ends from hi = firms_constrained (rule §4).
    law 'scalar' (Leo, 2026-11-12, central member p/q = 1/1, shift 0): lo = hi = firms_early; birth t =
    floor_div(max(rel, 0), 300000)·300 s; kept iff finite, not export-burned, rel > −T·1000 and t < H; interval
    [t, t + T + Q) — the same as the envelope law with hi = lo, so one code path."""
    lo_z = np.load(L / "variants/firms_early.npz")
    hi_z = lo_z if law == "scalar" else np.load(L / "variants/firms_constrained.npz")
    lo, hi = lo_z["arrival_h"], hi_z["arrival_h"]
    lo_ms, w_lo = to_ms(lo, lo_z["timestamp_exact"])
    hi_ms, w_hi = to_ms(hi, hi_z["timestamp_exact"])
    start_ms = int((st - t0).total_seconds()) * 1000
    assert (st - t0).total_seconds() == int((st - t0).total_seconds())
    QMS = 300000
    out, sched, kept = {}, {}, 0
    bnd_lo = bnd_hi = 0
    for r in range(Hn):
        for c in range(W):
            if burned[r, c] or not (np.isfinite(lo[r, c]) and np.isfinite(hi[r, c])):
                continue
            rlo, rhi = lo_ms[r, c] - start_ms, hi_ms[r, c] - start_ms
            b = (max(rlo, 0) // QMS) * 300
            hr = (max(rhi, 0) // QMS) * 300
            if b < H and F(rhi) > -T * 1000:
                out.setdefault(g(r, c), []).append((F(b), F(hr) + T + Q)); kept += 1
                sched[g(r, c)] = (b, hr)
                # boundary cells: rel exactly on a 300 s multiple (> 0), where a binary64 floor could flip a quantum
                bnd_lo += rlo > 0 and rlo % QMS == 0
                bnd_hi += rhi > 0 and rhi % QMS == 0
    if R is not None and R > 0:
        for r, c in zip(*np.nonzero(present)):
            out.setdefault(g(r, c), []).append((F(0), R))
    return out, dict(h_ms=start_ms, R=str(R), igniting_cells=kept, present_cells=int(present.sum()),
                     export_burned=int(burned.sum()), timestamp_exact_lo=int(lo_z["timestamp_exact"].sum()),
                     timestamp_exact_hi=int(hi_z["timestamp_exact"].sum()),
                     worst_exact_recovery_ms=float(max(w_lo, w_hi)), boundary_cells_lo=int(bnd_lo),
                     boundary_cells_hi=int(bnd_hi), _sched=sched)


def integer_schedule(haz, mine, sched, Hs):
    """Integer equality (rule acceptance). For a cell with exactly one merged interval on both sides: the HAZARD start
    must equal the integer b exactly, and round(e_hazard − T − Q) must equal the integer hi_rel with a residue < 1 µs
    (binary64 representation of the same end). A cell whose ignition interval merges with present fire, or is clipped
    at H, is compared as merged sets: same starts exactly, ends within 1 µs."""
    one = start_eq = hr_eq = merged_eq = 0
    bad, worst = [], F(0)
    for k in set(mine) | set(haz):
        m, h = mine.get(k, []), haz.get(k, [])
        if len(m) != len(h):
            bad.append((k, "count")); continue
        if k in sched and len(m) == 1 and m[0][1] < Hs:
            b, hr = sched[k]
            one += 1
            (hb, he), = h
            start_eq += hb == b
            imp = he - T - Q
            worst = max(worst, abs(imp - round(imp)))
            ok = round(imp) == hr and abs(imp - round(imp)) < F(1, 10**6)
            hr_eq += ok
            if hb != b or not ok:
                bad.append((k, "b %s/%s hr %s/%s" % (b, hb, hr, float(imp))))
        else:
            ok = all(x0 == y0 and abs(x1 - y1) < F(1, 10**6) for (x0, x1), (y0, y1) in zip(m, h))
            merged_eq += ok
            if not ok:
                bad.append((k, "merged"))
    return dict(single_interval_cells=one, start_equal=start_eq, hi_rel_equal=hr_eq, merged_or_clipped_cells_equal=merged_eq,
                mismatches=len(bad), mismatch_examples=[list(map(str, x)) for x in bad[:5]],
                worst_end_residue_s=float(worst))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leo", required=True)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--origins", type=int, default=10)
    ap.add_argument("--mode", choices=["exact", "float", "v31"], default="exact")
    ap.add_argument("--law", choices=["envelope", "scalar"], default="envelope", help="v31 only: the packet's variant law")
    ap.add_argument("--tag", default="", help="suffix for the results file name")
    a = ap.parse_args()
    L = Path(a.leo) / "research/harness-2026-11/F-DYN/_data"
    pk = Path(a.leo) / a.packet
    region = pk.parent.name
    hz = json.loads((pk / "HAZARD.json").read_text())
    H = int(F(float(hz["valid_until"])))
    mine_raw, info = independent_intervals(L, pk, a.start, H, a.mode, a.law)
    info["mode"] = a.mode
    info["law"] = a.law
    sched = info.pop("_sched", None)
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
    if sched is not None:
        report["integer_schedule"] = integer_schedule(haz, mine, sched, Hs)
    print(json.dumps({k: v for k, v in report.items() if k != "other_examples"}), flush=True)
    g = json.loads((L / "graphs_interim" / region / "graph.json").read_text())
    pg = prepared(g)
    # origins are the region's graph entry nodes, the same for every start of that region and horizon
    inst = [i for i in json.loads((L / "INSTANCE.json").read_text())["instances"] if i["region"] == region and i["horizon_s"] == H][0]
    report["origins_from_instance"] = "%s %s" % (inst["region"], inst.get("start_tag"))

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
    (HERE / "results" / ("envelope_o2_%s%s.json" % (a.mode, "_" + a.tag if a.tag else ""))).write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
