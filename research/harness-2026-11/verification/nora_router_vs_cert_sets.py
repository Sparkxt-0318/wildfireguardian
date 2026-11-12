# Router vs CERT feasible departure sets per (destination spec, origin), whole [0, H] (not only sampled job departures)
import json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, '.')
from deadline_field import intervals as iv
from deadline_field.core import backward, issue_set
from deadline_field.real import PacketModel
D = Path('../../../data/routing')
for cache in sys.argv[1:]:
    doc = json.loads(Path(cache).read_text()); region, compact = doc['region_id'], doc['input_time'].replace('-', '').replace(':', '')
    pm = PacketModel(D / 'graphs' / region / 'graph.json', D / 'latest_inputs_try02/packets' / region / compact)
    specs = defaultdict(set)
    for k, job in doc['route_checks'].items():
        q = job['request']; specs[(q['destination']['node_id'], q['dwell_s'], tuple(q['destination_window']))].add(q['start']['node_id'])
    n = eq = sup = viol = 0; extra_s = 0
    for spec in sorted(specs, key=str):
        f = {v: backward(pm.instance(v, [{'node': spec[0], 'dwell': spec[1], 'window': list(spec[2])}], sorted(specs[spec]))) for v in ('cert', 'router')}
        for o in specs[spec]:
            c, r = issue_set(f['cert'], pm.nidx[o]), issue_set(f['router'], pm.nidx[o])
            n += 1
            measure = lambda s: sum(b - a + 1 for a, b in iv.normalize(s))
            if iv.normalize(c) == iv.normalize(r): eq += 1
            else:
                inter = sum(1 for p in c)  # placeholder
                mc, mr = measure(c), measure(r)
                if mr > mc: sup += 1; extra_s += mr - mc
                else: viol += 1
    print(region, compact, 'pairs', n, 'identical', eq, 'router strictly larger', sup, '(extra seconds total %d)' % extra_s, 'router smaller/other', viol, flush=True)
