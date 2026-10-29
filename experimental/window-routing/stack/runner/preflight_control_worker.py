"""Synthetic controller-control worker (never a routing request). The job's 'control' field selects the behaviour:
normal   writes RESULT (authority_final) and PUBLICATION_BOUNDARY (published before the deadline), exits 0 -> on time
fail     exits 3 without a RESULT -> worker failure, not on time
deadline installs a SIGTERM handler, sleeps past the budget, exits 0 on SIGTERM -> deadline termination, no forced kill
stubborn ignores SIGTERM (inherited from the time process), sleeps -> deadline termination and forced kill
memory   commits about 400 MiB and holds it (job memory_guard_mib 200) -> memory-guard stop
desc     leaves one child in its process group and one detached child whose argv names the job file -> census + cleanup"""
import json, os, pathlib, signal, subprocess, sys, time
START = time.perf_counter()
job_path = pathlib.Path(sys.argv[sys.argv.index('--job-file') + 1]); job = json.loads(job_path.read_text()); folder = job_path.parent
origin = float(os.environ['WFG_OUTER_MONOTONIC_START']); deadline = origin + float(job['complete_budget_s']); mode = job['control']


def publish():
    (folder / 'RESULT.json').write_text(json.dumps({'authority_final': True, 'primary_status': 'CONTROL_' + mode.upper(),
                                                    'whole_road_check': {'status': 'NOT_RUN'}, 'control': mode}))
    (folder / 'PUBLICATION_BOUNDARY.json').write_text(json.dumps({'result_published_before_deadline': time.perf_counter() <= deadline}))


if mode == 'normal':
    time.sleep(0.5); publish(); sys.exit(0)
if mode == 'fail':
    sys.exit(3)
if mode == 'deadline':
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0)); time.sleep(60); sys.exit(0)
if mode == 'stubborn':
    signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60); sys.exit(0)
if mode == 'memory':
    n = 400 * 2 ** 20; b = bytearray(n)
    for i in range(0, n, 4096):
        b[i] = 1
    time.sleep(20); sys.exit(0)
if mode == 'desc':
    subprocess.Popen(['/bin/sleep', '120'])
    subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)', str(job_path)], start_new_session=True)
    time.sleep(0.5); publish(); sys.exit(0)
sys.exit(9)
