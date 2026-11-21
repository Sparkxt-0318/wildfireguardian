"""Nora: (d) no_reentry reading — Marcus's transform (EB := [min EB, H] on the as-built O2 instance) vs the true
no-re-entry instance (built from Leo's v3.6 no_reentry packet = Richard's never-clears, row 56), on Marcus's sampled
requests. Compares exact, S1, S2 verdicts."""
import json, sys, os
sys.path.insert(0, 'research/harness-2026-11/F-3.2'); sys.path.insert(0, sys.argv[5])
import generate, fbase, fbase_static as FS
from wfg_scenario_members.contact import ContactModel
from wfg_sipp.frontend import build_instance
P_RO, P_NR, REQDIR, CJSONL, _, GRAPH = sys.argv[1:7]
graph = json.load(open(GRAPH))
m_ro, m_nr = ContactModel.from_packet(P_RO), ContactModel.from_packet(P_NR)
id_ro = json.load(open(P_RO + '/HAZARD.json'))['members'][0]['id']; id_nr = json.load(open(P_NR + '/HAZARD.json'))['members'][0]['id']
rows = [json.loads(l) for l in open(CJSONL)][1:]
for r in rows:
    f = os.path.join(REQDIR, f"{r['origin']}__d{r['departure']}.json"); q = json.load(open(f))
    i_ro, _ = build_instance(graph, q, m_ro); _, _, b_ro, _, _ = generate.certify(i_ro)
    q2 = json.loads(json.dumps(q).replace(id_ro, id_nr)); i_nr, _ = build_instance(graph, q2, m_nr); _, _, b_nr, _, _ = generate.certify(i_nr)
    A = FS.no_reentry(fbase.parse_instance(b_ro)); B = fbase.parse_instance(b_nr)
    out = {}
    for name, I in (('marcus', A), ('true_nr', B)):
        out[name] = dict(exact=list(fbase.solve_exact(I)[:2]), s1=list(FS.solve_static(I, 'S1')[:2]), s2=list(FS.solve_static(I, 'S2')[:2]))
    print(json.dumps({'origin': r['origin'], 'dep': r['departure'], 'same': out['marcus'] == out['true_nr'], **out}), flush=True)
