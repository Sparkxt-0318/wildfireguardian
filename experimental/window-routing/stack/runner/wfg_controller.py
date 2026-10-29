"""Portable serial request controller, lifecycle-repaired version wfg.controller/2 (latest completion, 15 October 2026).

Derived from the inherited controller (sha256 8848f3c2..., itself derived from the frozen KLB A3 controller). Timing and
publication semantics are unchanged: one fresh worker per attempt launched as `time <python> <worker> --job-file JOB.json`
in a NEW SESSION (the time process ignores SIGTERM); the complete budget runs from immediately before launch to process
completion; SIGTERM to the attempt's process group at the deadline, 3 s, then SIGKILL; the sampled process-family RSS
guard (default 3,072 MiB); on time = no memory stop, no termination, exit 0, wall <= budget, RESULT authority_final and
PUBLICATION_BOUNDARY result_published_before_deadline; completed attempts are never rerun; a folder without a receipt is
INTERRUPTED and never relaunched.

Lifecycle repair (reviewer findings B02 and B05 on 8848f3c2):
  * Ownership is VERIFIED, never inferred from text: an attempt owns (a) every live process whose process group is the
    attempt's group (the new session the controller created; its id cannot be reused while any member lives),
    (b) every live descendant of an owned process by parent-pid lineage, and (c) every process observed in that lineage
    while the attempt ran whose current process group still equals the recorded one. A command line containing the
    attempt's JOB.json path (or any other text) is recorded only as a diagnostic and is never signalled.
  * Cleanup: only verified owned processes are signalled (SIGTERM, bounded wait, SIGKILL, bounded wait); the direct child
    is reaped; a final census must be empty. A census that fails, times out or is malformed is UNKNOWN, never empty.
  * An attempt whose cleanup is not CLEAN (survivors or unknown) is never an on-time complete publication; run_queue
    stops before the next launch and reports CLEANUP_NOT_CLEAN so the caller withholds normal lease release.
  * An exception or interrupt between spawn and receipt cleans verified ownership only, writes INTERRUPTED_RECEIPT.json
    with the partial artifacts left in place, and re-raises so no next attempt starts.
Revision 2.3 (native preflight finding on e509c5b2): the lstart identity is whitespace-normalized when parsed. BSD ps on
macOS pads the lstart column when it is the last field (sampling path without command) but not when command follows (census
path), so the same process compared unequal and a detached owned descendant was treated as a reused pid (not owned) and a
CLEAN state was reported while it survived. Both paths now yield identical identity strings.
Revision 2.2: CURRENT is set to a pessimistic SPAWNING marker before Popen and cleared only after cleanup_owned returns
CLEAN, so an interrupt between spawn and a CLEAN cleanup return, or a cleanup that is not CLEAN, always leaves the launcher
a non-None CURRENT (lease withheld).
Revision 2.1 (reviewer finding LC01 on fed8030a, observed-lineage transition): every snapshot records the process start
time (ps lstart) with pid, ppid and group. Each observation of a verified owned process REFRESHES its lineage record (no
first-seen-only record). A tracked process that is still alive is owned when its recorded start time equals its current
start time (same process identity, so a reused pid is never owned); without a start time it is owned only if its parent
and group are both unchanged since the last verified observation. A live tracked pid whose identity or transition cannot
be verified this way is UNKNOWN: the census raises CensusUnknown (never an empty, clean census) and it is not signalled.
Platform layer: BSD `/usr/bin/time -l` (macOS) or GNU `/usr/bin/time -v`; `ps -A -o pid=,ppid=,pgid=,rss=,stat=,lstart=`
snapshots for family RSS, lineage and census on both platforms."""
import datetime, hashlib, json, os, pathlib, platform, re, signal, subprocess, sys, time

DARWIN = sys.platform == 'darwin'
TIME_TOOL = ['/usr/bin/time', '-l'] if DARWIN else ['/usr/bin/time', '-v']
SAMPLE_S = 0.1
SPAWNING = 'SPAWNING_WITHOUT_RETURNED_POPEN'
CURRENT = None  # the in-flight attempt (SPAWNING before Popen returns); the launcher withholds lease release while it is set


def utc():
    return datetime.datetime.now(datetime.timezone.utc)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def save(p, obj):
    with pathlib.Path(p).open('x') as f:
        json.dump(obj, f, indent=1, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())


