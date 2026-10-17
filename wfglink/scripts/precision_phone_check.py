"""Strict phone non-regression for the precision verifier (2026-10-17), on the committed source.

The phone (ember) mode must be unchanged. Run from a committed export:

    bash scripts/run_from_head.sh python scripts/precision_phone_check.py --out results/runs/precision_20261017/phone

Gate (all must hold):
1. Source identity: the phone tracker, pipeline, camera and source files hash exactly as in the
   verified release comparison (results/validation/continuation_20261015/phone_fullrate_comparison.json).
2. Same-host equality with the release: the release commit (--reference, default 4d0092c, the
   published demo) is exported and run on this host next to the source under test, and every
   output must be equal: the release's executed exact-history harness (against the original
   tracker of 2d87bf3), validate --suite ember and check_ember_stride.py --seconds 60 (timing and
   provenance fields and temporary paths excluded).
Reported, not part of the gate: each report compared with the release's saved reports from the
booth Mac, and the harness's own asserts on this host. The synthetic phone videos are encoded
and decoded by platform builds, so a cross-platform difference with identical source is a
platform property (see results/validation/precision_20261017/c5_baseline_discrepancy.json), not a
code change; the same-host comparison isolates the code.
Writes <out>/phone_check.json and exits non-zero when the gate fails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "results/validation/continuation_20261015"
EXCLUDED = {"created", "report_path", "proc_ms_median", "proc_ms_p95", "git_dirty", "git_commit", "git_branch",
            "ms", "ms_median", "ms_p95", "wall_s", "elapsed_s", "out", "config_path"}
TMP_PATH = re.compile(r"\S*/wfglink(?=/data/)")      # the tree a report was made in: temporary or the checkout


def numeric(v):
    if isinstance(v, dict):
        return {k: numeric(x) for k, x in v.items() if k not in EXCLUDED and not k.endswith("_ms")}
    if isinstance(v, list):
        return [numeric(x) for x in v]
    if isinstance(v, str):
        return TMP_PATH.sub("<tree>", v)
    return v


def diff(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'second' if k in b else 'first'}")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def run_tree(tree: Path, out: Path, seconds: float, baseline: bytes) -> dict:
    """The three phone runs with the code of `tree`, outputs in `out`."""
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(tree / "src")}
    py = sys.executable
    harness = out / "compare_fullrate.py"
    harness.write_bytes((REL / "phone_uncertainty_compare_fullrate_executed.txt").read_bytes())
    (out / "baseline_track.py").write_bytes(baseline)
    res = {}
    r = subprocess.run([py, str(harness), "--out-dir", str(out)], cwd=tree, env=env, capture_output=True, text=True)
    (out / "harness.log").write_text(r.stdout + r.stderr)
    res["harness_returncode"] = r.returncode
    r = subprocess.run([py, "-m", "wfglink", "validate", "--suite", "ember", "--out", str(out / "ember_report.json")],
                       cwd=tree, env=env, capture_output=True, text=True)
    (out / "validate_ember.log").write_text(r.stdout + r.stderr)
    res["validate_returncode"] = r.returncode
    stride = tree / "scripts" / "check_ember_stride.py"
    if not stride.is_file():
        raise SystemExit(f"{stride} is missing")
    r = subprocess.run([py, str(stride), "--seconds", str(seconds), "--out",
                        str(out / "stride_report.json")], cwd=tree, env=env, capture_output=True, text=True)
    (out / "stride.log").write_text(r.stdout + r.stderr)
    res["stride_returncode"] = r.returncode
    return res


def load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--reference", default="4d0092c")
    ap.add_argument("--seconds", type=float, default=60.0)
    a = ap.parse_args()
    out = Path(a.out).resolve()                   # absolute: each tree runs in its own folder
    out.mkdir(parents=True, exist_ok=True)
    repo = (ROOT / "results").resolve().parent   # run_from_head links results to the checkout, a git work tree
    rec: dict = {"reference_commit": a.reference, "checks": {}, "informational": {}}

    ref = json.loads((REL / "phone_fullrate_comparison.json").read_text())["source_sha256"]
    now = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ref}
    rec["checks"]["source_identity"] = {"pass": now == ref, "release": ref, "now": now}

    baseline = subprocess.run(["git", "-C", str(repo), "show", "2d87bf3:wfglink/src/wfglink/ember/track.py"],
                              capture_output=True, check=True).stdout
    rec["baseline_track_sha256"] = hashlib.sha256(baseline).hexdigest()
    with tempfile.TemporaryDirectory() as td:      # outside results/: nothing a run cleans there can touch it
        export = Path(td)
        tar = subprocess.run(["git", "-C", str(repo), "archive", "--prefix=wfglink/", f"{a.reference}:wfglink"],
                             capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(export)], input=tar, check=True)
        rtree = export / "wfglink"
        (rtree / "data").mkdir(exist_ok=True)
        for d in ("raw", "synthetic"):
            if (ROOT / "data" / d).exists() and not (rtree / "data" / d).exists():
                (rtree / "data" / d).symlink_to((ROOT / "data" / d).resolve())
        reference = run_tree(rtree, out / "reference", a.seconds, baseline)
        rec["runs"] = {"reference": reference, "under_test": run_tree(ROOT, out / "under_test", a.seconds, baseline)}
    for name, fname in (("exact_history_harness", "fullrate_comparison.json"), ("validate_ember", "ember_report.json"),
                        ("stride", "stride_report.json")):
        x, y = load(out / "under_test" / fname), load(out / "reference" / fname)
        d = ["missing report"] if x is None or y is None else diff(numeric(y), numeric(x))
        rec["checks"][f"same_host_{name}"] = {"pass": not d, "n_differences": len(d), "differences": d[:40]}
    comp = load(out / "under_test" / "fullrate_comparison.json") or {}
    rec["informational"]["harness_asserts_on_this_host"] = {k: comp.get(k) for k in (
        "all_histories_and_legacy_tracks_exact", "quality_speed_ruler_reports_exact", "exact_speed_rows_match")}
    rec["informational"]["harness_inexact_histories_on_this_host"] = sorted(
        k for k, v in (comp.get("histories") or {}).items() if not v.get("exact_match"))
    for name, rel, fname in (("validate_ember_vs_mac_release", "ember_report.json", "ember_report.json"),
                             ("stride_vs_mac_release", "stride_report.json", "stride_report.json")):
        x = load(out / "under_test" / fname)
        d = ["missing report"] if x is None else diff(numeric(json.loads((REL / rel).read_text())), numeric(x))
        rec["informational"][name] = {"equal": not d, "n_differences": len(d), "differences": d[:20]}
    rec["pass"] = all(c["pass"] for c in rec["checks"].values())
    (out / "phone_check.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: v["pass"] for k, v in rec["checks"].items()}, indent=1), "PASS" if rec["pass"] else "FAIL")
    return 0 if rec["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
