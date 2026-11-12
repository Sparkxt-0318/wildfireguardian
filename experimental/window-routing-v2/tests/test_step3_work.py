"""Step 3 tests (STEP3_ACCEPTANCE.md D), written before the calibration run. Kit tests need WFG_V2_KIT (a built Step 3
kit); each kit probe runs in its own interpreter with the kit's own module paths.

Unit:   Budget counting / caps / deadline; the watchdog kills a synthetic non-returning stage within threshold + 1 s.
Z:      unit definitions (setup_contact, setup_wait, sweep = (E+1) per sweep second); a work budget stops Z inside setup
        and inside the sweep with WORK_BUDGET and no route; without a cap the result equals the parent's Z.
Bounds: after a bound-model interruption every cached coefficient / edge entry is byte-identical to an uninterrupted
        model's; road_core turns the StageCap into its incomplete-cap TIMEOUT with no route.
Determinism: Z's unit count at a work-budget stop is identical normally and under CPU contention (one core shared with
        a busy loop: a slower machine).
Watchdog in a job: a Z stage that never returns is killed at its threshold, reported STAGE_CAP_WATCHDOG, and no later
        stage runs (fail closed); the job still ends before its deadline.
"""
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
REPO = V2.parents[1]
sys.path.insert(0, str(V2 / 'stack-v2/phaseB'))
import v2_work as W  # noqa: E402

KIT = Path(os.environ['WFG_V2_KIT']).resolve() if os.environ.get('WFG_V2_KIT') else None
DATA = Path(os.environ.get('WFG_DATA_ROUTING', str(REPO / 'data/routing')))


class BudgetUnit(unittest.TestCase):
    def test_counts_and_work_cap(self):
        b = W.Budget(units_cap=10)
        b.tick(4, 'a'); b.tick(6, 'b')
        self.assertEqual(b.record()['by_kind'], {'a': 4, 'b': 6})
        with self.assertRaises(W.StageCap) as cm:
            b.tick(1, 'a')
        self.assertEqual((cm.exception.reason, cm.exception.units, b.stopped), ('WORK_BUDGET', 11, 'WORK_BUDGET'))

    def test_deadline(self):
        b = W.Budget(deadline=time.perf_counter() - 1, wall_reason='WALL_CLOCK')
        with self.assertRaises(W.StageCap) as cm:
            b.tick(1)
        self.assertEqual(cm.exception.reason, 'WALL_CLOCK')

    def test_threshold_rule(self):
        self.assertEqual(W.watchdog_threshold(6), 16.0); self.assertEqual(W.watchdog_threshold(100), 150.0)

    def test_watchdog_kills_non_returning_stage(self):
        t0 = time.perf_counter()
        with self.assertRaises(W.WatchdogFired):
            with W.watchdog('SYNTH', 0.5):
                while True:          # a synthetic stage that never returns (pure Python loop)
                    pass
        self.assertLess(time.perf_counter() - t0, 0.5 + 1.0)

    def test_watchdog_not_swallowed_by_except_exception(self):
        with self.assertRaises(W.WatchdogFired):
            with W.watchdog('SYNTH', 0.2):
                try:
                    time.sleep(2)
                except Exception:    # a stage's own broad handler must not swallow the watchdog
                    pass

    def test_watchdog_timer_cleared(self):
        import signal
        with W.watchdog('OK', 5):
            pass
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))


