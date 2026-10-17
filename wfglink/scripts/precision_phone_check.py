"""Strict phone non-regression for the precision verifier (2026-10-17), on the committed source.

The phone (ember) mode must be unchanged. Run from a committed export:

    bash scripts/run_from_head.sh python scripts/precision_phone_check.py --out results/runs/precision_20261017/phone

1. Source identity: the phone tracker, pipeline, camera and source files hash exactly as in the
   verified release comparison (results/validation/continuation_20261015/phone_fullrate_comparison.json).
2. The executed exact-history harness of that release (phone_uncertainty_compare_fullrate_executed.txt),
   unchanged, against the original tracker of 2d87bf3 (git show 2d87bf3:wfglink/src/wfglink/ember/track.py):
   every full-rate history, legacy track field and quality/speed/ruler report must be exact (its asserts).
3. validate --suite ember: every numeric field of the official report equals the release report
   (results/validation/continuation_20261015/ember_report.json), timing and provenance fields excluded.
4. check_ember_stride.py --seconds 60: equal to the release stride report, timing excluded.
Writes <out>/phone_check.json and exits non-zero on any failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "results/validation/continuation_20261015"
EXCLUDED = {"created", "report_path", "proc_ms_median", "proc_ms_p95", "git_dirty", "git_commit", "git_branch",
            "ms", "ms_median", "ms_p95", "wall_s", "elapsed_s", "out", "config_path"}


def numeric(v):
    if isinstance(v, dict):
        return {k: numeric(x) for k, x in v.items() if k not in EXCLUDED and not k.endswith("_ms")}
    if isinstance(v, list):
        return [numeric(x) for x in v]
    return v


def diff(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'new' if k in b else 'release'}")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=60.0)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    rec: dict = {"checks": {}}
    ok = True

    ref = json.loads((REL / "phone_fullrate_comparison.json").read_text())["source_sha256"]
    now = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ref}
    rec["checks"]["source_identity"] = {"pass": now == ref, "release": ref, "now": now}
    ok &= now == ref

    harness = out / "compare_fullrate.py"
    harness.write_bytes((REL / "phone_uncertainty_compare_fullrate_executed.txt").read_bytes())
    base = subprocess.run(["git", "-C", str(ROOT), "show", "2d87bf3:wfglink/src/wfglink/ember/track.py"],
                          capture_output=True, check=True).stdout
    (out / "baseline_track.py").write_bytes(base)
    r = subprocess.run([py, str(harness), "--out-dir", str(out)], cwd=ROOT, capture_output=True, text=True)
    (out / "harness.log").write_text(r.stdout + r.stderr)
    comp = json.loads((out / "fullrate_comparison.json").read_text()) if (out / "fullrate_comparison.json").exists() else {}
    hp = r.returncode == 0 and all(comp.get(k) for k in ("all_histories_and_legacy_tracks_exact",
                                                         "quality_speed_ruler_reports_exact", "exact_speed_rows_match"))
    rec["checks"]["exact_history_harness"] = {"pass": hp, "returncode": r.returncode,
                                              "baseline_track_sha256": hashlib.sha256(base).hexdigest(),
                                              **{k: comp.get(k) for k in ("all_histories_and_legacy_tracks_exact",
                                                                          "quality_speed_ruler_reports_exact",
                                                                          "exact_speed_rows_match")}}
    ok &= hp

    rep = out / "ember_report.json"
    r = subprocess.run([py, "-m", "wfglink", "validate", "--suite", "ember", "--out", str(rep)], cwd=ROOT,
                       capture_output=True, text=True)
    (out / "validate_ember.log").write_text(r.stdout + r.stderr)
    d = diff(numeric(json.loads((REL / "ember_report.json").read_text())), numeric(json.loads(rep.read_text()))) \
        if rep.exists() else ["no report"]
    rec["checks"]["validate_ember"] = {"pass": r.returncode in (0, 1) and not d, "returncode": r.returncode,
                                       "differences": d[:50], "n_differences": len(d),
                                       "note": "exit code 1 means a goal is missed, as in the release (identity switches)"}
    ok &= not d

    srep = out / "stride_report.json"
    r = subprocess.run([py, "scripts/check_ember_stride.py", "--seconds", str(a.seconds), "--out", str(srep)], cwd=ROOT,
                       capture_output=True, text=True)
    (out / "stride.log").write_text(r.stdout + r.stderr)
    d = diff(numeric(json.loads((REL / "stride_report.json").read_text())), numeric(json.loads(srep.read_text()))) \
        if srep.exists() else ["no report"]
    rec["checks"]["stride"] = {"pass": not d, "returncode": r.returncode, "differences": d[:50], "n_differences": len(d)}
    ok &= not d

    rec["pass"] = bool(ok)
    (out / "phone_check.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: v.get("pass") for k, v in rec["checks"].items()}, indent=1), "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
