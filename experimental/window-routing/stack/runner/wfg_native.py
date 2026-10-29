"""WildfireGuardian latest-forecast completion kit launcher, wfg_native/2 (latest_forecast_routing_completion_20261015_v1).

Derived from the inherited integrated-preparation launcher (sha256 36322a4a...). RUN is the extracted kit directory.
Commands:
  all        verify the immutable kit; take the local lock and the shared lease (only from a documented FREE record, or
             renew our own); set up and record the environment; copy and hash-verify the frozen latest inputs named by
             INPUT_BINDING.json; run the preflight gate (six controller lifecycle controls and one unscored real attempt);
             run the 80-attempt LATEST_PRIMARY queue serially (20 missions x 2 full-policy arms x 2 repetitions, 30 s
             complete-request deadline, 3,072 MiB guard, fast cold preparation in both arms); run offline independent
             checking and the tally; write NATIVE_SUMMARY_primary.json/.md; release the lock and, only if every attempt's
             cleanup was CLEAN, the lease. Rerunning resumes: completed attempts are never rerun, interrupted ones never
             relaunched.
  check      offline checking and tally only.     preflight   environment, inputs and preflight gate only.
  status     read-only progress report.            release     release this kit's shared lease if this holder holds it.
Changes from the inherited launcher: latest queues and inputs (INPUT_BINDING.json) replace the sealed regional freeze; the
warm option is removed; the lifecycle-repaired controller 2.1 is used; the preflight gate additionally requires CLEAN
cleanup in every control and a process table with start-time identity; the shared lease is NOT released normally when any
attempt's cleanup is not CLEAN (SURVIVORS/UNKNOWN), when a queue stopped for unclean cleanup, or when an in-flight attempt
was interrupted without a CLEAN cleanup (the record LEASE_WITHHELD.json then names the attempt).
Revision 2.1 (reviewer finding CK01 on 5bae85fc): offline checking, tally and report children run under the same verified
ownership rules as attempts (pessimistic CURRENT before spawn, own session, observed lineage, owned cleanup and a CLEAN final
census on exit or interruption; otherwise the lease release is withheld); see supervised().
Nothing here schedules anything or waits for resources: a busy lease or lock ends the command immediately."""
import argparse, datetime, fcntl, hashlib, json, os, pathlib, platform, shutil, signal, subprocess, sys, time

RUN = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / 'runner'))
import wfg_controller as C  # noqa: E402

PRIMARY = ['LATEST_PRIMARY']
WARM = []
PREFLIGHT_Q = ['LATEST_PREFLIGHT_CONTROLS', 'LATEST_PREFLIGHT_REAL']
RELEASE_OK = {'ok': True, 'reasons': []}


def withhold(reason):
    RELEASE_OK['ok'] = False; RELEASE_OK['reasons'].append(reason)
CODEX_PY = '/Users/jp/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
WHEELS = {('darwin', 'arm64'): ('outputs/wfg_integrated_release_review_20261012_v4/verified wheel cache/numpy-1.26.4-cp312-cp312-macosx_11_0_arm64.whl',
                                '03a8c78d01d9781b28a6989f6fa1bb2c4f2d51201cf99d3dd875df6fbd96b23b'),
          ('linux', 'aarch64'): ('outputs/final_forecast_routing_integration_20261011_v1/env/wheels_aarch64/numpy-1.26.4-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl',
                                 '9fad7dcb1aac3c7f0584a5a8133e3a43eeb2fe127f47e3632d43d677c66c102b')}
LOGS = RUN / 'logs'


def utc():
    return datetime.datetime.now(datetime.timezone.utc)


_MEMO = {}


def sha_memo(p):
    """Per-launch memo for input verification (the same sealed file is pinned by many jobs)."""
    p = pathlib.Path(p).resolve(); st = p.stat(); key = (str(p), st.st_size, st.st_mtime_ns)
    if key not in _MEMO:
        _MEMO[key] = sha(p)
    return _MEMO[key]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def log(event, **kw):
    LOGS.mkdir(exist_ok=True)
    C.emit(dict({'launcher': event, 'utc': utc().isoformat()}, **kw), LOGS / 'launcher.jsonl')


def write_new(path, obj):
    """Write a new JSON record; an existing file is never overwritten (a numbered sibling is used instead)."""
    path = pathlib.Path(path); p = path; n = 1
    while p.exists():
        n += 1; p = path.with_name(path.stem + '.%d' % n + path.suffix)
    with p.open('x') as f:
        json.dump(obj, f, indent=1, default=str); f.write('\n'); f.flush(); os.fsync(f.fileno())
    return p


class Stop(Exception):
    pass


