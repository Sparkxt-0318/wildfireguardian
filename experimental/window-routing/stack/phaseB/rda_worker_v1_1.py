"""RDA candidate worker v1.1 (Phase B, road-dose alignment campaign).

v1.1 = rda_worker.py (frozen v1, sha256 ba25714c...) with ONLY the publication contract changed (fix F-PC1, see
publication_v1_1.py): a published route carries CENTRE-model per_member (unchanged centre evaluation) with the search
mode's exposure under mode_exposure and the real checker's bounds under whole_road_bounds; an uncertified witness is never
placed in `result` (it goes to `rejected_witnesses`, prefilter outcomes labelled as prefilter); the lower-bound
prefilter memo is kept apart from real checks. This isolated candidate adds an exact request-window radiation
view and a general check-first Z schedule; the full checker, resource limits and publication rules are retained.

Derived from bundle_v1_1/runner/cand_worker_final.py (sha256 f337e58c...): same job file, same STAGE_* / RESULT /
PUBLICATION_BOUNDARY records, same outer controller (fresh process, complete budget from launch to exit, SIGTERM at
the deadline), same input/source hash binding, PreparedGraph admission, clock scope and mandatory fresh whole-road
check (the unchanged base HybridChecker unless an explicit job override is admitted). Every stage below is charged to the ONE outer
deadline (origin = WFG_OUTER_MONOTONIC_START, deadline = origin + complete_budget_s).

Stages (original wall allocations, with the declared request-window/check-first scheduling change):
  B  : exposure bound model (exact activity, radiation sources active during the request window) - charged, no cap of its own.
  Z  : contact-only lattice relaxation, own vectorised sweep (zsweep.py); cap min(remaining - 3 s, 6 s).
       complete & no arrival -> refusal certificate (contact_only_lattice_relaxation); witness W0 at L0 -> whole-road
       check first (all remaining time up to the deadline; no eager optional lower-bound prefilter)
       -> CERTIFIED -> optimality certificate lower_bound_arrival = L0.
  LO : road_core mode 'lo' (outward lower road bounds; a relaxation); cap 55 % of the time remaining after Z and its
       check. complete & infeasible -> refusal certificate (road_lower_bound_lattice_relaxation); route R_lo at A_lo
       -> check -> CERTIFIED -> optimality certificate lower_bound_arrival = A_lo (if LO complete).
  LO2: optional single selective refinement: only if R_lo was returned and not certified and >= 10 s remain:
       the witness edges carrying the largest (hi - lo) dose gap (until 80 % of the gap, <= 200 edges) get 4x more
       sub-boxes and LO is re-run once with cap 35 % of the remaining time; its route is checked like R_lo.
  HI : road_core mode 'hi' (outward upper road bounds; conservative); cap remaining - 4 s (reserve for its check)
       -> route R_hi -> check (mandatory: router contact can miss corner touches) -> CERTIFIED ->
       CHECKED_JOURNEY_FEASIBLE, or FULL_OPTIMUM_PROVEN when its arrival equals the best completed lower bound.
Publication: the first (= earliest, since Z/LO arrivals lower-bound later stages) whole-road-CERTIFIED route; a
rejected, unresolved, interrupted or late check is never success; TIMEOUT is never a refusal; a rejected witness
bans nothing (no no-good cuts; refinement only tightens bounds). The Phase A decision object is emitted as
RESULT['decision'] through journey_decision.decision_from_worker_record (same gate as the baseline worker).
"""
import time
START = time.perf_counter()
import argparse, copy, datetime, hashlib, json, os, pathlib, resource, signal, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
HERE = pathlib.Path(__file__).resolve().parent
DECISION_DIR = HERE.parent / 'decision'
STATE = {}; FOLDER = None; WRITE = None

