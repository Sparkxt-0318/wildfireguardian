"""Step 1 (STEP1_ACCEPTANCE.md + amendment 26e12e4): reason remapping in the v2 decision modules.
Unit tests on the pure post-step, plus a replay over recorded F-DYN folders when WFG_FDYN_SCRATCH is set."""
import copy, importlib.util, json, os, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEC = HERE.parent / 'stack-v2/decision'


def load(name):
    spec = importlib.util.spec_from_file_location('v2_' + name, DEC / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


MODS = [load('journey_decision_v2_1'), load('journey_decision')]


def dec(reason, status='UNRESOLVED', mismatch_state=None, rb_mismatch=False):
    fields = {'graph_file_sha256': {'state': mismatch_state or 'VERIFIED'}}
    return {'authoritative_status': status, 'unresolved_reason': reason, 'unresolved_reason_text': 'x',
            'unresolved_detail': {'k': 1}, 'identity': {'fields': fields},
            'route_binding': {'mismatch': rb_mismatch, 'match': (False if rb_mismatch else None)}, 'module_version': 'v'}


class Remap(unittest.TestCase):
    def each(self, d, res, rc, want):
        for M in MODS:
            out = M._v2_stop_reason(copy.deepcopy(d), res, rc)
            self.assertEqual(out['authoritative_status'], d['authoritative_status'])
            self.assertEqual(out['unresolved_reason'], want, M.__name__)
            if want != d['unresolved_reason']:
                self.assertEqual(out['unresolved_detail']['frozen_reason'], d['unresolved_reason'])
                self.assertIn('evidence', out['unresolved_detail'])
                self.assertIn(want, M.UNRESOLVED_REASONS)

    def test_a_memory_guard(self):
        self.each(dec('LATE_RESULT'), {}, {'memory_guard_triggered': True}, 'MEMORY_GUARD_STOP')
        self.each(dec('STALE_OR_IDENTITY_MISMATCH', mismatch_state='EXPECTED_NOT_OBSERVED'), {}, {'memory_guard_triggered': True}, 'MEMORY_GUARD_STOP')
        self.each(dec('SEARCH_TIMEOUT'), {'rda_stages': []}, {'memory_guard_triggered': True}, 'MEMORY_GUARD_STOP')

    def test_b_deadline_no_evidence(self):
        rc = {'deadline_termination_requested': True}
        self.each(dec('STALE_OR_IDENTITY_MISMATCH', mismatch_state='EXPECTED_NOT_OBSERVED'), {}, rc, 'DEADLINE_STOP_NO_EVIDENCE')
        self.each(dec('LATE_RESULT'), {'worker_failure': {'type': 'DeadlineStop'}}, rc, 'DEADLINE_STOP_NO_EVIDENCE')
        # amendment 2: stages recorded before the deadline stop -> DURING_SEARCH, never "no evidence"
        self.each(dec('LATE_RESULT'), {'worker_failure': {'type': 'DeadlineStop'}, 'rda_stages': [{'stage': 'Z', 'status': 'TIMEOUT'}]},
                  rc, 'DEADLINE_STOP_DURING_SEARCH')
        # deadline but the worker left a real search result: frozen reason kept
        self.each(dec('LATE_RESULT'), {'result': {'status': 'TIMEOUT'}, 'rda_stages': [{'stage': 'Z'}]}, rc, 'LATE_RESULT')

    def test_c_check_memory_on_found_route(self):
        st = [{'stage': 'Z', 'status': 'TIMEOUT', 'reason': 'WALL_CLOCK'},
              {'stage': 'LO', 'status': 'CONDITIONAL_OPTIMUM', 'arrival': 59, 'check_status': 'UNRESOLVED', 'check_reason': 'RSS_LIMIT'},
              {'stage': 'HI', 'status': 'CONDITIONAL_OPTIMUM', 'arrival': 59, 'check_status': 'UNRESOLVED', 'check_reason': 'RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK'}]
        self.each(dec('SEARCH_TIMEOUT'), {'rda_stages': st}, {}, 'CHECK_MEMORY_LIMIT_ON_FOUND_ROUTE')
        st2 = copy.deepcopy(st); st2[2]['check_reason'] = 'WALL_CAP_AFTER_CHECK'
        self.each(dec('SEARCH_TIMEOUT'), {'rda_stages': st2}, {}, 'SEARCH_TIMEOUT')

    def test_d_search_memory(self):
        st = [{'stage': 'Z', 'status': 'TIMEOUT', 'reason': 'WALL_CLOCK'},
              {'stage': 'LO', 'status': 'TIMEOUT', 'reason': 'RSS_LIMIT', 'arrival': None},
              {'stage': 'HI', 'status': 'TIMEOUT', 'reason': 'RSS_LIMIT', 'arrival': None}]
        self.each(dec('SEARCH_TIMEOUT'), {'rda_stages': st}, {}, 'SEARCH_MEMORY_LIMIT')
        wall = [{'stage': 'Z', 'status': 'TIMEOUT', 'reason': 'WALL_CLOCK'}, {'stage': 'LO', 'status': 'TIMEOUT', 'reason': 'WALL_CLOCK'}]
        self.each(dec('SEARCH_TIMEOUT'), {'rda_stages': wall}, {}, 'SEARCH_TIMEOUT')

    def test_genuine_mismatch_keeps_frozen(self):
        self.each(dec('STALE_OR_IDENTITY_MISMATCH', mismatch_state='MISMATCH'), {}, {'memory_guard_triggered': True}, 'STALE_OR_IDENTITY_MISMATCH')
        self.each(dec('STALE_OR_IDENTITY_MISMATCH', rb_mismatch=True), {}, {'memory_guard_triggered': True}, 'STALE_OR_IDENTITY_MISMATCH')

    def test_non_unresolved_untouched(self):
        for s in ('CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN', 'FULL_MODEL_REFUSAL_PROVEN', 'AT_ISSUE_FAILURE', 'CHECKED_JOURNEY_FEASIBLE'):
            d = dec(None, status=s)
            for M in MODS:
                self.assertEqual(M._v2_stop_reason(copy.deepcopy(d), {}, {'memory_guard_triggered': True}), d)

    def test_module_version_suffix(self):
        for M in MODS:
            # Step 1 introduced the suffix; later steps advance it (Step 2: v2_1 -> '+kit-v2-step2'), never drop it
            self.assertRegex(M.MODULE_VERSION, r'\+kit-v2-step[12]$')


SCRATCH = os.environ.get('WFG_FDYN_SCRATCH')


@unittest.skipIf(not SCRATCH, 'set WFG_FDYN_SCRATCH to replay recorded F-DYN folders')
class Replay(unittest.TestCase):
    """Recorded F-DYN folders through the v2 authoritative decision: statuses unchanged vs the frozen v2_1; reasons per
    the amendment's expected replay."""
    def run_dir(self, run):
        frozen = importlib.util.spec_from_file_location('frozen_v2_1', HERE.parents[1] / 'window-routing/stack/decision/journey_decision_v2_1.py')
        F = importlib.util.module_from_spec(frozen); frozen.loader.exec_module(F)
        V = MODS[0]; out = []
        for d in sorted((Path(SCRATCH) / run / 'runs').glob('*')):
            L = lambda n: json.loads((d / n).read_text()) if (d / n).exists() else {}
            res, rc, job = L('RESULT.json'), L('COMPLETE_PROCESS_RECEIPT.json'), L('JOB.json')
            kw = dict(graph=json.loads(Path(job['graph_path']).read_text()), request=json.loads(Path(job['request_path']).read_text()),
                      hazard=json.loads(Path(job['hazard_path']).read_text()),
                      optimality_certificate=res.get('optimality_certificate'), refusal_certificate=res.get('refusal_certificate'))
            a = F.decision_from_worker_record(res, rc, job, **kw); b = V.decision_from_worker_record(res, rc, job, **kw)
            if b['authoritative_status'] in getattr(V, 'MEMORY_BUDGET_STATUSES', ()):
                # Step 2 (STEP2_ACCEPTANCE (c)): a recorded frozen-kit success carries no resource_budget, so v2 reports
                # it apart. That must be the ONLY status change: the kit's certified status equals the frozen status,
                # the recorded check has no within_budget True, and the journey is kept beside it.
                self.assertEqual(b['certified_status_within_kit'], a['authoritative_status'], d.name)
                self.assertIsNot(((res.get('whole_road_check') or {}).get('resource_budget') or {}).get('within_budget'), True)
                self.assertEqual(b['journey_outside_memory_budget'], a['journey'], d.name)
            else:
                self.assertEqual(a['authoritative_status'], b['authoritative_status'], d.name)
            out.append((d.name, a['unresolved_reason'], b['unresolved_reason']))
        return out

    def test_b300_guard(self):
        r = self.run_dir('fdyn_b300')
        self.assertEqual({x[2] for x in r}, {'MEMORY_GUARD_STOP'}, r)

    def test_a1_yeongdeok_check_memory(self):
        r = {n: v for n, _, v in self.run_dir('fdyn_b300_g12k_rss12k')}
        for k, v in r.items():
            if 'yeongdeok' in k and not k.endswith(('firms_early__osm_node_11753630207', 'firms_early__osm_node_415158168')):
                self.assertEqual(v, 'CHECK_MEMORY_LIMIT_ON_FOUND_ROUTE', k)
            if 'uiseong' in k and not k.endswith('415158334'):
                self.assertEqual(v, 'DEADLINE_STOP_DURING_SEARCH', k)

    def test_controller_only_search_memory(self):
        r = {n: v for n, _, v in self.run_dir('fdyn_b300_g12k')}
        for k, v in r.items():
            if v not in (None,) and 'AT_ISSUE' not in str(v):
                self.assertIn(v, ('SEARCH_MEMORY_LIMIT', 'DEADLINE_STOP_NO_EVIDENCE', 'DEADLINE_STOP_DURING_SEARCH', None), k)


if __name__ == '__main__':
    unittest.main()
