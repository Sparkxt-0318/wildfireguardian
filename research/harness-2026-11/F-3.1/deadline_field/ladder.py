"""Deadline ladder per place and start across the F-DYN variants (SCENARIO, not what happened).

Per (region, start, horizon, origin): the contiguous deadline (merged rule) under each variant, with its soundness
label, ordered from the most to the least pessimistic in intent:
  envelope_burnset : sound relative to the final mapped burn set (fire never mapped is outside it); single
                     implementation, not independently checked
  firms_early      : bracket-start, not a lower bound
  kriged_mean      : central scenario (no soundness claim)
  envelope         : bracket-start, not a lower bound
None of the variants is a bound on another (measured: envelope vs kriged is not ordered), so the ladder is a list,
not an interval. Per origin also: spread (max - min over variants with a deadline), hole flag under any variant,
dose upper_bound flag (two placeholder dependencies). Not included: forecast-dependent flag on F-DYN (needs
present-only F-DYN fields, not run).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ORDER = ("envelope_burnset", "firms_early", "kriged_mean", "envelope")
LABELS = {"envelope_burnset": "sound relative to the final mapped burn set (fire never mapped is outside it); single "
                              "implementation, not independently checked",
          "firms_early": "bracket-start, not a lower bound", "kriged_mean": "central scenario, no soundness claim",
          "envelope": "bracket-start, not a lower bound"}


def contiguous(u):
    return u[0][1] if u and u[0][0] == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v31-claim", type=Path, required=True)
    ap.add_argument("--v33-dir", type=Path, required=True, help="raw fdyn_run outputs of the v3.3 variants")
    ap.add_argument("--v31-dir", type=Path, help="raw v3.1 outputs (for per-witness upper_bound labels)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    packets = {}
    for p in json.loads(a.v31_claim.read_text())["packets"]:
        packets[(p["region"], p["start"], p["horizon_h"], p["variant"])] = p
    for f in sorted(a.v33_dir.glob("*.json")):
        d = json.loads(f.read_text())
        e = d["manifest_entry"]
        packets[(e["region"], e["start"], e["horizon_h"], e["variant"])] = d
    ub = defaultdict(set)
    if a.v31_dir:
        for k, p in packets.items():
            f = a.v31_dir / ("%s__%s_h%d_%s.json" % k)
            if f.exists():
                for c in json.loads(f.read_text())["checks"]:
                    if not c["exact_full_policy"]:
                        ub[k].add(c["origin"])
    for k, p in packets.items():
        for c in p.get("checks", []):
            if not c["exact_full_policy"]:
                ub[k].add(c["origin"])
    groups = sorted({k[:3] for k in packets})
    rows, summ = [], {}
    for g in groups:
        vs = [v for v in ORDER if g + (v,) in packets]
        oids = sorted(packets[g + (vs[0],)]["origins_detail"])
        spread, cnt = [], Counter()
        for oid in oids:
            r = {"region": g[0], "start": g[1], "horizon_h": g[2], "origin": oid, "ladder": {}}
            hole = dose = False
            for v in vs:
                o = packets[g + (v,)]["origins_detail"][oid]
                u = o["union_cert"]
                r["ladder"][v] = contiguous(u)
                hole |= bool(u) and (len(u) > 1 or u[0][0] > 0)
                dose |= o["entry_node"] in ub[g + (v,)]
            have = [x for x in r["ladder"].values() if x is not None]
            r["spread_s"] = max(have) - min(have) if len(have) > 1 else 0 if have else None
            r["deadline_in_all_variants"] = len(have) == len(vs)
            r["hole_in_some_variant"] = hole
            r["dose_upper_bound_in_some_variant"] = dose
            rows.append(r)
            if r["spread_s"] is not None:
                spread.append(r["spread_s"])
            cnt["deadline_in_all"] += r["deadline_in_all_variants"]
            cnt["deadline_in_none"] += not have
            cnt["hole"] += hole
            cnt["dose_ub"] += dose
        spread.sort()
        summ["%s %s h%d" % g] = {"variants": vs, "origins": len(oids), **cnt,
                                 "spread_s": {"median": spread[len(spread) // 2] if spread else None,
                                              "max": spread[-1] if spread else None,
                                              "n_gt_30min": sum(s > 1800 for s in spread)}}
    out = {"what": "deadline ladder per place and start (contiguous deadlines; SCENARIO, not what happened; roads "
                   "limited to the recorded windows). Not a bound ordering: variants are not nested.",
           "labels": LABELS, "order": ORDER, "summary": summ, "rows": rows,
           "not_included": "forecast-dependent flag on F-DYN (present-only F-DYN fields not run); envelope_sound "
                           "(withdrawn)"}
    a.out.write_text(json.dumps(out, indent=1))
    for k, v in summ.items():
        print(k, json.dumps({x: v[x] for x in v if x != "variants"}))


if __name__ == "__main__":
    main()
