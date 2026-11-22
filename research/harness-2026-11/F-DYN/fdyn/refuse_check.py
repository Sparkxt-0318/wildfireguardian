"""Array entry points against packets (PACKET_CONSISTENCY_RULE.md B and C): does each array-based reader refuse a
HAZARD-only packet loudly, and accept a consistent one? Router and kit code is only called, never patched; a reader that
does not refuse is reported.

    python3 research/harness-2026-11/F-DYN/fdyn/refuse_check.py --hazard-only PKT [PKT ...] --consistent PKT [PKT ...] \
        [--f32-dir DIR_WITH_F-3.2_p1_check.py] --out REFUSE_CHECK.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def readers(f32_dir):
    sys.path.insert(0, str(REPO / 'experimental' / 'scenario-members' / 'src'))
    sys.path.insert(0, str(REPO / 'tools'))
    from wfg_scenario_members.contact import ContactModel
    from explain_deadlines.packet import Packet
    from explain_deadlines.geometry import Grid

    def replay(p):
        g = json.loads((Path(p) / 'HAZARD.json').read_text())['grid']
        return Packet(p, Grid(g['x0'], g['y0'], g['resolution'], g['width'], g['height'])).consistency

    out = {'ContactModel.from_packet (also frontend.build_instance, F-3.2 run_panel)':
           lambda p: len(ContactModel.from_packet(p).cell_intervals),
           'explain_deadlines.Packet (replay consistency)': replay}
    if f32_dir:
        sys.path.insert(0, str(f32_dir))
        import p1_check
        out['F-3.2 p1_check.from_raw'] = lambda p: len(p1_check.from_raw(p, int(json.loads(
            (Path(p) / 'HAZARD.json').read_text())['valid_until'])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hazard-only', nargs='*', default=[])
    ap.add_argument('--consistent', nargs='*', default=[])
    ap.add_argument('--f32-dir', type=Path, default=None)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    rows = []
    for kind, pkts in (('hazard_only', a.hazard_only), ('consistent', a.consistent)):
        for p in pkts:
            for name, fn in readers(a.f32_dir).items():
                try:
                    v = fn(p)
                    outcome, detail = 'ACCEPTED', str(v)[:160]
                except Exception as e:                      # noqa: BLE001 - recording the reader's own failure
                    outcome, detail = 'REFUSED', f'{type(e).__name__}: {str(e)[:160]}'
                ok = (outcome == 'REFUSED') if kind == 'hazard_only' else (outcome == 'ACCEPTED')
                rows.append({'packet': str(p), 'kind': kind, 'reader': name, 'outcome': outcome, 'detail': detail,
                             'as_required': ok})
    a.out.write_text(json.dumps({'rule': 'PACKET_CONSISTENCY_RULE.md B/C', 'rows': rows}, indent=1))
    for r in rows:
        print(('OK   ' if r['as_required'] else 'NOT  '), r['kind'], '|', r['reader'], '|', r['outcome'], '|', r['detail'][:90])


if __name__ == '__main__':
    main()
