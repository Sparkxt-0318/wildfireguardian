"""F-DYN v3 build manifest: one entry per (region, start, horizon, variant) in the fixed scoring set for the BUILT
starts (BUILT_STARTS.json, criterion in STARTS_RULE.md @24bbad9). Each entry is the exact build.py argument list;
packets are large (64-260 MB), so consumers build what they need in their own container.

    python3 research/harness-2026-11/F-DYN/fdyn/manifest.py --built BUILT_STARTS.json --out MANIFEST_v3_1.json

v3.1 (QUANT_v3_1_RULE.md): integer-ms quantization; packets under packets_v31/; MANIFEST_v3.json is superseded.
v3.5 (IDENTITY_PATH_RULE.md): repo-relative radiation module path in the packet identity; packets under packets_v35/.
v3.6 (NOREENTRY_RULE.md): v3.5 entries unchanged (transform 'reopening') + one no_reentry entry each (packets_v36_noreentry/).
v3.7 (NOREENTRY2_RULE.md): v3.6 entries with commands verbatim + one no_reentry/2 entry each (packets_v37_noreentry2/);
     burnset entries carry the held ENVELOPE_BURNSET_RULE.md label (label only). No dilation packets.
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
             'envelope_burnset': 'SOUND RELATIVE TO THE FINAL MAPPED BURN SET (fire never mapped is outside it): lo = ignition, no cell cleared within the horizon; single implementation, not independently checked (Nora PASS WITH NOTES, row 32); arrays encode the same law (scalar T = R = H, PACKET_CONSISTENCY_RULE.md A; Nora PASS WITH NOTES, row 37)'}
SUPERSEDED_V3 = 'c76b746d9a8131b2fec162177736fce72a76a43cba80f467ff63ae503d5da3fe'
SUPERSEDED_V31 = '1c2e73db20db7b1caa309ebde42d20629054cd49c8f1f2cd9e4e81b0b9c89bbe'
SUPERSEDED_V32 = 'd4dcf43b4029048c6d7e876d599d34d8d75e0b1419316e3a3e123fc4d9a5fc15'
SUPERSEDED_V33 = 'aaed2402e926a2e8c2341c9920f222b61c471cbd3bf76b66e3921158c71bb2b3'
SUPERSEDED_V34 = 'bcad0d4500a39b5cd44c33abb1daf159f844d7d1826ccaa89dd08a0bcbbdb6a1'
SUPERSEDED_V35 = '642ede3d882e8a1c7ff1da054cfc506a0b0148247677daefa4ca22bb736f28dd'
REOPENING = 'research variant: fixed burning duration, reopening after burn-out (unsourced; Sofia)'
NO_REENTRY = ('no re-entry (default for person-facing outputs); burning intensity held to the horizon; raises dose and '
              "peak vs reopening; contact set equals Richard's never-clears (NOREENTRY_RULE.md)")
SUPERSEDED_V36 = 'b9b1e8533766f37923b6b4a653bf72f03b41ce76c04f9354239054256cd2ed23'
NO_REENTRY1_V37 = ('VARIANT: no re-entry after the start; cells burned out before the start stay open (not the default '
                   'once Nora passes v3.7); ' + NO_REENTRY)
NO_REENTRY2 = ('no re-entry; also closed from the start where burned out before it (default for person-facing outputs '
               'once Nora passes v3.7); burning intensity held to the horizon, including cells burned out before the '
               'start; raises dose and peak vs reopening and vs no_reentry/1; contact set equals Richard\'s closed-from-0 '
               'field (NOREENTRY2_RULE.md)')
BURNSET_LABEL = ('static final-footprint bound (no timing; identical across starts); burn set = kriged footprint ∪ FIRMS ∪ '
                 'buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 FIRMS-only)')
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
                out = f'{D}/packets_v35/{region}/{start}_h{H}_{v}_central_q300'
                cmd = ['python3', 'research/harness-2026-11/F-DYN/fdyn/build.py', '--region', region, '--start', start,
                       '--horizon-h', str(H), *args, '--member-set', 'central', '--domain', 'full_grid',
                       '--graph', f'{D}/graphs_interim/{region}/graph.json', '--out', out]
                if not recorded:
                    cmd += ['--kriged-toa', f'{D}/KFS_01_pswt_ok_toa.tif', '--synthetic-export-dir',
                            f'{D}/synthetic_exports']
                entries.append({'region': region, 'start': start, 'start_kind': 'recorded' if recorded else 'synthetic',
                                'horizon_h': H, 'variant': v, 'out': out, 'cmd': cmd,
                                'soundness': SOUNDNESS[v], 'transform': 'reopening', 'transform_label': REOPENING})
                nr_out = out.replace('/packets_v35/', '/packets_v36_noreentry/')
                nr_cmd = list(cmd)
                nr_cmd[nr_cmd.index('--out') + 1] = nr_out
                nr_cmd.append('--no-reentry')
                nr_sound = SOUNDNESS[v] if v != 'envelope' else (
                    'BRACKET-START, NOT A LOWER BOUND (not guaranteed conservative); no re-entry from lo: scalar law, '
                    'arrays consistent with HAZARD (NOREENTRY_RULE.md)')
                entries.append({'region': region, 'start': start, 'start_kind': 'recorded' if recorded else 'synthetic',
                                'horizon_h': H, 'variant': v, 'out': nr_out, 'cmd': nr_cmd,
                                'soundness': nr_sound, 'transform': 'no_reentry/1', 'transform_label': NO_REENTRY1_V37})
                nr2_out = out.replace('/packets_v35/', '/packets_v37_noreentry2/')
                nr2_cmd = list(cmd)
                nr2_cmd[nr2_cmd.index('--out') + 1] = nr2_out
                nr2_cmd.append('--no-reentry2')
                entries.append({'region': region, 'start': start, 'start_kind': 'recorded' if recorded else 'synthetic',
                                'horizon_h': H, 'variant': v, 'out': nr2_out, 'cmd': nr2_cmd,
                                'soundness': nr_sound, 'transform': 'no_reentry/2', 'transform_label': NO_REENTRY2})
    for e in entries:
        if e['variant'] == 'envelope_burnset':
            e['burnset_label'] = BURNSET_LABEL
    a.out.write_text(json.dumps({'schema': 'wfg.fdyn.manifest/8', 'graph': 'interim full-grid (fdyn/regrid_graph.py)',
                                 'quantization': {'version': 'wfg.fdyn.quant/3.1', 'rule': 'QUANT_v3_1_RULE.md'},
                                 'packet_consistency': {'rule': 'PACKET_CONSISTENCY_RULE.md', 'builder_self_check': 'fdyn/consistency.py, every build',
                                                        'older_manifests': 'v3, v3.1, v3.2, v3.3 envelope and envelope_burnset/footprint/sound entries: arrays inconsistent with HAZARD; valid only for readers that take phases from HAZARD'},
                                 'packet_identity': {'rule': 'IDENTITY_PATH_RULE.md', 'radiation_operator_module': 'repo-relative path (host-independent HAZARD/REPORT/NATIVE_METADATA sha256)'},
                                 'transforms': {'reopening': REOPENING, 'no_reentry/1': NO_REENTRY1_V37,
                                                'no_reentry/2': NO_REENTRY2,
                                                'rule': ['NOREENTRY_RULE.md', 'NOREENTRY2_RULE.md']},
                                 'dilation_packets': 'none (NOREENTRY2_RULE.md 6.3)',
                                 'superseded': [{'manifest': 'MANIFEST_v3_6.json', 'sha256': SUPERSEDED_V36,
                                                 'reason': 'extended, not changed: its 976 commands are kept verbatim; no_reentry/1 is relabelled a VARIANT, no_reentry/2 entries are added, burnset entries carry the held label (NOREENTRY2_RULE.md)'},
                                                {'manifest': 'MANIFEST_v3_5.json', 'sha256': SUPERSEDED_V35,
                                                 'reason': 'extended, not changed: its 488 entries are kept verbatim (transform reopening) and no_reentry entries are added (NOREENTRY_RULE.md)'},
                                                {'manifest': 'MANIFEST_v3_4.json', 'sha256': SUPERSEDED_V34,
                                                 'reason': 'content-identical; differs only in the absolute radiation module path in the packet identity (Mira; IDENTITY_PATH_RULE.md)'},
                                                {'manifest': 'MANIFEST_v3_3.json', 'sha256': SUPERSEDED_V33,
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
