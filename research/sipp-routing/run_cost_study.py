"""Track 1C-2 evidence: SIPP versus the frozen contact sweep on the 20 frozen Korean missions.

Part 1 (equivalence and cost): every mission, two repetitions, ABBA order within a mission (rep 1: sweep, SIPP;
rep 2: SIPP, sweep), each execution in a fresh `python -I` child with the 30 s complete-request deadline (child killed at
30 s, recorded as unresolved) and the 3,072 MiB memory allowance (peak RSS above it is recorded as a memory stop; the
child also runs under an address-space limit of 6 GiB as a host safety). Members: the frozen v1 packet.
Part 2 (states versus members): SIPP and the sweep on the first K export v3 trajectories, K in {1, ..., 256}, for every
mission whose window has first-new ignitions, one repetition.

  python research/sipp-routing/run_cost_study.py --exports /path/exports_v3 --out research/sipp-routing/data
"""
import argparse
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import kit  # noqa: E402

DEADLINE_S, MEMORY_MIB, AS_LIMIT = 30.0, 3072.0, 6 * 1024 ** 3
KS = (1, 2, 4, 8, 16, 32, 64, 128, 256)


def limit():
    resource.setrlimit(resource.RLIMIT_AS, (AS_LIMIT, AS_LIMIT))


def execute(planner, region, tag, event, mission, members="v1", exports=None):
    cmd = [sys.executable, "-I", "-B", str(HERE / "exec_one.py"), "--planner", planner, "--region", region, "--cutoff", tag,
           "--event", event, "--mission", mission, "--members", members, "--wall", str(DEADLINE_S)]
    if exports:
        cmd += ["--exports", exports]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=DEADLINE_S, preexec_fn=limit,
                           env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
        wall = time.perf_counter() - t0
        if p.returncode != 0:
            return {"planner": planner, "region": region, "cutoff": tag, "mission": mission, "members": members, "status": "UNRESOLVED",
                    "raw_status": "WORKER_ERROR", "external_wall_s": wall, "tail": p.stderr[-400:]}
        row = json.loads(p.stdout.strip().splitlines()[-1])
        row["external_wall_s"] = wall
        if row["peak_rss_mib"] > MEMORY_MIB:
            row.update(status="UNRESOLVED", raw_status="MEMORY_STOP")
        return row
    except subprocess.TimeoutExpired:
        return {"planner": planner, "region": region, "cutoff": tag, "mission": mission, "members": members, "status": "UNRESOLVED",
                "raw_status": "DEADLINE", "external_wall_s": time.perf_counter() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exports", required=True)
    ap.add_argument("--out", default=str(HERE / "data"))
    ap.add_argument("--part", choices=("1", "2", "both"), default="both")
    a = ap.parse_args()
    kit.verify_inputs()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    host = {"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(),
            "loadavg_start": os.getloadavg(), "note": "host-specific Linux measurement, shared host; not comparable with the frozen native-Mac timings"}
    if a.part in ("1", "both"):
        rows = []
        for region, tag, event, mission in kit.missions():
            for rep, order in ((1, ("sweep", "sipp")), (2, ("sipp", "sweep"))):
                for pl in order:
                    r = execute(pl, region, tag, event, mission)
                    r["rep"] = rep
                    r["loadavg"] = os.getloadavg()[0]
                    rows.append(r)
                    print(json.dumps({k: r.get(k) for k in ("planner", "region", "cutoff", "mission", "rep", "raw_status", "arrival",
                                                            "complete_s", "planner_s", "peak_rss_mib")}), flush=True)
        with (out / "cost_executions.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    if a.part in ("2", "both"):
        rows = []
        for region, tag, event, mission in kit.missions():
            if region not in ("uiseong_andong_2025", "uljin_2022", "yeongdeok_2025") or tag in ("20220304T030000Z", "20250326T080000Z"):
                continue
            for K in KS:
                for pl in ("sipp", "sweep"):
                    r = execute(pl, region, tag, event, mission, members="first:%d" % K, exports=a.exports)
                    r["K"] = K
                    r["loadavg"] = os.getloadavg()[0]
                    rows.append(r)
                    print(json.dumps({k: r.get(k) for k in ("planner", "region", "mission", "K", "raw_status", "arrival", "planner_s",
                                                            "pieces", "states")}), flush=True)
        with (out / "members_scaling.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    host["loadavg_end"] = os.getloadavg()
    (out / ("host_part%s.json" % a.part)).write_text(json.dumps(host, indent=1) + "\n")


if __name__ == "__main__":
    main()
