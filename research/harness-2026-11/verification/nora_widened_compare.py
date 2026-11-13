"""Independent verifier: classes from my widened-graph runs (own derivation from the exact CERT feasible sets) vs the
author's WIDENED_RESULTS_UA per_place; also P4/P6 from the sets. argv: work dir, WIDENED_RESULTS_UA.json"""
import json, sys, glob, collections
work, his = sys.argv[1:3]
H = {(r['start'], r['horizon_h'], r['variant'], r['entry_node']): r for r in json.load(open(his))['per_place']}
def nonempty(ivs, grid=None):
    if grid is None: return bool(ivs)
    return any(a <= t <= b for a, b in ivs for t in grid)          # closed intervals [a, b] in seconds
C = collections.Counter(); mism = []; P = collections.Counter()
for f in sorted(glob.glob(work + '/candidates/*/*.json')):
    d = json.load(open(f)); s, h = d['start'], d['horizon_h']; v = f.split('_h%d_' % h)[1][:-5]
    grid = list(range(0, h * 3600 + 1, 1800))
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for arm, sets in d['sets'].items():
        for k, ivs in sets.items():
            rule, ent, dest, dw = k.split('|')
            if rule == 'cert': by[ent][arm].append(ivs)
    for ent, arms in by.items():
        any_ = lambda arm, g=None: any(nonempty(x, g) for x in arms.get(arm, []))
        mine = 'route found' if any_('b_closed') else 'undetermined' if any_('b_open') else 'no route'
        mine_grid = 'route found' if any_('b_closed', grid) else 'undetermined' if any_('b_open', grid) else 'no route'
        r = H.get((s, h, v, ent)); hc = r['class'].split(' by')[0].split(':')[0] if r else None
        hc = 'route found' if r and r['class'].startswith('route found') else 'undetermined' if r and r['class'].startswith('undetermined') else 'no route' if r else 'ABSENT'
        C[(mine, hc)] += 1
        if mine != hc or mine_grid != mine: mism.append((s, h, v, ent, mine, mine_grid, hc))
        for flag, arm in (('g1', 'g1'), ('a_closed', 'a_closed'), ('b_closed', 'b_closed')):
            if r is not None and r[flag] != any_(arm): mism.append(('flag', flag, s, h, v, ent, r[flag], any_(arm)))
    P['P4 violations'] += d['P4']['violations']; P['P4-open violations'] += d['P4_open']['violations']
    P['P6 viol'] += sum(x['closed_subset_open_violations'] + x['closed_witness_touching_padding'] for x in d['P6'].values())
    P['files'] += 1
print('files/P', dict(P)); print('(mine, his) classes', dict(C)); print('mismatches', len(mism)); [print(' ', m) for m in mism[:12]]