# ------------------------------------------------------------------ time tool parsing
def parse_time(text):
    def last(pat):
        m = re.findall(pat, text, re.M)
        return None if not m else m[-1]
    if DARWIN:
        rt = last(r'^\s*([\d.]+)\s+real\s+([\d.]+)\s+user\s+([\d.]+)\s+sys\s*$')
        user, sys_ = (None, None) if rt is None else (float(rt[1]), float(rt[2]))
        mr = last(r'^\s*(\d+)\s+maximum resident set size\s*$')
        rss = None if mr is None else int(mr)
        unit = 'bytes (BSD time -l on macOS)'
    else:
        u = last(r'User time \(seconds\):\s*([\d.]+)'); s = last(r'System time \(seconds\):\s*([\d.]+)')
        user, sys_ = (None if u is None else float(u)), (None if s is None else float(s))
        mr = last(r'Maximum resident set size \(kbytes\):\s*(\d+)')
        rss = None if mr is None else int(mr) * 1024
        unit = 'KiB (GNU time -v), converted to bytes'
    return {'user_s': user, 'sys_s': sys_, 'CPU_s': None if user is None or sys_ is None else user + sys_,
            'timed_command_RSS_bytes': rss, 'maxrss_unit': unit, 'time_tool': ' '.join(TIME_TOOL),
            'RSS_scope': 'time tool max RSS of the timed command (largest single process), not aggregate family peak.'}


# ------------------------------------------------------------------ process family
CLEANUP_TERM_WAIT_S = 2.0
CLEANUP_KILL_WAIT_S = 3.0


class CensusUnknown(Exception):
    """The process table could not be read reliably; ownership state is unknown (never treated as empty)."""


def _ps_rows(with_command=False):
    """(pid, ppid, pgid, rss_kib, command, state, start) for every process; zombies are kept here and skipped by callers.
    start is the ps lstart text (identity together with the pid). Raises CensusUnknown if ps fails, times out or returns
    no parsable row."""
    fields = 'pid=,ppid=,pgid=,rss=,stat=,lstart=' + (',command=' if with_command else '')
    try:
        p = subprocess.run(['/bin/ps', '-A', '-o', fields], capture_output=True, text=True, timeout=10)
    except Exception as exc:
        raise CensusUnknown('PS_FAILED %r' % exc)
    if p.returncode != 0:
        raise CensusUnknown('PS_RETURNCODE %s' % p.returncode)
    rows = []
    for line in p.stdout.splitlines():
        parts = line.split(None, 10 if with_command else 9)
        if len(parts) >= 10 and all(x.lstrip('-').isdigit() for x in parts[:4]):
            rows.append((int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]), parts[10] if with_command and len(parts) > 10 else '',
                         parts[4], ' '.join(' '.join(parts[5:10]).split())))   # 2.3: whitespace-normalized (BSD ps pads lstart)
    if not rows or not any(r[0] == os.getpid() for r in rows):
        raise CensusUnknown('PS_OUTPUT_MALFORMED')
    return rows


def _start(r):
    return r[6] if len(r) > 6 and r[6] else None


def _owned_set(rows, pgid, lineage=None, basis=None):
    """Verified owned pids and the set of live tracked pids whose ownership cannot be verified (UNKNOWN).
    Owned: (a) live members of the attempt's process group; (b) live tracked pids whose recorded start time equals the
    current one (same identity), or, without start times, whose parent and group are both unchanged since the last
    verified observation; (c) live parent-pid descendants of any owned process. A tracked pid whose start time differs
    is a reused pid and is not owned. basis (optional dict) receives the reason per owned pid."""
    me = os.getpid(); basis = {} if basis is None else basis
    live = {r[0]: r for r in rows if not r[5].startswith('Z') and r[0] != me}
    fam = set()
    for pid, r in live.items():
        if r[2] == pgid:
            fam.add(pid); basis[pid] = 'process_group'
    unverified = set()
    for pid, rec in (lineage or {}).items():
        if pid not in live or pid in fam:
            continue
        r = live[pid]; cur, old = _start(r), rec.get('start')
        if cur is not None and old is not None:
            if cur == old:
                fam.add(pid); basis[pid] = 'recorded_identity'
            # else: a different process now holds the pid; never owned, never signalled
        elif r[1] == rec['ppid'] and r[2] == rec['pgid']:
            fam.add(pid); basis[pid] = 'recorded_unchanged_observation'
        else:
            unverified.add(pid)
    roots = set(fam)   # a dead leader's pid is never a root (it could be reused once reaped)
    changed = True
    while changed:
        n = len(fam)
        kids = {pid for pid, r in live.items() if r[1] in roots and pid not in fam}
        for k in kids:
            basis[k] = 'parent_lineage'
        fam |= kids; roots |= kids
        changed = len(fam) != n
    return fam, live, unverified - fam


