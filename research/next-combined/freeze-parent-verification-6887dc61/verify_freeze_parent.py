"""Read-only verification of the committed current-cohort freeze."""
from pathlib import Path
import collections
import datetime as dt
import hashlib
import json
import math
import subprocess

ROOT = Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on')
REPO = ROOT / 'work/track-1b'
HEAD = '6887dc618253e6568c6cbbfd3c9a96f1d0d86b70'
def read(name):
    return json.loads((REPO / name).read_text())
def sha(data):
    return hashlib.sha256(data).hexdigest()
def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])
def stamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
assert git('rev-parse', 'HEAD').decode().strip() == HEAD
handoff = read('research/forecast-v2/FREEZE_HANDOFF.json')
selection = read('research/forecast-v2/MODEL_SELECTION.json')
registry = read('research/forecast-v2/BLIND_REGISTRY.json')
gate = read('research/forecast-v2/executions/final_software_gate_v2.json')
prior = json.loads((ROOT / 'work/seven-final-checkpoints-parent.json').read_text())
dev = json.loads((ROOT / 'work/development-scores-parent-v2.json').read_text())
assert sha((REPO / 'research/forecast-v2/FREEZE_HANDOFF.json').read_bytes()) == '5a0528835d29bde32fa553e99b096bb6910eea57df617ef8fcee4371383d63b3'
expected = dict(gate['source_sha256'])
assert len(expected) == handoff['code_json_sources'] == 201
assert handoff['all_201_code_json_sources_unchanged'] is True
assert handoff['source_pins'] == 86
assert len(registry['producer_source_sha256']) == 86
assert 'research/forecast-v2/BLIND_REGISTRY.json' not in registry['producer_source_sha256']
for name, value in registry['producer_source_sha256'].items():
    if name in expected:
        assert expected[name] == value
    expected[name] = value
expected.update(handoff['files_sha256'])
for name, value in handoff['execution_logs_sha256'].items():
    expected['research/forecast-v2/executions/' + name] = value
for row in prior['models']:
    variant = row['variant']
    identity = {'path': row['path'], 'sha256': row['sha256']}
    assert handoff['checkpoints'][variant] == selection['checkpoints'][variant] == identity
    assert registry['models'][variant + '_seed0'] == identity
    expected[row['path']] = row['sha256']
assert len(registry['models']) == 8
for identity in list(registry['models'].values()) + list(handoff['baselines'].values()):
    expected[identity['path']] = identity['sha256']
for name, value in expected.items():
    assert sha((REPO / name).read_bytes()) == value, name
    assert sha(git('show', HEAD + ':' + name)) == value, ('uncommitted or changed', name)
assert selection['selected_variant'] == handoff['selected_variant'] == dev['selected_variant'] == 'd4_wind'
for variant, value in selection['development_brier'].items():
    assert abs(value - dev['summary'][variant]['mean_fire_brier']) <= 1e-15
