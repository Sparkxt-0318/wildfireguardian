"""Batch for the multi-hour HEADLINE set: 48 no_reentry/2 packets (MANIFEST_v3_7.json, recorded starts: 2 regions x
3 starts x {5 h, 8 h} x 4 variants), each built with its manifest command UNCHANGED inside an F-DYN checkout at commit
819bcb91 (the commit F-3.1's headline batch used), run through c2_deadlines_multihour.py, then deleted.

    python scripts/c2_multihour_batch.py --leo LEO_CHECKOUT --out-dir DIR [--workers 3] [--child-python PY]

LEO_CHECKOUT needs data/routing (the frozen routing inputs) and research/harness-2026-11/F-DYN/_data rebuilt from
the repository's own branches (see ROUTING_EFFECT.md, "Multi-hour"). --child-python runs the packet writer child
(build.py --python); the builder itself runs under this interpreter (needs rasterio).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
F31 = HERE.parents[0] / "harness-2026-11" / "F-3.1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leo", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--builder-python", default=sys.executable)
    ap.add_argument("--child-python", default=sys.executable)
    ap.add_argument("--runner-python", default=sys.executable)
    ap.add_argument("--only", nargs="*", help="REGION:START:H:VARIANT")
    ap.add_argument("--dwell-dose", choices=("count", "exclude"), default="count")
    a = ap.parse_args()
    fd = a.leo / "research" / "harness-2026-11" / "F-DYN"
    m = json.loads((fd / "MANIFEST_v3_7.json").read_text())
    entries = {(e["region"], e["start"], e["horizon_h"], e["variant"]): e for e in m["entries"]
               if e["start_kind"] == "recorded" and e["transform"] == "no_reentry/2"}
    keys = sorted(entries, key=lambda k: (k[2], k[0], k[1], k[3]))
    if a.only:
        want = {tuple(x.split(":")) for x in a.only}
        keys = [k for k in keys if (k[0], k[1], str(k[2]), k[3]) in want]
    assert a.only or len(keys) == 48, len(keys)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    sh = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    ident = {"build.py": sh(fd / "fdyn" / "build.py"), "_packet_child.py": sh(fd / "fdyn" / "_packet_child.py"),
             "MANIFEST_v3_7.json": sh(fd / "MANIFEST_v3_7.json")}

    def job(k):
        region, start, h, var = k
        tag = "%s__%s_h%d_%s" % (region, start, h, var)
        res = a.out_dir / (tag + ".json")
        if res.exists():
            return tag, "skip"
        e = entries[k]
        cmd = list(e["cmd"])
        cmd[0] = a.builder_python
        out = a.leo / cmd[cmd.index("--out") + 1]
        r = subprocess.run(cmd + ["--python", a.child_python], cwd=a.leo, capture_output=True, text=True)
        if r.returncode:
            return tag, "BUILD_FAIL " + r.stderr[-500:]
        try:
            run = [a.runner_python, str(HERE / "scripts" / "c2_deadlines_multihour.py"),
                   "--graph", str(a.leo / cmd[cmd.index("--graph") + 1]), "--nr-packet", str(out),
                   "--instance-json", str(fd / "_data" / "INSTANCE.json"), "--region", region, "--start", start,
                   "--horizon-s", str(h * 3600), "--variant", var,
                   "--reference", str(F31 / "results" / "HEADLINE_NR2_summary.json"), "--dwell-dose", a.dwell_dose, "--out", str(res) + ".tmp"]
            r = subprocess.run(run, capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": "0"})
            if r.returncode:
                return tag, "RUN_FAIL " + r.stderr[-800:]
            d = json.loads(Path(str(res) + ".tmp").read_text())
            d["manifest_entry"] = e
            d["builder_identity"] = ident
            d["hazard_sha256"] = sh(out / "HAZARD.json")
            bs = out / "BUILD_SUMMARY.json"
            d["build_summary_writer_identity"] = json.loads(bs.read_text()).get("writer_identity") if bs.exists() else None
            res.write_text(json.dumps(d))
            os.remove(str(res) + ".tmp")
            return tag, "ok " + json.dumps({x: d[x] for x in ("reference_cert_reproduction", "witness_checks")})
        finally:
            shutil.rmtree(out, ignore_errors=True)
            for p in (Path(str(out) + ".plan.npz"), Path(str(out) + ".support.npz")):
                if p.exists():
                    p.unlink()

    with ThreadPoolExecutor(a.workers) as ex:
        for tag, st in ex.map(job, keys):
            print(tag, st, flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