def observe_lineage(rows, pgid, lineage):
    """Refresh the lineage record of every verified owned live process (pid -> ppid, pgid, start) at each observation."""
    fam, live, unverified = _owned_set(rows, pgid, lineage)
    for pid in fam:
        r = live[pid]; prev = lineage.get(pid)
        lineage[pid] = {'ppid': r[1], 'pgid': r[2], 'start': _start(r),
                        'first_seen': prev.get('first_seen') if prev else datetime.datetime.now(datetime.timezone.utc).isoformat()}
    return fam, live, unverified


def family_rss(pgid, lineage=None):
    """Sampled RSS of the verified family; raises CensusUnknown if a live tracked process cannot be verified."""
    rows = _ps_rows()
    fam, live, unverified = observe_lineage(rows, pgid, lineage) if lineage is not None else _owned_set(rows, pgid)
    if unverified:
        raise CensusUnknown('UNVERIFIED_TRACKED_PROCESS %s' % sorted(unverified))
    return sum(live[p][3] * 1024 for p in fam)


def census(label, pgid, job_path, lineage=None):
    """Verified owned live processes of the attempt (list of dicts). argv text never establishes ownership.
    Raises CensusUnknown when the process table cannot be read or a live tracked process cannot be verified."""
    rows = _ps_rows(with_command=True)
    basis = {}
    fam, live, unverified = _owned_set(rows, pgid, lineage, basis)
    if unverified:
        raise CensusUnknown('UNVERIFIED_TRACKED_PROCESS %s' % [{'pid': p, 'ppid': live[p][1], 'pgrp': live[p][2],
                                                                'recorded': (lineage or {}).get(p)} for p in sorted(unverified)])
    if lineage is not None:   # refresh observations of verified owned processes (LC01)
        for pid in fam:
            r = live[pid]; prev = lineage.get(pid)
            lineage[pid] = {'ppid': r[1], 'pgid': r[2], 'start': _start(r), 'first_seen': (prev or {}).get('first_seen')}
    return [{'pid': p, 'ppid': live[p][1], 'pgrp': live[p][2], 'cmd': live[p][4][:200], 'start': _start(live[p]),
             'basis': basis.get(p)} for p in sorted(fam)]


def argv_diagnostic(job_path, owned_pids):
    """Processes whose command line contains the JOB path but are NOT verified owned (diagnostic only; never signalled)."""
    try:
        rows = _ps_rows(with_command=True)
    except Exception as exc:   # diagnostic only; never affects ownership or cleanup
        return {'unavailable': type(exc).__name__ + ': ' + str(exc)}
    return [{'pid': r[0], 'ppid': r[1], 'pgrp': r[2], 'cmd': r[4][:200]} for r in rows
            if str(job_path) in r[4] and r[0] not in owned_pids and r[0] != os.getpid() and not r[4].startswith('/bin/ps ')]


