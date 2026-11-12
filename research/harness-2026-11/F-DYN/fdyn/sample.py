"""Build and check a fixed sample of MANIFEST_v3 entries (verification sample; the full set is built by consumers).

Checks per packet: writer omitted-source analysis reports window None / outside_sources_possible False (omitted dose 0
by construction); valid_until = horizon; identity checkpoint is the SYNTHETIC marker exactly for synthetic starts;
source_law_version is the envelope law exactly for envelope packets; ignition count; HAZARD sha256 and size.

    python3 research/harness-2026-11/F-DYN/fdyn/sample.py --manifest research/harness-2026-11/F-DYN/MANIFEST_v3.json \
        --pick yeongdeok_2025:20250325T110000Z:5 yeongdeok_2025:20250325T230000Z:5 uiseong_andong_2025:20250325T140000Z:5 \
        --out SAMPLE.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--pick', nargs='+', required=True, help='region:start:horizon_h')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    entries = json.loads(a.manifest.read_text())['entries']
    picks = {tuple(p.split(':')) for p in a.pick}
    rows = []
    for e in entries:
        if (e['region'], e['start'], str(e['horizon_h'])) not in picks:
            continue
        out = REPO / e['out']
        if not (out / 'HAZARD.json').exists():
            r = subprocess.run(e['cmd'], cwd=REPO, capture_output=True, text=True)
            if r.returncode != 0:
                rows.append({**{k: e[k] for k in ('region', 'start', 'horizon_h', 'variant')}, 'status': 'BUILD_FAILED',
                             'tail': (r.stdout + r.stderr)[-500:]})
                print(json.dumps(rows[-1]), flush=True)
                continue
        hz_path = out / 'HAZARD.json'
        b = json.loads((out / 'BUILD_SUMMARY.json').read_text())
        md = json.loads((out / 'NATIVE_METADATA.json').read_text())
        hz = json.loads(hz_path.read_text())
        ident = hz['provenance']['identity']
        synth = e['start_kind'] == 'synthetic'
        row = {k: e[k] for k in ('region', 'start', 'start_kind', 'horizon_h', 'variant')}
        row.update({
            'omitted': b.get('omitted'),
            'omitted_dose_zero_by_construction': b.get('omitted') == {'window': None, 'outside_sources_possible': False},
            'valid_until_ok': hz['valid_until'] == e['horizon_h'] * 3600.0,
            'synthetic_marker_ok': str(ident['checkpoint_sha256']).startswith('SYNTHETIC-fdyn-present-fire-from-TOA:') == synth,
            'envelope_law_ok': (md['settings']['source_law_version'] == 'wfg.fdyn.envelope-per-cell/1') ==
                               (e['variant'] == 'envelope'),
            'ignitions': b['ignitions_per_member'], 'present_fire_cells': b['present_fire_cells'],
            'max_flux_kW_m2': b['max_flux_kW_m2'], 'scenario_ids': ident['scenario_ids'],
            'hazard_sha256': hashlib.sha256(hz_path.read_bytes()).hexdigest(), 'hazard_mb': round(hz_path.stat().st_size / 2**20, 1)})
        row['status'] = 'OK' if all(row[k] for k in ('omitted_dose_zero_by_construction', 'valid_until_ok',
                                                       'synthetic_marker_ok', 'envelope_law_ok')) else 'CHECK_FAILED'
        rows.append(row)
        print(json.dumps({k: row[k] for k in ('region', 'start', 'horizon_h', 'variant', 'status', 'ignitions',
                                               'hazard_mb')}), flush=True)
        del hz
    a.out.write_text(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