def missing(item):
    """Record a precise missing prerequisite and stop (nothing timed has started)."""
    write_new(RUN / 'MISSING_PREREQUISITES.json', {'utc': utc().isoformat(), 'missing': [item]})
    raise Stop('MISSING_PREREQUISITE ' + item)


# ------------------------------------------------------------------ candidate immutability
def verify_candidate():
    man = json.loads((RUN / 'CANDIDATE_MANIFEST.json').read_text())
    bad = [k for k, h in man['files'].items() if not (RUN / k).is_file() or sha(RUN / k) != h]
    # Extra code is refused; extra queue files (for example separately declared diagnostic queues) are allowed because
    # every frozen queue is itself in the manifest and a queue cannot change code.
    extra = [p.relative_to(RUN).as_posix() for d in ('routing_candidate', 'phaseB', 'decision', 'runner')
             for p in (RUN / d).rglob('*.py') if '__pycache__' not in p.parts
             and p.relative_to(RUN).as_posix() not in man['files']]
    if bad or extra:
        raise Stop('CANDIDATE_NOT_AS_FROZEN changed=%s extra=%s' % (bad[:10], extra[:10]))
    return {'manifest_sha256': sha(RUN / 'CANDIDATE_MANIFEST.json'), 'files': len(man['files']), 'candidate_id': man.get('candidate_id')}


# ------------------------------------------------------------------ shared lease and local lock
class Lease:
    def __init__(self, workspace, holder, purpose):
        self.path = pathlib.Path(workspace) / 'outputs/SHARED_HEAVY_TIMING_LOCK.json'; self.holder = holder; self.purpose = purpose
        self.client = RUN / 'runner/lease.py'; self.acquired = False

    def read(self):
        try:
            return json.loads(self.path.read_text())
        except Exception as exc:
            return {'status': 'UNREADABLE', 'error': str(exc)}

    def _client(self, op):
        args = [sys.executable, '-I', '-B', str(self.client), str(self.path), op, self.holder] + ([self.purpose, '40'] if op != 'release' else [])
        return subprocess.run(args, capture_output=True, text=True, timeout=60)

    def _ours_valid(self, d, margin_s=60):
        try:
            return (d.get('status') == 'HELD' and d.get('holder') == self.holder
                    and datetime.datetime.fromisoformat(d['lease_until_utc']) > utc() + datetime.timedelta(seconds=margin_s))
        except Exception:
            return False

    def acquire(self):
        d = self.read()
        if d.get('status') == 'HELD' and d.get('holder') == self.holder:
            r = self._client('renew')  # our own lease, valid or expired (for example after a power loss)
        elif d.get('status') == 'FREE' and d.get('released_by'):
            r = self._client('acquire')
        else:
            raise Stop('NOT_STARTED_RESOURCE_BUSY: the shared lease is not documented FREE (%s)' % json.dumps(d))
        if r.returncode != 0 or not self._ours_valid(self.read()):
            raise Stop('LEASE_ACQUIRE_FAILED ' + (r.stdout + r.stderr)[-300:])
        self.acquired = True
        log('lease_held', lease=self.read())

    def check(self):
        d = self.read()
        if not self._ours_valid(d):
            return False, d
        if datetime.datetime.fromisoformat(d['lease_until_utc']) - utc() < datetime.timedelta(minutes=20):
            r = self._client('renew'); d = self.read()
            if r.returncode != 0 or not self._ours_valid(d):
                return False, d
        return True, d

    def release(self):
        d = self.read()
        if d.get('status') == 'HELD' and d.get('holder') == self.holder:
            self._client('release'); log('lease_released', lease=self.read())


class LocalLock:
    def __init__(self, path='/tmp/wfg/HEAVY.lock'):
        self.path = path; self.f = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, 'a')
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.f.close(); self.f = None
            raise Stop('NOT_STARTED_LOCAL_LOCK_BUSY: ' + self.path)

    def release(self):
        if self.f is not None:
            fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close(); self.f = None


# ------------------------------------------------------------------ environment
PROBE = ("import json,os,platform,sys\nd={'version':sys.version,'version_info':list(sys.version_info[:3]),'executable':sys.executable,"
         "'realpath':os.path.realpath(sys.executable),'prefix':sys.prefix,'base_prefix':sys.base_prefix,'platform':sys.platform,"
         "'machine':platform.machine(),'mac_ver':platform.mac_ver()[0]}\ntry:\n import numpy\n d['numpy']=numpy.__version__;d['numpy_file']=numpy.__file__\n"
         "except Exception as e:\n d['numpy']=None;d['numpy_error']=repr(e)\nprint(json.dumps(d))")


