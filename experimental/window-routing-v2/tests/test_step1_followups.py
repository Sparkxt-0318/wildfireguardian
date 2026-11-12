"""Mira R14 follow-ups (orchestrator, 17:42 UTC), on a built v2 kit (WFG_V2_KIT) and the frozen kit (WFG_FROZEN_KIT).
(N1) Two kits driven from ONE panel process each run their own controller and decision modules: g1_panel runs every
     job through tools/run_one_job.py in a fresh interpreter, which reports the module files it actually loaded.
(N2) An unwritable progress path never changes or aborts a search: the progress temp path is made a directory as soon
     as the job folder appears (root ignores file modes, so a directory is the reliable obstruction). The job must end
     with the same authoritative status and arrival as an unobstructed control run, with no SEARCH_PROGRESS.json, and
     with the write errors counted in RESULT.progress_hook.errors."""
import json, os, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUN_ONE = HERE.parent / 'tools/run_one_job.py'
KIT = Path(os.environ['WFG_V2_KIT']).resolve() if os.environ.get('WFG_V2_KIT') else None
FROZEN = Path(os.environ['WFG_FROZEN_KIT']).resolve() if os.environ.get('WFG_FROZEN_KIT') else None
INPUTS = REPO / 'data/routing'


def run_job(kit, region, case, budget, out):
    p = subprocess.run([sys.executable, '-B', str(RUN_ONE), str(kit), str(INPUTS), region, case, str(out), str(budget)],
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout.strip().splitlines()[-1])


@unittest.skipIf(KIT is None or FROZEN is None, 'set WFG_V2_KIT and WFG_FROZEN_KIT')
class TwoKitsOneProcess(unittest.TestCase):
    def test_each_job_runs_its_own_kits_controller_and_decision(self):
        tmp = Path(tempfile.mkdtemp(prefix='v2n1_'))
        seen = {}
        for name, kit in (('frozen', FROZEN), ('v2', KIT), ('frozen_again', FROZEN)):   # A, B, A in one process
            row = run_job(kit, 'yeongdeok_2025', '20250325T190000Z_FX2', 20.0, tmp / name)
            seen[name] = row['module_files']
            for mod, f in row['module_files'].items():
                self.assertIsNotNone(f, (name, mod))
                self.assertTrue(Path(f).resolve().is_relative_to(kit), (name, mod, f, str(kit)))
        self.assertNotEqual(seen['frozen']['journey_decision_v2_1'], seen['v2']['journey_decision_v2_1'])


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class UnwritableProgressPath(unittest.TestCase):
    def test_failed_progress_writes_do_not_change_the_search(self):
        region, case, budget = 'yeongdeok_2025', '20250325T190000Z_FD1', 81.0   # LO returns PROVEN_INFEASIBLE in ~39 s
        tmp = Path(tempfile.mkdtemp(prefix='v2n2_'))
        ctrl = run_job(KIT, region, case, budget, tmp / 'control')
        out = tmp / 'obstructed'
        blocked = {'at': None}
        def obstruct():
            t0 = time.time()
            while time.time() - t0 < 60:
                if out.is_dir():
                    (out / '.SEARCH_PROGRESS.json.tmp').mkdir()
                    blocked['at'] = time.time(); return
                time.sleep(0.005)
        th = threading.Thread(target=obstruct); th.start()
        row = run_job(KIT, region, case, budget, out)
        th.join()
        self.assertIsNotNone(blocked['at'], 'job folder never appeared')
        self.assertFalse((out / 'SEARCH_PROGRESS.json').exists(), 'a progress write got through the obstruction')
        res = json.loads((out / 'RESULT.json').read_text())
        ph = res.get('progress_hook') or {}
        self.assertGreater(ph.get('errors', 0), 0, ph)
        self.assertIn('IsADirectoryError', ph.get('last_error', ''))
        for k in ('authoritative_status', 'arrival_s', 'primary_status', 'unresolved_reason'):
            self.assertEqual(row[k], ctrl[k], k)
        self.assertEqual([s['stage'] for s in row['rda_stages']], [s['stage'] for s in ctrl['rda_stages']])


if __name__ == '__main__':
    unittest.main()