def cleanup_owned(label, pgid, job_path, lineage, proc):
    """Signal only verified owned processes; wait/reap; final census. Returns a cleanup record (state CLEAN/SURVIVORS/UNKNOWN)."""
    rec = {'policy': 'verified ownership only (process group, parent lineage, recorded lineage); argv diagnostic only',
           'signals': [], 'signal_errors': [], 'census': []}
    try:
        if proc is not None and proc.poll() is None:
            proc.wait(timeout=CLEANUP_KILL_WAIT_S)
    except Exception as exc:
        rec['signal_errors'].append('DIRECT_CHILD_WAIT %r' % exc)

    polls = [0]

    def take():
        c = census(label, pgid, job_path, lineage); polls[0] += 1
        if len(rec['census']) < 12:
            rec['census'].append([d['pid'] for d in c])
        rec['census_polls'] = polls[0]
        return c
    try:
        owned = take()
        rec['descendants_after_exit'] = owned
        for sig, wait_s in ((signal.SIGTERM, CLEANUP_TERM_WAIT_S), (signal.SIGKILL, CLEANUP_KILL_WAIT_S)):
            if not owned:
                break
            targets = sorted({d['pid'] for d in owned})
            if any(d['pgrp'] == pgid for d in owned):
                try:
                    os.killpg(pgid, sig); rec['signals'].append({'pgid': pgid, 'signal': int(sig)})
                except ProcessLookupError:
                    pass
                except PermissionError as exc:
                    rec['signal_errors'].append('KILLPG %d %r' % (pgid, exc))
            for pid in targets:
                try:
                    os.kill(pid, sig); rec['signals'].append({'pid': pid, 'signal': int(sig)})
                except ProcessLookupError:
                    pass
                except PermissionError as exc:
                    rec['signal_errors'].append('KILL %d %r' % (pid, exc))
            t_end = time.perf_counter() + wait_s; n_poll = 0
            while True:
                owned = take(); n_poll += 1
                if not owned or time.perf_counter() >= t_end or n_poll >= int(wait_s / 0.1) + 1:
                    break
                time.sleep(0.1)
        try:
            if proc is not None:
                proc.wait(timeout=CLEANUP_KILL_WAIT_S)
        except Exception as exc:
            rec['signal_errors'].append('DIRECT_CHILD_REAP %r' % exc)
        final = take()
        rec['descendants_remaining_after_cleanup'] = final
        rec['state'] = 'CLEAN' if not final else 'SURVIVORS'
    except CensusUnknown as exc:
        rec['state'] = 'UNKNOWN'; rec['census_error'] = str(exc)
        rec.setdefault('descendants_after_exit', None); rec['descendants_remaining_after_cleanup'] = None
    except Exception as exc:
        rec['state'] = 'UNKNOWN'; rec['census_error'] = type(exc).__name__ + ': ' + str(exc)
        rec.setdefault('descendants_after_exit', None); rec['descendants_remaining_after_cleanup'] = None
    owned_pids = {d['pid'] for d in (rec.get('descendants_after_exit') or [])}
    rec['argv_job_path_matches_not_owned'] = argv_diagnostic(job_path, owned_pids)
    return rec