def probe(py):
    p = subprocess.run([str(py), '-I', '-B', '-c', PROBE], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise Stop('INTERPRETER_PROBE_FAILED %s %s' % (py, p.stderr[-300:]))
    d = json.loads(p.stdout); d['realpath_sha256'] = sha(d['realpath']); return d


def ensure_env(args):
    if args.python:
        return pathlib.Path(args.python), {'created': False, 'source': '--python'}
    py = RUN / 'env/bin/python'
    if py.exists():
        return py, {'created': False, 'source': 'existing RUN/env'}
    here = sys.executable if sys.version_info[:2] == (3, 12) else None  # the interpreter the bootstrap chose
    bases = [b for b in [args.base_python, os.environ.get('WFG_BASE_PYTHON'), here, CODEX_PY, shutil.which('python3.12')] if b]
    base = next((b for b in bases if pathlib.Path(b).exists()), None)
    if base is None:
        missing('base interpreter CPython 3.12: none of %s exists; pass --base-python or set WFG_BASE_PYTHON' % bases)
    info = probe(base)
    if info['version_info'][:2] != [3, 12]:
        missing('CPython 3.12 base interpreter (found %s at %s)' % (info['version'], base))
    key = (sys.platform, platform.machine()); rel, wsha = WHEELS.get(key, (None, None))
    wheel = pathlib.Path(args.numpy_wheel) if args.numpy_wheel else (pathlib.Path(args.workspace) / rel if rel else None)
    if wheel is None or not wheel.is_file():
        missing('numpy 1.26.4 wheel for %s: %s (or pass --numpy-wheel)' % (key, wheel))
    if not args.numpy_wheel and sha(wheel) != wsha:
        missing('numpy wheel with the pinned SHA-256 %s at %s' % (wsha, wheel))
    p = subprocess.run([base, '-m', 'venv', '--clear', str(RUN / 'env.partial')], capture_output=True, text=True)
    if p.returncode != 0:
        missing('a working venv module in %s (%s)' % (base, p.stderr[-300:]))
    p = subprocess.run([str(RUN / 'env.partial/bin/python'), '-m', 'pip', 'install', '--no-index', '--no-deps',
                        '--disable-pip-version-check', str(wheel)], capture_output=True, text=True)
    if p.returncode != 0:
        missing('offline numpy install into the new environment (%s)' % (p.stdout + p.stderr)[-300:])
    os.replace(RUN / 'env.partial', RUN / 'env')  # only a complete environment is ever used
    return py, {'created': True, 'base_python': base, 'base_identity': info, 'numpy_wheel': str(wheel), 'numpy_wheel_sha256': sha(wheel)}


def host_identity():
    def cmd(*a):
        try:
            return subprocess.run(list(a), capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception as exc:
            return 'unavailable: %r' % exc
    h = {'platform': sys.platform, 'machine': platform.machine(), 'node': platform.node(), 'release': platform.release(),
         'cpu_count': os.cpu_count()}
    if sys.platform == 'darwin':
        h.update(sw_vers=cmd('/usr/bin/sw_vers'), cpu=cmd('/usr/sbin/sysctl', '-n', 'machdep.cpu.brand_string'),
                 memsize=cmd('/usr/sbin/sysctl', '-n', 'hw.memsize'), perf_cores=cmd('/usr/sbin/sysctl', '-n', 'hw.perflevel0.physicalcpu'),
                 eff_cores=cmd('/usr/sbin/sysctl', '-n', 'hw.perflevel1.physicalcpu'), power=cmd('/usr/bin/pmset', '-g', 'batt'),
                 power_settings=cmd('/usr/bin/pmset', '-g'))
    else:
        try:
            h['cpu'] = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.lower().startswith(('model name', 'cpu part'))), None)
            h['memtotal'] = next((l.split(':', 1)[1].strip() for l in open('/proc/meminfo') if l.startswith('MemTotal')), None)
        except Exception:
            pass
    return h


def env_records(run=RUN):
    """ENVIRONMENT.json (first launch), then ENVIRONMENT.2.json, .3, ... in launch order."""
    def idx(p):
        parts = p.name.split('.')
        return 1 if len(parts) == 2 else int(parts[1])
    return [json.loads(p.read_text()) for p in sorted(run.glob('ENVIRONMENT*.json'), key=idx)]


