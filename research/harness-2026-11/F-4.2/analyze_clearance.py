"""Tabulate CLEARANCE.jsonl (clearance_panel.py) [+ VERIFY.jsonl (verify_witnesses.py)] into the F-4.2 result table.

Per mission: published route clearance (exact geometry, binary64) and its limit; the margin bracket at the published
arrival (lower = max(search witness, published route), upper = r_fail from the relaxed search); trade-off points
(arrival cost vs clearance) for deadlines a0+60/300/600 and the horizon; limiting reason; crop distance.
Time equivalent = clearance / 341 m/h (the bridge's documented front-crossing speed): a labelled conversion only.

  python analyze_clearance.py CLEARANCE.jsonl [--verify VERIFY.jsonl] [--md OUT.md] [--json OUT.json]
"""
import argparse, json, math
from pathlib import Path

SPREAD_M_PER_H = 341.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('clearance', type=Path)
    ap.add_argument('--verify', type=Path)
    ap.add_argument('--md', type=Path); ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    rows = [json.loads(l) for l in a.clearance.read_text().splitlines() if l.strip()]
    ver = {}
    if a.verify and a.verify.exists():
        for l in a.verify.read_text().splitlines():
            v = json.loads(l); ver[(v['mission'], v['deadline'])] = v
    out = []; lines = []
    lines.append('| Mission | Arrival (s) | Published clearance (m) | Limit | Crop distance (m) | Margin bracket at same arrival (m) | +≤60 s | +≤300 s | +≤600 s | Horizon | Time-equivalent at 341 m/h (min) |')
    lines.append('|---|---:|---:|---|---:|---|---|---|---|---|---:|')
    for r in rows:
        pub = r['published_clearance_m']; dom = r['published_domain_distance_m']
        D = {e['deadline_name']: e for e in r['deadlines']}
        e0 = D.get('a0+0', {})
        lo = max(e0.get('r_lo_m') or 0.0, pub if r['a0'] == r['published_arrival'] else 0.0)
        up = e0.get('r_fail_m')
        def pt(name):
            e = D.get(name)
            if not e or e.get('arrival') is None:
                return '—'
            return '%.0f m @ +%d s%s' % (e['clearance_m'], e['arrival'] - r['a0'], '' if e.get('upper_bound_certified', True) else '†')
        label = r['published_limit_label'] + ('/' + r['published_limit_at_endpoint'] if r.get('published_limit_at_endpoint') else '')
        lines.append('| %s | %d | %.1f | %s | %.0f | [%.0f, %s] | %s | %s | %s | %s | %.0f |' % (
            r['mission'], r['published_arrival'], pub, label, dom, lo, ('censored (cap 6000 < published %.0f)' % pub) if up is None else '%.0f' % up,
            pt('a0+60'), pt('a0+300'), pt('a0+600'), pt('horizon'), 60 * pub / SPREAD_M_PER_H))
        best = max((e for e in r['deadlines'] if e.get('arrival') is not None), key=lambda e: e['clearance_m'], default=None)
        out.append({'mission': r['mission'], 'published_arrival': r['published_arrival'], 'published_clearance_m': pub,
                    'published_limit': label, 'domain_distance_m': dom, 'same_arrival_bracket_m': [lo, up],
                    'contact_time_margin_s': r['contact_time_margin_s'],
                    'best_within_600s': {k: (D[k].get('clearance_m'), None if D[k].get('arrival') is None else D[k]['arrival'] - r['a0'])
                                         for k in ('a0+60', 'a0+300', 'a0+600', 'horizon') if k in D},
                    'verified': {k: (ver.get((r['mission'], k)) or {}).get('full_checker_status') for k in D}})
    n = len(rows)
    fire = sum(1 for r in rows if r['published_limit_label'] == 'FIRE')
    crop = sum(1 for r in rows if r['published_limit_label'] == 'CROP')
    small = [o for o in out if o['published_clearance_m'] < 600]
    gain = []
    for o in out:
        for k in ('a0+60', 'a0+300', 'a0+600'):
            c, dt = o['best_within_600s'].get(k, (None, None))
            if c is not None and c >= 1.25 * o['published_clearance_m'] and c - o['published_clearance_m'] >= 100:
                gain.append((o['mission'], o['published_clearance_m'], c, dt, k)); break
    summ = {'missions': n, 'fire_limited': fire, 'crop_or_domain_limited': crop,
            'published_clearance_under_600m': len(small),
            'later_route_with_much_larger_clearance': [{'mission': g[0], 'earliest_m': g[1], 'later_m': g[2], 'extra_s': g[3], 'deadline': g[4]} for g in gain],
            'time_shift_contact_margin_finite': sum(1 for o in out if math.isfinite(o['contact_time_margin_s']))}
    txt = '\n'.join(lines) + '\n\n' + json.dumps(summ, indent=1) + '\n'
    print(txt)
    if a.md:
        a.md.write_text(txt)
    if a.json:
        a.json.write_text(json.dumps({'summary': summ, 'rows': out}, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
