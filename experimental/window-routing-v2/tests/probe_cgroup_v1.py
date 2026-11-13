"""Step 2 mechanism probe (Thomas 17:22 UTC): can a per-check cgroup v1 memory peak serve as an UPPER bound on a forked
check's own memory on this host? Parent moves itself into a fresh child cgroup, forks, moves back (fork-time charges
land in the child cgroup); read max_usage after the child exits, before force_empty + rmdir.
Tests: (a) child allocates N MiB -> max_usage >= N; (b) child only reads a large parent array -> max_usage << size;
(c) child writes every page of a parent array (COW) -> max_usage >= size; (d) spike-between-samples: cgroup peak sees it.
Also records: cgroup version/path, swap state, kmem accounting, use_hierarchy. Prints one JSON line."""
import json, os, sys, time
import numpy as np

BASE = None
for l in open('/proc/self/cgroup'):
    p = l.strip().split(':')
    if len(p) == 3 and p[1] == 'memory':
        BASE = '/sys/fs/cgroup/memory' + p[2]
MiB = 2 ** 20


def rd(cg, f):
    with open(os.path.join(cg, f)) as h:
        return int(h.read().strip())


def run_in_cgroup(fn, tag):
    cg = os.path.join(BASE, 'wfgv2_%s_%d_%d' % (tag, os.getpid(), time.monotonic_ns()))
    os.mkdir(cg)
    u0 = rd(cg, 'memory.usage_in_bytes')
    me = str(os.getpid())
    with open(os.path.join(cg, 'cgroup.procs'), 'w') as h:
        h.write(me)                                    # parent moves in ...
    pid = os.fork()
    if pid == 0:
        try:
            fn(); os._exit(0)
        except BaseException:
            os._exit(1)
    with open(os.path.join(BASE, 'cgroup.procs'), 'w') as h:
        h.write(me)                                    # ... and back out right after fork
    _, st = os.waitpid(pid, 0)
    peak = rd(cg, 'memory.max_usage_in_bytes')
    kmem = rd(cg, 'memory.kmem.max_usage_in_bytes') if os.path.exists(os.path.join(cg, 'memory.kmem.max_usage_in_bytes')) else None
    memsw = rd(cg, 'memory.memsw.max_usage_in_bytes') if os.path.exists(os.path.join(cg, 'memory.memsw.max_usage_in_bytes')) else None
    try:
        with open(os.path.join(cg, 'memory.force_empty'), 'w') as h:
            h.write('0')
    except OSError:
        pass
    try:
        os.rmdir(cg); rm = True
    except OSError:
        rm = False
    return {'usage_before_fork': u0, 'max_usage_mib': peak / MiB, 'kmem_max_mib': None if kmem is None else kmem / MiB,
            'memsw_max_mib': None if memsw is None else memsw / MiB, 'exit_ok': os.WEXITSTATUS(st) == 0, 'rmdir_ok': rm}


def main():
    out = {'cgroup_version': 'v1' if BASE else None, 'cgroup_path': BASE}
    swaps = open('/proc/swaps').read().strip().splitlines()
    out['swap_active'] = len(swaps) > 1
    out['use_hierarchy'] = rd(BASE, 'memory.use_hierarchy')
    N = 512
    out['a_alloc'] = run_in_cgroup(lambda: np.ones(N * MiB // 8).sum(), 'a'); out['a_N_mib'] = N
    big = np.ones(1024 * MiB // 8)                     # 1 GiB in the parent, touched
    out['b_read'] = run_in_cgroup(lambda: float(big.sum()), 'b')
    def cow():
        big[:] = 2.0                                   # write every page -> COW copies
    out['c_cow'] = run_in_cgroup(cow, 'c'); out['bc_array_mib'] = 1024
    def spike():
        x = np.ones(768 * MiB // 8); x.sum(); del x    # allocate, touch, free between any samples
        time.sleep(0.2)
    out['d_spike'] = run_in_cgroup(spike, 'd'); out['d_spike_mib'] = 768
    out['verdict'] = {
        'a_peak_ge_N': out['a_alloc']['max_usage_mib'] >= N,
        'b_shared_not_charged': out['b_read']['max_usage_mib'] < 0.2 * 1024,
        'c_cow_charged': out['c_cow']['max_usage_mib'] >= 1024,
        'd_spike_seen': out['d_spike']['max_usage_mib'] >= 768,
        'fresh_cgroups': all(out[k]['usage_before_fork'] <= 4096 for k in ('a_alloc', 'b_read', 'c_cow', 'd_spike')),
    }
    print(json.dumps(out))


if __name__ == '__main__':
    main()