def environment(args, py, created):
    info = probe(py); req = []
    if info['version_info'][:2] != [3, 12]:
        req.append('CPython 3.12 worker interpreter (found %s)' % info['version'])
    if info.get('numpy') != '1.26.4' and not args.allow_numpy_mismatch:
        req.append('numpy 1.26.4 in the worker interpreter (found %s)' % info.get('numpy'))
    for tool in ('/usr/bin/time', '/bin/ps'):
        if not os.path.exists(tool):
            req.append('system tool ' + tool)
    try:
        rows = C._ps_rows()
        mine = [r for r in rows if r[0] == os.getpid()]
        if not mine:
            req.append('/bin/ps -A -o pid=,ppid=,pgid=,rss=,stat=,lstart= did not list this process')
        elif not C._start(mine[0]):
            req.append('/bin/ps lstart (process start-time identity) unavailable')
    except Exception as exc:
        req.append('/bin/ps fields pid,ppid,pgid,rss,stat,lstart (%r)' % exc)
    free = shutil.disk_usage(RUN).free
    if free < args.min_free_gib * 2 ** 30:
        req.append('free disk >= %.1f GiB at %s (found %.2f GiB)' % (args.min_free_gib, RUN, free / 2 ** 30))
    env = {'schema': 'wfg.native-kit.environment/2', 'utc': utc().isoformat(), 'run_root': str(RUN), 'worker_python': str(py),
           'interpreter': info, 'env_setup': created, 'host': host_identity(), 'free_disk_bytes': free,
           'controller_platform_layer': {'time_tool': C.TIME_TOOL, 'rss_sampler': 'ps' if C.DARWIN else 'proc'},
           'launcher_python': sys.version, 'allow_numpy_mismatch': args.allow_numpy_mismatch, 'min_free_gib': args.min_free_gib,
           'missing_prerequisites': req}
    ref = next((r for r in env_records() if r.get('accepted')), None)  # a refused record never becomes the reference
    if ref is not None and (ref['interpreter']['realpath_sha256'], ref['interpreter'].get('numpy'), ref['host'].get('machine')) != \
            (info['realpath_sha256'], info.get('numpy'), env['host'].get('machine')):
        req.append('ENVIRONMENT_CHANGED_SINCE_FIRST_ACCEPTED_LAUNCH (reference recorded %s)' % ref.get('utc'))
    env['accepted'] = not req; env['missing_prerequisites'] = req
    write_new(RUN / 'ENVIRONMENT.json', env)
    if req:
        write_new(RUN / 'MISSING_PREREQUISITES.json', {'utc': utc().isoformat(), 'missing': req})
        raise Stop('MISSING_PREREQUISITES ' + '; '.join(req))
    return env


# ------------------------------------------------------------------ inputs
def copy_inputs(args, queues):
    """Copy and verify the frozen latest inputs named by RUN/INPUT_BINDING.json (study-relative sources with SHA-256)."""
    bind = json.loads((RUN / 'INPUT_BINDING.json').read_text())
    study = pathlib.Path(args.workspace) / bind['study_relative_to_workspace']
    fz = study / bind['freeze']['path']; missing_ = []
    if not fz.is_file() or sha(fz) != bind['freeze']['sha256']:
        write_new(RUN / 'MISSING_PREREQUISITES.json', {'utc': utc().isoformat(), 'missing': ['latest input freeze ' + str(fz)]})
        raise Stop('MISSING_PREREQUISITE latest input freeze %s (sha256 %s...)' % (fz, bind['freeze']['sha256'][:12]))
    rows = []
    for run_rel, meta in sorted(bind['files'].items()):
        src = study / meta['source']; dst = RUN / run_rel
        if dst.exists() and sha(dst) == meta['sha256']:
            rows.append({'run': run_rel, 'source': meta['source'], 'sha256': meta['sha256'], 'copied': False}); continue
        if not src.is_file() or sha(src) != meta['sha256'] or src.stat().st_size != meta['bytes']:
            missing_.append('frozen input with the bound hash ' + str(src)); continue
        dst.parent.mkdir(parents=True, exist_ok=True); tmp = dst.with_name(dst.name + '.partial')
        shutil.copyfile(src, tmp); os.replace(tmp, dst)
        if sha(dst) != meta['sha256']:
            missing_.append('verified copy of ' + run_rel); continue
        rows.append({'run': run_rel, 'source': meta['source'], 'sha256': meta['sha256'], 'copied': True})
    for qn in queues:
        for j in json.loads((RUN / 'queues' / (qn + '.json')).read_text())['jobs']:
            if 'control' in j:
                continue
            for k, h in j.get('input_sha256', {}).items():
                p = RUN / j[k]
                if not p.is_file() or sha_memo(p) != h:
                    missing_.append('%s %s for %s' % (k, j[k], j['label']))
            for n, h in j.get('source_sha256', {}).items():
                p = RUN / j['source_directory'] / n
                if not p.is_file() or sha_memo(p) != h:
                    missing_.append('packet source %s for %s' % (p.relative_to(RUN), j['label']))
    rec = {'schema': 'wfg.native-kit.input-copy/2', 'utc': utc().isoformat(), 'study': str(study), 'freeze': bind['freeze'],
           'files': len(rows), 'copied_now': sum(r['copied'] for r in rows), 'missing': sorted(set(missing_)), 'rows': rows}
    write_new(RUN / 'INPUT_COPY_RECEIPT.json', rec)
    if missing_:
        write_new(RUN / 'MISSING_PREREQUISITES.json', {'utc': utc().isoformat(), 'missing': sorted(set(missing_))})
        raise Stop('MISSING_PREREQUISITES %d input items, first: %s' % (len(set(missing_)), sorted(set(missing_))[0]))
    return rec


