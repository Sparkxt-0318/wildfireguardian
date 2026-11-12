"""Thomas's Step 3 conditions (19:16 UTC), as tests (STEP3_ACCEPTANCE amendments). Kit tests need WFG_V2_KIT and the
1-hour data (WFG_DATA_ROUTING). Each kit probe runs in its own interpreter with the kit's module paths.

B3.2  whole-state completeness: interrupt the bound model at tick k in {1, 2, 3, 5, last} while it answers a fixed query
      list; (a) right after the interruption every cache entry it holds equals the fresh model's entry for that key
      (no partial entry); (b) after replaying the same queries, every returned value is byte-identical to the fresh
      model's, and the whole reachable state (all attributes, recursively) equals the fresh model's except counters.
B3.3  downstream: an LO solve interrupted by a StageCap, then LO and HI solves on the same model, equal the same solves
      on a fresh model.
B3.4  a capped stage is never a refusal or a bound: a job whose LO is StageCap'd (LO would otherwise PROVE_INFEASIBLE)
      has no refusal certificate and no LO lower bound.
B5.2  alarm scope: in real jobs, every HybridChecker.check starts with the stage alarm disarmed (ITIMER_REAL == 0).
B5.4  never two alarms: arming while one is active raises.
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
F34 = Path(os.environ.get('WFG_F34_DIR', str(REPO / 'research/harness-2026-11/F-3.4')))


class SingleAlarm(unittest.TestCase):
    def test_second_arming_raises(self):
        with W.watchdog('A', 5):
            with self.assertRaises(RuntimeError):
                with W.watchdog('B', 5):
                    pass

    def test_exceptions_are_base_exceptions(self):
        self.assertFalse(issubclass(W.StageCap, Exception)); self.assertFalse(issubclass(W.WatchdogFired, Exception))
        self.assertFalse(issubclass(W.WatchdogFired, W.StageCap)); self.assertFalse(issubclass(W.StageCap, W.WatchdogFired))


PROBE = r'''
import json, sys, copy, hashlib
from pathlib import Path
from fractions import Fraction as F
import numpy as np
kit, data, region, case, what = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
arg = json.loads(sys.argv[6])
q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(kit / 'phaseB')]
import road_bounds, road_core, v2_work
cut = case.split('_')[0]
graph = json.loads((data / 'graphs' / region / 'graph.json').read_text())
packet = data / 'latest_inputs_try02/packets' / region / cut
hazard = json.loads((packet / 'HAZARD.json').read_text())
req = json.loads((data / 'latest_inputs_try02/requests' / region / (case + '.json')).read_text())
win = (F(req['departure']), F(req['horizon']))
def model():
    # road_bounds._REGISTRY is a PROCESS-WIDE coefficient cache keyed by model identity, shared by every model built in
    # this process; each probe model must start from an empty one, as a worker process does
    road_bounds._REGISTRY.clear()
    return road_bounds.RoadBoundModel(graph, packet, active_window=win)

class TickAt(v2_work.Budget):
    """Raise StageCap at the k-th tick (ticks, not units); k=None counts only. With snap_at, record the container
    sizes of the whole reachable model state AT the given tick numbers (before that tick's chunk runs)."""
    def __init__(self, k, model=None, snap_at=()):
        super().__init__(); self.k = k; self.ticks = 0; self.model = model; self.snap_at = set(snap_at); self.snaps = {}
    def tick(self, n=1, kind=None):
        self.ticks += 1; self.units += n
        if self.ticks in self.snap_at:
            self.snaps[self.ticks] = sizes(state(self.model))
        if self.k is not None and self.ticks == self.k:
            raise v2_work.StageCap('WORK_BUDGET', self.units)

E = len(graph['edges']); dep, hor = req['departure'], req['horizon']
edges = [graph['edges'][i]['id'] for i in range(0, E, max(1, E // arg.get('n_edges', 40)))][:arg.get('n_edges', 40)]
nodes = [n['id'] for n in graph['nodes'][:: max(1, len(graph['nodes']) // 10)]][:10]
def queries(M):
    out = []
    for mode in ('lo', 'hi'):
        v = M.view(mode)
        for e in edges:
            out.append(v.edge(e, dep, min(hor, dep + 5)))
        for n in nodes:
            out.append(v.node(n, dep, min(hor, dep + 3)))
    return out
def enc(vals):
    return hashlib.sha256(repr([[(str(d), float(p).hex()) for d, p in v] for v in vals]).encode()).hexdigest()

SKIP = ('stats', 'stage_budget', 'construct_s', 'coef_s', 'activity_s', 'build_s')
DYN = None   # path prefixes the queries change (set after a fresh before/after full walk); None = walk everything
def allowed(path):
    return DYN is None or any(path.startswith(d) or d.startswith(path) for d in DYN)
def walk(x, path, out, seen):
    if id(x) in seen or not allowed(path):
        return
    if isinstance(x, (dict, list, tuple, set, np.ndarray)) or hasattr(x, '__dict__'):
        seen.add(id(x))
    if isinstance(x, np.ndarray):
        out[path] = ('nd', x.dtype.str, x.shape, x.tobytes()); return
    if isinstance(x, dict):
        out[path] = ('dict', len(x))
        for k, v in x.items():
            walk(v, path + '[' + repr(k) + ']', out, seen)
        return
    if isinstance(x, (list, tuple)):
        out[path] = (type(x).__name__, len(x))
        for i, v in enumerate(x):
            walk(v, path + '[%d]' % i, out, seen)
        return
    if isinstance(x, set):
        out[path] = ('set', repr(sorted(map(repr, x)))); return
    if callable(x) and not isinstance(x, type):
        # bound methods / functions: identity by qualified name and owner type (a repr carries a memory address);
        # a memo (functools.lru_cache) is compared by its statistics' size field
        owner = getattr(x, '__self__', None)
        ci = x.cache_info().currsize if hasattr(x, 'cache_info') else None
        out[path] = ('callable', getattr(x, '__qualname__', type(x).__name__), type(owner).__name__ if owner is not None else None, ci)
        return
    if hasattr(x, '__dict__') and type(x).__module__ not in ('builtins',) and not callable(x) or (hasattr(x, '__dict__') and type(x).__name__ in ('RoadBoundModel', 'HybridRadiationBounds', 'Adaptive', 'MappingProxyType')):
        for k, v in vars(x).items():
            if k in SKIP or k.endswith('_s') and isinstance(v, float):
                continue
            walk(v, path + '.' + k, out, seen)
        return
    out[path] = ('v', repr(x))
def state(M, full=False):
    global DYN
    keep = DYN
    if full:
        DYN = None
    out = {}; walk(M, 'M', out, set())
    DYN = keep
    return out
def top(p, depth=2):
    """prefix of a path: its first `depth` ATTRIBUTE segments, cut before any dict/list key (so a changed cache entry
    selects its whole cache, e.g. 'M._coef', not one prefix per key)"""
    import re
    out = 'M'
    for seg in re.findall(r'\.[^.\[]+|\[[^\]]*\]', p[1:])[:depth]:
        if seg.startswith('['):
            break
        out += seg
    return out
def sizes(st):
    """Container sizes only (dict/list/tuple lengths and array shapes): what a chunk would grow if it had run."""
    return {p: (v[0], v[1]) if v[0] in ('dict', 'list', 'tuple') else (v[0], v[2]) if v[0] == 'nd' else (v[0],) for p, v in st.items()}

if what == 'completeness':
    fresh = model(); before = state(fresh, full=True); ref_vals = queries(fresh); ref_full = state(fresh, full=True)
    changed = sorted(p for p in set(before) | set(ref_full) if before.get(p) != ref_full.get(p))
    DYN = sorted({top(p) for p in changed})   # every container the queries touch (plus its subtree) is walked per k
    ref_state = state(fresh)
    cnt = model(); cnt.stage_budget = TickAt(None); queries(cnt); total = cnt.stage_budget.ticks
    K = sorted({1, 2, 3, 5, total})
    snap = model(); snap.stage_budget = TickAt(None, snap, K); queries(snap); snaps = snap.stage_budget.snaps
    res = {'total_ticks': total, 'cases': [], 'dynamic_prefixes': DYN, 'n_full_paths': len(ref_full)}
    for k in K:
        M = model(); M.stage_budget = TickAt(k); stopped = None
        try:
            queries(M)
        except v2_work.StageCap as exc:
            stopped = exc.reason
        M.stage_budget = None
        mid = state(M)
        # Thomas 19:36: nothing of the chunk whose tick raised reached ANY reachable cache (ivkernel, hybrid_radiation,
        # adaptive, road_bounds): the state's container sizes equal those of an uninterrupted run AT tick k
        sm = sizes(mid)
        grew = sorted(p for p in set(sm) | set(snaps[k]) if sm.get(p) != snaps[k].get(p))
        partial = [p for p, v in mid.items() if p in ref_state and ref_state[p] != v and v[0] != 'dict' and not p.startswith('M.n_override')]
        # entries present right after the interruption must equal the fresh model's (dict sizes may be smaller)
        missing_in_ref = [p for p in mid if p not in ref_state]
        vals = queries(M)
        after = state(M, full=True)                     # final check: the WHOLE reachable state, not only DYN
        diff = sorted(p for p in set(after) | set(ref_full) if after.get(p) != ref_full.get(p))
        res['cases'].append({'k': k, 'stopped': stopped, 'n_grown_vs_tick_k': len(grew), 'grown': grew[:5], 'partial_entries': partial[:5], 'n_partial': len(partial),
                             'paths_not_in_fresh': missing_in_ref[:5], 'n_paths_not_in_fresh': len(missing_in_ref),
                             'values_identical': enc(vals) == enc(ref_vals), 'state_diff': diff[:5], 'n_state_diff': len(diff),
                             'n_state_paths': len(after)})
    print(json.dumps(res, default=str))
elif what == 'downstream':
    def solve(M, mode, wall=60):
        rq = copy.deepcopy(req); rq['limits'] = dict(rq.get('limits') or {}, wall_s=wall)
        r = road_core.solve(graph, hazard, rq, exposure=M.view(mode), mode=mode)
        return {'status': r['status'], 'reason': r.get('reason'), 'arrival': r.get('arrival'), 'legs': r.get('legs'),
                'per_member': {k: {'dose': str(v.get('dose_exact', v.get('dose'))), 'peak': v.get('peak')} for k, v in (r.get('per_member') or {}).items()}}
    M = model(); M.stage_budget = TickAt(arg['k']); first = solve(M, 'lo'); M.stage_budget = None
    a = [solve(M, 'lo'), solve(M, 'hi')]
    Mf = model(); b = [solve(Mf, 'lo'), solve(Mf, 'hi')]
    print(json.dumps({'interrupted': first, 'after': a, 'fresh': b}, default=str))
'''


def probe(region, case, what, arg):
    p = subprocess.run([sys.executable, '-B', '-c', PROBE, str(KIT), str(DATA), region, case, what, json.dumps(arg)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(p.stderr[-3000:])
    return json.loads(p.stdout.strip().splitlines()[-1])


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class WholeStateCompleteness(unittest.TestCase):
    def test_interrupt_at_k_then_replay(self):
        # missions with contact edges and 1.8k / 18.9k road edges (the 112k-edge Yeongdeok graph makes each whole-state
        # walk minutes long; the bound-model code path is the same)
        for region, case in (('hongseong_2023', '20230402T140000Z_FW2'), ('uljin_2022', '20220304T120000Z_FW2')):
            r = probe(region, case, 'completeness', {'n_edges': 40})
            self.assertGreater(r['total_ticks'], 5, r)
            for c in r['cases']:
                with self.subTest(mission=case, k=c['k']):
                    self.assertEqual(c['stopped'], 'WORK_BUDGET')
                    self.assertEqual(c['n_partial'], 0, c)              # no partial entry right after the interruption
                    self.assertEqual(c['n_grown_vs_tick_k'], 0, c)      # nothing from the chunk whose tick raised
                    self.assertEqual(c['n_paths_not_in_fresh'], 0, c)   # nothing the fresh model would not hold
                    self.assertTrue(c['values_identical'], c)           # replayed answers byte-identical
                    self.assertEqual(c['n_state_diff'], 0, c)           # whole reachable state identical (counters excluded)


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class Downstream(unittest.TestCase):
    def test_interrupted_lo_then_lo_and_hi_equal_fresh(self):
        r = probe('uljin_2022', '20220304T120000Z_FW2', 'downstream', {'k': 3})
        self.assertEqual((r['interrupted']['status'], r['interrupted']['reason'], r['interrupted']['legs']),
                         ('TIMEOUT', 'WORK_BUDGET_IN_BOUND_MODEL', []))
        self.assertEqual(r['after'], r['fresh'])


LAUNCH = r'''
import json, os, runpy, signal, sys
target = os.environ['WFG_PHASE_TARGET']; log = os.environ['WFG_TEST_LOG']; mode = os.environ['WFG_TEST_MODE']
sys.path.insert(0, os.path.dirname(target))
q = json.loads(open(os.path.join(os.path.dirname(os.path.dirname(target)), 'queues/LATEST_PREFLIGHT_REAL.json')).read())['jobs'][0]
kit = os.path.dirname(os.path.dirname(target)); src = q['source_root'] if os.path.isabs(q['source_root']) else os.path.join(kit, q['source_root'])
sys.path[:0] = [os.path.join(src, 'baseline/routing-package'), os.path.join(src, 'baseline')]
if mode == 'alarm_scope':
    import adaptive_checker, hybrid_checker
    for cls in (adaptive_checker.HybridChecker, hybrid_checker.HybridChecker):
        orig = cls.check
        def wrapped(self, *a, _orig=orig, **k):
            with open(log, 'a') as f:
                f.write(json.dumps({'itimer': signal.getitimer(signal.ITIMER_REAL)[0]}) + '\n')
            return _orig(self, *a, **k)
        cls.check = wrapped
if mode == 'cap_lo':
    import road_core
    orig_solve = road_core.solve
    def solve(*a, **k):
        ex = k.get('exposure')
        if k.get('mode') == 'lo' and ex is not None and ex.m.stage_budget is not None:
            ex.m.stage_budget.units_cap = 0                  # force a StageCap at the first bound-model tick in LO
            with open(log, 'a') as f:
                f.write(json.dumps({'forced_cap_lo': True}) + '\n')
        return orig_solve(*a, **k)
    road_core.solve = solve
sys.argv[0] = target
runpy.run_path(target, run_name='__main__')
'''


def run_job(region, case, mode, budget=81.0):
    d = Path(tempfile.mkdtemp(prefix='v2t_')); (d / 'phase_worker.py').write_text(LAUNCH); log = d / 'log.jsonl'
    out = d / 'job'
    code = ('import json,os,sys;from pathlib import Path;sys.path.insert(0,%r);import run_profile as RP;RP.HERE=Path(%r);'
            'r=RP.run_one(Path(%r),Path(%r),%r,%r,Path(%r),%r,"phase",sys.executable);print(json.dumps(r,default=str))'
            % (str(F34), str(d), str(KIT), str(DATA), region, case, str(out), budget))
    env = dict(os.environ, WFG_TEST_LOG=str(log), WFG_TEST_MODE=mode)
    p = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise AssertionError(p.stderr[-3000:])
    # the controller passes only job['env'] to the worker; the test log path and mode must reach it
    return json.loads((out / 'RESULT.json').read_text()), [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT')
class InJob(unittest.TestCase):
    def test_capped_lo_is_never_a_refusal_or_bound(self):
        res, log = run_job('yeongdeok_2025', '20250325T190000Z_FD1', 'cap_lo')       # frozen: LO PROVEN_INFEASIBLE
        self.assertTrue(any(x.get('forced_cap_lo') for x in log), log)
        lo = [s for s in res['rda_stages'] if s.get('stage') == 'LO']
        self.assertEqual((lo[0]['status'], lo[0]['reason']), ('TIMEOUT', 'WORK_BUDGET_IN_BOUND_MODEL'), lo)
        self.assertIsNone(res.get('refusal_certificate'))
        self.assertFalse([b for b in res.get('lower_bounds') or [] if b['kind'] == 'road_lower_bound_lattice_relaxation'])
        self.assertNotEqual(res['decision']['authoritative_status'], 'FULL_MODEL_REFUSAL_PROVEN')

    def test_whole_road_checks_start_with_alarm_disarmed(self):
        seen = []
        for region, case in (('uljin_2022', '20220304T120000Z_FW2'), ('uiseong_andong_2025', '20250323T010000Z_FD1')):
            res, log = run_job(region, case, 'alarm_scope')
            seen += [x['itimer'] for x in log if 'itimer' in x]
        self.assertGreater(len(seen), 0, 'no whole-road check observed')
        self.assertEqual(set(seen), {0.0}, seen)


if __name__ == '__main__':
    unittest.main()
