import sys
sys.path.insert(0,'.'); sys.path.insert(0,'tests')
from fractions import Fraction as F
from deadline_field.real import ROOT, PacketModel
from tools.explain_deadlines.geometry import chord_pieces
from test_real_masks import direct_edge, direct_point
DATA = ROOT/'data'/'routing'
for pdir in sorted((DATA/'latest_inputs_try02'/'packets').glob('*_2025/*')):
    pm = PacketModel(DATA/'graphs'/pdir.parent.name/'graph.json', pdir)
    burn = pm.burning; g = pm.g; H = pm.H
    bps = sorted({int(b) for s in range(pm.pk.S) for b in getattr(pm.pk,'breakpoints',[[0,H]])[s]} | {0,H}) if hasattr(pm.pk,'breakpoints') else None
    empty = []
    for j in range(len(g.u)):
        if pm.B['router'][j]: continue
        pieces, points = chord_pieces(g.grid, g.xy(g.u[j]), g.xy(g.v[j]))
        cells = {c for c,_,_ in pieces} | {c for c,_ in points}
        if cells & burn: empty.append(j)
    bad = 0; n = 0
    for j in empty:
        D = g.ticks[j]
        ts = set(range(0, H-D+1, 5))
        for t in sorted(ts):
            n += 1
            if direct_edge(pm, j, t, 'router'):
                bad += 1; print('MISSED BLOCK', pdir.name, j, t); break
    print(pdir.parent.name, pdir.name, 'edges through burning cells with EMPTY router mask', len(empty), 'probes', n, 'missed', bad, flush=True)
