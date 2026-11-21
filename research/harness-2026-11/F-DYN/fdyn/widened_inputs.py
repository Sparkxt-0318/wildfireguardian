"""WIDENED_GRAPH_RULE.md §7/§8 input checks, before any routing run (no fire, no routes).

Per old window (uiseong_andong_2025, yeongdeok_2025), from the rebuilt step-1 graph and the widened graph:
  1  INSTANCE membership: every entry_node and destination node id (all starts) in the step-1 node set, and in the
     widened node set; absent ids -> place "not located on the 2025-01-01 graph" (listed)
  2  arm (a) waitable dict: {node id: step-1 waitable} for every node in both graphs (§7 'How the arm (a) dict is built');
     step-1-waitable nodes absent from the widened graph are listed (expected 0); the in-window delta is recomputed and
     compared with STEP2_WAITABLE_DELTA.json @ ccc1de58 (removed / added lists)
  3  identical edges (id, u, v, direction_evidence, travel_ticks, segments mapped to absolute col,row within 1e-9):
     counts of step-1 edges identical / differing / absent in the widened graph
  4  §8(v): forbidden-turn pairs on identical edges that the widened graph forbids and step 1 does not (count + list)

    python3 -I fdyn/widened_inputs.py --step1 UA.json YD.json --widened KFS.json --instance _data/INSTANCE.json \
        --waitable-delta STEP2_WAITABLE_DELTA.json --out results/WIDENED_INPUTS.json --arm-a-out results/WIDENED_ARM_A_WAITABLE.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

X0W, Y0W, RES = 1080000.0, 1810500.0, 375.0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def absseg(segs, gr):
    ox = round((gr['x0'] - X0W) / RES)
    oy = round((gr['y0'] - Y0W) / RES)
    return [((s['cell'] % gr['width']) + ox, (s['cell'] // gr['width']) + oy, s['start'], s['end']) for s in segs]


def same_edge(a, b, ga, gb):
    if any(a[k] != b[k] for k in ('u', 'v', 'travel_ticks', 'direction_evidence')):
        return False
    sa, sb = absseg(a['segments'], ga), absseg(b['segments'], gb)
    return len(sa) == len(sb) and all(p[0] == q[0] and p[1] == q[1] and abs(p[2] - q[2]) <= 1e-9 and abs(p[3] - q[3]) <= 1e-9
                                      for p, q in zip(sa, sb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--step1', nargs=2, type=Path, required=True, help='UA then YD step-1 graph')
    ap.add_argument('--widened', type=Path, required=True)
    ap.add_argument('--instance', type=Path, required=True)
    ap.add_argument('--waitable-delta', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--arm-a-out', type=Path, required=True)
    a = ap.parse_args()
    W = json.loads(a.widened.read_text())
    WN = {n['id']: n for n in W['nodes']}
    WE = {e['id']: e for e in W['edges']}
    WF = {tuple(p) for p in W['forbidden_turns']}
    inst = json.loads(a.instance.read_text())['instances']
    delta = json.loads(a.waitable_delta.read_text())['windows']
    out = {'rule': 'WIDENED_GRAPH_RULE.md §7, §8', 'label': 'roads as of 2025-01-01 (before the March 2025 fires)',
           'inputs': {'widened': {'file': a.widened.name, 'sha256': sha(a.widened)},
                      'instance': {'file': str(a.instance), 'sha256': sha(a.instance)},
                      'waitable_delta': {'file': a.waitable_delta.name, 'sha256': sha(a.waitable_delta)}},
           'windows': {}}
    arm_a = {}
    for region, p in zip(('uiseong_andong_2025', 'yeongdeok_2025'), a.step1):
        S = json.loads(p.read_text())
        assert S['grid']['resolution'] == RES
        SN = {n['id']: n for n in S['nodes']}
        SE = {e['id']: e for e in S['edges']}
        r = {'step1': {'file': p.name, 'sha256': sha(p), 'nodes': len(SN), 'edges': len(SE)}}
        # 1 membership
        ids = {}
        for i in inst:
            if i['region'] != region:
                continue
            for o in i['origins']:
                ids.setdefault(o['entry_node'], set()).add(('entry', o['origin_id'], i['start_tag']))
                for d in o['destinations']:
                    ids.setdefault(d['node'], set()).add(('destination', o['origin_id'], i['start_tag']))
        miss1 = sorted(k for k in ids if k not in SN)
        missw = sorted(k for k in ids if k not in WN)
        r['membership'] = {'ids_checked': len(ids),
                           'absent_from_step1': [{'id': k, 'uses': sorted(map(list, ids[k]))} for k in miss1],
                           'absent_from_widened': missw,
                           'places_not_located': sorted({u[1] for k in miss1 for u in ids[k]})}
        # 2 arm (a) dict and delta recomputation
        both = [k for k in SN if k in WN]
        for k in both:
            if k in arm_a and arm_a[k] != SN[k]['waitable']:
                raise SystemExit('arm (a) conflict between windows at %s' % k)
            arm_a[k] = bool(SN[k]['waitable'])
        gr = S['grid']
        X1, Y1 = gr['x0'] + gr['width'] * RES, gr['y0'] + gr['height'] * RES
        inwin = [k for k, n in WN.items() if gr['x0'] <= n['x'] < X1 and gr['y0'] <= n['y'] < Y1]
        s1w = {k for k in SN if SN[k]['waitable']}
        ww = {k for k in inwin if WN[k]['waitable']}
        removed, added = sorted(s1w - ww), sorted(ww - s1w)
        dw = delta[region]
        r['arm_a'] = {'nodes_in_both': len(both), 'step1_waitable': len(s1w),
                      'step1_waitable_absent_from_widened': sorted(k for k in s1w if k not in WN),
                      'widened_waitable_in_window': len(ww), 'removed': len(removed), 'added': len(added),
                      'equals_STEP2_WAITABLE_DELTA': removed == sorted(dw['removed']) and added == sorted(dw['added'])}
        # 3 identical edges
        ident = [e for e in SE if e in WE and same_edge(SE[e], WE[e], gr, W['grid'])]
        r['edges'] = {'identical': len(ident), 'differing': sum(1 for e in SE if e in WE) - len(ident),
                      'absent_from_widened': sum(1 for e in SE if e not in WE)}
        # 4 forbidden turns added by the widened graph on identical edges (§8 v)
        I = set(ident)
        SF = {tuple(t) for t in S['forbidden_turns']}
        extra = sorted(t for t in WF if t[0] in I and t[1] in I and t not in SF)
        r['forbidden_turns_added_on_identical_edges'] = {'count': len(extra), 'pairs': [list(t) for t in extra]}
        out['windows'][region] = r
        print(region, json.dumps({k: (v if k != 'forbidden_turns_added_on_identical_edges' else v['count'])
                                  for k, v in r.items() if k != 'step1'})[:1500])
    a.arm_a_out.write_text(json.dumps(dict(sorted(arm_a.items())), separators=(',', ':')))
    out['arm_a_dict'] = {'file': a.arm_a_out.name, 'sha256': sha(a.arm_a_out), 'entries': len(arm_a)}
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print('arm_a', out['arm_a_dict'])


if __name__ == '__main__':
    main()
