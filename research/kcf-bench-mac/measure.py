"""Measure one command the same way for both methods (PLAN.md 4).

    python3 measure.py OUT_JSON -- CMD ARGS...

Runs CMD as a child of this fresh process and records, for the child and every descendant it waited for:
  wall_s      perf_counter from launch to exit
  cpu_s       user + system CPU of all waited descendants (RUSAGE_CHILDREN)
  peak_rss_mib  ru_maxrss of RUSAGE_CHILDREN = peak resident set of the LARGEST single descendant process (macOS: bytes)
  loadavg     1/5/15-min load average just before and just after
"""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time

out = sys.argv[1]
assert sys.argv[2] == "--"
cmd = sys.argv[3:]
la0 = os.getloadavg()
t0 = time.perf_counter()
rc = subprocess.call(cmd)
wall = time.perf_counter() - t0
la1 = os.getloadavg()
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
scale = 1.0 if sys.platform == "darwin" else 1024.0      # macOS reports bytes, Linux KiB
rec = {"cmd": cmd, "exit_code": rc, "wall_s": wall, "cpu_user_s": ru.ru_utime, "cpu_sys_s": ru.ru_stime,
       "cpu_s": ru.ru_utime + ru.ru_stime, "peak_rss_mib": ru.ru_maxrss * scale / 2 ** 20,
       "loadavg_before": la0, "loadavg_after": la1, "finished_at_unix": time.time()}
with open(out, "w") as f:
    json.dump(rec, f, indent=1)
sys.exit(rc)
