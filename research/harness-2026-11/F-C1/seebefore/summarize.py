"""Summarize an F-C1 run (cases_results.json) into SUMMARY.json and printed tables.

Two gap notions, never mixed:
  * fire-deadline gap (DEFINITION.md classes): sign decidable only when visible now, or deadline fire-set.
  * displayed-deadline gap: the leave-by the planner DISPLAYS (latest checked departure L < +50 min, i.e. the 147
    cases whose deadline is window- or fire-set) against t_vis. If t_vis > 3600 s in every member (or > L), a resident
    waiting for the fire would not see it before the displayed deadline. This says nothing about the true fire
    deadline when the deadline is window-set (132 of 147).

    python3 seebefore/summarize.py _data/run1/cases_results.json --out _data/run1/SUMMARY.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

PRIMARY = ['flame10@centre_eye2', 'glow150@centre_eye2', 'smoke1000@centre_eye2']


def displayed_class(row, tv):
    L = row['latest_s']
    if L is None or L >= 3000:
        return None
    if all(t is None or t > L for t in tv):
        return 'unseen_before_displayed'          # every member: fire first visible after L (or beyond 1 h)
    if all(t is not None and t <= L for t in tv):
        return 'seen_before_displayed'
    return 'mixed'


def summarize(doc):
    rows = doc['rows']
    tags = sorted({t for r in rows for t in r['results']})
    out = {'n_cases': len(rows), 'n_places': len({(r['region'], r['origin_id']) for r in rows}), 'by_tag': {}}
    for tag in tags:
        ch = tag.split('@')[0]
        rs = [r for r in rows if tag in r['results']]
        if ch.startswith('glow'):
            rs = [r for r in rs if r['light'] != 'day']       # glow only at night / dusk inputs
        cls = Counter(r['results'][tag]['class'] for r in rs)
        disp = Counter(displayed_class(r, r['results'][tag]['t_vis_members_s']) for r in rs)
        disp.pop(None, None)
        vis_now = sum(all(t == 0.0 for t in r['results'][tag]['t_vis_members_s']) for r in rs)
        neg_places = sorted({(r['region'], r['origin_id']) for r in rs if r['results'][tag]['class'] == 'negative'})
        unseen_places = sorted({(r['region'], r['origin_id']) for r in rs
                                if displayed_class(r, r['results'][tag]['t_vis_members_s']) == 'unseen_before_displayed'})
        by_deadline = defaultdict(Counter)
        for r in rs:
            by_deadline[str(r['deadline_set_by'])][r['results'][tag]['class']] += 1
        out['by_tag'][tag] = {'cases': len(rs), 'visible_at_t0': vis_now, 'fire_deadline_class': dict(cls),
                              'fire_deadline_class_by_deadline_set_by': {k: dict(v) for k, v in by_deadline.items()},
                              'displayed_deadline_class': dict(disp),
                              'places_negative': len(neg_places),
                              'places_unseen_before_displayed': len(unseen_places)}
    # case table for the 15 fire-set deadlines and the 21 no-route cases (flame primary)
    tag = PRIMARY[0]
    out['fire_set_cases'] = [
        {k: r[k] for k in ('scope', 'origin_id', 'name', 'latest_s', 'light', 'nearest_present_fire_km')} |
        {'t_vis_members_s': r['results'][tag]['t_vis_members_s'], 'class': r['results'][tag]['class']}
        for r in rows if r['deadline_set_by'] == 'fire_or_limits']
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results', type=Path)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    doc = json.loads(a.results.read_text())
    s = summarize(doc)
    if a.out:
        a.out.write_text(json.dumps(s, indent=1, ensure_ascii=False))
    print(f"cases {s['n_cases']} places {s['n_places']}")
    for tag, v in s['by_tag'].items():
        print(f"{tag:28s} n={v['cases']:3d} visible_t0={v['visible_at_t0']:3d} fire-deadline={v['fire_deadline_class']} "
              f"displayed={v['displayed_deadline_class']} places_neg={v['places_negative']} "
              f"places_unseen_displayed={v['places_unseen_before_displayed']}")
    print('fire-set deadline cases (flame 10 m, centre, eye 2 m):')
    for r in s['fire_set_cases']:
        print('  ', r)


if __name__ == '__main__':
    main()
