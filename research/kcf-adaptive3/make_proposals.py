#!/usr/bin/env python3
"""Write PROPOSALS.md from derived/proposals.jsonl and derived/dev_log.jsonl (every proposal, kept or not)."""
import json
from pathlib import Path

H = Path(__file__).resolve().parent
P = [json.loads(l) for l in open(H / "derived" / "proposals.jsonl")]
dev = {}
for l in open(H / "derived" / "dev_log.jsonl"):
    d = json.loads(l)
    dev[d["name"]] = d
kept = json.load(open(H / "derived" / "kept.json"))
o = ["# PROPOSALS: the bounded agent loop (PROTOCOL section 4)", "",
     "Scored on the 16 CA-DEV fires only, 4-fold by-fire cross-validation. **M1** = flagged area read at exactly 10% "
     "cross-validated miss (km2, lower is better). **M2** = run fire-days warned at their first run hour, of 72, with the "
     "threshold set so that at most 10% of fire-days without a run alarm (higher is better). Kept if M1 falls by at least "
     "1% and M2 does not fall, or M2 rises and M1 does not rise by more than 1%; each proposal is the kept version plus "
     "one change. The proposals were written by the agent from CA-DEV diagnostics. 20 of 20 used.", "",
     f"Reference points on the same folds: FIXED M1 {dev['FIXED']['M1']:.1f}; QUANTILE M1 {dev['QUANTILE']['M1']:.1f}; "
     f"version 0 with the update off {dev['TRACKER-noupdate']['M1']:.1f} (M2 {dev['TRACKER-noupdate']['warned']} of 72); "
     f"version 0 with the forecast off {dev['TRACKER-nofc']['M1']:.1f} (M2 {dev['TRACKER-nofc']['warned']} of 72). "
     "(The two ablations were scored for version 0 only, before the loop.)", "",
     "| # | Change | Reason | M1 (km2) | M2 (of 72) | Kept | Rule |", "|---|---|---|---|---|---|---|"]
for p in P:
    ch = json.dumps(p["change"]) if p["change"] else "version 0"
    o.append(f"| {p['n']} | `{ch}` | {p['reason']} | {p.get('M1', float('nan')):.1f} | {p.get('warned', '-')} | "
             f"{'**kept**' if p['kept'] else 'no'} | {p['rule']} |")
k = [p for p in P if p["kept"]]
o += ["", f"**Kept version** (proposal {kept['n']}): version 0 plus " + ", ".join(json.dumps(p["change"]) for p in k[1:]) +
      f". M1 {kept['M1']:.1f} km2, M2 {round(kept['M2'] * 72)} of 72.", "",
      "Read with care: 20 tries on 16 fires. The kept changes each moved M1 by 0.2% to 3% and M2 by 1 to 6 days of 72; "
      "the last two were kept on M2 gains of one and two run-days, which is within noise. No proposal failed to run."]
open(H / "PROPOSALS.md", "w").write("\n".join(o) + "\n")
print("\n".join(o[-6:]))
