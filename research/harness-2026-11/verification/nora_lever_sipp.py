# Independent check of lever B = 0 / lever A rescue with Thomas's SIPP (router rule; cert is stricter, so router NO_ROUTE => cert NO_ROUTE)
import json, sys
sys.path.insert(0, 'research/harness-2026-11/F-3.2')
import generate
from wfg_scenario_members.contact import ContactModel
from wfg_sipp.frontend import build_instance
L, F, P, REQ, REGION, START, HS = sys.argv[1:8]
HS = int(HS)
lev = json.load(open(L)); inst = json.load(open(F + '/_data/INSTANCE.json'))
I = next(i for i in inst['instances'] if i['region'] == REGION and i['horizon_s'] == HS and i['start_tag'] == START)
tmpl = json.load(open(REQ))
graph = json.load(open(F + f'/_data/graphs_interim/{REGION}/graph.json'))
model = ContactModel.from_packet(P)
dall = sorted({(d['node'], d['dwell_s']) for o in I['origins'] for d in o['destinations']})
def solve(o, dests, dep):
    q = dict(tmpl); q['departure'] = dep; q['position'] = {'node': o['entry_node']}
    q['destinations'] = [{'dwell': dw, 'node': n, 'open_intervals': [[0, HS]]} for n, dw in dests]
    inst_, _ = build_instance(graph, q, model); claim, T, *_ = generate.certify(inst_)
    return claim, T
for s in ('30', '60', '120'):
    for oid, r in lev['primary'][s]['rows'].items():
        if r['class'] == 'checked_at_ref': continue
        o = next(x for x in I['origins'] if x['origin_id'] == oid)
        own = [(d['node'], d['dwell_s']) for d in o['destinations']]
        b = solve(o, dall, 9000); base = solve(o, own, 9000)
        a = solve(o, own, 9000 - int(s) * 60)
        print(s, oid, r['class'], '| router: own@9000', base, '| all 30 @9000', b, '| own @', 9000 - int(s) * 60, a, flush=True)
