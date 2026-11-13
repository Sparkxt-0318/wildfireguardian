"""The g1_panel harness memory sampler (STEP2_ACCEPTANCE F2/R7; sampling-error rules per Mira 122 N2), importable so it
is tested (tests/test_step2f_guard.HarnessSampler). Used by run_one_job.py.

- a pid that vanished between the listing and the read is skipped and counted (vanished_pids);
- a sample in which a LIVE pid could not be read is NOT MEASURED: counted (unmeasured_samples), excluded from every
  peak, never summed partially.
"""
import os, time

def descendants(root):
    kids = {}
    for d in os.listdir('/proc'):
        if d.isdigit():
            try:
                with open('/proc/%s/stat' % d) as f:
                    ppid = int(f.read().rsplit(')', 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(d))
            except (OSError, IndexError, ValueError):
                pass
    out, todo = [], list(kids.get(root, []))
    while todo:
        x = todo.pop(); out.append(x); todo.extend(kids.get(x, []))
    return out


class Unreadable(Exception):
    """A live pid's smaps_rollup could not be read (Mira 122 N2)."""


def rollup(pid):
    """{'Rss': bytes, 'Pss': bytes}; None if the pid vanished; raises Unreadable if it is live but could not be read."""
    r = {}
    try:
        with open('/proc/%d/smaps_rollup' % pid) as f:
            for line in f:
                if line.startswith(('Rss:', 'Pss:')):
                    r[line[:3]] = int(line.split()[1]) * 1024
    except (FileNotFoundError, ProcessLookupError):
        return None
    except OSError as e:
        if not os.path.exists('/proc/%d' % pid):
            return None
        raise Unreadable(pid) from e
    if 'Pss' not in r or 'Rss' not in r:
        if not os.path.exists('/proc/%d' % pid):
            return None                    # exited mid-read: the file ended early
        raise Unreadable(pid)
    return r


MEM = {'pss_peak': 0, 'rss_peak': 0, 'pss_at_rss_peak': 0, 'n_at_pss_peak': 0, 'samples': 0, 'sampler_cpu_s': 0.0,
       'measured_samples': 0, 'unmeasured_samples': 0, 'vanished_pids': 0}
STOP = [False]


def sample(me=None):
    me = os.getpid() if me is None else me; t_cpu = time.thread_time()
    while not STOP[0]:
        fam = descendants(me)          # the harness interpreter itself is excluded: it is the same for every arm
        MEM['samples'] += 1
        try:
            vals = [rollup(p) for p in fam]
        except Unreadable:
            vals = None
        if vals is None:
            MEM['unmeasured_samples'] += 1          # N2: never a partial sum
        else:
            MEM['vanished_pids'] += sum(1 for v in vals if v is None)
            vals = [v for v in vals if v is not None]
            pss = sum(v['Pss'] for v in vals); rss = sum(v['Rss'] for v in vals)
            MEM['measured_samples'] += 1
            if pss > MEM['pss_peak']:
                MEM['pss_peak'] = pss; MEM['n_at_pss_peak'] = len(vals)
            if rss > MEM['rss_peak']:
                MEM['rss_peak'] = rss; MEM['pss_at_rss_peak'] = pss
        MEM['sampler_cpu_s'] = time.thread_time() - t_cpu
        time.sleep(0.01)


