"""Nora: Marcus's fbase_static.no_reentry (EB := [min EB, H]) on the reopening O2 instance vs the O2 instance built
directly from Leo's v3.6 no-re-entry packet (scalar law T = R = H, verified = Richard's never-clears, row 56)."""
import json, sys, glob, os, hashlib
sys.path.insert(0, 'research/harness-2026-11/F-3.2'); sys.path.insert(0, sys.argv[4])
import generate, fbase, fbase_static as FS
from wfg_scenario_members.contact import ContactModel
from wfg_sipp.frontend import build_instance
P_RO, P_NR, REQDIR, _, GRAPH = sys.argv[1:6]
graph = json.load(open(GRAPH))
m_ro, m_nr = ContactModel.from_packet(P_RO), ContactModel.from_packet(P_NR)
id_ro = json.load(open(P_RO + '/HAZARD.json'))['members'][0]['id']; id_nr = json.load(open(P_NR + '/HAZARD.json'))['members'][0]['id']
tot = dict(req=0, eb_eq=0, wb_eq=0, verdict_eq=0)
for f in sorted(glob.glob(REQDIR + '/*.json')):
    q = json.load(open(f))
    i_ro, _ = build_instance(graph, q, m_ro); _, _, b_ro, _, _ = generate.certify(i_ro)
    s = json.dumps(q).replace(id_ro, id_nr); q2 = json.loads(s)
    i_nr, _ = build_instance(graph, q2, m_nr); c_nr, T_nr, b_nr, _, _ = generate.certify(i_nr)
    A = FS.no_reentry(fbase.parse_instance(b_ro)); B = fbase.parse_instance(b_nr)
    norm = lambda d: {k: [tuple(x) for x in v] for k, v in d.items() if v}
    # compare on the starts that matter: an EDGE start a needs a + D_j <= H; a WAIT start needs a < H
    def clipE(d, I):
        out = {}
        for j, v in d.items():
            lim = I.H - I.D[j]
            w = [(a, min(b, lim)) for a, b in v if a <= lim]
            if w: out[j] = w
        return out
    def clipW(d, I):
        return {n: [(a, min(b, I.H - 1)) for a, b in v if a <= I.H - 1] for n, v in d.items() if any(a <= I.H - 1 for a, _ in v)}
    eb = norm(clipE(A.EB, A)) == norm(clipE(B.EB, B)); wb = norm(clipW(A.WB, A)) == norm(clipW(B.WB, B))
    raw_eb = norm(A.EB) == norm(B.EB)
    ea = list(fbase.solve_exact(A)[:2]); eb_ = list(fbase.solve_exact(B)[:2])
    tot['req'] += 1; tot['eb_eq'] += eb; tot['wb_eq'] += wb; tot['verdict_eq'] += ea == eb_
    print(os.path.basename(f), "raw_EB_eq", raw_eb, "EB_eq(clipped)", eb, "WB_eq", wb, "exact", ea, eb_, flush=True)
    if not (eb and wb and ea == eb_):
        cA, cB = norm(clipE(A.EB, A)), norm(clipE(B.EB, B)); dE = {k for k in set(cA) | set(cB) if cA.get(k) != cB.get(k)}
        print(os.path.basename(f), 'EB diff edges', len(dE), [(k, cA.get(k), cB.get(k), A.D[k]) for k in sorted(dE)[:3]], 'WB eq', wb, 'exact', ea, eb_, 'sipp_nr', c_nr, T_nr)
print(tot)
