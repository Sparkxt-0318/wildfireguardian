"""WIDENED_GRAPH_RULE.md router-only runner (§8(iii)4): one (region, start, horizon, variant) packet pair, one process.

Never calls full_check or headline.py's witness check (padded packets are refused there by design, P5).
Uses the routing author's PacketModel + deadline-field solver (claude/f31-deadline-field, support-aware read path).

Per (place entry node, destination, dwell) it computes exact CERT-feasible departure sets (interval sets, s):
  old side (v3.7 `/2` packet on the export grid):  F(G1), F(G1')       [G1'' == G1' when no G1 geometry touches padding]
  widened side (padded packet):  waiting (a) x padding {closed, open},  waiting (b) x padding {closed, open};
                                 plus ROUTER-rule sets on the padding-closed arm (refusal claims, §2.3)
and asserts:
  P4      F(G1') ⊆ F(widened, (a), closed)       P4-open  F(G1'') ⊆ F(widened, (a), open)
  P6      F(widened, x, closed) ⊆ F(widened, x, open) for both waiting arms, and a closed-arm witness at each union's
          latest departure touches no padding cell
One PacketModel in memory at a time (the routing author's YD OOM note); peak RSS recorded.

    python3 fdyn/widened_run.py --f31 F31_DIR --region R --start TAG --horizon-h 5 --old-packet P37 --new-packet PW \
        --g1 G1.json --g1p G1p.json --widened KFS.json --arm-a WIDENED_ARM_A_WAITABLE.json --instance _data/INSTANCE.json \
        --places ALL|id,id,... --out ROW.json
"""
from __future__ import annotations

import argparse
import gc
import json
import resource
import sys
import time
from pathlib import Path

PAD = 14


def rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def padding_cells(grid):
    W, H = grid['width'], grid['height']
    return [r * W + c for r in range(H) for c in range(W) if r < PAD or r >= H - PAD or c < PAD or c >= W - PAD]


