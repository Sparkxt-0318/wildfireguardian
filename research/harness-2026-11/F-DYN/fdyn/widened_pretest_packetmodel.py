"""WIDENED_GRAPH_RULE.md §8(iii)4 pre-build test: does the routing author's PacketModel load an F-9.3 support-masked packet?

Pass: the masked packet loads and its Instance B/W/A arrays equal those of the unmasked twin. Refusal stops the work
(the rule returns to the orchestrator; PacketModel is not patched here).

    python3 fdyn/widened_pretest_packetmodel.py --f31 <routing-author worktree>/research/harness-2026-11/F-3.1 \
        --graph GRAPH.json --plain PLAIN_PACKET --masked MASKED_PACKET --out results/WIDENED_PRETEST_PACKETMODEL.json
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    for k in ('--f31', '--graph', '--plain', '--masked', '--out'):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(a.f31))
    from deadline_field.real import PacketModel
    head = subprocess.run(['git', '-C', str(a.f31), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    out = {'rule': 'WIDENED_GRAPH_RULE.md §8(iii)4', 'packetmodel_head': head,
           'graph_sha256': hashlib.sha256(a.graph.read_bytes()).hexdigest()}
    models = {}
    for tag, p in (('plain', a.plain), ('masked', a.masked)):
        with np.load(p / 'constructed_arrays.npz', allow_pickle=False) as z:
            nf = int((~z['support'].astype(bool)).sum())
        r = {'npz_sha256': hashlib.sha256((p / 'constructed_arrays.npz').read_bytes()).hexdigest(), 'support_false': nf}
        try:
            models[tag] = PacketModel(a.graph, p)
            r['result'] = 'LOADED'
        except Exception as e:                       # noqa: BLE001 - the refusal is the measured outcome
            r['result'] = 'REFUSED'
            r['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
        out[tag] = r
    if len(models) == 2:
        from fractions import Fraction
        P, M = models['plain'], models['masked']
        out['B_identical'] = P.B == M.B                     # edge blocks, router and closed rules
        inst = json.loads((Path(__file__).resolve().parents[1] / '_data' / 'INSTANCE.json').read_text())['instances']
        dests = sorted({(d['node'], d['dwell_s']) for i in inst if i['region'] == P.raw.get('region', i['region'])
                        for o in i['origins'] for d in o['destinations'] if d['node'] in P.nidx})
        w_same = all(P.point_blocks(n, Fraction(1), r) == M.point_blocks(n, Fraction(1), r)
                     for n in P.node_ids if P.g.waitable[n] for r in ('router', 'closed'))
        a_same = all(P.point_blocks(n, Fraction(dw), r) == M.point_blocks(n, Fraction(dw), r)
                     for n, dw in dests for r in ('router', 'closed'))
        out['W_point_blocks_identical'] = w_same              # wait blocks (W) at every waitable node
        out['A_destination_blocks_identical'] = a_same        # destination dwell blocks (A) at INSTANCE destinations
        out['destinations_compared'] = len(dests)
        out['masked_attrs'] = {k: (len(v) if hasattr(v, '__len__') and not isinstance(v, (str, bool)) else v)
                               for k, v in ((a, getattr(M, a, None)) for a in ('support_masked', 'support_false_cells'))}
        out['pass'] = bool(out['B_identical'] and w_same and a_same)
    else:
        out['pass'] = False
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out))


if __name__ == '__main__':
    main()