# ------------------------------------------------------------------ one attempt
def run_attempt(root, job, python, lease_state, private_cache_root=None, log=None):
    folder = root / job['output_path']
    folder.mkdir(parents=True, exist_ok=False)
    job = dict(job); job['root'] = str(root); job['decision_dir'] = str(root / 'decision')
    job_path = folder / 'JOB.json'; save(job_path, job)
    for k, h in job.get('input_sha256', {}).items():
        if sha(root / job[k]) != h:
            save(folder / 'PRELAUNCH_FAILURE.json', {'reason': 'INPUT_HASH_MISMATCH:' + k, 'utc': utc().isoformat()})
            raise SystemExit('PRELAUNCH_INPUT_HASH_MISMATCH ' + job['label'] + ' ' + k)
    env = {k: v for k, v in os.environ.items() if not (k.startswith('PYTHON') and k != 'PYTHONDONTWRITEBYTECODE')}
    scrubbed = sorted(k for k in os.environ if k not in env)
    env.pop('WFG_OWNER_PREPARED_CACHE', None)
    env.update(PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    declared = job.get('preparation_mode')
    if declared == 'AUTHENTICATED_ARTIFACT':
        if not private_cache_root:
            raise SystemExit('WARM_OPTION_REQUIRES_PRIVATE_CACHE_ROOT')
        env['WFG_OWNER_PREPARED_CACHE'] = str(private_cache_root)
    env.update(job.get('env', {}))
    env['WFG_NATIVE_ATTEMPT'] = job['label']
    guard = float(job.get('memory_guard_mib', 3072)) * 2 ** 20
    budget = float(job['complete_budget_s'])
    command = TIME_TOOL + [str(python), str(root / job['worker']), '--job-file', str(job_path)]
    so = (folder / 'stdout.log').open('x'); se = (folder / 'PROCESS.time').open('x')
    started = utc().isoformat(); begun = time.perf_counter(); env['WFG_OUTER_MONOTONIC_START'] = str(begun)
    global CURRENT
    CURRENT = SPAWNING   # pessimistic marker set before spawn; cleared only after cleanup_owned returns CLEAN
    proc = subprocess.Popen(command, stdout=so, stderr=se, env=env, cwd=str(root), start_new_session=True,
                            preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_IGN))
    CURRENT = proc
    pgid = proc.pid   # new session: the time process is session and group leader
    lineage = {}
    term = killed = mem_stop = False; peak = 0; nsamp = 0; last = -1.0; sample_cost = 0.0; sample_errors = 0
    try:
        while proc.poll() is None and time.perf_counter() - begun < budget:
            tt = time.perf_counter()
            if tt - last >= SAMPLE_S and begun + budget - tt > 0.15:
                last = tt
                try:
                    r = family_rss(pgid, lineage)
                except CensusUnknown:
                    r = 0; sample_errors += 1
                nsamp += 1; peak = max(peak, r); sample_cost += time.perf_counter() - tt
                if r > guard:
                    mem_stop = True; break
            time.sleep(.01)
        if proc.poll() is None:
            term = True
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=3.)
            except subprocess.TimeoutExpired:
                killed = True
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
        ended = time.perf_counter(); so.close(); se.close()
        cleanup = cleanup_owned(job['label'], pgid, job_path, lineage, proc)
        if cleanup.get('state') == 'CLEAN':
            CURRENT = None   # otherwise stays set: the launcher withholds lease release
    except BaseException as exc:
        try:
            so.close(); se.close()
        except Exception:
            pass
        cleanup = cleanup_owned(job['label'], pgid, job_path, lineage, proc)
        if cleanup.get('state') == 'CLEAN':
            CURRENT = None
        save(folder / 'INTERRUPTED_RECEIPT.json', {'schema': 'wfg.controller.interrupted/2', 'job_id': job['label'],
             'utc': utc().isoformat(), 'exception': type(exc).__name__ + ': ' + str(exc), 'cleanup': cleanup,
             'partial_artifacts_preserved': True, 'relaunch': 'never (frozen rule A1)'})
        raise
    fields = parse_time((folder / 'PROCESS.time').read_text(errors='replace'))
    rp, bp = folder / 'RESULT.json', folder / 'PUBLICATION_BOUNDARY.json'
    res = json.loads(rp.read_text()) if rp.exists() else None
    bd = json.loads(bp.read_text()) if bp.exists() else None
    cleanup_ok = cleanup.get('state') == 'CLEAN'
    ontime = (cleanup_ok and not mem_stop and not term and not killed and proc.returncode == 0 and ended - begun <= budget and res is not None
              and res.get('authority_final') is True and bd is not None and bd.get('result_published_before_deadline') is True)
    prep = (res or {}).get('preparation') or {}
    desc = cleanup.get('descendants_after_exit'); desc_after = cleanup.get('descendants_remaining_after_cleanup')
    rec = {'schema': 'wfg.controller.outer-complete-receipt/2 (A3 timing semantics; verified-ownership cleanup)', 'job_id': job['label'],
           'case_id': job['case_id'], 'arm': job['arm'], 'repetition': job.get('rep'), 'campaign': job.get('campaign'),
           'started_utc': started, 'ended_utc': utc().isoformat(), 'complete_budget_s': job['complete_budget_s'],
           'external_launch_to_completion_wall_s': ended - begun, 'exit_code': proc.returncode,
           'deadline_termination_requested': term and not mem_stop, 'termination_requested': term,
           'memory_guard_mib': guard / 2 ** 20, 'memory_guard_triggered': mem_stop, 'sampled_family_peak_rss_bytes': peak,
           'rss_samples': nsamp, 'rss_sample_errors': sample_errors, 'rss_sample_interval_s': SAMPLE_S, 'rss_sampling_cost_s': sample_cost,
           'rss_sampler': 'ps', 'attempt_process_group': pgid, 'lineage_observed': len(lineage),
           'cleanup_state': cleanup.get('state'), 'cleanup_ok': cleanup_ok, 'cleanup': cleanup,
           'descendants_after_exit': desc, 'descendants_killed': [s.get('pid') for s in cleanup.get('signals', []) if 'pid' in s],
           'descendants_remaining_after_cleanup': desc_after,
           'forced_kill': killed, 'on_time_complete_publication': ontime,
           'raw_primary_status': None if res is None else res.get('primary_status'),
           'runtime_whole_road_status': None if res is None else (res.get('whole_road_check') or {}).get('status'),
           'preparation_mode_declared': declared, 'preparation_mode_recorded': prep.get('mode'),
           'preparation_cache_hit': prep.get('cache_hit'), 'worker_cache_env_set': 'WFG_OWNER_PREPARED_CACHE' in env,
           'scrubbed_env': scrubbed, 'time_v': fields, 'host': os.uname().nodename, 'platform': sys.platform,
           'machine': platform.machine(), 'python': str(python), 'command': command,
           'controller_sha256': sha(__file__), 'lease_at_launch': lease_state, 'physical_safety_claim': False}
    save(folder / 'COMPLETE_PROCESS_RECEIPT.json', rec)
    line = {'label': job['label'], 'status': rec['raw_primary_status'], 'road': rec['runtime_whole_road_status'],
            'ontime': ontime, 'wall': round(ended - begun, 2), 'cpu': fields['CPU_s'],
            'rss_mb': None if fields['timed_command_RSS_bytes'] is None else round(fields['timed_command_RSS_bytes'] / 2 ** 20, 1),
            'fam_peak_mb': round(peak / 2 ** 20, 1), 'mem_stop': mem_stop, 'term': term, 'killed': killed,
            'desc': None if desc is None else len(desc), 'desc_left': None if desc_after is None else len(desc_after),
            'cleanup': cleanup.get('state'), 'prep': prep.get('mode'), 'hit': prep.get('cache_hit'),
            'exit': proc.returncode, 'utc': rec['ended_utc']}
    emit(line, log)
    return rec


