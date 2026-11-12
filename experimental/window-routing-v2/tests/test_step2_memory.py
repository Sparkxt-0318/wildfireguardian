"""Step 2 memory accounting tests (STEP2_ACCEPTANCE.md, written before the Step 2 code is run).

Mechanism (v2_memory, overlay source):
  2  checker private memory: a forked check whose parent holds 1 GiB passes a 512 MiB gate (shared pages not its own);
  T  Thomas: a forked check that spikes 768 MiB and frees between samples, through the FULL gate at 512 MiB, is
     within_budget False (the cgroup peak decides); the fork-sampled path alone never says True for it;
  M  the parent is back in its original cgroup after every fork; a failed move-back raises (and leaves no child/cgroup);
  5  fork safety: the child exits cleanly; no child process is left; a child past deadline + grace is killed.
Checker gate (kit's hybrid_checker / adaptive_checker, built v2 kit WFG_V2_KIT; frozen kit WFG_FROZEN_KIT as control):
  3  completed-then-over-budget keeps the result with within_budget False; an interrupted check stays UNRESOLVED;
     an authority change still replaces; a wall cap still replaces (after check and after adaptive fallback).
Decision: a certified journey is a within-budget success only with within_budget True.
Solver gate:
  1  transient peak: after allocating and freeing more than the gate, road_core.solve (v2) still expands; the frozen
     road_core stops at 0 expansions with RSS_LIMIT (control).
"""
import importlib, json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
REPO = V2.parents[1]
sys.path.insert(0, str(V2 / 'stack-v2/phaseB'))
import v2_memory as VM  # noqa: E402

KIT = Path(os.environ['WFG_V2_KIT']).resolve() if os.environ.get('WFG_V2_KIT') else None
FROZEN = Path(os.environ['WFG_FROZEN_KIT']).resolve() if os.environ.get('WFG_FROZEN_KIT') else None
MiB = 2 ** 20
HAVE_CG = VM.host_state()['cgroup_path'] is not None


def _children_left():
    try:
        return os.waitpid(-1, os.WNOHANG)[0] != 0 or True
    except ChildProcessError:
        return False


