"""Summarize an F-C1 v2 run (cases_results.json): per channel (flame, smoke) and setting (optimistic, pessimistic,
robust), class counts over all cases, by deadline class, and with observers flagged non-ground excluded.

The planner-cache F-C1 is a NEGATIVE result by design (DEFINITION.md v2): it reports how many cases are decidable.

    python3 seebefore/summarize.py _data/run_v2/cases_results.json --out _data/run_v2/SUMMARY.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def summarize(doc):
    rows = doc['rows']
    out = {'n_cases': len(rows), 'n_places': len({(r['region'], r['origin_id']) for r in rows}),
           'settings': doc.get('settings'),
           'observer_nonground_places': len({(r['region'], r['origin_id']) for r in rows if r['observer_nonground']}),
           'deadline_set_by': dict(Counter(str(r['deadline_set_by']) for r in rows)), 'by_tag': {}}
    tags = sorted({t for r in rows for t in r['results']})
    for tag in tags:
        cls = Counter(r['results'][tag]['class'] for r in rows)
        cls_ground = Counter(r['results'][tag]['class'] for r in rows if not r['observer_nonground'])
        by_deadline = defaultdict(Counter)
        for r in rows:
            by_deadline[str(r['deadline_set_by'])][r['results'][tag]['class']] += 1
        neg_places = sorted({(r['region'], r['origin_id']) for r in rows
                             if r['results'][tag]['class'] in ('negative', 'robust_negative')})
        out['by_tag'][tag] = {'class': dict(cls), 'class_ground_observers_only': dict(cls_ground),
                              'by_deadline_set_by': {k: dict(v) for k, v in by_deadline.items()},
                              'places_with_negative': len(neg_places)}
    out['fire_set_cases'] = [
        {k: r[k] for k in ('scope', 'origin_id', 'name', 'latest_s', 'light', 'nearest_present_fire_km',
                           'observer_nonground')} |
        {t: r['results'][t].get('t_vis_members_s', r['results'][t]['class']) for t in r['results']} |
        {t + ':class': r['results'][t]['class'] for t in r['results']}
        for r in rows if r['deadline_set_by'] == 'fire_or_limits']
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results', type=Path)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    s = summarize(json.loads(a.results.read_text()))
    if a.out:
        a.out.write_text(json.dumps(s, indent=1, ensure_ascii=False))
    print(f"cases {s['n_cases']} places {s['n_places']} non-ground observer places {s['observer_nonground_places']}")
    print('deadline_set_by', s['deadline_set_by'])
    for tag, v in s['by_tag'].items():
        print(f"{tag:22s} {v['class']}  places_neg={v['places_with_negative']}")
        print(f"{'':22s} ground-only {v['class_ground_observers_only']}")
    print('fire-set deadline cases:')
    for r in s['fire_set_cases']:
        print('  ', {k: r[k] for k in ('scope', 'origin_id', 'latest_s', 'nearest_present_fire_km')},
              {k: v for k, v in r.items() if k.endswith(':class')})


if __name__ == '__main__':
    main()
