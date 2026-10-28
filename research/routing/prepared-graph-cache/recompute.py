#!/usr/bin/env python3
"""Recompute descriptive statistics from the exported paired records.

This does not rerun the router, authenticate cached artifacts, or grade routes.
"""
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load(name):
    with (ROOT / name).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))

def summarize(records, first, second):
    a = [float(row[first]) for row in records]
    b = [float(row[second]) for row in records]
    if not a or any(x <= 0 for x in a):
        raise ValueError('positive, non-empty first-arm timings are required')
    return {'pairs': len(a), 'first_median_s': statistics.median(a),
            'second_median_s': statistics.median(b),
            'median_paired_ratio': statistics.median(y / x for x, y in zip(a, b)),
            'second_faster': sum(y < x for x, y in zip(a, b))}

def main():
    warm = load('warm_cache_pairs.csv')
    native = load('native_cold_pairs.csv')
    if len(warm) != 40 or len(native) != 40:
        raise ValueError('expected 40 warm and 40 native matched pairs')
    if any(row['verified'] != 'True' or row['matching_graph'] != 'True' for row in warm):
        raise ValueError('export includes an unverified or graph-mismatched warm pair')
    groups = {
        'warm_build': [r for r in warm if r['stage'] == 'build'],
        'warm_hit': [r for r in warm if r['stage'] == 'hit'],
        'warm_hit_changed_hazard': [r for r in warm if r['transition'] == 'changed_hazard'],
        'warm_hit_same_hazard': [r for r in warm if r['transition'] == 'new_mission_same_hazard'],
    }
    if {k: len(v) for k, v in groups.items()} != {
        'warm_build': 10, 'warm_hit': 30,
        'warm_hit_changed_hazard': 20, 'warm_hit_same_hazard': 10,
    }:
        raise ValueError('unexpected warm stage counts')
    out = {}
    for name, rows in groups.items():
        out[name] = {
            'complete_request': summarize(rows, 'cold_elapsed_s', 'cached_elapsed_s'),
            'preparation_operation': summarize(rows, 'cold_prepare_s', 'cached_prepare_s'),
            'preparation_wrapper': summarize(rows, 'cold_prepare_total_s', 'cached_prepare_total_s'),
        }
    streams = defaultdict(list)
    for row in warm:
        streams[row['stream']].append(row)
    if len(streams) != 10 or any(len(rows) != 4 for rows in streams.values()):
        raise ValueError('expected ten four-request streams')
    totals = [{'cold': sum(float(x['cold_elapsed_s']) for x in rows),
               'cached': sum(float(x['cached_elapsed_s']) for x in rows)} for rows in streams.values()]
    out['four_request_lifecycle'] = summarize(totals, 'cold', 'cached')
    routes = [r for r in native if r['both_verified_routes'] == 'True']
    out['native_cold_preparation'] = summarize(native, 'baseline_prepare_s', 'candidate_prepare_s')
    out['native_cold_verified_route_complete_request'] = summarize(routes, 'baseline_elapsed_s', 'candidate_elapsed_s')
    print(json.dumps(out, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