@unittest.skipUnless(HAVE_CG, 'no cgroup v1 memory hierarchy on this host')
class Mechanism(unittest.TestCase):
    def run_fn(self, fn, gate, **kw):
        return VM.run_check_forked(fn, gate, time.perf_counter() + 60, **kw)

    def test_alloc_within_and_over(self):
        import numpy as np
        p, c, b = self.run_fn(lambda: {'s': float(np.ones(100 * MiB // 8).sum())}, 512)
        self.assertEqual(c['exit_code'], 0); self.assertIsNotNone(p)
        self.assertIs(b['within_budget'], True); self.assertEqual(b['mechanism'], 'cgroup_v1_max_usage_parent_moved')
        self.assertGreaterEqual(b['peak_mb'], 100)
        p, c, b = self.run_fn(lambda: {'s': float(np.ones(600 * MiB // 8).sum())}, 512)
        self.assertIs(b['within_budget'], False); self.assertGreaterEqual(b['peak_mb'], 600)

    def test_2_parent_allocation_not_charged_to_check(self):
        import numpy as np
        big = np.ones(1024 * MiB // 8)                       # parent holds 1 GiB, touched
        p, c, b = self.run_fn(lambda: {'s': float(big.sum())}, 512)
        self.assertIs(b['within_budget'], True, b); self.assertLess(b['peak_mb'], 200)
        del big

    def test_T_spike_between_samples_full_gate(self):
        import numpy as np
        def spike():
            x = np.ones(768 * MiB // 8); x.sum(); del x
            return {'ok': True}
        p, c, b = self.run_fn(spike, 512)
        self.assertIs(b['within_budget'], False, b)              # the cgroup peak saw the spike
        self.assertGreaterEqual(b['peak_mb'], 768)
        self.assertLessEqual(b['sampled_private_peak_mb'], 512)  # the samples alone did not
        p, c, b = self.run_fn(spike, 512, use_cgroup=False)      # fork-sampled path only
        self.assertEqual(b['within_budget'], 'not_proven', b)
        self.assertIsNot(b['within_budget'], True)

    def test_M_parent_back_in_original_cgroup(self):
        before = Path('/proc/self/cgroup').read_text()
        self.run_fn(lambda: {'ok': 1}, 512)
        self.assertEqual(Path('/proc/self/cgroup').read_text(), before)

    def test_M_failed_move_back_raises_and_cleans_up(self):
        real = VM._self_cgroup_line; calls = {'n': 0}
        def fake():
            calls['n'] += 1
            return real() if calls['n'] == 1 else 'moved-elsewhere'
        VM._self_cgroup_line = fake
        try:
            with self.assertRaises(RuntimeError):
                self.run_fn(lambda: (time.sleep(5), {'ok': 1})[1], 512)
        finally:
            VM._self_cgroup_line = real
        self.assertFalse(_children_left())
        base = VM.host_state()['cgroup_path']
        self.assertFalse([d for d in os.listdir(base) if d.startswith('wfgv2_check_%d_' % os.getpid())])

    def test_5_fork_safety(self):
        p, c, b = self.run_fn(lambda: {'ok': 1}, 512)
        self.assertEqual((c['exit_code'], c['signal'], c['killed_after_deadline']), (0, None, False))
        self.assertTrue(b['cgroup']['rmdir_ok']); self.assertLessEqual(b['cgroup']['usage_before_fork_bytes'], 4096)
        self.assertFalse(_children_left())
        p, c, b = VM.run_check_forked(lambda: (time.sleep(30), {'late': 1})[1], 512, time.perf_counter() + 0.5, grace_s=0.5)
        self.assertIsNone(p); self.assertTrue(c['killed_after_deadline']); self.assertFalse(_children_left())

    def test_3_interrupted_check_returns_no_payload(self):
        def boom():
            raise MemoryError('synthetic')
        p, c, b = self.run_fn(boom, 512)
        self.assertIsNone(p); self.assertEqual(c['exit_code'], 3); self.assertIn('MemoryError', c['error'])

    def test_fork_failure_is_not_proven_never_false(self):
        real = os.fork
        def boom():
            raise OSError(11, 'synthetic EAGAIN')
        os.fork = boom
        try:
            p, c, b = self.run_fn(lambda: {'ok': 1}, 1)
        finally:
            os.fork = real
        self.assertIsNone(p); self.assertIn('FORK_FAILED', c['error']); self.assertEqual(b['within_budget'], 'not_proven')
        base = VM.host_state()['cgroup_path']
        self.assertFalse([d for d in os.listdir(base) if d.startswith('wfgv2_check_%d_' % os.getpid())])
        self.assertEqual(Path('/proc/self/cgroup').read_text().count('wfgv2_check'), 0)

    def test_cgroup_setup_failure_falls_back_to_child_sample(self):
        p, c, b = self.run_fn(lambda: {'ok': 1}, 3072, use_cgroup=False)
        self.assertEqual(p, {'ok': 1}); self.assertEqual(b['within_budget'], 'not_proven'); self.assertIsNone(b['cgroup'])

    def test_payload_types_preserved(self):
        from fractions import Fraction
        p, c, b = self.run_fn(lambda: {'f': Fraction(1, 3), 'n': None, 'x': [1.5]}, 512)
        self.assertEqual(p, {'f': Fraction(1, 3), 'n': None, 'x': [1.5]}); self.assertIsInstance(p['f'], Fraction)


def _kit_checker_modules(kit):
    q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
    src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
    paths = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(kit / 'phaseB')]
    return paths


CHECKER_PROBE = r'''
import json, sys, time, copy
sys.path[:0] = json.loads(sys.argv[1]); case = sys.argv[2]
sys.path.insert(0, sys.argv[3])
import hybrid_checker as H, adaptive_checker as A
from test_full_checker_window import packet, mission
import tempfile
from pathlib import Path
d = Path(tempfile.mkdtemp()); packet(d); g, r, legs, dest = mission()
out = {}
def keys_named(x, name):
    if isinstance(x, dict):
        return sum((k == name) + keys_named(v, name) for k, v in x.items())
    if isinstance(x, (list, tuple)):
        return sum(keys_named(v, name) for v in x)
    return 0
if case == 'over_budget_kept':
    H.RSS_LIMIT_MB = 1                                       # any real check is over a 1 MiB gate
    c = H.HybridChecker(d); res = c.check(g, r, legs, dest, wall_s=30)
    out = {'status': res['status'], 'reason': res.get('reason'), 'rb': res.get('resource_budget'),
           'cs': res.get('checker_sampled_budget'), 'n_resource_budget': keys_named(res, 'resource_budget')}
elif case == 'over_budget_kept_in_child':
    import v2_memory as VM
    H.RSS_LIMIT_MB = 1
    c = H.HybridChecker(d)
    res, child, budget = VM.run_check_forked(lambda: c.check(g, r, legs, dest, wall_s=30), 1, time.perf_counter() + 60)
    out = {'status': res['status'], 'reason': res.get('reason'), 'cs': res.get('checker_sampled_budget'),
           'budget': {k: budget[k] for k in ('within_budget', 'mechanism')}, 'n_resource_budget': keys_named(res, 'resource_budget')}
elif case == 'parent_check_refused':
    import v2_memory as VM
    VM.REQUIRE_CHILD_FOR_CHECK = True
    c = H.HybridChecker(d)
    try:
        c.check(g, r, legs, dest, wall_s=30); out = {'parent': 'ran'}
    except RuntimeError as exc:
        out = {'parent': str(exc)}
    res, child, budget = VM.run_check_forked(lambda: c.check(g, r, legs, dest, wall_s=30), 3072, time.perf_counter() + 60)
    out.update(child_status=res and res['status'], within=budget['within_budget'])
elif case == 'wall_cap_after_check':
    c = H.HybridChecker(d); t = time.perf_counter()
    res = c._finish({'status': 'CERTIFIED_ADMISSIBLE', 'reason': 'X'}, t, t - 1, {})
    out = {'status': res['status'], 'reason': res.get('reason')}
elif case in ('authority_changed', 'wall_cap_after_adaptive', 'adaptive_over_budget_kept'):
    if case == 'adaptive_over_budget_kept':
        H.RSS_LIMIT_MB = 1
    c = A.HybridChecker(d)
    def fake_base(self, graph, request, legs_, destination, **kw):
        self._radiation = object()
        return {'status': 'UNRESOLVED', 'reason': 'RADIATION_UNRESOLVED_OR_UNSUPPORTED', 'contact': {'status': 'CLEAR'},
                'trajectory': [], 'radiation': {}}
    A._BaseChecker.check = fake_base
    c._source_identity = H.file_sha(d / 'constructed_arrays.npz') + ':' + H.file_sha(d / 'REPORT.json')
    def fake_adaptive(rad, traj, req, stop):
        if case == 'authority_changed':
            g['revision'] = 'changed-during-fallback'
        if case == 'wall_cap_after_adaptive':
            time.sleep(max(0, stop - time.perf_counter()) + 1.2)
        return {'status': 'CERTIFIED_RADIATION'}
    A.adaptive_bound = fake_adaptive
    res = A.HybridChecker.check(c, g, r, legs, dest, wall_s=2 if case == 'wall_cap_after_adaptive' else 30)
    out = {'status': res['status'], 'reason': res.get('reason'), 'rb': res.get('resource_budget'),
           'cs': res.get('checker_sampled_budget')}
print(json.dumps(out, default=str))
'''


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class CheckerGate(unittest.TestCase):
    def probe(self, kit, case):
        p = subprocess.run([sys.executable, '-B', '-c', CHECKER_PROBE, json.dumps(_kit_checker_modules(kit)), case,
                            str(REPO / 'experimental/window-routing/tests')], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_completed_then_over_budget_keeps_result(self):
        # outside a forked check child (Thomas 18:12 point 2): the result is kept, and NO outside claim is made from a
        # sample that is not the check's own; the checker never writes resource_budget (point 1)
        v2 = self.probe(KIT, 'over_budget_kept')
        self.assertNotEqual(v2['status'], 'UNRESOLVED', v2)
        self.assertIsNone(v2['rb']); self.assertEqual(v2['n_resource_budget'], 0)
        self.assertIs(v2['cs']['sample_is_check_own'], False); self.assertIs(v2['cs']['over_gate_from_sample'], False)
        # inside run_check_forked's child: kept, the checker's own sample says over, and the wrapper's verdict is False
        c = self.probe(KIT, 'over_budget_kept_in_child')
        self.assertNotEqual(c['status'], 'UNRESOLVED', c); self.assertEqual(c['n_resource_budget'], 0)
        self.assertIs(c['cs']['sample_is_check_own'], True); self.assertIs(c['cs']['over_gate_from_sample'], True)
        self.assertIs(c['budget']['within_budget'], False)
        if FROZEN is not None:                                # control: the frozen checker replaces it
            fz = self.probe(FROZEN, 'over_budget_kept')
            self.assertEqual((fz['status'], fz['reason']), ('UNRESOLVED', 'RSS_LIMIT'))

    def test_adaptive_over_budget_keeps_result(self):
        v2 = self.probe(KIT, 'adaptive_over_budget_kept')
        self.assertEqual(v2['status'], 'CERTIFIED_ADMISSIBLE', v2); self.assertIsNone(v2['rb'])
        self.assertIs(v2['cs']['over_gate_from_sample'], False)        # parent process: never an outside claim
        if FROZEN is not None:
            fz = self.probe(FROZEN, 'adaptive_over_budget_kept')
            self.assertEqual(fz['reason'], 'RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK')

    def test_wall_cap_still_replaces(self):
        self.assertEqual(self.probe(KIT, 'wall_cap_after_check'), {'status': 'UNRESOLVED', 'reason': 'WALL_CAP_AFTER_CHECK'})
        v2 = self.probe(KIT, 'wall_cap_after_adaptive')
        self.assertEqual((v2['status'], v2['reason']), ('UNRESOLVED', 'WALL_CAP_AFTER_ADAPTIVE_FALLBACK'))

    def test_whole_road_check_refused_in_parent_when_required(self):
        v2 = self.probe(KIT, 'parent_check_refused')
        self.assertEqual(v2['parent'], 'V2_WHOLE_ROAD_CHECK_IN_PARENT_PROCESS')
        self.assertNotEqual(v2['child_status'], None); self.assertIs(v2['within'], True)

    def test_authority_change_still_replaces(self):
        v2 = self.probe(KIT, 'authority_changed')
        self.assertEqual((v2['status'], v2['reason']), ('UNRESOLVED', 'AUTHORITY_CHANGED_DURING_ADAPTIVE_FALLBACK'))


class DecisionMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(V2 / 'stack-v2/decision'))
        cls.JD = importlib.import_module('journey_decision_v2_1')

    def dec(self, within):
        d = {'authoritative_status': 'CHECKED_JOURNEY_FEASIBLE', 'is_successful_journey': True, 'journey': {'arrival': 5}}
        res = {'whole_road_check': {'status': 'CERTIFIED_ADMISSIBLE', 'resource_budget': {'within_budget': within}}}
        if within == 'absent':
            res['whole_road_check'].pop('resource_budget')
        return self.JD._v2_memory_budget(d, res)

    def test_mapping(self):
        self.assertEqual(self.dec(True)['authoritative_status'], 'CHECKED_JOURNEY_FEASIBLE')
        for w, s in ((False, 'CHECKED_JOURNEY_OUTSIDE_MEMORY_BUDGET'), ('not_proven', 'CHECKED_JOURNEY_MEMORY_BUDGET_NOT_PROVEN'),
                     ('absent', 'CHECKED_JOURNEY_MEMORY_BUDGET_NOT_PROVEN'), (None, 'CHECKED_JOURNEY_MEMORY_BUDGET_NOT_PROVEN')):
            d = self.dec(w)
            self.assertEqual(d['authoritative_status'], s); self.assertFalse(d['is_successful_journey'])
            self.assertIsNone(d['journey']); self.assertEqual(d['certified_status_within_kit'], 'CHECKED_JOURNEY_FEASIBLE')
            self.assertEqual(d['journey_outside_memory_budget'], {'arrival': 5})
        self.assertNotIn('CHECKED_JOURNEY_OUTSIDE_MEMORY_BUDGET', self.JD.SUCCESS_STATUSES)

    def test_non_success_untouched(self):
        d = {'authoritative_status': 'UNRESOLVED', 'journey': None}
        self.assertIs(self.JD._v2_memory_budget(d, {}), d)


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class ResultHasOneVerdict(unittest.TestCase):
    def test_one_within_budget_field_and_it_is_true(self):
        # Thomas 18:12 point 1, on a real job that publishes a checked journey (Uljin 0304T12 FW2, ~7 s)
        out = Path(tempfile.mkdtemp(prefix='v2rb_')) / 'job'
        p = subprocess.run([sys.executable, '-B', str(V2 / 'tools/run_one_job.py'), str(KIT), str(REPO / 'data/routing'),
                            'uljin_2022', '20220304T120000Z_FW2', str(out), '81'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])
        row = json.loads(p.stdout.strip().splitlines()[-1])
        text = (out / 'RESULT.json').read_text(); res = json.loads(text)
        wr = res['whole_road_check']
        self.assertEqual(text.count('"within_budget"'), 1, 'exactly one within_budget field in RESULT')
        self.assertIs(wr['resource_budget']['within_budget'], True, wr['resource_budget'])
        self.assertEqual(wr['resource_budget']['mechanism'], 'cgroup_v1_max_usage_parent_moved')
        self.assertNotIn('within_budget', json.dumps(wr.get('checker_sampled_budget')))
        self.assertEqual(row['authoritative_status'], 'CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN', row)
        self.assertEqual(wr['check_child']['exit_code'], 0)
        self.assertNotEqual(wr['check_child']['pid'], os.getpid())
        self.assertIn('dist_sha256', res['bound_model_dist'])


SOLVE_PROBE = r'''
import json, sys, os, numpy as np
sys.path[:0] = json.loads(sys.argv[1]); inputs, region, case = sys.argv[2:5]
from pathlib import Path
inputs = Path(inputs); cutoff = case.split('_')[0]
graph = json.loads((inputs / 'graphs' / region / 'graph.json').read_text())
hazard = json.loads((inputs / 'latest_inputs_try02/packets' / region / cutoff / 'HAZARD.json').read_text())
req = json.loads((inputs / 'latest_inputs_try02/requests' / region / (case + '.json')).read_text())
import road_core
cur = lambda: int(open('/proc/self/statm').read().split()[1]) * os.sysconf('SC_PAGE_SIZE') / 2**20
x = np.ones(1536 * 2**20 // 8); x.sum(); del x               # transient 1.5 GiB, freed
gate = cur() + 400
req['limits'] = dict(req.get('limits') or {}, wall_s=40, rss_limit_mb=gate)
r = road_core.solve(graph, hazard, req, mode='centre')
m = r.get('metrics') or {}
print(json.dumps({'gate': gate, 'current_after': cur(), 'expansions': m.get('expansions'), 'reason': r.get('reason'),
                  'status': r.get('status'), 'gate_kind': m.get('rss_gate_kind'), 'gate_rss_now': m.get('gate_rss_mb_current'),
                  'lifetime_mb': m.get('peak_rss_mb'), 'core': road_core.__file__}))
'''


@unittest.skipIf(KIT is None or FROZEN is None, 'set WFG_V2_KIT and WFG_FROZEN_KIT')
class TransientPeak(unittest.TestCase):
    def probe(self, kit):
        p = subprocess.run([sys.executable, '-B', '-c', SOLVE_PROBE, json.dumps(_kit_checker_modules(kit)),
                            str(REPO / 'data/routing'), 'yeongdeok_2025', '20250325T190000Z_FD1'],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_1_freed_transient_does_not_stop_search(self):
        v2 = self.probe(KIT); fz = self.probe(FROZEN)
        self.assertTrue(v2['core'].startswith(str(KIT))); self.assertTrue(fz['core'].startswith(str(FROZEN)))
        self.assertEqual((fz['reason'], fz['expansions']), ('RSS_LIMIT', 0), fz)       # control: lifetime gate
        self.assertGreater(v2['expansions'], 0, v2)
        self.assertGreater(v2['lifetime_mb'], v2['gate'], v2)          # the lifetime peak is over the gate throughout
        if v2['reason'] == 'RSS_LIMIT':                                  # a later stop must be on CURRENT memory growth
            self.assertGreater(v2['gate_rss_now'], v2['gate'], v2)
        self.assertEqual(v2['gate_kind'], 'current_resident_statm')


if __name__ == '__main__':
    unittest.main()
