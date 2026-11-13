"""WIDENED_GRAPH_RULE.md P5: every padded packet is refused by full_check, the kit checker and the F-3.2 certifier.

Per packet, in this process:
  full_check   routing author's deadline_field.verify.full_check on a PacketModel of the packet -> REFUSED_SUPPORT_MASKED
  kit          integration/kit/runner/ffi_independent_checker.py Packet(dir, Graph) -> CheckerInputError (support)
  F-3.2        thomas/routing-next research/harness-2026-11/F-3.2/p1_check.routable_contact_model -> ValueError (5.3)
A packet passes P5 only if all three refuse. The unpadded v3.7 twin is run through the kit and F-3.2 readers too, as a
control that the refusal comes from support (the twin must load).

    python3 fdyn/widened_p5.py --f31 F31_DIR --f32 F32_DIR --graph KFS.json --packet PW [--twin P37 --twin-graph G] --out ROW.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def attempt(fn):
    try:
        fn()
        return {'refused': False}
    except Exception as e:                                  # noqa: BLE001 - the refusal is the measured outcome
        return {'refused': True, 'error': f'{type(e).__name__}: {str(e)[:240]}'}


def main():
    ap = argparse.ArgumentParser()
    for k in ('--f31', '--f32', '--graph', '--packet', '--out'):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument('--twin', type=Path, default=None)
    ap.add_argument('--twin-graph', type=Path, default=None)
    a = ap.parse_args()
    kit = load_module('wfg_kit_ffi_checker', REPO / 'integration/kit/runner/ffi_independent_checker.py')
    sys.path.insert(0, str(a.f32))
    sys.path.insert(0, str(a.f32.parents[2] / 'experimental' / 'scenario-members' / 'src'))   # F-3.2's ContactModel
    p1 = load_module('f32_p1_check', a.f32 / 'p1_check.py')
    out = {'rule': 'WIDENED_GRAPH_RULE.md P5', 'packet': str(a.packet)}
    graph = json.loads(a.graph.read_text())
    out['kit'] = attempt(lambda: kit.Packet(a.packet, kit.Graph(graph)))
    out['f32'] = attempt(lambda: p1.routable_contact_model(a.packet))
    sys.path.insert(0, str(a.f31))
    from deadline_field.real import PacketModel
    from deadline_field.verify import full_check
    pm = PacketModel(a.graph, a.packet)
    hz = json.loads((a.packet / 'HAZARD.json').read_text())
    node = pm.node_ids[0]
    r = full_check(pm, hz, origin=node, legs=[], dest=node, dwell=1, window=[0, pm.H], departure=0)
    out['full_check'] = {'refused': r.get('full_status') == 'REFUSED_SUPPORT_MASKED', 'status': r.get('full_status')}
    out['support_masked'] = bool(getattr(pm, 'support_masked', False))
    if a.twin is not None:
        tg = json.loads(a.twin_graph.read_text())
        out['twin_kit'] = attempt(lambda: kit.Packet(a.twin, kit.Graph(tg)))
        out['twin_f32'] = attempt(lambda: p1.routable_contact_model(a.twin))
    out['P5'] = bool(out['kit']['refused'] and out['f32']['refused'] and out['full_check']['refused'])
    out['twin_loads'] = None if a.twin is None else (not out['twin_kit']['refused'] and not out['twin_f32']['refused'])
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out))


if __name__ == '__main__':
    main()
