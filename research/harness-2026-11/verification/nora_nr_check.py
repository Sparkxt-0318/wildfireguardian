"""Nora: independent checks of F-DYN v3.6 no-re-entry packets (flame equivalence, array readers)."""
import json, sys, numpy as np
from pathlib import Path
W = Path(sys.argv[1]); D = W / 'research/harness-2026-11/F-DYN/_data'
sys.path[:0] = [str(W), str(W / 'experimental/scenario-members/src'), str(W / 'research/harness-2026-11/F-DYN'),
                str(W / 'integration/kit/runner'), str(W / 'integration/kit/routing_candidate/baseline')]
from fdyn.consistency import check as self_check
from tools.explain_deadlines.packet import Packet as Replay
from tools.explain_deadlines.geometry import Grid
from wfg_scenario_members.contact import ContactModel
import ffi_independent_checker as K
from road_exposure import RoadExposure
pairs = [('yeongdeok_2025', f'20250325T110000Z_h5_{v}_central_q300') for v in ('kriged_mean', 'firms_early', 'envelope', 'envelope_burnset')]
pairs.append(('uiseong_andong_2025', '20250325T170000Z_h5_kriged_mean_central_q300'))
def flame_first(hz):
    out = []
    for m in hz['members']:
        fl = np.array(m['flame'], bool); bp = np.array(m['breakpoints'], float)
        first = np.full(fl.shape[1], np.inf)
        for i in range(fl.shape[0] - 1, -1, -1): first[fl[i]] = bp[i]
        out.append((bp, fl, first))
    return out
def probe(name, f):
    try: r = f(); return f'{name}: OK' + (f' {r}' if r else '')
    except Exception as e: return f'{name}: {type(e).__name__} {str(e)[:90]}'
for reg, p in pairs:
    ro, nr = D / 'packets_v35' / reg / p, D / 'packets_v36_noreentry' / reg / p
    hro, hnr = json.loads((ro / 'HAZARD.json').read_text()), json.loads((nr / 'HAZARD.json').read_text())
    H = float(hnr['valid_until']); print('==', reg, p.split('_central')[0], 'H', H, 'members', len(hnr['members']))
    # (c) flame equivalence: NR flame in bin [l, r) == {cells with reopening birth <= l}; births from reopening HAZARD
    for k, ((bp0, fl0, first0), (bp1, fl1, first1)) in enumerate(zip(flame_first(hro), flame_first(hnr))):
        ends = list(bp1[1:]) + [H] if len(bp1) == fl1.shape[0] else list(bp1[1:])
        mism = sum(int((fl1[i] != (first0 <= bp1[i])).sum()) for i in range(fl1.shape[0]))
        inside = int(sum(((first0 > bp1[i]) & (first0 < ends[i])).sum() for i in range(fl1.shape[0])))
        mism += inside
        print(f'  member {k}: knots reopen {len(bp0)} NR {len(bp1)}; births strictly inside an NR bin {inside}')
        ends_early = int(sum(((fl1[i] & ~fl1[i + 1]).sum()) for i in range(fl1.shape[0] - 1)))
        # births from the reopening npz (non-envelope): ignition plan + present fire at 0
        z = np.load(ro / 'constructed_arrays.npz'); ign = z['ignition_time_s'][k]
        if np.isnan(ign).all(): npz_note = 'reopening npz NaN (HAZARD-only), births from HAZARD only'
        else:
            b = np.where(np.flipud(z['current_active']).ravel(), 0.0, np.flipud(ign).ravel())
            b = np.where(np.isfinite(b) & (b < H), np.floor(b / 300) * 300, np.inf)
            npz_note = f'npz births vs reopening HAZARD first-flame: {int((b != first0).sum())} diffs'
        print(f'  member {k}: bins {fl1.shape[0]} NR-vs-births mismatches {mism}; NR cells leaving flame before H {ends_early}; '
              f'NR flame cells {int(np.isfinite(first1).sum())} = reopening ever-flame {int(np.isfinite(first0).sum())}; {npz_note}')
    # (b) self-check and (d) array readers
    for tag, d in (('reopen', ro), ('NR', nr)):
        sc = self_check(d)
        g = hnr['grid']; grid = Grid(g['x0'], g['y0'], g['resolution'], g['width'], g['height'])
        gj = json.loads((W / f'research/harness-2026-11/F-DYN/_data/graphs_interim/{reg}/graph.json').read_text())
        z = np.load(d / 'constructed_arrays.npz'); rep = json.loads((d / 'REPORT.json').read_text())
        asm = rep['native_metadata']['construction']['assumptions']; aff = rep['native_metadata']['affine_transform']
        res = [f"self_check consistent={sc.get('consistent')} {sc.get('array_path', '')}",
               probe('replay Packet', lambda: Replay(d, grid).verify_consistency()['status']),
               probe('ContactModel.from_packet', lambda: type(ContactModel.from_packet(d)).__name__),
               probe('kit checker Packet', lambda: (K.Packet(d, K.Graph(gj)), '')[1]),
               probe('RoadExposure', lambda: (RoadExposure(np.array(z['ignition_time_s']), np.array(z['current_active']), dict(asm), tuple(aff)), '')[1])]
        print(f'  [{tag}] ' + ' | '.join(res))
