"""Kit v2 Step 2: memory measurement for the solver gate and the whole-road check (STEP2_ACCEPTANCE.md).

- current_rss_mb(): the process's CURRENT resident set (/proc/self/statm), used by the v2 solver gate in place of the
  lifetime ru_maxrss.
- private_mb(): the process's private (unshared) memory from /proc/self/smaps_rollup. In a forked check child this is
  a SAMPLED LOWER bound on the check's own memory; it can only prove "outside budget".
- run_check_forked(fn, gate_mb, deadline): runs fn() in a forked child inside a fresh cgroup v1 memory cgroup
  (parent moved in for the fork and back out, asserted). The cgroup peak (memsw when present) is an UPPER bound on the
  check's own memory. Returns (payload or None, child_status, resource_budget).

Asymmetric rule (Thomas 17:21 UTC):
  sampled private > gate                     -> within_budget False   (mechanism fork_sampled_private)
  cgroup peak (upper bound) > gate           -> within_budget False
  cgroup peak <= gate and sampled <= gate    -> within_budget True    (mechanism cgroup_v1_max_usage_parent_moved)
  no upper-bound mechanism                   -> within_budget "not_proven"
"""
import os, pickle, select, signal, struct, time

MiB = 2 ** 20
PAGE = os.sysconf('SC_PAGE_SIZE')
KMEM_MARGIN_MB = 64           # used only if kmem is not accounted (Thomas point 3)
FRESH_USAGE_MAX_BYTES = 4096  # usage of a new cgroup before the fork (Thomas point 4)


def current_rss_mb():
    with open('/proc/self/statm') as f:
        return int(f.read().split()[1]) * PAGE / MiB


def private_mb():
    try:
        tot = 0
        with open('/proc/self/smaps_rollup') as f:
            for line in f:
                if line.startswith(('Private_Clean:', 'Private_Dirty:')):
                    tot += int(line.split()[1])
        return tot / 1024
    except OSError:
        return None


class PrivateSampler:
    """Maximum of sampled private memory (a lower bound on the true private peak)."""
    def __init__(self):
        self.max_mb = None; self.samples = 0

    def sample(self):
        v = private_mb()
        if v is not None:
            self.samples += 1
            self.max_mb = v if self.max_mb is None else max(self.max_mb, v)
        return v


SAMPLER = PrivateSampler()   # the check child's sampler (fresh per fork: the child starts from the parent's copy)


def _memory_cgroup_base():
    try:
        with open('/proc/self/cgroup') as f:
            lines = f.read().splitlines()
        for line in lines:
            p = line.strip().split(':', 2)
            if len(p) == 3 and 'memory' in p[1].split(','):
                base = '/sys/fs/cgroup/memory' + p[2]
                return base if os.path.isdir(base) else None
    except OSError:
        pass
    return None


def _rd(cg, name):
    p = os.path.join(cg, name)
    if not os.path.exists(p):
        return None
    with open(p) as h:
        return int(h.read().strip())


def host_state():
    base = _memory_cgroup_base()
    try:
        with open('/proc/swaps') as f:
            swap_on = len(f.read().strip().splitlines()) > 1
    except OSError:
        swap_on = None
    return {'cgroup_version': 'v1' if base else None, 'cgroup_path': base, 'swap_active': swap_on,
            'use_hierarchy': _rd(base, 'memory.use_hierarchy') if base else None,
            'memsw_present': bool(base) and os.path.exists(os.path.join(base, 'memory.memsw.max_usage_in_bytes'))}


def _self_cgroup_line():
    with open('/proc/self/cgroup') as f:
        return f.read()


def _write(path, text):
    with open(path, 'w') as h:
        h.write(text)


def _send(fd, obj):
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)   # exact types (Fractions) preserved, own child only
    os.write(fd, struct.pack('>Q', len(data)))
    view = memoryview(data)
    while view:
        n = os.write(fd, view); view = view[n:]


def _recv_all(fd, t_end):
    """Read until EOF or until t_end (perf_counter). Returns (message or None, timed_out)."""
    chunks = []
    while True:
        left = t_end - time.perf_counter()
        if left <= 0:
            return None, True
        ready, _, _ = select.select([fd], [], [], min(left, 1.0))
        if not ready:
            continue
        b = os.read(fd, 1 << 20)
        if not b:
            break
        chunks.append(b)
    raw = b''.join(chunks)
    if len(raw) < 8:
        return None, False
    n = struct.unpack('>Q', raw[:8])[0]
    body = raw[8:8 + n]
    return (pickle.loads(body) if len(body) == n else None), False


def _abandon(pid, cg, base, me, w):
    """Parent interrupted mid-check: kill and reap the child, make sure the parent is back out, drop the cgroup."""
    for f in (lambda: os.kill(pid, signal.SIGKILL), lambda: os.waitpid(pid, 0),
              lambda: w is not None and os.close(w),
              lambda: cg is not None and _write(os.path.join(base, 'cgroup.procs'), me),
              lambda: cg is not None and os.rmdir(cg)):
        try:
            f()
        except OSError:
            pass


def verdict(gate_mb, sampled_private_mb, upper_mb, mechanism, kmem_accounted):
    """The asymmetric rule. upper_mb is an upper bound on the check's own memory, or None."""
    if sampled_private_mb is not None and sampled_private_mb > gate_mb:
        return False, 'fork_sampled_private'
    if upper_mb is None:
        return 'not_proven', mechanism
    limit = gate_mb if kmem_accounted else gate_mb - KMEM_MARGIN_MB
    return (upper_mb <= limit), mechanism


