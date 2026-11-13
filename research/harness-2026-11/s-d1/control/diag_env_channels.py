"""ADDITIONAL DIAGNOSTIC, outside REBUILT_INPUT_PLAN (orchestrator 2026-11-13 03:50Z; rule fixed before running):
are the rebuilt US2024 inputs a reproduction of the owner-archive inputs, channel by channel, on all 273 stored cases?

Rule (reported, no threshold, no pass/fail):
- For each stored case (case_id as in rebuilt_input_run.py), sample.environment is built by the unmodified
  pipeline.perimeter_samples under (A) Daniel's rebuilt inputs (pins 286f4c47) and (B) the owner-archive inputs used by
  the unmodified-rollout control (pins computed from the extracted, CRC-checked archive members, as the control does).
- Per channel: EQUAL iff the finite masks are identical and every finite value is identical (max |A-B| = 0).
  Otherwise record max |A-B| over cells finite in both, the fraction of such cells that differ, and the count of
  cells finite in exactly one of A, B.
- Summary per channel: cases EQUAL (of 273), max of max|A-B| over cases, max fraction changed, total finite mismatches.
- Wording fixed: a result of near-zero |Δp| that coincides with equal channels is "reproduction of the inputs", not
  evidence that the model is insensitive to its inputs.

    python diag_env_channels.py --new WS/data/environment --new-pins PINS.json --old ARCH/wildfire/data/environment \
        --perimeters PERIM --heldout HELDOUT --work W --out DIAG_env_channels.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import unmodified_rollout_control as U  # noqa: E402

import numpy as np  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("--new", "--new-pins", "--old", "--perimeters", "--heldout", "--work", "--out"):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    P = U.load_module("full_cohort_pipeline", U.SCRIPTS / "pipeline.py")
    new_pins = json.loads(a.new_pins.read_text())
    e_new = P.Environment(a.new.resolve(), a.work / "new", input_sha256=new_pins)
    ro = a.old.resolve()
    old_pins = {str(p.relative_to(ro.parent)): U.sha(p) for p in ro.rglob("*") if p.is_file()}
    e_old = P.Environment(ro, a.work / "old", input_sha256=old_pins)
    if tuple(e_new.names) != tuple(e_old.names):
        raise SystemExit("channel names differ")
    names = list(e_new.names)
    stored = {p.stem for p in (a.heldout / "cases").glob("*.json")}
    cases = []
    for event in U.EVENTS:
        sn = P.perimeter_samples(event, a.perimeters, e_new, crop=False)
        so = P.perimeter_samples(event, a.perimeters, e_old, crop=False)
        if [s.t1 for s in sn] != [s.t1 for s in so]:
            raise SystemExit(f"interval sets differ for {event}")
        for s1, s0 in zip(sn, so):
            case = dict(event=event, cutoff=s1.t1, endpoint=s1.meta["t2"], hours=s1.hours)
            cid = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()[:24]
            if cid not in stored:
                continue
            x, y = s1.environment.astype(np.float64), s0.environment.astype(np.float64)
            per = {}
            for i, n in enumerate(names):
                fx, fy = np.isfinite(x[i]), np.isfinite(y[i])
                both = fx & fy
                d = np.abs(x[i][both] - y[i][both])
                per[n] = dict(equal=bool((fx == fy).all() and (d.size == 0 or d.max() == 0)),
                              max_abs=float(d.max()) if d.size else 0.0,
                              frac_changed=float((d > 0).mean()) if d.size else 0.0,
                              finite_mismatch=int((fx != fy).sum()))
            cases.append(dict(case_id=cid, event=event, cutoff=s1.t1, channels=per,
                              all_equal=all(v["equal"] for v in per.values())))
    summary = {n: dict(cases_equal=sum(c["channels"][n]["equal"] for c in cases),
                       max_abs=max(c["channels"][n]["max_abs"] for c in cases),
                       max_frac_changed=max(c["channels"][n]["frac_changed"] for c in cases),
                       finite_mismatch_total=sum(c["channels"][n]["finite_mismatch"] for c in cases)) for n in names}
    out = dict(label="ADDITIONAL DIAGNOSTIC outside REBUILT_INPUT_PLAN; reproduction of inputs, not evidence of model insensitivity",
               script_sha256=U.sha(__file__), new_pins_sha256=U.sha(a.new_pins), n_old_files=len(old_pins),
               old_inputs_digest=hashlib.sha256(json.dumps(sorted(old_pins.items())).encode()).hexdigest(),
               n_cases=len(cases), stored_cases=len(stored), cases_all_channels_equal=sum(c["all_equal"] for c in cases),
               per_channel=summary, cases=cases)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "cases"}, indent=1))


if __name__ == "__main__":
    main()