# ------------------------------------------------------------------ preflight gate
def preflight(args, py, lease):
    gate_path = RUN / 'PREFLIGHT_GATE.json'
    if gate_path.exists() and json.loads(gate_path.read_text()).get('PASS'):
        return json.loads(gate_path.read_text())
    k = 1 + len(list(RUN.glob('PREFLIGHT_GATE_try*.json')))
    folders = {qn: (qn if k == 1 else '%s_try%02d' % (qn, k)) for qn in PREFLIGHT_Q}
    (RUN / 'runtime_queues').mkdir(exist_ok=True)
    for qn in PREFLIGHT_Q:
        q = json.loads((RUN / 'queues' / (qn + '.json')).read_text())
        for j in q['jobs']:
            j['output_path'] = j['output_path'].replace('raw/%s/' % qn, 'raw/%s/' % folders[qn], 1)
        qp = RUN / 'runtime_queues' / ('%s_try%02d.json' % (qn, k))
        if not qp.exists():
            qp.write_text(json.dumps(q, indent=1) + '\n')
        s = C.run_queue(RUN, qp, py, lease.check, log=LOGS / ('controller_%s.jsonl' % qn))
        if s['stopped'] == 'CLEANUP_NOT_CLEAN':
            withhold('preflight %s attempt %s cleanup not CLEAN' % (qn, s.get('unclean_attempt')))
        if s['stopped']:
            raise Stop('PREFLIGHT_STOPPED ' + str(s['stopped']))

    def rc(qn, label):
        p = RUN / 'raw' / folders[qn] / label / 'COMPLETE_PROCESS_RECEIPT.json'
        return json.loads(p.read_text()) if p.exists() else {}
    c = {m: rc('LATEST_PREFLIGHT_CONTROLS', 'CONTROL_' + m) for m in ('normal', 'fail', 'deadline', 'stubborn', 'memory', 'desc')}
    tv = c['normal'].get('time_v') or {}
    checks = {
        'normal_on_time': c['normal'].get('on_time_complete_publication') is True and c['normal'].get('exit_code') == 0,
        'normal_time_tool_parsed': tv.get('CPU_s') is not None and tv.get('timed_command_RSS_bytes') is not None,
        'fail_reported': c['fail'].get('exit_code') == 3 and c['fail'].get('on_time_complete_publication') is False
                         and not c['fail'].get('termination_requested'),
        'deadline_terminated': c['deadline'].get('deadline_termination_requested') is True and c['deadline'].get('forced_kill') is False
                               and c['deadline'].get('on_time_complete_publication') is False,
        'deadline_wall_within_budget_plus_4s': (c['deadline'].get('external_launch_to_completion_wall_s') or 99) < 2 + 4,
        'stubborn_forced_kill': c['stubborn'].get('deadline_termination_requested') is True and c['stubborn'].get('forced_kill') is True,
        'memory_guard': c['memory'].get('memory_guard_triggered') is True and (c['memory'].get('sampled_family_peak_rss_bytes') or 0) > 200 * 2 ** 20,
        'descendants_cleaned': len(c['desc'].get('descendants_after_exit') or []) >= 2 and not c['desc'].get('descendants_remaining_after_cleanup'),
        'every_control_cleanup_clean': all(c[m].get('cleanup_ok') is True and c[m].get('cleanup_state') == 'CLEAN' for m in c),
        'descendant_signals_targeted_verified_only': all(s.get('pid') in {d['pid'] for d in (c['desc'].get('descendants_after_exit') or [])}
                                                         for s in (c['desc'].get('cleanup') or {}).get('signals', []) if 'pid' in s),
    }
    real_q = json.loads((RUN / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
    r = rc('LATEST_PREFLIGHT_REAL', real_q['label'])
    res_p = RUN / 'raw' / folders['LATEST_PREFLIGHT_REAL'] / real_q['label'] / 'RESULT.json'
    res = json.loads(res_p.read_text()) if res_p.exists() else {}
    prep = res.get('preparation') or {}
    checks.update({
        'real_worker_no_failure': r.get('exit_code') == 0 or r.get('deadline_termination_requested') is True,
        'real_cold_fast_recorded': prep.get('mode') == 'COLD_FAST' and prep.get('preparation_source_sha256') == real_q['preparation_source_sha256'],
        'real_whole_road_check_ran': (res.get('whole_road_check') or {}).get('status') not in (None, 'NOT_RUN'),
        'real_cleanup_clean': r.get('cleanup_ok') is True,
    })
    gate = {'schema': 'wfg.native-kit.preflight-gate/2', 'utc': utc().isoformat(), 'try': k, 'raw_folders': folders,
            'checks': checks, 'PASS': all(checks.values()),
            'controls': {m: {k: c[m].get(k) for k in ('exit_code', 'on_time_complete_publication', 'termination_requested', 'forced_kill',
                                                      'memory_guard_triggered', 'sampled_family_peak_rss_bytes', 'rss_samples',
                                                      'external_launch_to_completion_wall_s')}
                         | {'descendants': len(c[m].get('descendants_after_exit') or []), 'time_v': c[m].get('time_v')} for m in c},
            'real_attempt': {'label': real_q['label'], 'scope': 'preflight only, never counted; the same mission is also a scored slot (disclosed)',
                             'receipt_wall_s': r.get('external_launch_to_completion_wall_s'), 'on_time': r.get('on_time_complete_publication'),
                             'primary_status': res.get('primary_status'), 'whole_road': (res.get('whole_road_check') or {}).get('status'),
                             'preparation': prep}}
    p = write_new(RUN / ('PREFLIGHT_GATE_try%02d.json' % k), gate)
    if not gate['PASS']:
        raise Stop('PREFLIGHT_GATE_FAILED %s (see %s; rerunning the command retries the gate in new folders)'
                   % ([c for c, v in checks.items() if not v], p.name))
    write_new(gate_path, gate)
    return gate


# ------------------------------------------------------------------ checking and tally
def supervised(cmd, log_path, env, label):
    """Run one offline checking/tally/report child under the controller's verified-ownership rules: CURRENT is pessimistic
    before spawn; the child runs in its own session; its family (group, refreshed lineage, parent lineage) is observed while
    it runs; after exit or on any exception the owned family is cleaned and a final census must be CLEAN, otherwise the lease
    release is withheld. Returns (returncode, log tail)."""
    lineage = {}; proc = None; t0 = time.perf_counter()
    LOGS.mkdir(exist_ok=True)
    C.CURRENT = C.SPAWNING
    with open(log_path, 'a') as lf:
        lf.write('# %s %s\n' % (utc().isoformat(), label)); lf.flush()
        try:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, cwd=str(RUN), start_new_session=True)
            C.CURRENT = proc
            while proc.poll() is None:
                try:
                    C.family_rss(proc.pid, lineage)
                except C.CensusUnknown:
                    pass
                time.sleep(0.25)
        except BaseException as exc:
            if proc is not None:
                cl = C.cleanup_owned(label, proc.pid, str(log_path), lineage, proc)
                C.emit({'checking_child_interrupted': label, 'exception': repr(exc), 'cleanup_state': cl.get('state'), 'cleanup': cl,
                        'utc': utc().isoformat()}, LOGS / 'checking_lifecycle.jsonl')
                if cl.get('state') == 'CLEAN':
                    C.CURRENT = None
                else:
                    withhold('checking child %s cleanup %s after interruption' % (label, cl.get('state')))
            raise
        cl = C.cleanup_owned(label, proc.pid, str(log_path), lineage, proc)
    C.emit({'checking_child': label, 'exit_code': proc.returncode, 'wall_s': time.perf_counter() - t0, 'cleanup_state': cl.get('state'),
            'cleanup': cl, 'utc': utc().isoformat()}, LOGS / 'checking_lifecycle.jsonl')
    if cl.get('state') != 'CLEAN':
        withhold('checking child %s cleanup %s' % (label, cl.get('state')))
        raise Stop('CHECKING_CLEANUP_NOT_CLEAN %s %s' % (label, cl.get('state')))
    C.CURRENT = None
    try:
        tail = pathlib.Path(log_path).read_text(errors='replace')[-600:]
    except Exception:
        tail = ''
    return proc.returncode, tail


def check_queue(py, qn, lease, max_pass_s=900):
    tally = [str(py), '-I', '-B', str(RUN / 'runner/native_tally.py')]
    env = dict(os.environ, WFG_CHECK_PYTHON=str(py), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    env.pop('WFG_OWNER_PREPARED_CACHE', None)
    (RUN / 'raw' / qn).mkdir(parents=True, exist_ok=True)  # a queue with no attempt yet is tallied as NOT_RUN slots
    for mode in ('indep', 'wroad'):
        while True:
            ok, st = lease.check()
            if not ok:
                raise Stop('LEASE_LOST_DURING_CHECKING %s' % json.dumps(st))
            ind = RUN / 'raw' / (qn + '_INDEPENDENT'); wr = RUN / 'raw' / (qn + '_WITNESS_WROAD')
            before = (len(list(ind.glob('*'))) if ind.exists() else 0, len(list(wr.glob('*'))) if wr.exists() else 0)
            rc, tail = supervised(tally + [mode, str(RUN), qn, str(max_pass_s)], LOGS / ('checking_%s.log' % qn), env, 'tally_%s_%s' % (mode, qn))
            if rc != 0:
                raise Stop('CHECKING_FAILED %s %s' % (mode, tail[-300:]))
            after = (len(list(ind.glob('*'))) if ind.exists() else 0, len(list(wr.glob('*'))) if wr.exists() else 0)
            if after == before:
                break
    out = RUN / 'analysis' / qn
    rc, tail = supervised(tally + ['tally', str(RUN), qn, str(out)], LOGS / ('checking_%s.log' % qn), env, 'tally_final_%s' % qn)
    if rc != 0:
        raise Stop('TALLY_FAILED ' + tail[-300:])
    return json.loads((out / 'SUMMARY.json').read_text())


def summarize(py, campaign):
    rc, tail = supervised([str(py), '-I', '-B', str(RUN / 'runner/native_report.py'), str(RUN), campaign], LOGS / 'report.log', dict(os.environ), 'report_' + campaign)
    if rc != 0:
        raise Stop('REPORT_FAILED ' + tail[-300:])
    return (RUN / ('NATIVE_SUMMARY_%s.md' % campaign)).read_text()


# ------------------------------------------------------------------ status
def status(workspace=None):
    out = {'run_root': str(RUN), 'utc': utc().isoformat(), 'queues': {}}
    for qn in PREFLIGHT_Q + PRIMARY + WARM:
        qp = RUN / 'queues' / (qn + '.json')
        if not qp.exists():
            continue
        jobs = json.loads(qp.read_text())['jobs']
        done = sum((RUN / j['output_path'] / 'COMPLETE_PROCESS_RECEIPT.json').exists() for j in jobs)
        intr = sum((RUN / j['output_path']).exists() and not (RUN / j['output_path'] / 'COMPLETE_PROCESS_RECEIPT.json').exists() for j in jobs)
        ind = RUN / 'raw' / (qn + '_INDEPENDENT')
        out['queues'][qn] = {'jobs': len(jobs), 'completed': done, 'interrupted': intr, 'not_started': len(jobs) - done - intr,
                             'independent_outputs': len(list(ind.glob('*.json'))) if ind.exists() else 0,
                             'tallied': (RUN / 'analysis' / qn / 'SUMMARY.json').exists()}
    for n in ('PREFLIGHT_GATE.json', 'NATIVE_SUMMARY_primary.json', 'MISSING_PREREQUISITES.json', 'LEASE_WITHHELD.json'):
        out[n] = (RUN / n).exists()
    out['preflight_gate_tries'] = {p.name: json.loads(p.read_text()).get('PASS') for p in sorted(RUN.glob('PREFLIGHT_GATE_try*.json'))}
    try:
        out['shared_lease'] = json.loads((pathlib.Path(workspace or RUN.resolve().parents[2]) / 'outputs/SHARED_HEAVY_TIMING_LOCK.json').read_text())
    except Exception:
        pass
    try:
        out['last_launcher_events'] = (LOGS / 'launcher.jsonl').read_text().splitlines()[-3:]
    except Exception:
        pass
    print(json.dumps(out, indent=1))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['all', 'check', 'preflight', 'status', 'release'])
    ap.add_argument('--workspace', default=None, help='workspace root holding outputs/ (default: three levels above runner/, i.e. WORKSPACE/outputs/<run folder>/<kit>)')
    ap.add_argument('--python', default=None, help='worker interpreter (default: RUN/env/bin/python, created if absent)')
    ap.add_argument('--base-python', default=None, help='CPython 3.12 used to create RUN/env')
    ap.add_argument('--numpy-wheel', default=None)
    ap.add_argument('--allow-numpy-mismatch', action='store_true', help='record and continue with a numpy other than 1.26.4 (deviation)')
    ap.add_argument('--holder', default='Claude-latest-completion-campaign-20261015')
    ap.add_argument('--purpose', default='Latest-forecast completion campaign (80 attempts, 2 full-policy arms x 2 repetitions, serial)')
    ap.add_argument('--keep-lease', action='store_true', help='do not release the lease at exit (diagnostic use only)')
    ap.add_argument('--min-free-gib', type=float, default=2.0, help='free-disk requirement at RUN')
    args = ap.parse_args()
    if args.command == 'status':
        return status(args.workspace)
    args.workspace = args.workspace or str(RUN.resolve().parents[2])
    lease = Lease(args.workspace, args.holder, args.purpose)
    lock = LocalLock()
    if args.command == 'release':
        try:
            lock.acquire()  # a running instance holds the local lock; never release its lease underneath it
        except Stop:
            print('RELEASE_REFUSED: a running kit instance holds %s' % lock.path, file=sys.stderr); sys.exit(3)
        try:
            lease.release(); print(json.dumps(lease.read()))
        finally:
            lock.release()
        return
    rc = 0

    def on_signal(signum, frame):
        raise Stop('INTERRUPTED_BY_SIGNAL %d' % signum)
    for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        if s == signal.SIGHUP and signal.getsignal(s) == signal.SIG_IGN:
            continue  # started under nohup: closing the terminal must not stop the campaign
        signal.signal(s, on_signal)
    try:
        log('start', command=args.command, argv=sys.argv, run_root=str(RUN))
        cand = verify_candidate(); log('candidate_verified', **cand)
        lock.acquire()   # busy: ends here without touching the shared lease
        lease.acquire()
        py, created = ensure_env(args)
        env = environment(args, py, created)
        copy_inputs(args, PREFLIGHT_Q + PRIMARY)
        if args.command in ('all', 'preflight'):
            preflight(args, py, lease)
        if args.command == 'preflight':
            return
        if args.command == 'all':
            for qn in PRIMARY:
                s = C.run_queue(RUN, RUN / 'queues' / (qn + '.json'), py, lease.check, log=LOGS / ('controller_%s.jsonl' % qn))
                if s['stopped'] == 'CLEANUP_NOT_CLEAN':
                    withhold('queue %s attempt %s cleanup not CLEAN' % (qn, s.get('unclean_attempt')))
                if s['stopped']:
                    raise Stop('QUEUE_STOPPED %s %s' % (qn, s['stopped']))
        for qn in PRIMARY:
            check_queue(py, qn, lease)
        print(summarize(py, 'primary'))
    except Stop as exc:
        rc = 3; log('stopped', reason=str(exc)); print('STOPPED: ' + str(exc), file=sys.stderr)
    except BaseException as exc:
        rc = 4; log('error', error=repr(exc)); raise
    finally:
        cur = getattr(C, 'CURRENT', None)
        if cur is not None:   # run_attempt did not finish its own verified cleanup; never assume clean
            pid = getattr(cur, 'pid', str(cur))
            withhold('in-flight attempt %s without completed verified cleanup' % pid)
            log('in_flight_attempt_not_cleaned', pid=pid, alive=(cur.poll() is None) if hasattr(cur, 'poll') else None)
        for qn in PREFLIGHT_Q + PRIMARY:   # any receipt or interrupted record with a cleanup that is not CLEAN withholds release
            for d in (RUN / 'raw').glob(qn + '*/*') if (RUN / 'raw').exists() else []:
                for fn in ('COMPLETE_PROCESS_RECEIPT.json', 'INTERRUPTED_RECEIPT.json'):
                    f = d / fn
                    if f.exists():
                        try:
                            o = json.loads(f.read_text())
                        except Exception:
                            withhold('unreadable %s' % f); continue
                        st = o.get('cleanup_state') or (o.get('cleanup') or {}).get('state')
                        if st != 'CLEAN':
                            withhold('%s cleanup %s' % (f.relative_to(RUN), st))
        if lease.acquired and not args.keep_lease:
            if RELEASE_OK['ok']:
                lease.release()   # only a lease this process acquired or renewed while holding the local lock
            else:
                write_new(RUN / 'LEASE_WITHHELD.json', {'utc': utc().isoformat(), 'reasons': RELEASE_OK['reasons'][:50],
                                                       'lease': lease.read(), 'note': 'normal release withheld: cleanup not verified CLEAN'})
                log('lease_withheld', reasons=RELEASE_OK['reasons'][:10])
        lock.release()
        log('end', rc=rc)
    sys.exit(rc)


if __name__ == '__main__':
    main()
