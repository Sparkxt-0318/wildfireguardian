"""STEP2_ACCEPTANCE amendment F, M3(d) with R5: one F-DYN job run by the research harness's fdyn_profile.py (in this
interpreter), with the harness sampler (tools/harness_mem.py, Mira 122 N2 rules) sampling every descendant of this
interpreter every 10 ms. Writes HARNESS_MEM.json into OUT and prints the M3(d) comparison against the controller
receipt's sampled_family_peak_pss_bytes:
  R5: controller PSS peak <= harness PSS max AND >= 0.95 x harness PSS max; also below the harness RSS-sum peak.
  WFG_F34=.../F-3.4 python -B m3d_run.py OUT TAG KIT LEO [BUDGET_S=300] [GUARD_MIB=12288]
Inputs (Mira 125 N4): fdyn_profile.py builds the requests for ALL of its PACKETS before applying --only, so LEO must
hold every packet it lists, even when only TAG runs.
A harness sample with a live unreadable pid is not measured; any such sample makes M3(d) not evaluable (never a pass).
"""
import hashlib, json, os, runpy, sys, threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
# fdyn_profile.py is on the research harness branch, not on this one: WFG_F34 names that F-3.4 directory (recorded).
F34 = Path(os.environ.get('WFG_F34', REPO / 'research/harness-2026-11/F-3.4')).resolve()
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(F34))
import harness_mem as HM  # noqa: E402

out, tag, kit, leo = (Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4])
budget = sys.argv[5] if len(sys.argv) > 5 else '300'
guard = sys.argv[6] if len(sys.argv) > 6 else '12288'
th = threading.Thread(target=HM.sample, daemon=True); th.start()
sys.argv = ['fdyn_profile.py', '--kit', kit, '--leo', leo, '--out', str(out), '--budget', budget, '--mode', 'plain',
            '--memory-guard-mib', guard, '--rss-limit-mb', guard, '--only', tag]
try:
    runpy.run_path(str(F34 / 'fdyn_profile.py'), run_name='__main__')
finally:
    HM.STOP[0] = True; th.join(timeout=2)
MiB = 2 ** 20
h = {'family_pss_peak_mib': HM.MEM['pss_peak'] / MiB, 'family_rss_peak_mib': HM.MEM['rss_peak'] / MiB,
     'pss_at_rss_peak_mib': HM.MEM['pss_at_rss_peak'] / MiB, 'processes_at_pss_peak': HM.MEM['n_at_pss_peak'],
     'samples': HM.MEM['samples'], 'measured_samples': HM.MEM['measured_samples'],
     'unmeasured_samples': HM.MEM['unmeasured_samples'], 'vanished_pids': HM.MEM['vanished_pids'],
     'sampler_cpu_s': HM.MEM['sampler_cpu_s'], 'interval_s': 0.01}
rec = json.loads((out / 'runs' / tag / 'COMPLETE_PROCESS_RECEIPT.json').read_text())
c_pss = rec['sampled_family_peak_pss_bytes'] / MiB; c_rss = rec['sampled_family_peak_rss_bytes'] / MiB
ok = None if (h['unmeasured_samples'] or not h['measured_samples']) else (
    0.95 * h['family_pss_peak_mib'] <= c_pss <= h['family_pss_peak_mib'] and c_pss < h['family_rss_peak_mib'])
res = {'tag': tag, 'f34': str(F34), 'fdyn_profile_sha256': hashlib.sha256((F34 / 'fdyn_profile.py').read_bytes()).hexdigest(),
       'run_profile_sha256': hashlib.sha256((F34 / 'run_profile.py').read_bytes()).hexdigest(), 'harness': h, 'controller': {'pss_peak_mib': c_pss, 'rss_sum_peak_mib': c_rss,
       'guard_measure': rec.get('guard_measure'), 'pss_samples': rec.get('pss_samples'),
       'pss_fallback_samples': rec.get('pss_fallback_samples'), 'pss_vanished_pids': rec.get('pss_vanished_pids'),
       'memory_guard_triggered': rec.get('memory_guard_triggered'), 'raw_primary_status': rec.get('raw_primary_status')},
       'controller_over_harness_pss': c_pss / h['family_pss_peak_mib'] if h['family_pss_peak_mib'] else None,
       'M3d_ok': ok, 'M3d_not_evaluable': None if ok is not None else 'harness had unmeasured samples or none measured'}
(out / 'HARNESS_MEM.json').write_text(json.dumps(res, indent=1) + '\n')
print(json.dumps(res))
