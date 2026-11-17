"""Measure, on the six recorded caches, every hypothesis of THEOREM.md Theorem 2 (closure monotonicity) and its
conclusion (every feasible set is a prefix [0, L]).

Uses the repository's own reduction (deadline_field.real.PacketModel) and backward pass, unchanged. Read-only.

    python3 research/kcf-theorem/measure_assumptions.py --data-root <fetched data/routing> --out <json>
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
from deadline_field.core import backward, issue_set  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402


def is_suffix(ivs, top):
    """Set ∩ [0, top] is empty or [c, top]."""
    s = [(lo, min(hi, top)) for lo, hi in ivs if lo <= top]
    return not s or (len(s) == 1 and s[0][1] == top)


def is_prefix(ivs):
    return not ivs or (len(ivs) == 1 and ivs[0][0] == 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--variants", default="router,cert")
    a = ap.parse_args()
    report = []
    for cp in sorted(glob.glob(str(ROOT / "planner/cache/*/*.json"))):
        t0 = time.perf_counter()
        doc = json.loads(Path(cp).read_text())
        region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
        pm = PacketModel(a.data_root / "graphs" / region / "graph.json",
                         a.data_root / "latest_inputs_try02/packets" / region / compact)
        specs = {}
        for job in doc["route_checks"].values():
            q = job["request"]
            k = (q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))
            specs.setdefault(k, set()).add(q["start"]["node_id"])
        row = {"cache": str(Path(cp).relative_to(ROOT)), "H": pm.H, "specs": len(specs)}
        for var in a.variants.split(","):
            c = Counter()
            ex = {}
            for (dn, dwell, win), origins in sorted(specs.items(), key=str):
                inst = pm.instance(var, [{"node": dn, "dwell": dwell, "window": list(win)}], sorted(origins))
                H = inst.H
                if not c["_masks_done"]:
                    # B, W do not depend on the destination: count once per (cache, variant)
                    c["_masks_done"] = 1
                    for j, b in enumerate(inst.B):
                        top = H - inst.D[j]
                        if top < 0:
                            continue
                        c["edges"] += 1
                        if b:
                            c["edges_with_block"] += 1
                        if not is_suffix(b, top):
                            c["B_not_suffix"] += 1
                            ex.setdefault("B_not_suffix", (j, b[:3], inst.D[j]))
                    for v, w in enumerate(inst.W):
                        if inst.waitable[v]:
                            c["waitable_nodes"] += 1
                            if not is_suffix(w, H - 1):
                                c["W_not_suffix"] += 1
                                ex.setdefault("W_not_suffix", (v, w[:3]))
                acc = next((x for x in inst.A if x), [])
                c["dest_specs"] += 1
                if not is_prefix(acc):
                    c["A_not_prefix"] += 1
                    ex.setdefault("A_not_prefix", (dn, win, acc[:3]))
                for o, ib in inst.IB.items():
                    c["origin_issue_checks"] += 1
                    if not is_suffix(ib, H):
                        c["IB_not_suffix"] += 1
                fld = backward(inst)
                for s in range(len(inst.tail)):
                    if fld.G[s]:
                        c["G_nonempty"] += 1
                        if not is_prefix(fld.G[s]):
                            c["G_not_prefix"] += 1
                for o in origins:
                    fs = issue_set(fld, pm.nidx[o])
                    c["origin_sets"] += 1
                    if fs and not is_prefix(fs):
                        c["origin_set_not_prefix"] += 1
                        ex.setdefault("origin_set_not_prefix", []).append((o, dn, win, fs[:3])) if len(
                            ex.get("origin_set_not_prefix", [])) < 5 else None
            c.pop("_masks_done", None)
            row[var] = {"counts": dict(c), "examples": ex}
        row["seconds"] = round(time.perf_counter() - t0, 1)
        print(json.dumps(row, default=str), flush=True)
        report.append(row)
    a.out.write_text(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main()