def main():
    ap = argparse.ArgumentParser()
    for k in ('--f31', '--old-packet', '--new-packet', '--g1', '--g1p', '--widened', '--arm-a', '--instance', '--out'):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument('--region', required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--horizon-h', type=int, required=True)
    ap.add_argument('--places', default='ALL')
    ap.add_argument('--arms', default='g1,g1p,a_closed,a_open,b_closed,b_open')
    a = ap.parse_args()
    sys.path.insert(0, str(a.f31))
    from deadline_field import intervals as iv
    from deadline_field.core import backward, issue_set, witness_greedy
    from deadline_field.real import PacketModel

    inst = [i for i in json.loads(a.instance.read_text())['instances']
            if i['region'] == a.region and i['start_tag'] == a.start and i['horizon_s'] == a.horizon_h * 3600]
    if len(inst) != 1:
        raise SystemExit(f'INSTANCE entries for {a.region} {a.start} h{a.horizon_h}: {len(inst)}')
    inst = inst[0]
    places = None if a.places == 'ALL' else set(a.places.split(','))
    origins = [o for o in inst['origins'] if places is None or o['origin_id'] in places]
    wide = json.loads(a.widened.read_text())
    pad = padding_cells(wide['grid'])
    arm_a = json.loads(a.arm_a.read_text())
    arm_a = {k: v for k, v in arm_a.items()}
    out = {'rule': 'WIDENED_GRAPH_RULE.md §8', 'label': 'roads as of 2025-01-01 (before the March 2025 fires); '
           'router-only, not independently checked; no fire data outside the export grid; not shown safe',
           'region': a.region, 'start': a.start, 'horizon_h': a.horizon_h, 'old_packet': str(a.old_packet),
           'new_packet': str(a.new_packet), 'places': len(origins), 'arms': {}, 'timing_s': {}, 'peak_rss_mib': {}}
    specs = {}
    for o in origins:
        for d in o['destinations']:
            specs.setdefault((d['node'], d['dwell_s']), set()).add(o['entry_node'])
    window = [0, a.horizon_h * 3600]
    arms = {'g1': (a.g1, a.old_packet, {}, None, ('cert',)),
            'g1p': (a.g1p, a.old_packet, {}, None, ('cert',)),
            'a_closed': (a.widened, a.new_packet, {c: 0 for c in pad}, arm_a, ('cert', 'router')),
            'a_open': (a.widened, a.new_packet, {}, arm_a, ('cert',)),
            'b_closed': (a.widened, a.new_packet, {c: 0 for c in pad}, None, ('cert', 'router')),
            'b_open': (a.widened, a.new_packet, {}, None, ('cert',))}
    sel = a.arms.split(',')
    F = {}
    padset = set(pad)
    for name in sel:
        graph, packet, extra, wov, variants = arms[name]
        t0 = time.perf_counter()
        pm = PacketModel(graph, packet, extra_blocks=extra or None, waitable_override=wov)
        res, missing, wit = {}, [], {}
        for (dnode, dwell), ents in sorted(specs.items()):
            if dnode not in pm.nidx:
                missing.append(dnode)
                continue
            for var in variants:
                I = pm.instance(var, [{'node': dnode, 'dwell': dwell, 'window': window}],
                                sorted(e for e in ents if e in pm.nidx))
                fld = backward(I)
                for e in ents:
                    if e not in pm.nidx:
                        missing.append(e)
                        continue
                    f = issue_set(fld, pm.nidx[e])
                    res[f'{var}|{e}|{dnode}|{dwell}'] = [list(p) for p in f]
                    if var == 'cert' and name.endswith('_closed') and f:   # P6: witness at the latest departure
                        w = witness_greedy(fld, pm.nidx[e], f[-1][1])
                        cells = set()
                        for k, x, _a, _b in w[1]:
                            if k == 'EDGE':                  # closed-rule cells of each witness edge
                                p0, p1 = pm.g.xy(pm.g.u[x]), pm.g.xy(pm.g.v[x])
                                cells.update(pm.g.grid.cells_touching_box(min(p0[0], p1[0]), max(p0[0], p1[0]),
                                                                          min(p0[1], p1[1]), max(p0[1], p1[1])))
                        wit[f'{e}|{dnode}|{dwell}'] = bool(cells & padset)
        F[name] = res
        out['arms'][name] = {'sets': len(res), 'missing_ids': sorted(set(missing)),
                             'witness_touches_padding': sum(wit.values()) if wit else 0, 'witnesses': len(wit)}
        out['timing_s'][name] = time.perf_counter() - t0
        out['peak_rss_mib'][name] = rss_mib()
        del pm
        gc.collect()

    def sub(x, y):                       # x \ y, as interval sets
        return iv.subtract_all(iv.normalize([tuple(p) for p in x]), iv.normalize([tuple(p) for p in y]))

    def measure(s):
        return sum(b - a_ + 1 for a_, b in s)

    def contain(small, big, var='cert'):
        bad, n, ne, sec = [], 0, 0, 0
        for k, v in F[small].items():
            if not k.startswith(var + '|'):
                continue
            n += 1
            ne += bool(v)
            sec += measure(v)
            d = sub(v, F[big].get(k, []))
            if d:
                bad.append({'key': k, 'lost': [list(p) for p in d]})
        return {'triples': n, 'nonempty': ne, 'departure_seconds': sec, 'violations': len(bad), 'detail': bad[:50]}

    if {'g1p', 'a_closed'} <= set(sel):
        out['P4'] = contain('g1p', 'a_closed')
    if {'g1p', 'a_open'} <= set(sel):
        out['P4_open'] = contain('g1p', 'a_open')        # G1'' == G1' here (no G1 geometry touches padding)
    if {'g1', 'g1p'} <= set(sel):
        lost = contain('g1', 'g1p')
        out['G1_minus_G1p'] = {'triples_with_loss': lost['violations'], 'detail': lost['detail']}
        g1sec = sum(measure(v) for k, v in F['g1'].items() if k.startswith('cert|'))
        out['coverage'] = {'g1_departure_seconds': g1sec,
                           'g1p_departure_seconds': out.get('P4', {}).get('departure_seconds'),
                           'ratio': (out['P4']['departure_seconds'] / g1sec) if g1sec and 'P4' in out else None,
                           'g1p_nonempty_triples': out.get('P4', {}).get('nonempty')}
    p6 = {}
    for w in ('a', 'b'):
        if {f'{w}_closed', f'{w}_open'} <= set(sel):
            c = contain(f'{w}_closed', f'{w}_open')
            p6[w] = {'closed_subset_open_violations': c['violations'],
                     'closed_witness_touching_padding': out['arms'][f'{w}_closed']['witness_touches_padding']}
    out['P6'] = p6
    out['sets'] = F
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out))
    print(json.dumps({k: v for k, v in out.items() if k != 'sets'})[:3000])


if __name__ == '__main__':
    main()
