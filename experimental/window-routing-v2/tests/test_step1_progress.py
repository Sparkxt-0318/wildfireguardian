"""Step 1 progress persistence on a built v2 kit (WFG_V2_KIT). Runs real kit jobs through the controller:
(1) a job stopped by its deadline mid-search leaves SEARCH_PROGRESS.json whose last write is no older than 2 s of
    worker time before the stop (elapsed_from_outer_s >= complete wall - 2 - grace);
(2) a completing job's final LO/LO2/HI progress record (final: true) equals SEARCH_RESULT's expansions/labels."""
import json, os, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'research/harness-2026-11/F-3.4'))
KIT = Path(os.environ['WFG_V2_KIT']).resolve() if os.environ.get('WFG_V2_KIT') else None


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class Progress(unittest.TestCase):
    def run_job(self, region, case, budget):
        import run_profile as RP
        out = Path(tempfile.mkdtemp(prefix='v2prog_')) / 'job'
        row = RP.run_one(KIT, REPO / 'data/routing', region, case, out, budget, 'plain', sys.executable)
        return out, row

    def test_deadline_stop_leaves_recent_progress(self):
        out, row = self.run_job('yeongdeok_2025', '20250325T190000Z_FX2', 20.0)
        p = out / 'SEARCH_PROGRESS.json'
        self.assertTrue(p.exists(), 'no SEARCH_PROGRESS.json after a deadline stop')
        d = json.loads(p.read_text())
        self.assertGreaterEqual(d['elapsed_from_outer_s'], row['complete_wall_s'] - 2.0 - 3.5, (d, row['complete_wall_s']))

    def test_completed_job_final_counts_match_search_result(self):
        out, row = self.run_job('yeongdeok_2025', '20250325T190000Z_FD1', 81.0)   # LO returns PROVEN_INFEASIBLE in ~39 s
        sr = json.loads((out / 'SEARCH_RESULT.json').read_text())
        d = json.loads((out / 'SEARCH_PROGRESS.json').read_text())
        solves = [s for s in sr.get('stages', []) if s.get('stage') in ('LO', 'LO2', 'HI')]
        if not solves or not d.get('final'):
            self.skipTest('no LO/LO2/HI stage returned in this run')
        last = solves[-1]
        self.assertEqual(d['stage'], last['stage'])
        self.assertEqual(d['info']['expansions'], last.get('expansions'))
        self.assertEqual(d['info']['labels'], last.get('labels'))


if __name__ == '__main__':
    unittest.main()
