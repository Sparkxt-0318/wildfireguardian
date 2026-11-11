#!/usr/bin/env python3
"""Measure the real CLI offline: one subprocess per case, wall time, status, replay and wfg_sipp results.

    python3 measure.py [--out out/measurements.json] [--repeat 3]
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from kcf_planner.explain import apply_delay  # noqa: E402
from kcf_planner.io import write_json_atomic  # noqa: E402


def cases(tmp):
    out = [(p.stem, p) for p in sorted((ROOT / "fixtures" / "contract").glob("*.json"))]
    for name, vi in (("demo_two_vehicle", 1), ("demo_shuttle", 0)):
        raw = json.loads((ROOT / "fixtures" / ("%s.json" % name)).read_text(encoding="utf-8"))
        for m in (0, 5, 10, 15, 20, 25, 30):
            p = Path(tmp) / ("%s_delay%02d.json" % (name, m))
            p.write_text(json.dumps(apply_delay(raw, vi, m * 60), ensure_ascii=False), encoding="utf-8")
            out.append(("%s+%dmin" % (name, m), p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out" / "measurements.json"))
    ap.add_argument("--repeat", type=int, default=3)
    a = ap.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, path in cases(tmp):
            walls = []
            for _ in range(a.repeat):
                res_path = Path(tmp) / ("%s.result.json" % path.stem)
                t0 = time.perf_counter()
                p = subprocess.run([sys.executable, str(ROOT / "cli.py"), "--case", str(path.resolve()),
                                    "--output", str(res_path.resolve())], capture_output=True, text=True,
                                   cwd=tmp, env={k: v for k, v in os.environ.items() if not k.endswith("PROXY")})
                walls.append(time.perf_counter() - t0)
            r = json.loads(res_path.read_text(encoding="utf-8"))
            v = r.get("verification", {})
            rows.append({"case": name, "exit_code": p.returncode, "status": r["status"],
                         "reason_codes": r.get("reason_codes"), "final_unload_s": r["final_unload_s"],
                         "people_with_checked_transport": r["people_with_checked_transport"],
                         "people_total": r["people_total"], "trips": len(r["trips"]),
                         "conditional_trips": len(r.get("conditional_trips", [])),
                         "replay_ok": v.get("independent_replay", {}).get("ok"),
                         "wfg_sipp_ok": v.get("wfg_sipp", {}).get("all_ok"),
                         "settled_labels": r.get("search", {}).get("settled_labels"),
                         "planner_wall_s": r.get("wall_s"),
                         "process_wall_s_median": sorted(walls)[len(walls) // 2],
                         "process_wall_s_max": max(walls)})
    doc = {"tool": "kcf-facility-planner measure.py", "python": sys.version.split()[0],
           "platform": platform.platform(), "repeat": a.repeat, "network": "not used (proxy variables removed)",
           "rows": rows}
    write_json_atomic(a.out, doc)
    for r in rows:
        print("%-28s %-22s final=%-5s people=%s/%s replay=%s sipp=%s median=%.3fs" % (
            r["case"], r["status"], r["final_unload_s"], r["people_with_checked_transport"], r["people_total"],
            r["replay_ok"], r["wfg_sipp_ok"], r["process_wall_s_median"]))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
