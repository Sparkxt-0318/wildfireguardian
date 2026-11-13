"""F-DYN v3.3 envelope / envelope_burnset report (SCENARIO, not what happened; roads limited to the recorded windows).

Per region-start and horizon, and per region (sum over its starts): origins with a checked route at the start
(contiguous deadline exists) and origins whose contiguous deadline is unchanged against the kriged_mean packet of the
same start and horizon (v3.1). Labels:
  envelope        : bracket-start, not a lower bound
  envelope_burnset: sound relative to the final mapped burn set (fire never mapped is outside it); single
                    implementation, not independently checked
Witness verdicts (unchanged full checker + closed replay) per packet. Optional: burnset blocked-road fraction file.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

LABELS = {"envelope": "bracket-start, not a lower bound",
          "envelope_burnset": "sound relative to the final mapped burn set (fire never mapped is outside it); "
                              "single implementation, not independently checked"}


def contiguous(u):
    return u[0][1] if u and u[0][0] == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v33-dir", type=Path, required=True)
    ap.add_argument("--v31-claim", type=Path, required=True, help="results/FDYN_V31_recorded_starts.json")
    ap.add_argument("--blocked", type=Path, help="burnset blocked-road fractions (JSON)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    base = {(p["region"], p["start"], p["horizon_h"]): p for p in json.loads(a.v31_claim.read_text())["packets"]
            if p["variant"] == "kriged_mean"}
    rows, per_region = [], defaultdict(lambda: defaultdict(int))
    for f in sorted(a.v33_dir.glob("*.json")):
        d = json.loads(f.read_text())
        e = d["manifest_entry"]
        b = base[(e["region"], e["start"], e["horizon_h"])]
        n = checked = unchanged = 0
        for oid, o in d["origins_detail"].items():
            c, c0 = contiguous(o["union_cert"]), contiguous(b["origins_detail"][oid]["union_cert"])
            n += 1
            checked += c is not None
            unchanged += c is not None and c == c0
        wc = d["witness_checks"]
        r = {"region": e["region"], "start": e["start"], "horizon_h": e["horizon_h"], "variant": e["variant"],
             "label": LABELS[e["variant"]], "manifest_soundness": e.get("soundness"), "hazard_sha256": d.get("hazard_sha256"),
             "origins": n, "checked_route_at_start": checked, "baseline_kriged_checked": sum(
                 contiguous(x["union_cert"]) is not None for x in b["origins_detail"].values()),
             "deadline_unchanged_vs_kriged": unchanged, "classes": d["classes"], "witness_checks": wc,
             "witness_fail": sum(v for k, v in wc.items() if "FAIL" in k), "holes_cert": d["holes_cert"]}
        rows.append(r)
        k = (e["region"], e["horizon_h"], e["variant"])
        for x in ("origins", "checked_route_at_start", "deadline_unchanged_vs_kriged", "witness_fail"):
            per_region[k][x] += r[x]
    out = {"what": "F-DYN v3.3 envelope variants vs kriged_mean (v3.1), contiguous deadlines (merged rule); SCENARIO, "
                   "not what happened; envelope_sound is withdrawn and not scored",
           "labels": LABELS, "per_region_start": rows,
           "per_region": [{"region": k[0], "horizon_h": k[1], "variant": k[2], **v} for k, v in sorted(per_region.items())]}
    if a.blocked:
        out["burnset_blocked_roads"] = json.loads(a.blocked.read_text())
    a.out.write_text(json.dumps(out, indent=1))
    for r in rows:
        print("%-20s %s h%d %-16s checked %2d/%2d (kriged %2d) unchanged %2d fail %d" % (
            r["region"], r["start"], r["horizon_h"], r["variant"], r["checked_route_at_start"], r["origins"],
            r["baseline_kriged_checked"], r["deadline_unchanged_vs_kriged"], r["witness_fail"]))
    for p in out["per_region"]:
        print(p)


if __name__ == "__main__":
    main()