ALLOCATION = {'version': 'wfg.rda.allocation/2-window-check-first',
              'Z_optional_prefilter': 'SKIPPED_FOR_ALL_Z_WITNESSES',
              'Z_cap_s': 'min(remaining - 3, 6)', 'Z_reserve_s': 3.0, 'Z_max_s': 6.0,
              'LO_fraction_of_remaining': 0.55,
              'LO2_min_remaining_s': 10.0, 'LO2_fraction_of_remaining': 0.35,
              'HI_check_reserve_s': 4.0, 'min_search_cap_s': 0.5,
              'checks': 'each whole-road check gets all remaining time up to the deadline'}


class DeadlineStop(Exception):
    pass


def stop(signum, frame):
    raise DeadlineStop('Parent complete deadline')


signal.signal(signal.SIGTERM, stop)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def canonical(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def resolve(p):
    p = pathlib.Path(p)
    return p if p.is_absolute() else ROOT / p


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def route_key(res):
    return canonical({'legs': res.get('legs', []), 'destination': res.get('destination'), 'arrival': res.get('arrival')})


def jsonable(x):
    """JSON-safe copy (Fractions are kept: exact_transport.preflight encodes them losslessly)."""
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, float) and not (x == x and abs(x) != float('inf')):
        return None
    if type(x).__module__ == 'numpy':
        return x.item() if hasattr(x, 'item') else x
    return x


