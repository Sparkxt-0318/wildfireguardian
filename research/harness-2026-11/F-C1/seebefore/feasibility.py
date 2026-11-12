"""Print the measured facts behind DEFINITION.md ("what the replay data can and cannot support").

Run from the repository root (needs data/routing from tools/fetch_routing_inputs.py):
    python3 research/harness-2026-11/F-C1/seebefore/feasibility.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seebefore import extract, fire  # noqa: E402


def main():
    cases = extract.build()
    print(f'cases {len(cases)}, places {len({(c["region"], c["origin_id"]) for c in cases})}')
    print('deadline class:', dict(Counter(c['deadline_set_by'] for c in cases)))
    scopes = sorted({c['scope'] for c in cases})
    for s in scopes:
        region, t = s.split('/')
        fs = fire.load(region, t)
        new = [sum(len(xy) for _, xy in m) for m in fs.member_new]
        first_new = [min((t0 for t0, _ in m), default=None) for m in fs.member_new]
        print(f'{s}: horizon {fs.valid_until_s:.0f}s; present fire full grid {len(fs.present_xy)}, inside packet '
              f'{fs.packet_present}; new cells per member {new}; first new ignition s {first_new}; '
              f'unknown-state cells {fs.unknown_cells}/{fs.grid_cells}')


if __name__ == '__main__':
    main()