def run_check_forked(fn, gate_mb, deadline, grace_s=2.0, use_cgroup=True):
    """fn() runs in a forked child and must return a JSON-able dict. Returns (payload, child, resource_budget)."""
    hs = host_state()
    base = hs['cgroup_path'] if use_cgroup else None
    cg = None; usage0 = None; mech = None
    before = _self_cgroup_line()
    if base is not None and not (hs['swap_active'] and not hs['memsw_present']):
        try:
            cg = os.path.join(base, 'wfgv2_check_%d_%d' % (os.getpid(), time.monotonic_ns()))
            os.mkdir(cg)
            usage0 = _rd(cg, 'memory.usage_in_bytes')
            if usage0 is None or usage0 > FRESH_USAGE_MAX_BYTES:
                raise OSError('cgroup not fresh: usage %r' % usage0)
            mech = 'cgroup_v1_max_usage_parent_moved'
        except OSError as exc:
            if cg is not None:
                try:
                    os.rmdir(cg)
                except OSError:
                    pass
            cg = None; mech = None; hs['cgroup_error'] = repr(exc)
    r, w = os.pipe()
    me = str(os.getpid())
    if cg is not None:
        _write(os.path.join(cg, 'cgroup.procs'), me)          # parent in: fork-time charges land in the check cgroup
    pid = os.fork()
    if pid == 0:                                               # ---------------- check child
        code = 0
        try:
            os.close(r)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)      # never run the worker's publication handlers here
            SAMPLER.max_mb = None; SAMPLER.samples = 0
            SAMPLER.sample()
            out = fn()
            SAMPLER.sample()
            _send(w, {'payload': out, 'sampled_private_mb': SAMPLER.max_mb, 'samples': SAMPLER.samples})
        except BaseException as exc:                           # MemoryError included: the check is interrupted
            code = 3
            try:
                _send(w, {'payload': None, 'error': repr(exc), 'sampled_private_mb': SAMPLER.max_mb,
                          'samples': SAMPLER.samples})
            except BaseException:
                pass
        finally:
            os._exit(code)
    # -------------------------------------------------------------------------------- parent
    try:
        if cg is not None:
            _write(os.path.join(base, 'cgroup.procs'), me)    # parent back out, right after the fork
            if _self_cgroup_line() != before:
                raise RuntimeError('PARENT_CGROUP_MOVE_BACK_FAILED')
        os.close(w); w = None
        msg = None; killed = False
        t_end = deadline + grace_s  # the child honours the deadline itself; one still running at deadline + grace is killed
        try:
            msg, timed_out = _recv_all(r, t_end)               # child writes once, then exits; EOF on exit
        finally:
            os.close(r)
        while True:
            wp, st = os.waitpid(pid, os.WNOHANG)
            if wp:
                break
            if time.perf_counter() > t_end:
                os.kill(pid, signal.SIGKILL); killed = True
                wp, st = os.waitpid(pid, 0); break
            time.sleep(0.005)
    except BaseException:                                      # e.g. DeadlineStop (SIGTERM) in the parent
        _abandon(pid, cg, base, me, w)
        raise
    child = {'pid': pid, 'exit_code': os.WEXITSTATUS(st) if os.WIFEXITED(st) else None,
             'signal': os.WTERMSIG(st) if os.WIFSIGNALED(st) else None, 'killed_after_deadline': killed,
             'error': (msg or {}).get('error')}
    upper = None; cgrec = None
    if cg is not None:
        memsw = _rd(cg, 'memory.memsw.max_usage_in_bytes')
        mx = _rd(cg, 'memory.max_usage_in_bytes')
        kmem = _rd(cg, 'memory.kmem.max_usage_in_bytes')
        if memsw is not None:
            upper = memsw / MiB; read = 'memsw.max_usage_in_bytes'
        elif hs['swap_active'] is False:
            upper = mx / MiB if mx is not None else None; read = 'max_usage_in_bytes (swap off)'
        else:
            upper = None; read = None
        try:
            _write(os.path.join(cg, 'memory.force_empty'), '0')
        except OSError:
            pass
        try:
            os.rmdir(cg); rm = True
        except OSError:
            rm = False
        cgrec = {'path': cg, 'usage_before_fork_bytes': usage0, 'max_usage_mb': None if mx is None else mx / MiB,
                 'memsw_max_usage_mb': None if memsw is None else memsw / MiB,
                 'kmem_max_usage_mb': None if kmem is None else kmem / MiB, 'read': read, 'rmdir_ok': rm}
    kmem_acc = bool(cgrec and cgrec['kmem_max_usage_mb'])
    sampled = (msg or {}).get('sampled_private_mb')
    within, mech_used = verdict(gate_mb, sampled, upper, mech, kmem_acc)
    budget = {'gate_mb': gate_mb, 'peak_mb': upper, 'sampled_private_peak_mb': sampled,
              'private_samples': (msg or {}).get('samples'), 'within_budget': within, 'mechanism': mech_used,
              'kmem_accounted': kmem_acc, 'host': hs, 'cgroup': cgrec,
              'scope': 'the check child only: pages it first touches, incl. copy-on-write copies; pages shared with '
                       'the parent stay charged to the parent'}
    if not kmem_acc and upper is not None:
        budget['kmem_note'] = 'kmem not counted: within_budget needs peak <= gate - %d MiB' % KMEM_MARGIN_MB
    return (msg or {}).get('payload'), child, budget
