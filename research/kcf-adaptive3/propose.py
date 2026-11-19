#!/usr/bin/env python3
"""One step of the bounded agent loop (PROTOCOL section 4). CA-DEV only.

    python3 propose.py 0 "version 0" '{}'                     # scores version 0 and makes it the kept version
    python3 propose.py 3 "reason ..." '{"temper": 0.5}'       # kept version + this change; kept or discarded by the frozen rule
Log: derived/proposals.jsonl (every proposal, kept or not); kept version: derived/kept.json.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import json, sys, time, traceback
from lib3 import *

LOG, KEPT = HERE / "derived" / "proposals.jsonl", HERE / "derived" / "kept.json"
MAX = 20


def main():
    n, reason, delta = int(sys.argv[1]), sys.argv[2], json.loads(sys.argv[3])
    done = [json.loads(l) for l in open(LOG)] if LOG.exists() else []
    if any(d["n"] == n for d in done):
        raise SystemExit(f"proposal {n} already logged")
    if n > MAX:
        raise SystemExit("the 20-proposal budget is spent")
    if (HERE / "derived" / "final_ca.json").exists():
        raise SystemExit("the final run has been made: no more proposals")
    cur = json.load(open(KEPT)) if KEPT.exists() else None
    base = cur["cfg"] if cur else dict(V0)
    cfg = dict(base, **delta)
    rec = dict(n=n, reason=reason, change=delta, time_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    try:
        r = dev_cv(load(), Tracker("TRACKER", cfg))
        rec.update(M1=r["M1"], M2=r["M2"], warned=r["warned"], run_days=r["run_days"], miss=r["miss"], area=r["area"])
        if cur is None:
            rec["kept"] = True
            rec["rule"] = "version 0"
        else:
            a = r["M1"] <= 0.99 * cur["M1"] and r["M2"] >= cur["M2"]
            b = r["M2"] > cur["M2"] and r["M1"] <= 1.01 * cur["M1"]
            rec["kept"] = bool(a or b)
            rec["rule"] = ("M1 down >= 1%, M2 not down" if a else "M2 up, M1 not up > 1%" if b else "neither")
            rec["against"] = dict(n=cur["n"], M1=cur["M1"], M2=cur["M2"])
        if rec["kept"]:
            json.dump(dict(n=n, cfg=cfg, M1=r["M1"], M2=r["M2"]), open(KEPT, "w"), indent=1)
    except Exception as e:      # a proposal that fails to run is logged and discarded
        rec.update(kept=False, rule="failed to run", error=repr(e), trace=traceback.format_exc()[-400:])
    with open(LOG, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "trace"}))


if __name__ == "__main__":
    main()
