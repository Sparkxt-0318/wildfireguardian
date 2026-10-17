"""Strict phone non-regression for the precision verifier (2026-10-17), on the committed source.

The phone (ember) mode must be unchanged. Run from a committed export:

    bash scripts/run_from_head.sh python scripts/precision_phone_check.py --out results/runs/precision_20261017/phone

Gate (all must hold):
1. Source identity: the phone tracker, pipeline, camera and source files hash exactly as in the
   verified release comparison (results/validation/continuation_20261015/phone_fullrate_comparison.json),
   and the original tracker read from 2d87bf3 hashes as that comparison's baseline_track_sha256.
2. Same-host equality with the release: the release commit (--reference, default 4d0092c, the
   published demo) is exported and run on this host next to the source under test, and every
   output must be equal: the release's executed exact-history harness (against the original
   tracker of 2d87bf3), validate --suite ember and check_ember_stride.py --seconds 60 (timing and
   provenance fields and temporary paths excluded).
3. Every run is what it claims: each release step runs in a fresh export whose file list equals
   git's list of the release's wfglink folder, each step's wfglink is imported from its own tree
   (not the checkout's installed copy), each report is deleted before its step and written by it,
   validate returns 0 or 1 and the stride check 0. The harness asserts exactness, so its return
   code is recorded, not gated (its asserts fail on this host, see below).
Reported, not part of the gate: each report compared with the release's saved reports from the
booth Mac, and the harness's own asserts on this host. The synthetic phone videos are encoded
and decoded by platform builds, so a cross-platform difference with identical source is a
platform property (see results/validation/precision_20261017/c5_baseline_discrepancy.json), not a
code change; the same-host comparison isolates the code.
Writes <out>/phone_check.json and exits non-zero when the gate fails.

Why the export is checked (2026-10-17): the release was exported with git archive run inside the
wfglink folder. Run in a subfolder, git archive keeps only the paths under that subfolder's name,
which inside the tree <commit>:wfglink is nothing, so the export was an empty wfglink folder. The
release's harness and validate then imported the checkout's installed wfglink (its src was not
there) and its scripts/check_ember_stride.py was reported missing: it had never been exported.
git archive now runs at the repository's top level.
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
sys.path.insert(0, str(ROOT / "src"))
REL = ROOT / "results/validation/continuation_20261015"
EXCLUDED = {"created", "report_path", "proc_ms_median", "proc_ms_p95", "git_dirty", "git_commit", "git_branch",
            "ms", "ms_median", "ms_p95", "wall_s", "elapsed_s", "out", "config_path"}
TMP_PATH = re.compile(r"\S*/wfglink(?=/data/)")      # the tree a report was made in: temporary or the checkout
STEPS = ("harness", "validate", "stride")
LOGS = {"harness": "harness.log", "validate": "validate_ember.log", "stride": "stride.log"}
REPORTS = {"harness": ("fullrate_comparison.json", "baseline_fullrate_suite.json", "cadence_fullrate_suite.json",
                       "compare_fullrate.executed.py"),
           "validate": ("ember_report.json",), "stride": ("stride_report.json",)}
RETURNCODES_OK = {"validate": (0, 1), "stride": (0,)}   # the harness's return code is recorded, not gated


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


def git(top: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(top), *args], capture_output=True, check=True).stdout


def tree_files(tree: Path) -> set[str]:
    """Files and symbolic links under tree, relative, without following linked folders."""
    out = set()
    for dp, dirs, files in os.walk(tree):
        d = Path(dp)
        out |= {str((d / f).relative_to(tree)) for f in files}
        out |= {str((d / x).relative_to(tree)) for x in dirs if (d / x).is_symlink()}
    return out


def export_tree(top: Path, commit: str, dest: Path) -> Path:
    """<commit>:wfglink exported into dest/wfglink with git archive at the repository's top level
    (see the module notes), checked against git's own file list, with data/raw and data/synthetic
    linked to the checkout's."""
    subprocess.run(["tar", "-x", "-C", str(dest)], input=git(top, "archive", "--prefix=wfglink/", f"{commit}:wfglink"),
                   check=True)
    tree = dest / "wfglink"
    want = set(git(top, "ls-tree", "-r", "-z", "--name-only", f"{commit}:wfglink").decode().split("\0")) - {""}
    have = tree_files(tree) if tree.is_dir() else set()
    if not want:
        raise SystemExit(f"git lists no files of {commit[:7]}:wfglink from {top} (not the repository's top level?)")
    if have != want:
        raise SystemExit(f"the export of {commit[:7]} in {tree} is not the commit's wfglink folder: "
                         f"{len(want - have)} files missing, {len(have - want)} extra")
    (tree / "data").mkdir(exist_ok=True)
    for d in ("raw", "synthetic"):
        if (ROOT / "data" / d).exists() and not (tree / "data" / d).exists():
            (tree / "data" / d).symlink_to((ROOT / "data" / d).resolve())
    return tree