assert registry['selected_model'] == 'd4_wind_seed0'
assert handoff['best_dilation_hours_per_cell'] == registry['best_dilation_hours_per_cell'] == 8
assert registry['selection']['sha256'] == handoff['files_sha256']['research/forecast-v2/MODEL_SELECTION.json']
assert registry['fit_coverage'] == selection['fit_coverage']
assert registry['fit_coverage']['sha256'] == '4c4330d841b4ac0ad0259ba04f781a5c386352da1e91358fbc2aee51276ca971'
assert registry['producer_source_sha256']['forecast/documents/preregistration_blind_test.md'] == 'aaae3df67d4297d486ad3f81ab6b32692157d1390d9adf2e41cfc6617866dbe6'
assert selection['protocol_sha256'] == 'c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243'
assert registry['execution_status'] == handoff['future_2026_execution'] == 'NOT_READY_FOR_2026_EXECUTION'
assert registry['protocol_status'] == 'READY_FOR_OWNER_REGISTRATION'
assert handoff['external_OSF_registration'] is False and registry['future_inputs_pinned'] is False
assert selection['frozen_before_heldout_scoring'] is True and handoff['heldout_inference_started'] is False
assert stamp(selection['frozen_utc']) < stamp(registry['generated_utc']) <= stamp(handoff['frozen_utc'])
run = REPO / 'forecast/runs/20261030_perimeter_trained/execution_v3'
assert not (run / 'heldout').exists() and not (run / 'korean2025').exists()
us = read('research/forecast-v2/PREASSESSMENT_US2024_TIMESTAMPS.json')
kr = read('research/forecast-v2/PREASSESSMENT_KOREA2025_WINDOWS.json')
assert us['case_count'] == len(us['cases']) == 273
us_counts = collections.Counter(case['event'] for case in us['cases'])
assert dict(us_counts) == handoff['cohorts']['us2024']['event_case_counts']
assert len({(c['event'], c['cutoff'], c['endpoint']) for c in us['cases']}) == 273
for c in us['cases']:
    elapsed = (stamp(c['endpoint']) - stamp(c['cutoff'])).total_seconds() / 3600
    assert 0 < elapsed <= 48 and abs(elapsed - c['hours']) < 1e-12
assert kr['case_count'] == len(kr['cases']) == len(set(kr['case_ids'])) == 33
assert kr['event_counts'] == handoff['cohorts']['korea2025']['event_case_counts'] == {'KFS_01': 8, 'KFS_04': 14, 'KFS_06': 8, 'KFS_13': 3}
assert kr['scorer_sha256'] == sha((REPO / 'research/forecast-v2/scripts/score_cohorts.py').read_bytes())
reconstructed = []
for event in kr['event_metadata']:
    t0 = stamp(event['t0_utc'])
    start, end = stamp(event['start_utc']), stamp(event['end_utc'])
    accepted = []
    for hour in range(math.floor(event['arrival_minimum_hours']), math.ceil(event['arrival_maximum_hours']), 12):
        cutoff = (t0 + dt.timedelta(hours=hour)).replace(minute=0, second=0, microsecond=0)
        if not start <= cutoff <= end:
            continue
        elapsed = (cutoff - t0).total_seconds() / 3600
        if event['arrival_minimum_hours'] > elapsed:
            continue
        accepted.append({'event': event['event'], 'cutoff': cutoff.isoformat(), 'endpoint': (cutoff + dt.timedelta(hours=12)).isoformat(), 'hours': 12.0})
    assert accepted == [c['case'] for c in event['cases']]
    assert len(accepted) == event['window_count']
    reconstructed.extend(accepted)
assert reconstructed == [c['case'] for c in kr['cases']]
assert handoff['total_expected_current_cases'] == 273 + 33 == 306
result = {
    'status': 'PASS_COMMITTED_FREEZE_BYTES_AND_METADATA',
    'verified_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
    'freeze_commit': HEAD,
    'scope': 'Current/Git byte identity, fixed development arithmetic and saved timestamp enumeration only. No model deserialization, forecast, spatial-label replay or physical validation.',
    'files_current_and_git_checked': len(expected),
    'seven_new_checkpoint_bytes_unchanged_from_376292bc': True,
    'eight_registry_models_and_86_dependencies_exact': True,
    'code_json_sources_unchanged': 201,
    'selected_variant': selection['selected_variant'],
    'expected_current_cases': {'us2024': 273, 'korea2025': 33},
    'korean_timestamps_reconstructed_from_saved_temporal_extrema': True,
    'intended_output_directories_absent_at_check': True,
    'future_2026_execution_authorized': False,
    'current_cohort_inference_authorized_by_this_audit': False,
    'source_identity_files': handoff['files_sha256'],
    'verified_file_sha256': expected,
}
out = ROOT / 'work/FREEZE_PARENT_VERIFICATION.json'
out.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'verified_file_sha256', 'source_identity_files'}}, indent=2))
