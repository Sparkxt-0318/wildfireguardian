#!/usr/bin/env python3
"""Path B: recompute every number in NUMBERS.json independently (pandas + networkx) and compare.

    python research/solve2027-impact/verify.py

Exit status 1 on any missing/extra key or any difference in value, numerator or denominator (lengths in metres are
compared to 0.05 m because NUMBERS.json stores them rounded to 0.1 m; everything else must be equal exactly). Also
checks that NUMBERS.json's recorded input SHA-256 values match the files on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from wfg_impact import path_b, sources  # noqa: E402


def compare(doc: dict, recomputed: dict) -> list[str]:
    problems = []
    published = doc['numbers']
    for key in sorted(set(published) - set(recomputed)):
        problems.append(f'missing in path B: {key}')
    for key in sorted(set(recomputed) - set(published)):
        problems.append(f'not in NUMBERS.json: {key}')
    for key in sorted(set(published) & set(recomputed)):
        a, b = published[key], recomputed[key]
        for field in ('value', 'numerator', 'denominator'):
            x, y = a[field], b[field]
            if a['unit'] == 'm' and field == 'value':
                ok = x is not None and y is not None and abs(x - y) <= 0.05 + 1e-9
            else:
                ok = x == y and type(x) is type(y)
            if not ok:
                problems.append(f'{key}.{field}: NUMBERS.json {x!r} != path B {y!r}')
    for key, h in doc['headline'].items():
        n = published[key]
        for field in ('value', 'numerator', 'denominator'):
            if h.get(field) != n.get(field):
                problems.append(f'headline {key}.{field} differs from numbers section')
        for path, digest in h['input_sha256'].items():
            if doc['inputs'][path]['sha256'] != digest:
                problems.append(f'headline {key}: input hash of {path} differs from the inputs section')
    for path, row in doc['inputs'].items():
        p = sources.REPO / path if not path.startswith('data/routing/') else sources.routing_data_root() / path[len('data/routing/'):]
        if not p.is_file() or sources.sha256_file(p) != row['sha256']:
            problems.append(f'input changed or missing: {path}')
    return problems


def main() -> int:
    doc = json.loads((HERE / 'NUMBERS.json').read_text(encoding='utf-8'))
    recomputed, _ = path_b.compute()
    problems = compare(doc, recomputed)
    if problems:
        print(f'FAIL: {len(problems)} problem(s)')
        for p in problems[:200]:
            print('  ' + p)
        return 1
    print(f'PASS: path B reproduces all {len(recomputed)} numbers of NUMBERS.json '
          f'({len(doc["headline"])} headline) and every input SHA-256')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
