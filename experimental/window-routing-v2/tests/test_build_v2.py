"""Step 0 tests for build_kit_v2.py. Needs a built request-window parent kit: WFG_V2_PARENT=/path/to/window-kit."""
import hashlib, json, os, shutil, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_kit_v2 as B  # noqa: E402

PARENT = Path(os.environ.get('WFG_V2_PARENT', '')).resolve() if os.environ.get('WFG_V2_PARENT') else None
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


@unittest.skipIf(PARENT is None, 'set WFG_V2_PARENT to a built request-window kit')
class BuildV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='v2test_'))
        cls.out = cls.tmp / 'kit-v2'
        cls.man, cls.pm = B.build(cls.out, PARENT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_identity(self):
        ident = json.loads((self.out / 'KIT_IDENTITY.json').read_text())
        self.assertEqual(ident['candidate_id'], B.V2_ID)
        self.assertEqual(ident['parent_candidate_id'], B.PARENT_ID)
        self.assertNotEqual(self.man['candidate_id'], self.pm['candidate_id'])
        self.assertIn('NOT the frozen kit', (self.out / 'README_KIT.md').read_text())

    def test_only_declared_files_differ(self):
        sealed = json.loads((B.HERE / 'SOURCE_SHA256.json').read_text())
        overlay = {str(Path(p).relative_to('stack-v2')) for p in sealed}
        allowed = overlay | {'KIT_IDENTITY.json', 'README_KIT.md', 'CANDIDATE_MANIFEST.json'} | \
            {str(p.relative_to(self.out)) for p in (self.out / 'queues').glob('*.json')}
        for rel, h in self.pm['files'].items():
            if rel not in allowed:
                self.assertEqual(sha(self.out / rel), h, rel)
        for rel in overlay:
            self.assertEqual(sha(self.out / rel), sealed['stack-v2/' + rel])

    def test_manifest_matches_files(self):
        for rel, h in self.man['files'].items():
            self.assertEqual(sha(self.out / rel), h, rel)

    def test_queue_hashes_point_at_v2_worker(self):
        for q in (self.out / 'queues').glob('*.json'):
            for j in json.loads(q.read_text()).get('jobs', []):
                for n, h in (j.get('phaseB_sha256') or {}).items():
                    self.assertEqual(h, sha(self.out / 'phaseB' / n))

    def test_parent_unchanged_after_build(self):
        B.verify_parent(PARENT)

    def test_refuses_existing_output(self):
        with self.assertRaises(FileExistsError):
            B.build(self.out, PARENT)

    def test_refuses_frozen_and_parent_paths(self):
        for bad in [B.REPO / 'integration' / 'kit-v2-x', B.REPO / 'experimental/window-routing' / 'x', PARENT / 'x']:
            with self.assertRaises(ValueError):
                B.build(bad, PARENT)

    def test_refuses_changed_parent(self):
        bad = self.tmp / 'parent-changed'
        shutil.copytree(PARENT, bad)
        f = bad / 'README_KIT.md'; f.write_text(f.read_text() + 'x')
        with self.assertRaises(ValueError):
            B.build(self.tmp / 'never', bad)


# The declared Step 2 wrapper around the parent's checker call in whole_road (STEP2_ACCEPTANCE (a)), statement by statement.
# Step 2: every added worker line carrying the Step 2 marker (besides the 4-line closure), exactly and in order.
STEP2_WORKER_LINES = [
    "    import v2_memory; v2_memory.REQUIRE_CHILD_FOR_CHECK = job.get('v2_check_isolation', True) is not False   # kit-v2 Step 2: no whole-road check in this process (amendment F: unless the labelled comparison arm)",
    "    if job.get('v2_check_isolation', True) is False:   # kit-v2 Step 2 amendment F: baseline comparison arm, set only by the panel harness",
    "        STATE['comparison_arm'] = 'no_check_isolation'   # kit-v2 Step 2",
    '            import v2_memory, hybrid_checker as _v2_hc   # kit-v2 Step 2',
    "            if job.get('v2_check_isolation', True) is False:   # kit-v2 Step 2 amendment F: comparison arm, in-process as the parent",
    '                rec, _v2_child = _v2_check(), None   # kit-v2 Step 2',
    "                _v2_budget = {'gate_mb': _v2_hc.RSS_LIMIT_MB, 'within_budget': 'not_proven', 'mechanism': None, 'comparison_arm': 'no_check_isolation'}   # kit-v2 Step 2",
    '            else:   # kit-v2 Step 2',
    '                rec, _v2_child, _v2_budget = v2_memory.run_check_forked(_v2_check, _v2_hc.RSS_LIMIT_MB, deadline)  # kit-v2 Step 2',
    '            if rec is None:   # kit-v2 Step 2: interrupted check (MemoryError, crash, kill) stays UNRESOLVED',
    "                rec = {'status': 'UNRESOLVED', 'reason': 'CHECK_CHILD_FAILED', 'check_child': _v2_child}   # kit-v2 Step 2",
    "            STATE.setdefault('check_budgets', []).append({k: _v2_budget.get(k) for k in ('peak_mb', 'sampled_private_peak_mb', 'mechanism')})   # kit-v2 Step 2 amendment F: every check's memory for M2-model; no verdict field (Thomas 18:12 point 1)",
    "            rec['resource_budget'] = _v2_budget; rec['check_child'] = _v2_child   # kit-v2 Step 2",
    "        STATE['bound_model_dist'] = {'dist_sha256': M.dist_sha256, 'dist_block_rows': M.dist_block_rows}   # kit-v2 Step 2",
]

STEP2_WRAPPER = ['import v2_memory, hybrid_checker as _v2_hc',
                 "if job.get('v2_check_isolation', True) is False:\n    rec, _v2_child = (_v2_check(), None)\n    _v2_budget = {'gate_mb': _v2_hc.RSS_LIMIT_MB, 'within_budget': 'not_proven', 'mechanism': None, 'comparison_arm': 'no_check_isolation'}\nelse:\n    rec, _v2_child, _v2_budget = v2_memory.run_check_forked(_v2_check, _v2_hc.RSS_LIMIT_MB, deadline)",
                 "if rec is None:\n    rec = {'status': 'UNRESOLVED', 'reason': 'CHECK_CHILD_FAILED', 'check_child': _v2_child}",
                 "STATE.setdefault('check_budgets', []).append({k: _v2_budget.get(k) for k in ('peak_mb', 'sampled_private_peak_mb', 'mechanism')})",
                 "rec['resource_budget'] = _v2_budget",
                 "rec['check_child'] = _v2_child"]

# Step 3: every added worker line carrying the Step 3 marker, exactly and in order (STEP3_ACCEPTANCE B).
# Identity record (IDENTITY_RECORD_ACCEPTANCE): every worker line carrying its marker, exactly and in order.
IDENTITY_RECORD_WORKER_LINES = [
    "    STATE['checker_identity'] = {}   # kit-v2 identity record: the three checker modules as imported (path, sha256)",
    "    for _ir in ('contact_first', 'mission_contract', 'hybrid_checker'):   # kit-v2 identity record",
    '        _irm = sys.modules.get(_ir)   # kit-v2 identity record',
    "        STATE['checker_identity'][_ir] = {'imported': True, 'path': _irm.__file__, 'sha256': sha(pathlib.Path(_irm.__file__))} if _irm is not None and getattr(_irm, '__file__', None) else {'imported': False}   # kit-v2 identity record",
]

STEP3_WORKER_LINES = [
    "V2_STEP3 = {'Z_setup_units': 4096, 'Z_sweep_units': 268435456,   # kit-v2 Step 3: 2**12 / 2**28, results/step3/Z_CALIBRATION_V2.json (both extrapolated)",
    "            'watchdog': 'max(1.5 x cap, cap + 10 s); after it fires no later stage uses the bound model or EA'}   # kit-v2 Step 3",
    "    import v2_work; _V2W = {'poisoned': False}   # kit-v2 Step 3",
    '    def _v2_run(name, cap_s, fn, bound_budget=True):   # kit-v2 Step 3: prompt cap checks + watchdog for one stage',
    "        if bound_budget and M is not None:   # kit-v2 Step 3: the bound model ticks this stage's wall deadline per chunk",
    '        try:   # kit-v2 Step 3',
    '            with v2_work.watchdog(name, v2_work.watchdog_threshold(cap_s)):   # kit-v2 Step 3',
    '                return fn()   # kit-v2 Step 3',
    '        except v2_work.WatchdogFired as exc:   # kit-v2 Step 3: killed, reported, never continued; fail closed after',
    "            _V2W['poisoned'] = True; _V2W['stage'] = name; _V2W['threshold_s'] = exc.threshold_s   # kit-v2 Step 3",
    "            STATE['stage_cap_watchdog'] = dict(_V2W)   # kit-v2 Step 3",
    "            return {'status': 'TIMEOUT', 'reason': 'STAGE_CAP_WATCHDOG', 'legs': [], 'arrival': None, 'destination': None,   # kit-v2 Step 3",
    "                    'per_member': {}, 'solver_status': 'INCOMPLETE_CAP', 'metrics': {'watchdog_threshold_s': exc.threshold_s}}   # kit-v2 Step 3",
    '        finally:   # kit-v2 Step 3',
    '            if M is not None:   # kit-v2 Step 3',
    '                M.stage_budget = None   # kit-v2 Step 3',
    "                _zw = {'setup': V2_STEP3['Z_setup_units'], 'sweep': V2_STEP3['Z_sweep_units']}; _zwall = cap if None in _zw.values() else max(0., remaining() - ALLOCATION['Z_reserve_s'])   # kit-v2 Step 3",
    '                _zb = v2_work.Budget(group_caps={k: v for k, v in _zw.items() if v is not None}, deadline=time.perf_counter() + _zwall)   # kit-v2 Step 3',
    "                z = _v2_run('Z', ALLOCATION['Z_max_s'], lambda: zsweep.contact_sweep(graph, hazard, request, M, wall_s=_zwall, core=core,   # kit-v2 Step 3",
    "                                         check_route_mode=road_core.check_route_mode, zero_view=M.view('zero'), budget=_zb), bound_budget=False)   # kit-v2 Step 3",
    "            record('Z', 'zero', cap, t0, z, {'z_work': _zb.record(), 'z_work_caps': dict(_zw)})   # kit-v2 Step 3",
    "            done = done or _V2W['poisoned']   # kit-v2 Step 3: fail closed after a watchdog",
    "                EA = _v2_run('EA', max(0., deadline - ALLOCATION['HI_check_reserve_s'] - time.perf_counter()), lambda: zsweep.EarliestArrivalBound(graph, hazard, request, M, core, deadline=deadline - ALLOCATION['HI_check_reserve_s']), bound_budget=False)   # kit-v2 Step 3",
    '                if isinstance(EA, dict):   # kit-v2 Step 3: watchdog fired',
    "                    raise TimeoutError('STAGE_CAP_WATCHDOG')   # kit-v2 Step 3",
    "            done = done or _V2W['poisoned']   # kit-v2 Step 3: fail closed after a watchdog",
    "                lo_res = _v2_run('LO', cap, lambda: road_core.solve(graph, hazard, rq, prepared=pg, exposure=M.view('lo'), mode='lo', arrival_bound=EA))   # kit-v2 Step 3",
    "                done = consider('LO', 'lo', lo_res, 'road_lower_bound_lattice_relaxation') or _V2W['poisoned']   # kit-v2 Step 3",
    "                    lo2 = _v2_run('LO2', cap, lambda: road_core.solve(graph, hazard, rq, prepared=pg, exposure=M.view('lo'), mode='lo', arrival_bound=EA))   # kit-v2 Step 3",
    "                    done = consider('LO2', 'lo', lo2, 'road_lower_bound_lattice_relaxation') or _V2W['poisoned']   # kit-v2 Step 3",
    "                hi = _v2_run('HI', cap, lambda: road_core.solve(graph, hazard, rq, prepared=pg, exposure=M.view('hi'), mode='hi', arrival_bound=EA))   # kit-v2 Step 3",
]


class Sealed(unittest.TestCase):
    def test_overlay_sealed(self):
        B.check_sealed()

    def test_worker_overlay_is_parent_plus_declared_hunks_only(self):
        # Step 0: exactly the 3 identity lines. Step 1 (STEP1_ACCEPTANCE): plus the progress-hook lines, each of which
        # must carry a declared marker. No parent line may be removed except the one global statement Step 1 extends.
        parent = (B.REPO / 'experimental/window-routing/stack/phaseB/rda_worker_v1_1.py').read_text().splitlines()
        v2 = (B.HERE / 'stack-v2/phaseB/rda_worker_v1_1.py').read_text().splitlines()
        removed = [l for l in parent if l not in v2]
        # Step 2 (STEP2_ACCEPTANCE (a)): the in-process check call (3 lines) is replaced by the forked, measured call.
        step2_removed = ["            rec = checker['obj'].check(graph, original, res['legs'], res['destination'], deadline=deadline,",
                         "                                       wall_s=max(0., deadline - time.perf_counter()),",
                         "                                       expected_graph_revision=graph['revision'], expected_graph_sha256=gdig)"]
        # Step 3 (STEP3_ACCEPTANCE B): exactly the five stage calls are re-written to run under _v2_run (prompt cap
        # checks + watchdog). Each replacement line must contain the parent's call expression verbatim (Z: its two
        # lines joined, plus the declared budget keyword and the Step 3 wall/deadline variable in place of the cap).
        step3_removed = [l for l in removed if l.strip().startswith(('z = zsweep.contact_sweep', 'check_route_mode=road_core',
                         'EA = zsweep.EarliestArrivalBound', 'lo_res = road_core.solve', 'lo2 = road_core.solve', 'hi = road_core.solve'))]
        self.assertEqual(len(step3_removed), 6, step3_removed)
        # plus three lines EXTENDED in place: the Z record gains the work record; LO/LO2 'done' gain the fail-closed or
        extended = [l for l in removed if l.strip() in ("record('Z', 'zero', cap, t0, z)",
                    "done = consider('LO', 'lo', lo_res, 'road_lower_bound_lattice_relaxation')",
                    "done = consider('LO2', 'lo', lo2, 'road_lower_bound_lattice_relaxation')")]
        self.assertEqual(len(extended), 3, extended)
        for l in extended:
            head = l.rstrip()[:-1] if l.strip().startswith('record(') else l.rstrip()
            self.assertTrue(any(a.startswith(head) and 'kit-v2 Step 3' in a for a in v2), l)
        # Step 2 + Step 3 (rebased Step 3 on Step 2): nothing else is removed, in parent order
        self.assertEqual([l for l in removed if l not in step3_removed + extended], ['    global STATE, FOLDER, WRITE, ROOT'] + step2_removed)
        for l in step3_removed:
            call = l.strip().split(' = ', 1)[1] if ' = ' in l.strip().split('(')[0] else l.strip()
            if call.startswith('zsweep.contact_sweep'):
                call = call.replace('wall_s=cap', 'wall_s=_zwall')
            if call.startswith('check_route_mode'):
                call = call[:-1] + ', budget=_zb)'
            self.assertTrue(any(call in a and 'kit-v2 Step 3' in a for a in v2), call)
        added = [l for l in v2 if l not in parent]
        step2 = ['            def _v2_check():   # kit-v2 Step 2: runs in a forked child, own memory measured by a fresh cgroup v1 peak',
                 "                return checker['obj'].check(graph, original, res['legs'], res['destination'], deadline=deadline,",
                 '                                            wall_s=max(0., deadline - time.perf_counter()),',
                 "                                            expected_graph_revision=graph['revision'], expected_graph_sha256=gdig)"]
        marked = [l for l in added if 'kit-v2 Step 2' in l and l not in step2]
        self.assertEqual(marked, STEP2_WORKER_LINES)                   # every marked Step 2 line, exactly and in order
        step3 = [l for l in added if 'kit-v2 Step 3' in l]
        self.assertEqual(step3, STEP3_WORKER_LINES)                    # exact, in order (declared in STEP3_ACCEPTANCE B)
        self.assertFalse([l for l in step3 if 'kit-v2 Step 2' in l])   # no line claims both steps
        step2 += marked
        idrec = [l for l in added if 'kit-v2 identity record' in l]
        self.assertEqual(idrec, IDENTITY_RECORD_WORKER_LINES)          # exact, in order (IDENTITY_RECORD_ACCEPTANCE)
        self.assertFalse([l for l in idrec if 'kit-v2 Step' in l])     # no line claims two markers
        added = [l for l in added if l not in step2 + step3 + idrec]
        ident = [l for l in added if ('kit' in l.lower() or '_kid' in l) and 'Step 1' not in l and '_V2_PROG' not in l]
        self.assertEqual(len(ident), 3, ident)
        markers = ('_prog', '_PROG', 'PROGRESS', 'p[', 'p = ', 'tmp', 'f_', 'm_', 'res_', "'stage'", "'info'", 'return',
                   'try:', 'except', 'pass', 'with open', 'def ', 'global STATE')
        rest = [l for l in added if l not in ident and l.strip()]
        self.assertTrue(all(any(m in l for m in markers) for l in rest), [l for l in rest if not any(m in l for m in markers)])

    def test_step2_whole_road_is_parent_check_wrapped(self):
        """Replaces the parent's test_general_check_first_preserves_mandatory_checker_and_limits for Step 2 (declared
        in run_parent_tests.REPLACED). Same three properties, with the whole_road identity made exact modulo the
        declared wrapper: substituting `rec = <the _v2_check call>` back for the Step 2 block gives the parent's
        whole_road AST exactly, and the call itself is the parent's call (same callee, arguments, deadline, wall)."""
        import ast
        old = ast.parse((B.REPO / 'experimental/window-routing/tests/baseline_prior_worker.py').read_text())
        new = ast.parse((B.HERE / 'stack-v2/phaseB/rda_worker_v1_1.py').read_text())
        find = lambda tree, name: next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == name)
        wo, wn = find(old, 'whole_road'), find(new, '_v2_check')
        old_assign = next(x for x in ast.walk(wo) if isinstance(x, ast.Assign) and isinstance(x.value, ast.Call)
                          and isinstance(x.value.func, ast.Attribute) and x.value.func.attr == 'check')
        self.assertEqual(len(wn.body), 1); self.assertIsInstance(wn.body[0], ast.Return)
        self.assertEqual(ast.dump(wn.body[0].value), ast.dump(old_assign.value))
        whole = find(new, 'whole_road')
        for node in ast.walk(whole):
            for field in ('body', 'orelse'):
                body = getattr(node, field, None)
                if isinstance(body, list) and wn in body:
                    i = body.index(wn)
                    j = max(k for k, st in enumerate(body) if k > i and isinstance(st, ast.Assign) and any(
                        isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == 'rec'
                        for t in st.targets))
                    self.assertEqual([ast.unparse(st) for st in body[i + 1:j + 1]], STEP2_WRAPPER)   # exact wrapper
                    body[i:j + 1] = [old_assign]
        self.assertEqual(ast.dump(wo), ast.dump(whole))
        consider = find(new, 'consider')
        calls = [x.func.id for x in ast.walk(consider) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)]
        self.assertIn('whole_road', calls); self.assertNotIn('lo_prefilter', calls)
        get = lambda tree: ast.literal_eval(next(x.value for x in tree.body if isinstance(x, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'ALLOCATION' for t in x.targets)))
        oa, na = get(old), get(new)
        for k, v in oa.items():
            if k != 'version':
                self.assertEqual(v, na[k])


if __name__ == '__main__':
    unittest.main()
