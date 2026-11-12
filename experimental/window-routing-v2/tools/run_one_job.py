"""One g1_panel job in its own interpreter (Mira R14 N1): run_profile.run_one imports the kit's controller and decision
modules by name, so a fresh process per job guarantees they are the job's own kit's. Prints the row as one JSON line.
  python -B run_one_job.py KIT INPUTS REGION CASE_ID OUT_DIR BUDGET_S [ARM]

Step 2 amendment F (STEP2_ACCEPTANCE F2, R7):
- ARM V2_NOISO sets the job field `v2_check_isolation: false` (the labelled baseline comparison arm); any other ARM leaves
  the job exactly as run_profile builds it.
- The harness samples the job's whole process family (every descendant of this interpreter) every 10 ms: family PSS and
  RSS sums from /proc/<pid>/smaps_rollup, identically for every arm, plus its own CPU time (thread_time).
"""
import json, os, sys, threading, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'research/harness-2026-11/F-3.4'))
import run_profile as RP  # noqa: E402

kit, inputs, region, case, out, budget = sys.argv[1:7]
arm = sys.argv[7] if len(sys.argv) > 7 else None

if arm == 'V2_NOISO':
    _build = RP.build_job
    def build_job(*a, **k):
        job, *rest = _build(*a, **k)
        job['v2_check_isolation'] = False      # labelled baseline comparison arm (STEP2_ACCEPTANCE F1.2)
        return (job, *rest)
    RP.build_job = build_job


def descendants(root):
    kids = {}
    for d in os.listdir('/proc'):
        if d.isdigit():
            try:
                with open('/proc/%s/stat' % d) as f:
                    ppid = int(f.read().rsplit(')', 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(d))
            except (OSError, IndexError, ValueError):
                pass
    out, todo = [], list(kids.get(root, []))
    while todo:
        x = todo.pop(); out.append(x); todo.extend(kids.get(x, []))
    return out


def rollup(pid):
    r = {}
    try:
        with open('/proc/%d/smaps_rollup' % pid) as f:
            for line in f:
                if line.startswith(('Rss:', 'Pss:')):
                    r[line[:3]] = int(line.split()[1]) * 1024
    except OSError:
        pass
    return r


MEM = {'pss_peak': 0, 'rss_peak': 0, 'pss_at_rss_peak': 0, 'n_at_pss_peak': 0, 'samples': 0, 'sampler_cpu_s': 0.0}
STOP = [False]


def sample():
    me = os.getpid(); t_cpu = time.thread_time()
    while not STOP[0]:
        fam = descendants(me)          # the harness interpreter itself is excluded: it is the same for every arm
        vals = [rollup(p) for p in fam]
        pss = sum(v.get('Pss', 0) for v in vals); rss = sum(v.get('Rss', 0) for v in vals)
        MEM['samples'] += 1
        if pss > MEM['pss_peak']:
            MEM['pss_peak'] = pss; MEM['n_at_pss_peak'] = sum(1 for v in vals if v)
        if rss > MEM['rss_peak']:
            MEM['rss_peak'] = rss; MEM['pss_at_rss_peak'] = pss
        MEM['sampler_cpu_s'] = time.thread_time() - t_cpu
        time.sleep(0.01)


th = threading.Thread(target=sample, daemon=True); th.start()
row = RP.run_one(Path(kit), Path(inputs), region, case, Path(out), float(budget), 'plain', sys.executable)
STOP[0] = True; th.join(timeout=2)
# which controller and decision modules this job actually ran (checked by tests/test_step1_followups.py)
row['module_files'] = {m: getattr(sys.modules.get(m), '__file__', None) for m in ('wfg_controller', 'journey_decision_v2_1')}
row['arm'] = arm
row['harness_mem'] = {'family_pss_peak_mib': MEM['pss_peak'] / 2 ** 20, 'family_rss_peak_mib': MEM['rss_peak'] / 2 ** 20,
                      'pss_at_rss_peak_mib': MEM['pss_at_rss_peak'] / 2 ** 20, 'processes_at_pss_peak': MEM['n_at_pss_peak'],
                      'samples': MEM['samples'], 'sampler_cpu_s': MEM['sampler_cpu_s'], 'interval_s': 0.01}
print(json.dumps(row, sort_keys=True, default=str))
