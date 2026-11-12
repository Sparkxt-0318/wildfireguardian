"""F-DYN v3 build manifest: one entry per (region, start, horizon, variant) in the fixed scoring set for the BUILT
starts (BUILT_STARTS.json, criterion in STARTS_RULE.md @24bbad9). Each entry is the exact build.py argument list;
packets are large (64-260 MB), so consumers build what they need in their own container.

    python3 research/harness-2026-11/F-DYN/fdyn/manifest.py --built BUILT_STARTS.json --out MANIFEST_v3_1.json

v3.1 (QUANT_v3_1_RULE.md): integer-ms quantization; packets under packets_v31/; MANIFEST_v3.json is superseded.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

D = 'research/harness-2026-11/F-DYN/_data'
VARIANTS = {
    'kriged_mean': ['--arrival', f'{D}/KFS_01_pswt_ok_toa.tif', '--arrival-variant', 'kriged_mean',
                    '--sd', f'{D}/KFS_01_pswt_ok_std.tif'],
    'firms_early': ['--arrival', f'{D}/variants/firms_early.npz', '--arrival-variant', 'firms_early'],
    'envelope': ['--arrival', f'{D}/variants/firms_early.npz', '--arrival-hi', f'{D}/variants/firms_constrained.npz',
                 '--arrival-variant', 'envelope'],
    'envelope_burnset': ['--arrival', f'{D}/variants/envelope_burnset_lo.npz', '--arrival-hi',
                           f'{D}/variants/envelope_burnset_hi.npz', '--arrival-variant', 'envelope_burnset'],
}
SOUNDNESS = {'kriged_mean': 'kriged mean (not a bound; sd ~17 h; late for the coastal run)',
             'firms_early': 'BRACKET-START, NOT A LOWER BOUND (not guaranteed early enough)',
             'envelope': 'BRACKET-START, NOT A LOWER BOUND (not guaranteed conservative); per-cell law; HAZARD-only: '
                         'arrays refuse, not for array-based routing or certification (PACKET_CONSISTENCY_RULE.md B)',
             'envelope_burnset': 'SOUND RELATIVE TO THE FINAL MAPPED BURN SET (fire never mapped is outside it): lo = ignition, no cell cleared within the horizon; single implementation, not independently checked (Nora PASS WITH NOTES, row 32); arrays encode the same law (scalar T = R = H, PACKET_CONSISTENCY_RULE.md A)'}
SUPERSEDED_V3 = 'c76b746d9a8131b2fec162177736fce72a76a43cba80f467ff63ae503d5da3fe'
SUPERSEDED_V31 = '1c2e73db20db7b1caa309ebde42d20629054cd49c8f1f2cd9e4e81b0b9c89bbe'
SUPERSEDED_V32 = 'd4dcf43b4029048c6d7e876d599d34d8d75e0b1419316e3a3e123fc4d9a5fc15'
SUPERSEDED_V33 = 'aaed2402e926a2e8c2341c9920f222b61c471cbd3bf76b66e3921158c71bb2b3'
RECORDED = {'uiseong_andong_2025': {'20250323T010000Z', '20250324T090000Z', '20250325T170000Z'},
            'yeongdeok_2025': {'20250325T190000Z', '20250325T230000Z', '20250326T080000Z'}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--built', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    built = json.loads(a.built.read_text())['built']
    seen, entries = set(), []
    for region, start, _kind in built:
        if (region, start) in seen:               # a rule start that coincides with a recorded input time
            continue
        seen.add((region, start))
        recorded = start in RECORDED[region]
        for H in (5, 8):
            for v, args in VARIANTS.items():
                out = f'{D}/packets_v34/{region}/{start}_h{H}_{v}_central_q300'
                cmd = ['python3', 'research/harness-2026-11/F-DYN/fdyn/build.py', '--region', region, '--start', start,
                       '--horizon-h', str(H), *args, '--member-set', 'central', '--domain', 'full_grid',
                       '--graph', f'{D}/graphs_interim/{region}/graph.json', '--out', out]
                if not recorded:
                    cmd += ['--kriged-toa', f'{D}/KFS_01_pswt_ok_toa.tif', '--synthetic-export-dir',
                            f'{D}/synthetic_exports']
                entries.append({'region': region, 'start': start, 'start_kind': 'recorded' if recorded else 'synthetic',
                                'horizon_h': H, 'variant': v, 'out': out, 'cmd': cmd,
                                'soundness': SOUNDNESS[v]})
    a.out.write_text(json.dumps({'schema': 'wfg.fdyn.manifest/5', 'graph': 'interim full-grid (fdyn/regrid_graph.py)',
                                 'quantization': {'version': 'wfg.fdyn.quant/3.1', 'rule': 'QUANT_v3_1_RULE.md'},
                                 'packet_consistency': {'rule': 'PACKET_CONSISTENCY_RULE.md', 'builder_self_check': 'fdyn/consistency.py, every build',
                                                        'older_manifests': 'v3, v3.1, v3.2, v3.3 envelope and envelope_burnset/footprint/sound entries: arrays inconsistent with HAZARD; valid only for readers that take phases from HAZARD'},
                                 'superseded': [{'manifest': 'MANIFEST_v3_3.json', 'sha256': SUPERSEDED_V33,
                                                 'reason': 'per-cell-law packets had arrays inconsistent with HAZARD (Thomas P1, Nora row 34)'},
                                                {'manifest': 'MANIFEST_v3_2.json', 'sha256': SUPERSEDED_V32,
                                                 'reason': 'pure rename envelope_footprint -> envelope_burnset and label after '
                                                           'Nora PASS (row 32); arrays identical'},
                                                {'manifest': 'MANIFEST_v3_1.json', 'sha256': SUPERSEDED_V31,
                                                 'reason': 'envelope_sound withdrawn as a bound (Nora, row 28); replaced '
                                                           'by envelope_burnset (ENVELOPE_BURNSET_RULE.md)'},
                                                {'manifest': 'MANIFEST_v3.json', 'sha256': SUPERSEDED_V3,
                                                 'reason': 'binary64 floor_300 flips a quantum at exact minute '
                                                           'boundaries (Thomas, F-3.2 O2); see DIFF_v3_v31.json'}],
                                 'entries': entries}, indent=1))
    print(f'{len(entries)} packets for {len(seen)} region-starts -> {a.out}')


if __name__ == '__main__':
    main()
