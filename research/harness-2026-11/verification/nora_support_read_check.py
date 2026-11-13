"""Independent verifier: SUPPORT_READ path. Run inside an F-3.1 tree (cwd = .../F-3.1).
argv: graph, instance_json, region, start_tag, packet_dir [packet_dir ...]
Prints per packet: load result, support_masked, n support_false_cells, and a digest of every instance
(CERT and ROUTER, each destination of the first 4 origins, window [0, H)) plus the per-rule edge blocks B."""
import json, sys, hashlib
from fractions import Fraction
sys.path.insert(0, '.')
from deadline_field.real import PacketModel
G, IJ, region, start = sys.argv[1:5]
inst = [i for i in json.load(open(IJ))['instances'] if i['region'] == region and i['start_tag'] == start][0]
def dig(o):
    h = hashlib.sha256()
    def walk(x):
        if isinstance(x, dict):
            for k in sorted(x, key=str): h.update(repr(k).encode()); walk(x[k])
        elif isinstance(x, (list, tuple)):
            h.update(b'['); [walk(y) for y in x]; h.update(b']')
        elif hasattr(x, 'tobytes'): h.update(x.tobytes())
        elif hasattr(x, '__dict__') and not isinstance(x, type): walk(vars(x))
        else: h.update(repr(x).encode())
    walk(o); return h.hexdigest()[:16]
for pd in sys.argv[5:]:
    try:
        pm = PacketModel(G, pd)
    except Exception as ex:
        print(pd.split('/')[-1], 'REFUSED', type(ex).__name__, str(ex)[:120]); continue
    out = {'masked': getattr(pm, 'support_masked', None), 'n_false': len(getattr(pm, 'support_false_cells', [])), 'B': dig(pm.B)}
    for rule in ('cert', 'router'):
        ds = []
        for o in inst['origins'][:4]:
            for d in o['destinations']:
                x = pm.instance(rule, [{'node': d['node'], 'dwell': d['dwell_s'], 'window': [0, pm.H]}], [o['entry_node']])
                ds.append(dig({k: v for k, v in vars(x).items()}))
        out[rule] = hashlib.sha256('|'.join(ds).encode()).hexdigest()[:16] + f' ({len(ds)} inst)'
    import tools.explain_deadlines.packet as _pm, numpy
    out['np_restored'] = _pm.np is numpy
    if getattr(pm, 'support_masked', False):
        from deadline_field.verify import full_check
        hz = json.load(open(pd + '/HAZARD.json'))
        o = inst['origins'][0]; d = o['destinations'][0]
        r = full_check(pm, hz, origin=o['entry_node'], legs=[], dest=d['node'], dwell=d['dwell_s'], window=(0, pm.H), departure=0)
        out['full_check'] = r['full_status']
    print(pd.split('/')[-1], json.dumps(out), flush=True)