PROBE = r'''
import json, sys, time, copy
from pathlib import Path
from fractions import Fraction as F
kit, data, region, case, what = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
arg = json.loads(sys.argv[6]) if len(sys.argv) > 6 else {}
q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(kit / 'phaseB')]
from routing import core
import road_bounds, zsweep, road_core, v2_work
cut = case.split('_')[0]
graph = json.loads((data / 'graphs' / region / 'graph.json').read_text())
packet = data / 'latest_inputs_try02/packets' / region / cut
hazard = json.loads((packet / 'HAZARD.json').read_text())
req = json.loads((data / 'latest_inputs_try02/requests' / region / (case + '.json')).read_text())
M = road_bounds.RoadBoundModel(graph, packet, active_window=(F(req['departure']), F(req['horizon'])))
out = {'E': len(graph['edges'])}
def z(budget, wall=600):
    return zsweep.contact_sweep(graph, hazard, req, M, wall_s=wall, core=core, check_route_mode=road_core.check_route_mode,
                                zero_view=M.view('zero'), budget=budget)
if what == 'z_count':
    b = v2_work.Budget(); r = z(b)
    r0 = z(None)
    out.update(status=r['status'], arrival=r.get('arrival'), legs=r.get('legs'), sweep_seconds=r['metrics'].get('sweep_seconds'),
               work=b.record(), parent_status=r0['status'], parent_arrival=r0.get('arrival'), parent_legs=r0.get('legs'))
elif what == 'z_cap':
    b = v2_work.Budget(units_cap=arg['cap']); r = z(b)
    out.update(status=r['status'], reason=r.get('reason'), arrival=r.get('arrival'), legs=r.get('legs'), work=b.record())
elif what == 'bounds_interrupt':
    M2 = road_bounds.RoadBoundModel(graph, packet, active_window=(F(req['departure']), F(req['horizon'])))
    eis = list(range(min(len(graph['edges']), arg['n_edges'])))
    M.stage_budget = v2_work.Budget(units_cap=arg['cap'])
    stopped = None
    for ei in eis:
        try:
            M.edge_store(ei)
        except v2_work.StageCap as exc:
            stopped = exc.reason; break
    M.stage_budget = None
    for ei in eis:
        M2.edge_store(ei)
    import numpy as np
    bad = [k for k, v in M._coef.items() if not (np.array_equal(v[0], M2._coef[k][0]) and np.array_equal(v[1], M2._coef[k][1])
           and v[0].tobytes() == M2._coef[k][0].tobytes() and v[1].tobytes() == M2._coef[k][1].tobytes())]
    badE = [k for k, v in M._edge.items() if any(a[0].tobytes() != b[0].tobytes() or a[1].tobytes() != b[1].tobytes()
                                                  for a, b in zip(v, M2._edge[k]))]
    out.update(stopped=stopped, coef_entries=len(M._coef), edge_entries=len(M._edge), coef_mismatch=len(bad),
               edge_mismatch=len(badE), M2_coef=len(M2._coef))
elif what == 'solve_cap':
    M.stage_budget = v2_work.Budget(units_cap=arg['cap'])
    rq = copy.deepcopy(req); rq['limits'] = dict(rq.get('limits') or {}, wall_s=120)
    r = road_core.solve(graph, hazard, rq, exposure=M.view('lo'), mode='lo')
    out.update(status=r['status'], reason=r.get('reason'), legs=r.get('legs'), arrival=r.get('arrival'),
               solver_status=r.get('solver_status'), metrics=r.get('metrics'))
print(json.dumps(out, default=str))
'''


