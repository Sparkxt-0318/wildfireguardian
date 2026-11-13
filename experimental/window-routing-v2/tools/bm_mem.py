import json, os, sys, threading, time, resource
from pathlib import Path
kit, graph_p, packet, dep, hor = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(kit / 'phaseB')]
import road_bounds
from fractions import Fraction as F
g = json.loads(graph_p.read_text())
pg = os.sysconf('SC_PAGE_SIZE')
samp = {'max': 0, 't': 0}
def rss():
    return int(open('/proc/self/statm').read().split()[1]) * pg / 2**20
stopf = False
def run():
    while not stopf:
        r = rss()
        if r > samp['max']: samp['max'] = r; samp['t'] = time.perf_counter()
        time.sleep(0.002)
th = threading.Thread(target=run, daemon=True); th.start()
base = rss(); t0 = time.perf_counter()
M = road_bounds.RoadBoundModel(g, packet, active_window=(F(dep), F(hor)))
t1 = time.perf_counter(); stopf = True; th.join()
print(json.dumps({'base_mb': base, 'peak_sampled_mb': samp['max'], 'peak_at_frac': (samp['t'] - t0) / (t1 - t0),
                  'after_mb': rss(), 'ru_maxrss_mb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                  'edges': len(g['edges']), 'full_pot': int(M.full_pot.size), 'P': M.P,
                  'gx_mib_each': len(g['edges']) * int(M.full_pot.size) * 8 / 2**20, 'construct_s': t1 - t0}))
