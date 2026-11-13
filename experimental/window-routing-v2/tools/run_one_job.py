"""One g1_panel job in its own interpreter (Mira R14 N1): run_profile.run_one imports the kit's controller and decision
modules by name, so a fresh process per job guarantees they are the job's own kit's. Prints the row as one JSON line.
  python -B run_one_job.py KIT INPUTS REGION CASE_ID OUT_DIR BUDGET_S [ARM]

Step 2 amendment F (STEP2_ACCEPTANCE F2, R7):
- ARM V2_NOISO sets the job field `v2_check_isolation: false` (the labelled baseline comparison arm); any other ARM leaves
  the job exactly as run_profile builds it.
- The harness samples the job's whole process family (every descendant of this interpreter) every 10 ms: family PSS and
  RSS sums from /proc/<pid>/smaps_rollup, identically for every arm, plus its own CPU time (thread_time).
- Sampling-error rules (Mira 122 N2, the same rules as the controller's R3): a pid that vanished between the listing and
  the read is skipped and counted (vanished_pids); a sample in which a LIVE pid could not be read is NOT MEASURED: it is
  counted (unmeasured_samples) and excluded from every peak, never summed partially. Both counts are in harness_mem.
"""
import json, os, sys, threading, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'research/harness-2026-11/F-3.4'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
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


from harness_mem import MEM, STOP, sample  # noqa: E402  (Mira 122 N2: tested sampler)


th = threading.Thread(target=sample, daemon=True); th.start()
row = RP.run_one(Path(kit), Path(inputs), region, case, Path(out), float(budget), 'plain', sys.executable)
STOP[0] = True; th.join(timeout=2)
# which controller and decision modules this job actually ran (checked by tests/test_step1_followups.py)
row['module_files'] = {m: getattr(sys.modules.get(m), '__file__', None) for m in ('wfg_controller', 'journey_decision_v2_1')}
row['arm'] = arm
row['harness_mem'] = {'family_pss_peak_mib': MEM['pss_peak'] / 2 ** 20, 'family_rss_peak_mib': MEM['rss_peak'] / 2 ** 20,
                      'pss_at_rss_peak_mib': MEM['pss_at_rss_peak'] / 2 ** 20, 'processes_at_pss_peak': MEM['n_at_pss_peak'],
                      'samples': MEM['samples'], 'measured_samples': MEM['measured_samples'],
                      'unmeasured_samples': MEM['unmeasured_samples'], 'vanished_pids': MEM['vanished_pids'],
                      'sampler_cpu_s': MEM['sampler_cpu_s'], 'interval_s': 0.01}
print(json.dumps(row, sort_keys=True, default=str))
