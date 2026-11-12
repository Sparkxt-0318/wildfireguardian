"""Phase-timing launcher for the frozen RDA_CAND routing worker (F-3.4).

The kit controller starts this file in place of ``phaseB/rda_worker_v1_1.py``; the real worker path comes from
``WFG_PHASE_TARGET``. The worker source is not copied or edited: it runs with ``runpy.run_path`` under its own
``__file__``, so its module-hash checks still bind the frozen bytes. The launcher only

* records when the interpreter reached its first statement (launch-to-interpreter cost),
* attributes wall time spent executing *top-level* module imports (an import hook; nested imports are inclusive),
* wraps a handful of named functions with ``perf_counter`` timers (after their module has executed, before use).

Wrapping changes nothing the worker computes; each wrapper costs two ``perf_counter`` calls per invocation. On exit
it writes ``PHASE_TIMERS.json`` into the job's output folder (also after a deadline stop).
"""
import time

T_INTERPRETER = time.perf_counter()   # first statement of the launched interpreter

import functools, importlib.abc, importlib.machinery, json, os, pathlib, runpy, sys  # noqa: E402

TIMERS = {}           # name -> {'calls': n, 'total_s': s, 'first_start': t, 'last_end': t}
IMPORT = {'top_level_s': 0.0, 'modules': 0, 'depth': 0, 'by_root': {}}
WRAP = {   # module name -> attribute paths to time
    'routing.validation': ['validate_hazard', 'validate_request', 'validate_graph'],
    'routing.prepared': ['PreparedGraph.__init__', 'PreparedGraph.snapshot'],
    'clock_scope': ['check_clock_scope'],
    'road_bounds': ['RoadBoundModel.__init__', 'RoadBoundModel.view', 'RoadBoundModel.prepare_route'],
    'zsweep': ['contact_sweep', 'EarliestArrivalBound.__init__'],
    'road_core': ['solve', 'check_route_mode'],
    'publication_v1_1': ['publish'],
    'journey_decision': ['decision_from_worker_record'],
    'routing.core': ['check_route'],
    'hybrid_checker': ['HybridChecker.__init__', 'HybridChecker.check', 'check_contact', 'prepare_mission'],
    'adaptive_checker': ['adaptive_bound', 'HybridChecker.check'],
    'hybrid_radiation': ['HybridRadiationBounds.from_case_for_window', 'HybridRadiationBounds.trajectory_bound'],
    'radiation_bounds': ['RadiationBounds._pass'],
    'contact_first': ['ContactSources.from_case'],
    'exact_transport': ['atomic_create', 'preflight'],
}


def _timed(name, fn):
    rec = TIMERS.setdefault(name, {'calls': 0, 'total_s': 0.0, 'first_start': None, 'last_end': None})

    @functools.wraps(fn)
    def inner(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            t1 = time.perf_counter()
            rec['calls'] += 1; rec['total_s'] += t1 - t0
            if rec['first_start'] is None:
                rec['first_start'] = t0
            rec['last_end'] = t1
    inner.__wfg_phase_wrapped__ = True
    return inner


def _patch(module, paths):
    for path in paths:
        owner, attr = module, path
        if '.' in path:
            cls, attr = path.split('.', 1)
            owner = getattr(module, cls, None)
            if owner is None:
                continue
        fn = owner.__dict__.get(attr) if isinstance(owner, type) else getattr(owner, attr, None)
        if fn is None or getattr(fn, '__wfg_phase_wrapped__', False):
            continue
        if isinstance(fn, (staticmethod, classmethod)):
            setattr(owner, attr, type(fn)(_timed(module.__name__ + '.' + path, fn.__func__)))
        elif callable(fn):
            setattr(owner, attr, _timed(module.__name__ + '.' + path, fn))


class _Loader(importlib.abc.Loader):
    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        top = IMPORT['depth'] == 0
        IMPORT['depth'] += 1; t0 = time.perf_counter()
        try:
            self.inner.exec_module(module)
        finally:
            IMPORT['depth'] -= 1; dt = time.perf_counter() - t0
            IMPORT['modules'] += 1
            if top:
                IMPORT['top_level_s'] += dt
                root = module.__name__.split('.')[0]
                IMPORT['by_root'][root] = IMPORT['by_root'].get(root, 0.0) + dt
        if module.__name__ in WRAP:
            _patch(module, WRAP[module.__name__])

    def __getattr__(self, name):   # resource readers etc.
        return getattr(self.inner, name)


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, 'find_spec'):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None:
                if spec.loader is not None and hasattr(spec.loader, 'exec_module'):
                    spec.loader = _Loader(spec.loader)
                return spec
        return None


def _write(folder, status):
    origin = float(os.environ['WFG_OUTER_MONOTONIC_START'])
    out = {'schema': 'wfg.harness.f34.phase-timers/1', 'status': status, 'outer_origin': origin,
           'interpreter_first_statement_from_outer_s': T_INTERPRETER - origin,
           'launcher_end_from_outer_s': time.perf_counter() - origin,
           'imports': {k: v for k, v in IMPORT.items() if k != 'depth'},
           'timers': {k: dict(v, first_start_from_outer_s=None if v['first_start'] is None else v['first_start'] - origin,
                              last_end_from_outer_s=None if v['last_end'] is None else v['last_end'] - origin)
                      for k, v in TIMERS.items()},
           'python': sys.version, 'pid': os.getpid()}
    (folder / 'PHASE_TIMERS.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')


def main():
    target = pathlib.Path(os.environ['WFG_PHASE_TARGET']).resolve()
    job = json.loads(pathlib.Path(sys.argv[sys.argv.index('--job-file') + 1]).read_text())
    root = pathlib.Path(job.get('root') or '.')
    folder = pathlib.Path(job['output_path']);
    folder = folder if folder.is_absolute() else root / folder
    sys.meta_path.insert(0, _Finder())
    sys.argv = [str(target)] + sys.argv[1:]
    sys.path[0] = str(target.parent)
    status = 'EXITED'
    try:
        runpy.run_path(str(target), run_name='__main__')
    except SystemExit as exc:
        status = 'SYSTEM_EXIT_%s' % exc.code
        _write(folder, status)
        raise
    _write(folder, status)


if __name__ == '__main__':
    main()