def probe(region, case, what, arg=None, prefix=()):
    p = subprocess.run(list(prefix) + [sys.executable, '-B', '-c', PROBE, str(KIT), str(DATA), region, case, what, json.dumps(arg or {})],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(p.stderr[-3000:])
    return json.loads(p.stdout.strip().splitlines()[-1])


YD = ('yeongdeok_2025', '20250325T190000Z_FX2')      # contact edges present; Z sweeps


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class ZWork(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = probe(*YD, 'z_count')

    def test_unit_definitions(self):
        c = self.c; E = c['E']; bk = c['work']['by_kind']
        self.assertGreater(bk.get('setup_contact', 0), 0, bk)
        self.assertEqual(bk['sweep'] % (E + 1), 0)
        self.assertIn(bk['sweep'] // (E + 1), (c['sweep_seconds'], c['sweep_seconds'] + 1))
        self.assertEqual(c['work']['units'], sum(bk.values()))

    def test_counting_does_not_change_z(self):
        c = self.c
        self.assertEqual((c['status'], c['arrival'], c['legs']), (c['parent_status'], c['parent_arrival'], c['parent_legs']))

    def test_stop_inside_setup(self):
        r = probe(*YD, 'z_cap', {'cap': 3})
        self.assertEqual((r['status'], r['reason'], r['arrival'], r['legs']), ('TIMEOUT', 'WORK_BUDGET', None, []))
        self.assertEqual(r['work']['units'], 4); self.assertNotIn('sweep', r['work']['by_kind'])

    def test_stop_inside_sweep(self):
        E = self.c['E']; setup = self.c['work']['units'] - self.c['work']['by_kind']['sweep']
        if self.c['work']['by_kind']['sweep'] < 4 * (E + 1):
            self.skipTest('Z sweeps fewer than 4 seconds on this mission')
        r = probe(*YD, 'z_cap', {'cap': setup + 3 * (E + 1)})
        self.assertEqual((r['status'], r['reason'], r['legs']), ('TIMEOUT', 'WORK_BUDGET', []))
        self.assertEqual(r['work']['by_kind']['sweep'], 4 * (E + 1)); self.assertEqual(r['work']['units'], setup + 4 * (E + 1))


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class Determinism(unittest.TestCase):
    def test_unit_count_identical_under_contention(self):
        c = probe(*YD, 'z_count'); cap = c['work']['units'] // 2
        a = probe(*YD, 'z_cap', {'cap': cap})
        busy = subprocess.Popen(['taskset', '-c', '0', sys.executable, '-c', 'while True: pass'])
        try:
            b = probe(*YD, 'z_cap', {'cap': cap}, prefix=('taskset', '-c', '0'))
        finally:
            busy.kill(); busy.wait()
        self.assertEqual(a, b)
        self.assertEqual(a['work']['units'], cap + (a['work']['units'] - cap))


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class BoundInterruption(unittest.TestCase):
    def test_caches_identical_after_interruption(self):
        r = probe(*YD, 'bounds_interrupt', {'n_edges': 400, 'cap': 50})
        self.assertEqual(r['stopped'], 'WORK_BUDGET', r)
        self.assertGreater(r['coef_entries'], 0)
        self.assertEqual((r['coef_mismatch'], r['edge_mismatch']), (0, 0), r)

    def test_solve_returns_incomplete_cap_timeout(self):
        r = probe(*YD, 'solve_cap', {'cap': 1})
        self.assertEqual((r['status'], r['reason'], r['solver_status'], r['legs'], r['arrival']),
                         ('TIMEOUT', 'WORK_BUDGET_IN_BOUND_MODEL', 'INCOMPLETE_CAP', [], None), r)


HANG = r'''
import os, runpy, sys
target = os.environ['WFG_PHASE_TARGET']
sys.path.insert(0, os.path.dirname(target))
import zsweep
def never_returns(*a, **k):
    while True:
        pass
zsweep.contact_sweep = never_returns        # a synthetic Z stage that never returns
sys.argv[0] = target
runpy.run_path(target, run_name='__main__')
'''


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class WatchdogInJob(unittest.TestCase):
    def test_hung_z_is_killed_and_later_stages_do_not_run(self):
        d = Path(tempfile.mkdtemp(prefix='v2wd_')); (d / 'phase_worker.py').write_text(HANG)
        out = d / 'job'
        code = ('import json,sys;from pathlib import Path;sys.path.insert(0,%r);import run_profile as RP;RP.HERE=Path(%r);'
                'r=RP.run_one(Path(%r),Path(%r),%r,%r,Path(%r),81.0,"phase",sys.executable);print(json.dumps(r,default=str))'
                % (str(REPO / 'research/harness-2026-11/F-3.4'), str(d), str(KIT), str(DATA), YD[0], YD[1], str(out)))
        t0 = time.time()
        p = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])
        res = json.loads((out / 'RESULT.json').read_text())
        z = [s for s in res['rda_stages'] if s['stage'] == 'Z']
        self.assertEqual(z[0]['reason'], 'STAGE_CAP_WATCHDOG', z)
        self.assertEqual(res['stage_cap_watchdog']['stage'], 'Z')
        self.assertEqual([s['stage'] for s in res['rda_stages']], ['Z'])          # fail closed: no EA/LO/LO2/HI
        self.assertNotIn('earliest_arrival_bound', [k for k, v in res.items() if v])
        self.assertLess(z[0]['elapsed_s'], 16.0 + 1.0); self.assertGreater(z[0]['elapsed_s'], 16.0 - 0.5)
        self.assertLess(time.time() - t0, 81.0)


if __name__ == '__main__':
    unittest.main()
