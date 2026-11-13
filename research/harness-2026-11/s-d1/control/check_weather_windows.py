"""Coverage of the 273 stored heldout cases (6a3265a0) by Daniel's rebuilt US2024 weather bands (night 1).
A case is covered iff first_band <= cutoff and endpoint <= last_band for its event. Uncovered cases are reported, not dropped.

    python check_weather_windows.py CASES_DIR WINDOWS_JSON OUT_JSON
"""
import hashlib, json, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

def t(s): return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

cases, win, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
W = json.loads(win.read_text())
rows, per = [], Counter()
for f in sorted(cases.glob("*.json")):
    c = json.loads(f.read_text())["case"]
    w = W.get(c["event"])
    if w is None:
        rows.append(dict(case=f.stem, event=c["event"], covered=None, reason="event not in weather summary")); continue
    lo, hi = t(w["first_band_utc"]), t(w["last_band_utc"])
    cu, en = t(c["cutoff"]), t(c["endpoint"])
    ok = lo <= cu and en <= hi
    per[(c["event"], ok)] += 1
    rows.append(dict(case=f.stem, event=c["event"], cutoff=c["cutoff"], endpoint=c["endpoint"], covered=ok,
                     margin_before_h=(cu - lo).total_seconds() / 3600, margin_after_h=(hi - en).total_seconds() / 3600))
cov = [r for r in rows if r["covered"]]
res = dict(windows_sha256=hashlib.sha256(win.read_bytes()).hexdigest(), n_cases=len(rows), covered=len(cov),
           uncovered=[r for r in rows if not r["covered"]],
           per_event={e: dict(covered=per[(e, True)], uncovered=per[(e, False)]) for e in sorted({r["event"] for r in rows})},
           min_margin_before_h=min(r["margin_before_h"] for r in cov) if cov else None,
           min_margin_after_h=min(r["margin_after_h"] for r in cov) if cov else None, rows=rows)
out.write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps({k: res[k] for k in ("windows_sha256", "n_cases", "covered", "per_event", "min_margin_before_h", "min_margin_after_h")}, indent=1))
print("uncovered:", len(res["uncovered"]))