def main():
    global STATE, FOLDER, WRITE, ROOT
    p = argparse.ArgumentParser(); p.add_argument('--job-file', required=True); a = p.parse_args()
    job = json.loads(pathlib.Path(a.job_file).read_text())
    if job.get('root'):
        ROOT = pathlib.Path(job['root']).resolve()
    FOLDER = resolve(job['output_path']); assert FOLDER.is_dir()
    src = resolve(job['source_root']); arm = job['arm']
    if arm not in ('RDA_CAND',):
        raise ValueError('ARM_NOT_SUPPORTED:' + arm)
    origin = float(os.environ['WFG_OUTER_MONOTONIC_START']); deadline = origin + float(job['complete_budget_s'])
    remaining = lambda: deadline - time.perf_counter()
    sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(HERE),
                    str(pathlib.Path(job.get('decision_dir', DECISION_DIR)))]
    from exact_transport import preflight, atomic_create
    WRITE = lambda name, obj: atomic_create(FOLDER / (name + '.json'), preflight(jsonable(obj)))
    STATE = {'schema': 'wfg.audit.cand-worker/1', 'worker_kind': 'wfg.rda.road-dose-worker/1.1+prep-integration-20261014', 'job_id': job['label'],
             'case_id': job['case_id'], 'cohort': job['cohort'], 'arm': arm, 'repetition': job['rep'],
             'source_root': str(src), 'source_directory': str(resolve(job['source_directory'])),
             'complete_budget_s': job['complete_budget_s'], 'started_utc': utc(), 'worker_import_start_monotonic': START,
             'outer_start_monotonic': origin, 'deadline_monotonic': deadline, 'result': None,
             'whole_road_check': {'status': 'NOT_RUN', 'reason': 'NO_SOLVER_WITNESS'}, 'stages': {}, 'identities': {},
             'physical_safety_claim': False, 'original_limits': job['original_limits'], 'allocation': ALLOCATION,
             'rda_stages': [], 'optimality_certificate': None, 'refusal_certificate': None}

    def checkpoint(phase):
        WRITE('STAGE_' + phase, {'phase': phase, 'utc': utc(), 'monotonic': time.perf_counter(),
                                 'elapsed_from_outer_s': time.perf_counter() - origin})
    checkpoint('IMPORTED'); t = time.perf_counter()
    paths = {k: resolve(job[k]) for k in ('graph_path', 'hazard_path', 'request_path')}
    objects = {k: json.loads(v.read_text()) for k, v in paths.items()}
    for k, v in paths.items():
        actual = sha(v)
        if actual != job['input_sha256'][k]:
            raise ValueError('INPUT_HASH_MISMATCH:' + k)
        STATE['identities'][k] = {'path': str(v), 'sha256': actual, 'canonical_sha256': canonical(objects[k])}
    packet = resolve(job['source_directory'])
    for n, expected in job['source_sha256'].items():
        actual = sha(packet / n)
        if actual != expected:
            raise ValueError('SOURCE_HASH_MISMATCH:' + n)
        STATE['identities']['source:' + n] = {'path': str(packet / n), 'sha256': actual}
    graph, hazard, original = (objects[k] for k in ('graph_path', 'hazard_path', 'request_path'))
    WRITE('ORIGINAL_REQUEST', original); STATE['stages']['load_hash_binding_s'] = time.perf_counter() - t
    checkpoint('INPUTS_BOUND')
    from routing import core, validation
    actual_core = pathlib.Path(core.__file__).resolve(); expected_core = (src / 'baseline/routing-package/routing/core.py').resolve()
    if actual_core != expected_core:
        raise ValueError('ACTUAL_IMPORTED_CORE_PATH_MISMATCH')
    actual_core_sha256 = sha(actual_core)
    if job.get('core_sha256', actual_core_sha256) != actual_core_sha256:
        raise ValueError('ACTUAL_IMPORTED_CORE_HASH_MISMATCH')
    import road_core, road_bounds, zsweep, publication_v1_1
    phaseb = {m.__name__ + '.py': sha(m.__file__) for m in (road_core, road_bounds, zsweep, publication_v1_1)}
    phaseb['rda_worker_v1_1.py'] = sha(__file__)
    for n, h in (job.get('phaseB_sha256') or {}).items():
        if phaseb.get(n) != h:
            raise ValueError('PHASEB_MODULE_HASH_MISMATCH:' + n)
    from clock_scope import check_clock_scope
    t = time.perf_counter(); import importlib.util as _iu; _ps = _iu.spec_from_file_location('preparation_mode', pathlib.Path(__file__).resolve().parent / 'preparation_mode.py'); _pm = _iu.module_from_spec(_ps); _ps.loader.exec_module(_pm); pg = _pm.prepare_graph(graph, job, STATE); vg = pg.snapshot()
    vh = validation.validate_hazard(vg, hazard, original.get('as_of'), _graph_validated=True)
    vr = validation.validate_request(vg, vh, original, _validated_inputs=True); scope = check_clock_scope(vh, vr)
    STATE['clock_scope'] = scope; STATE['stages']['normal_admission_clock_s'] = time.perf_counter() - t; checkpoint('ADMITTED')
    request = copy.deepcopy(original); request['solver'] = 'astar_opening'
    STATE['engine_binding'] = {'core_path': str(expected_core), 'core_sha256': actual_core_sha256,
                               'actual_imported_core_path': str(actual_core), 'actual_imported_core_sha256': actual_core_sha256,
                               'phaseB_modules': phaseb, 'solver': request['solver'], 'actual_invocations': 0,
                               'original_request_sha256': STATE['identities']['request_path']['sha256'],
                               'selected_core_unchanged': True,
                               'note': 'core.py is the unchanged validator/geometry provider; searches run road_core (copy with the exposure injection) and zsweep'}
    WRITE('ACTUAL_SEARCH_REQUEST', request); WRITE('ENGINE_BINDING', STATE['engine_binding'])

    # ---------------------------------------------------------------- whole-road checker (one instance per process)
    from hybrid_checker import HybridChecker
    if job.get('checker_module'):
        import importlib; _m = importlib.import_module(job['checker_module']); HybridChecker = _m.HybridChecker
        _files = {n: sha(pathlib.Path(_m.__file__).parent / n) for n in job.get('checker_sha256', {})}
        if _files != job.get('checker_sha256', {}) or not _files:
            raise ValueError('CHECKER_MODULE_HASH_MISMATCH')
        STATE['checker_module'] = {'module': job['checker_module'], 'path': _m.__file__, 'sha256': _files}
    from mission_contract import graph_digest
    gdig = graph_digest(graph)
    checker = {'obj': None}
    checks = {}   # route key -> REAL whole-road check record (a deterministic function of the route; reused)
    prefiltered = {}   # route key -> lower-bound prefilter rejection (kept apart from real checks, v1.1)
    time_capped = []   # stages skipped or cut by a time cap (v1.1: decides TIMEOUT vs UNRESOLVED when nothing certifies)

    def whole_road(res, label):
        key = route_key(res)
        if key in checks:
            return checks[key], True
        if remaining() <= 0:
            rec = {'status': 'UNRESOLVED', 'reason': 'NO_REMAINING_COMPLETE_BUDGET'}
        else:
            STATE['whole_road_check'] = {'status': 'UNRESOLVED', 'reason': 'CHECK_STARTED_NOT_COMPLETED'}
            t0 = time.perf_counter()
            if checker['obj'] is None:
                checker['obj'] = HybridChecker(packet)
            rec = checker['obj'].check(graph, original, res['legs'], res['destination'], deadline=deadline,
                                       wall_s=max(0., deadline - time.perf_counter()),
                                       expected_graph_revision=graph['revision'], expected_graph_sha256=gdig)
            STATE['stages']['whole_road_check_' + label + '_s'] = time.perf_counter() - t0
        checks[key] = rec
        return rec, False

    # ---------------------------------------------------------------- stage records
    def record(stage, mode, cap, t0, res, extra=None):
        m = res.get('metrics') or {}
        r = {'stage': stage, 'mode': mode, 'wall_cap_s': cap, 'elapsed_s': time.perf_counter() - t0,
             'status': res.get('status'), 'reason': res.get('reason'), 'mode_raw_status': res.get('mode_raw_status'),
             'arrival': res.get('arrival'), 'n_legs': len(res.get('legs') or []),
             'labels': m.get('labels'), 'expansions': m.get('expansions'), 'occupancy_evaluations': m.get('occupancy_evaluations'),
             'z_method': res.get('z_method'), 'sweep_metrics': m if stage == 'Z' else None,
             'exposure_stats': res.get('exposure_stats'), 'extinction_gap_hits': res.get('extinction_gap_hits'),
             'rss_mb_after': rss_mb(), 'remaining_after_s': remaining()}
        if extra:
            r.update(extra)
        STATE['rda_stages'].append(r)
        return r

    candidates = []          # (stage, mode, result, check, role) in stage order
    lower_bounds = []        # completed relaxation lower bounds: (arrival, kind)
    refusal = None
    published = None         # index into candidates

    def lo_prefilter(route):
        """Sound rejection without the checker (deviation D9): the outward LOWER road-bound total of the route
        (incurred + issue + legs + dwell) exceeding a member budget, or its lower peak exceeding the peak budget, proves
        the route inadmissible in the whole-road model. It never certifies anything."""
        from fractions import Fraction
        v = M.view('lo'); ids = list(original['incurred'])
        tot = [Fraction(original['incurred'][i]) for i in ids]; pk = [0.0] * len(ids)
        def add(vals):
            for s_, (d_, p_) in enumerate(vals):
                tot[s_] += d_; pk[s_] = max(pk[s_], p_)
        t0 = time.perf_counter()
        M.prepare_route([L['edge'] for L in route['legs'] if L['kind'] == 'EDGE'])
        add(v.node(original['position']['node'], original['departure'], original['departure']))
        for L in route['legs']:
            add(v.edge(L['edge'], L['start'], L['end']) if L['kind'] == 'EDGE' else v.node(L['node'], L['start'], L['end']))
        d = [x for x in original['destinations'] if x['node'] == route['destination']]
        if len(d) == 1:
            add(v.node(route['destination'], route['arrival'], route['arrival'] + d[0]['dwell']))
        over = [i for s_, i in enumerate(ids) if tot[s_] > Fraction(original['budgets']['dose'][i])]
        peak_over = any(p_ > original['budgets']['peak'] for p_ in pk)
        info = {'lower_totals_kj_m2': {i: float(tot[s_]) for s_, i in enumerate(ids)}, 'lower_peaks_kw_m2': dict(zip(ids, pk)),
                'members_over_budget': over, 'peak_over_budget': peak_over, 'elapsed_s': time.perf_counter() - t0}
        STATE['stages']['lo_prefilter_s'] = info['elapsed_s']; STATE['rda_stages'][-1]['lo_prefilter'] = info
        if over or peak_over:
            return {'status': 'DEFINITE_REJECT', 'reason': 'RDA_LOWER_ROAD_BOUND_EXCEEDS_BUDGET', 'prefilter': info,
                    'checker': 'rda_road_bounds lower-bound prefilter (not the integration whole-road checker)',
                    'is_integration_whole_road_check': False, 'fixed_path_only': True,
                    'global_optimality_or_infeasibility_claim': False, 'physical_validation': False}
        return None

    def consider(stage, mode, res, kind):
        nonlocal refusal, published
        route = res if res.get('destination') is not None else res.get('checked_incumbent')
        complete_relax = kind is not None and res.get('status') == 'CONDITIONAL_OPTIMUM'
        if kind is not None and res.get('status') == 'PROVEN_INFEASIBLE':
            refusal = {'relaxation_kind': kind, 'complete': True, 'stage': stage,
                       'scope': ('no arrival exists on the declared 1 s lattice (router grammar: turns, waits, horizon, '
                                 'destination openings, dwell) that is admissible in the full whole-road model (exact '
                                 'closed-footprint contact, outward road dose and peak, incurred history, all budgets) for '
                                 'the supplied members and the declared policies; proven by a complete exact search of a '
                                 'relaxation of that model (%s)' % kind),
                       'provenance': 'rda_worker stage %s' % stage, 'mathematics': 'MATH_PROOF.md obligation 7'}
            candidates.append((stage, mode, res, None, None, None))
            return True
        if res.get('status') == 'TIMEOUT':
            time_capped.append(stage + ':search')
        if route is None:
            candidates.append((stage, mode, res, None, None, None)); return False
        if complete_relax:
            lower_bounds.append((res['arrival'], kind))
        rk = route_key(route)
        pre = prefiltered.get(rk)
        if pre is None and rk not in checks and stage == 'Z':
            # General check-first schedule for every Z witness. The optional
            # eager rejection filter may cost more than the mandatory checker;
            # it is never required to justify publication or a refusal.
            STATE['rda_stages'][-1]['optional_prefilter_policy'] = 'SKIPPED_GENERAL_CHECK_FIRST_POLICY'
        if pre is not None:
            rec, reused, kind_ = pre, rk in prefiltered, publication_v1_1.KIND_PREFILTER
            prefiltered[rk] = pre
        else:
            rec, reused = whole_road(route, stage); kind_ = publication_v1_1.KIND_CHECKER
            if str(rec.get('reason') or '').startswith(publication_v1_1.TIME_REASONS):
                time_capped.append(stage + ':check')
        role = 'PRIMARY' if res.get('destination') is not None else 'CHECKED_TIMEOUT_INCUMBENT'
        candidates.append((stage, mode, res, rec, role, kind_))
        STATE['rda_stages'][-1].update(check_status=rec.get('status'), check_reason=rec.get('reason'), check_kind=kind_,
                                       check_reused=reused, check_elapsed_s=rec.get('elapsed_s'), route_sha256=rk)
        if kind_ == publication_v1_1.KIND_CHECKER and rec.get('status') == 'CERTIFIED_ADMISSIBLE' and remaining() > 0:
            published = len(candidates) - 1
            return True
        return False

    M = None; done = False
    if not scope['supported']:
        result = {'status': 'UNKNOWN', 'reason': 'EXACT_CLOCK_SCOPE_UNSUPPORTED', 'solver_status': 'UNSUPPORTED_CLOCK_SCOPE',
                  'legs': [], 'destination': None, 'arrival': None, 'metrics': {}}
        candidates.append(('ADMISSION', 'none', result, None, None, None)); done = True
    if not done:
        t = time.perf_counter()
        M = road_bounds.RoadBoundModel(graph, packet, graph_sha=STATE['identities']['graph_path']['canonical_sha256'],
                                      active_window=(original['departure'], original['horizon']))
        STATE['stages']['bound_model_construction_s'] = time.perf_counter() - t
        STATE['bound_model'] = M.key(); checkpoint('BOUND_MODEL')
        # ------------------------------------------------------------ Z
        cap = min(remaining() - ALLOCATION['Z_reserve_s'], ALLOCATION['Z_max_s'])
        if cap <= 0:
            time_capped.append('Z:skipped')
        if cap > 0:
            t0 = time.perf_counter()
            try:
                z = zsweep.contact_sweep(graph, hazard, request, M, wall_s=cap, core=core,
                                         check_route_mode=road_core.check_route_mode, zero_view=M.view('zero'))
            except zsweep.SweepUnsupported as exc:
                rq = copy.deepcopy(request); rq['limits']['wall_s'] = max(0., cap - (time.perf_counter() - t0))
                z = road_core.solve(graph, hazard, rq, prepared=pg, exposure=M.view('zero'), mode='zero')
                z['z_method'] = 'road_core_zero_mode'; z['z_fallback_reason'] = str(exc)
            STATE['engine_binding']['actual_invocations'] += 1
            record('Z', 'zero', cap, t0, z)
            checkpoint('Z_RETURNED')
            if z.get('status') in ('AT_ISSUE_FAILURE', 'DISCONNECTED', 'INVALID_INPUT'):
                candidates.append(('Z', 'zero', z, None, None, None)); done = True
            else:
                done = consider('Z', 'zero', z, 'contact_only_lattice_relaxation')
        # ------------------------------------------------------------ EA (admissible A* tightening for LO / LO2 / HI)
        EA = None
        if not done and remaining() > ALLOCATION['HI_check_reserve_s']:
            t0 = time.perf_counter()
            try:
                EA = zsweep.EarliestArrivalBound(graph, hazard, request, M, core, deadline=deadline - ALLOCATION['HI_check_reserve_s'])
                start_bound = EA.bound(request['position']['node'], request['incoming_edge'], request['departure'], True)
                z_arr = next((c[2].get('arrival') for c in candidates if c[0] == 'Z'), None)
                z_status = next((c[2].get('status') for c in candidates if c[0] == 'Z'), None)
                consistent = (z_status != 'CONDITIONAL_OPTIMUM') or (start_bound == z_arr)
                STATE['earliest_arrival_bound'] = {'build_s': EA.build_s, 'bytes': EA.bytes, 'start_bound': start_bound,
                                                   'forward_sweep_arrival': z_arr, 'consistent_with_forward_sweep': consistent}
                if not consistent:
                    # two independent computations disagree: fail closed (no Z certificate, no bound use)
                    lower_bounds[:] = [lb for lb in lower_bounds if lb[1] != 'contact_only_lattice_relaxation']
                    EA = None
            except (zsweep.SweepUnsupported, TimeoutError) as exc:
                STATE['earliest_arrival_bound'] = {'error': str(exc), 'elapsed_s': time.perf_counter() - t0}
                EA = None
            STATE['stages']['earliest_arrival_bound_s'] = time.perf_counter() - t0
            checkpoint('EA_BUILT')
        # ------------------------------------------------------------ LO
        lo_res = None
        if not done and M.unsupported:
            # outward road bounds need the complete declared source law; Z (contact-only) is all that is sound here
            STATE['rda_stages'].append({'stage': 'LO/HI', 'skipped': True, 'reason': 'BOUND_MODEL_UNSUPPORTED:' + ';'.join(M.unsupported)})
            done = True
        if not done:
            cap = ALLOCATION['LO_fraction_of_remaining'] * remaining()
            if cap < ALLOCATION['min_search_cap_s']:
                time_capped.append('LO:skipped')
            if cap >= ALLOCATION['min_search_cap_s']:
                rq = copy.deepcopy(request); rq['limits']['wall_s'] = cap; t0 = time.perf_counter()
                lo_res = road_core.solve(graph, hazard, rq, prepared=pg, exposure=M.view('lo'), mode='lo', arrival_bound=EA)
                STATE['engine_binding']['actual_invocations'] += 1
                record('LO', 'lo', cap, t0, lo_res); checkpoint('LO_RETURNED')
                done = consider('LO', 'lo', lo_res, 'road_lower_bound_lattice_relaxation')
        # ------------------------------------------------------------ LO2 (one selective refinement)
        lo_route_uncertified = (lo_res is not None and lo_res.get('destination') is not None)
        if not done and lo_route_uncertified and remaining() >= ALLOCATION['LO2_min_remaining_s']:
            traversals = []
            for (_, _, r, c, _, _) in candidates:
                if c is not None and c.get('status') != 'CERTIFIED_ADMISSIBLE':
                    rt = r if r.get('destination') is not None else (r.get('checked_incumbent') or {})
                    traversals += [(L['edge'], L['start'], L['end']) for L in rt.get('legs') or [] if L['kind'] == 'EDGE']
            if traversals:
                t0 = time.perf_counter(); selected, selinfo = M.select_refinement(traversals)
                nref = M.refine_edges(selected); tref = time.perf_counter() - t0
                rejected_edges = selected
                cap = ALLOCATION['LO2_fraction_of_remaining'] * remaining()
                if cap >= ALLOCATION['min_search_cap_s']:
                    rq = copy.deepcopy(request); rq['limits']['wall_s'] = cap; t1 = time.perf_counter()
                    lo2 = road_core.solve(graph, hazard, rq, prepared=pg, exposure=M.view('lo'), mode='lo', arrival_bound=EA)
                    STATE['engine_binding']['actual_invocations'] += 1
                    record('LO2', 'lo', cap, t1, lo2, {'refined_edges': nref, 'refinement_s': tref, 'refinement_selection': selinfo})
                    checkpoint('LO2_RETURNED')
                    done = consider('LO2', 'lo', lo2, 'road_lower_bound_lattice_relaxation')
        # ------------------------------------------------------------ HI
        if not done:
            cap = remaining() - ALLOCATION['HI_check_reserve_s']
            if cap < ALLOCATION['min_search_cap_s']:
                time_capped.append('HI:skipped')
            if cap >= ALLOCATION['min_search_cap_s']:
                rq = copy.deepcopy(request); rq['limits']['wall_s'] = cap; t0 = time.perf_counter()
                hi = road_core.solve(graph, hazard, rq, prepared=pg, exposure=M.view('hi'), mode='hi', arrival_bound=EA)
                STATE['engine_binding']['actual_invocations'] += 1
                record('HI', 'hi', cap, t0, hi); checkpoint('HI_RETURNED')
                done = consider('HI', 'hi', hi, None)
    # ---------------------------------------------------------------- final selection (v1.1 publication contract)
    def centre_fn(route):
        # unchanged centre evaluation, exactly as the baseline router reports it (validated graph/hazard/request)
        return core.check_route(vg, vh, vr, route['legs'], route['destination'])
    t = time.perf_counter()
    witnesses = [{'stage': c[0], 'mode': c[1], 'search': c[2], 'check': c[3], 'check_kind': c[5]} for c in candidates]
    pub = publication_v1_1.publish(witnesses, published_index=published, refusal=refusal, lower_bounds=lower_bounds,
                                   centre_fn=centre_fn, time_capped=time_capped)
    STATE['stages']['publication_contract_s'] = time.perf_counter() - t
    result, check, opt = pub['result'], pub['whole_road_check'], pub['optimality_certificate']
    if pub['returned_witness_role']:
        STATE['returned_witness_role'] = pub['returned_witness_role']
    STATE['rejected_witnesses'] = pub['rejected_witnesses']; STATE['time_capped'] = time_capped
    STATE['publication_contract'] = 'wfg.rda.publication/1.1 (publication_v1_1.py)'
    STATE['result'] = result; STATE['whole_road_check'] = check
    STATE['optimality_certificate'] = opt; STATE['refusal_certificate'] = refusal
    STATE['lower_bounds'] = [{'arrival': a, 'kind': k} for a, k in lower_bounds]
    STATE['bound_model_cache'] = None if M is None else M.cache_info()
    WRITE('SEARCH_RESULT', {'result': result, 'engine_binding': STATE['engine_binding'], 'stages': STATE['rda_stages'],
                            'authority': 'Secondary raw primary evidence; outer complete gate determines on-time success.'})
    checkpoint('SEARCH_RETURNED')
    WRITE('WHOLE_ROAD_CHECK', STATE['whole_road_check']); checkpoint('ROAD_CHECK_RETURNED')
    t = time.perf_counter()
    for k, v in paths.items():
        if sha(v) != STATE['identities'][k]['sha256'] or canonical(objects[k]) != STATE['identities'][k]['canonical_sha256']:
            raise ValueError('FINAL_INPUT_AUTHORITY_CHANGED:' + k)
    for n, expected in job['source_sha256'].items():
        if sha(packet / n) != expected:
            raise ValueError('FINAL_SOURCE_AUTHORITY_CHANGED:' + n)
    STATE['stages']['final_input_source_binding_s'] = time.perf_counter() - t; STATE['authority_final'] = True
    STATE.update(primary_status=result['status'], primary_reason=result.get('reason'),
                 worker_elapsed_before_publication_s=time.perf_counter() - START,
                 elapsed_from_outer_before_publication_s=time.perf_counter() - origin, publication_started_utc=utc(),
                 self_lifetime_highwater_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    import journey_decision
    _pub = time.perf_counter() < deadline
    STATE['decision'] = journey_decision.decision_from_worker_record(
        jsonable(STATE), {'on_time_complete_publication': _pub, 'complete_budget_s': job['complete_budget_s']}, job,
        optimality_certificate=opt, refusal_certificate=refusal)
    STATE['decision_provenance'] = {'module': journey_decision.__file__, 'sha256': sha(journey_decision.__file__),
                                    'provisional_publication_flag': _pub,
                                    'scope': 'provisional: publication measured before the RESULT write; authoritative = '
                                             'decision_from_worker_record(RESULT, outer COMPLETE_PROCESS_RECEIPT, JOB, '
                                             'optimality_certificate=RESULT.optimality_certificate, '
                                             'refusal_certificate=RESULT.refusal_certificate)'}
    WRITE('RESULT', STATE); end = time.perf_counter()
    WRITE('PUBLICATION_BOUNDARY', {'utc': utc(), 'monotonic_after_result_publication': end,
                                   'elapsed_from_outer_after_result_publication_s': end - origin,
                                   'result_published_before_deadline': end <= deadline,
                                   'scope': 'RESULT completed; boundary receipt/normal process exit remain charged by outer process completion.'})
    print(json.dumps({'job': job['label'], 'primary_status': result['status'], 'whole_road_status': STATE['whole_road_check']['status'],
                      'decision': STATE['decision']['authoritative_status'], 'published_stage': result.get('published_stage'),
                      'worker_elapsed_s': time.perf_counter() - START}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if WRITE is None:
            raise
        STATE.update(worker_failure={'type': type(exc).__name__, 'reason': str(exc)}, publication_complete=False,
                     authority_final=False, worker_cleanup_elapsed_s=time.perf_counter() - START,
                     primary_status=(STATE.get('result') or {}).get('status', 'TIMEOUT' if isinstance(exc, DeadlineStop) else 'NOT_RUN'))
        if STATE.get('result') is None:
            STATE['result'] = {'status': 'TIMEOUT' if isinstance(exc, DeadlineStop) else 'UNKNOWN', 'reason': str(exc),
                               'solver_status': 'INCOMPLETE_CAP' if isinstance(exc, DeadlineStop) else 'UNSUPPORTED',
                               'legs': [], 'destination': None, 'arrival': None, 'metrics': {}}
        WRITE('FAILURE', STATE)
        if not (FOLDER / 'RESULT.json').exists():
            WRITE('RESULT', STATE)
        print(json.dumps({'failure': type(exc).__name__, 'reason': str(exc)})); sys.exit(2)