def emit(obj, log=None):
    s = json.dumps(obj)
    print(s, flush=True)
    if log is not None:
        with open(log, 'a') as f:
            f.write(s + '\n'); f.flush(); os.fsync(f.fileno())


def run_queue(root, queue_path, python, lease_check, private_cache_root=None, stop_after=None, log=None):
    """lease_check() -> (ok, state); called before every launch (it may renew). Returns a summary dict.
    Stops before the next launch if an attempt's cleanup is not CLEAN (summary stopped='CLEANUP_NOT_CLEAN')."""
    root = pathlib.Path(root); q = json.loads(pathlib.Path(queue_path).read_text()); t0 = time.perf_counter(); ran = 0
    emit({'queue_start': q.get('name'), 'utc': utc().isoformat(), 'jobs': len(q['jobs']), 'stop_after': stop_after}, log)
    stopped = None; unclean = None
    for job in q['jobs']:
        folder = root / job['output_path']
        if (folder / 'COMPLETE_PROCESS_RECEIPT.json').exists():
            prev = json.loads((folder / 'COMPLETE_PROCESS_RECEIPT.json').read_text())
            if prev.get('cleanup_ok') is False:
                stopped = 'CLEANUP_NOT_CLEAN'; unclean = job['label']
                emit({'stop': 'PREVIOUS_ATTEMPT_CLEANUP_NOT_CLEAN', 'label': job['label']}, log); break
            continue
        if folder.exists():
            emit({'interrupted': job['label'], 'action': 'SKIPPED_NOT_RELAUNCHED'}, log); continue
        if stop_after is not None and time.perf_counter() - t0 > stop_after - float(job['complete_budget_s']) - 6:
            stopped = 'STOP_AFTER'; break
        ok, state = lease_check()
        if not ok:
            stopped = 'LEASE_NOT_HELD'; emit({'stop': 'LEASE_NOT_HELD_OR_EXPIRING', 'lease': state}, log); break
        rec = run_attempt(root, job, python, state, private_cache_root, log); ran += 1
        if not rec.get('cleanup_ok'):
            stopped = 'CLEANUP_NOT_CLEAN'; unclean = job['label']
            emit({'stop': 'CLEANUP_NOT_CLEAN', 'label': job['label'], 'cleanup_state': rec.get('cleanup_state')}, log); break
    left = sum(1 for j in q['jobs'] if not (root / j['output_path'] / 'COMPLETE_PROCESS_RECEIPT.json').exists())
    interrupted = sum(1 for j in q['jobs'] if (root / j['output_path']).exists() and not (root / j['output_path'] / 'COMPLETE_PROCESS_RECEIPT.json').exists())
    summary = {'queue_end': q.get('name'), 'ran': ran, 'remaining_without_receipt': left, 'interrupted': interrupted,
               'stopped': stopped, 'unclean_attempt': unclean, 'utc': utc().isoformat()}
    emit(summary, log)
    return summary
