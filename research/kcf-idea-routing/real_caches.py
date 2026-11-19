"""Exactness of the margin field on the six recorded caches (planner/cache/*/*.json).

For every cache, both contact rules (router, cert), every destination spec, and both acceptance variants (keep,
erode): one margin pass with M = 600 s, then for every margin in MARGINS the existing ``core.backward`` is run on the
widened instance and compared, set by set:

  * R and G of every edge state;
  * the issue set of every recorded origin of the spec;
  * the margin fixed-point certificate (METHOD.md, equation E_mu);
  * (keep variant, margins 0, 60, 600) the witness route at the last feasible second of every origin, taken from the
    field read off the margin field, is checked by the independent checker (research/kcf-theorem/checker.py) against
    masks widened here, second by interval, without ``field.widen``.

The existing code is imported unchanged. Usage (one cache per process):

    python3 research/kcf-idea-routing/real_caches.py --data-root data/routing --only <substring> --out <json>
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/kcf-theorem"))
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
import checker  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from differential_witnesses import sub_instance  # noqa: E402
from margin_field import field as mf  # noqa: E402
from margin_field import pl  # noqa: E402

M = 600
MARGINS = (0, 1, 10, 30, 60, 120, 300, 600)
WITNESS_MARGINS = (0, 60, 600)


def cache_specs(doc):
    specs = {}
    for job in doc["route_checks"].values():
        q = job["request"]
        k = (q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))
        specs.setdefault(k, set()).add(q["start"]["node_id"])
    return sorted(specs.items(), key=str)


def load(cp, data_root):
    doc = json.loads(Path(cp).read_text())
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    pm = PacketModel(data_root / "graphs" / region / "graph.json",
                     data_root / "latest_inputs_try02/packets" / region / compact)
    return doc, pm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", help="substring of the cache path (default: all six)")
    ap.add_argument("--variants", default="router,cert")
    a = ap.parse_args()
    report = []
    for cp in sorted(glob.glob(str(ROOT / "planner/cache/*/*.json"))):
        if a.only and a.only not in cp:
            continue
        t_start = time.perf_counter()
        doc, pm = load(cp, a.data_root)
        row = {"cache": str(Path(cp).relative_to(ROOT)), "H": pm.H, "M": M, "margins": list(MARGINS)}
        for var in a.variants.split(","):
            c = Counter()
            t_new = t_old = 0.0
            curves = {}
            first_bad = None
            for (dn, dwell, win), origins in cache_specs(doc):
                inst = pm.instance(var, [{"node": dn, "dwell": dwell, "window": list(win)}], sorted(origins))
                E = len(inst.tail)
                c["specs"] += 1
                for erode in (False, True):
                    tag = "erode" if erode else "keep"
                    t0 = time.perf_counter()
                    fld = mf.margin_field(inst, M, erode_accept=erode)
                    t_new += time.perf_counter() - t0
                    mf.check_fixed_point(fld)
                    c[tag + ":margin_fixed_point_ok"] += 1
                    c[tag + ":pieces"] += fld.stats["pieces"]
                    c[tag + ":max_pieces_per_state"] = max(c[tag + ":max_pieces_per_state"], fld.stats["max_pieces"])
                    c[tag + ":pops"] += fld.stats["pops"]
                    fo = {o: mf.issue_margin(fld, pm.nidx[o]) for o in origins}
                    for m in MARGINS:
                        wi = mf.widen(inst, m, erode_accept=erode)
                        t0 = time.perf_counter()
                        ref = backward(wi)
                        t_old += time.perf_counter() - t0
                        c[tag + ":existing_pushes"] += ref.stats["pushes"]
                        bad = 0
                        for s in range(E):
                            if pl.level_set(fld.mu[s], m) != ref.R[s] or pl.level_set(fld.gamma[s], m) != ref.G[s]:
                                bad += 1
                            if ref.G[s]:
                                c[tag + ":nonempty_G_sets"] += 1
                                c[tag + ":G_sets_not_prefix"] += not (len(ref.G[s]) == 1 and ref.G[s][0][0] == 0)
                        c[tag + ":state_sets_compared"] += 2 * E
                        c[tag + ":state_sets_MISMATCH"] += bad
                        for o in sorted(origins):
                            oi = pm.nidx[o]
                            want = issue_set(ref, oi)
                            got = pl.level_set(fo[o], m)
                            c[tag + ":origin_sets_compared"] += 1
                            if got != want:
                                c[tag + ":origin_sets_MISMATCH"] += 1
                                first_bad = first_bad or {"spec": [dn, dwell, list(win)], "origin": o, "m": m,
                                                          "got": got[:3], "want": want[:3], "variant": tag}
                            c[tag + ":origin_sets_nonempty"] += bool(want)
                            c[tag + ":origin_sets_not_prefix"] += bool(want) and not (
                                len(want) == 1 and want[0][0] == 0)
                        if not erode and m in WITNESS_MARGINS:
                            fa = mf.field_at(fld, m)
                            for o in sorted(origins):
                                oi = pm.nidx[o]
                                S = pl.level_set(fo[o], m)
                                if not S:
                                    continue
                                L = S[-1][1]
                                w = witness(fa, oi, L)
                                d, route, ni = sub_instance(inst, w[1])
                                for k in ("B", "W", "IB"):                 # widen here, independent of field.widen
                                    d[k] = {x: [[lo - m, hi + m] for lo, hi in v] for x, v in d[k].items()}
                                if not route:
                                    c["witness:empty_route"] += 1
                                    continue
                                ok, why = checker.check_route(d, ni[oi], L, route)
                                c["witness:" + ("VALID" if ok else "INVALID")] += 1
                                if not ok:
                                    first_bad = first_bad or {"witness": why, "origin": o, "m": m}
                    if not erode and var == "cert":
                        for o in sorted(origins):
                            curves.setdefault(o, {})[str(dn)] = mf.leave_by(fld, pm.nidx[o])
            row[var] = {"counts": dict(sorted(c.items())), "first_mismatch": first_bad,
                        "seconds_margin_passes_M600": round(t_new, 2),
                        "seconds_existing_passes_%d_margins" % len(MARGINS): round(t_old, 2)}
            if curves:
                row["leave_by_curves_cert_keep"] = curves
        row["seconds_total"] = round(time.perf_counter() - t_start, 1)
        print(json.dumps({k: v for k, v in row.items() if k != "leave_by_curves_cert_keep"}), flush=True)
        report.append(row)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