def run_step(step: str, tree: Path, out: Path, env: dict, seconds: float, baseline: bytes) -> dict:
    """One phone run with the code of `tree`, its reports in `out` (deleted first, so a report
    found afterwards was written by this run)."""
    out.mkdir(parents=True, exist_ok=True)
    for name in REPORTS[step]:
        (out / name).unlink(missing_ok=True)
    py = sys.executable
    if step == "harness":
        harness = out / "compare_fullrate.py"
        harness.write_bytes((REL / "phone_uncertainty_compare_fullrate_executed.txt").read_bytes())
        (out / "baseline_track.py").write_bytes(baseline)
        cmd = [py, str(harness), "--out-dir", str(out)]
    elif step == "validate":
        cmd = [py, "-m", "wfglink", "validate", "--suite", "ember", "--out", str(out / "ember_report.json")]
    else:
        cmd = [py, str(tree / "scripts" / "check_ember_stride.py"), "--seconds", str(seconds), "--out",
               str(out / "stride_report.json")]
    probe = subprocess.run([py, "-c", "import wfglink; print(wfglink.__file__)"], cwd=tree, env=env,
                           capture_output=True, text=True)
    imported = probe.stdout.strip()
    in_tree = bool(imported) and Path(imported).resolve().is_relative_to((tree / "src").resolve())
    r = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True)
    (out / LOGS[step]).write_text(r.stdout + r.stderr)
    return {"returncode": r.returncode, "wfglink_imported_from": imported, "import_in_tree": in_tree,
            "missing_reports": [n for n in REPORTS[step] if not (out / n).is_file()]}


def load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    from wfglink.provenance import git_state, now_shanghai

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--reference", default="4d0092c")
    ap.add_argument("--seconds", type=float, default=60.0)
    a = ap.parse_args()
    out = Path(a.out).resolve()                   # absolute: each tree runs in its own folder
    out.mkdir(parents=True, exist_ok=True)
    (out / "phone_check.json").unlink(missing_ok=True)   # a run that stops early leaves no earlier verdict
    repo = (ROOT / "results").resolve().parent   # run_from_head links results to the checkout's
    top = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip())
    ref_sha = git(top, "rev-parse", "--verify", f"{a.reference}^{{commit}}").decode().strip()
    rec: dict = {"created": now_shanghai(), "reference_commit": a.reference, "reference_sha": ref_sha, **git_state(),
                 "wfglink_export_commit": os.environ.get("WFGLINK_EXPORT_COMMIT"), "checks": {}, "informational": {}}

    release = json.loads((REL / "phone_fullrate_comparison.json").read_text())
    ref = release["source_sha256"]
    now = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ref}
    rec["checks"]["source_identity"] = {"pass": now == ref, "release": ref, "now": now}

    baseline = git(top, "show", "2d87bf3:wfglink/src/wfglink/ember/track.py")
    rec["baseline_track_sha256"] = hashlib.sha256(baseline).hexdigest()
    rec["checks"]["baseline_track"] = {"pass": rec["baseline_track_sha256"] == release["baseline_track_sha256"],
                                       "release": release["baseline_track_sha256"], "now": rec["baseline_track_sha256"]}
    runs: dict = {"reference": {}, "under_test": {}}
    for step in STEPS:                             # the release first, each step in a fresh export of it
        with tempfile.TemporaryDirectory() as td:
            rtree = export_tree(top, ref_sha, Path(td))
            env = {**os.environ, "PYTHONPATH": str(rtree / "src"), "WFGLINK_EXPORT_COMMIT": ref_sha}
            runs["reference"][step] = run_step(step, rtree, out / "reference", env, a.seconds, baseline)
    for step in STEPS:
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        runs["under_test"][step] = run_step(step, ROOT, out / "under_test", env, a.seconds, baseline)
    rec["runs"] = runs
    every = [(tree, step, r) for tree, steps in runs.items() for step, r in steps.items()]
    rec["checks"]["imports_from_own_tree"] = {
        "pass": all(r["import_in_tree"] for _, _, r in every),
        "outside": [f"{tree}/{step}: {r['wfglink_imported_from'] or 'no import'}" for tree, step, r in every
                    if not r["import_in_tree"]]}
    rec["checks"]["returncodes"] = {
        "pass": all(r["returncode"] in RETURNCODES_OK[step] for _, step, r in every if step in RETURNCODES_OK),
        "allowed": {k: list(v) for k, v in RETURNCODES_OK.items()},
        "returncodes": {tree: {step: r["returncode"] for step, r in steps.items()} for tree, steps in runs.items()},
        "note": "the harness asserts exactness, so its return code is recorded, not gated"}
    rec["checks"]["reports_written_by_this_run"] = {
        "pass": not any(r["missing_reports"] for _, _, r in every),
        "missing": [f"{tree}/{step}: {n}" for tree, step, r in every for n in r["missing_reports"]]}
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
