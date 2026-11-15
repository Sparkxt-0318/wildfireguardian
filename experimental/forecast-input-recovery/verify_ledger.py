"""Reconcile the public recovery receipts with the preceding strict 273-case run."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1] / 'corridor-router-v8' / 'evidence'
RECOVERY = EVIDENCE / 'forecast_input_recovery'


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def read_json(name):
    return json.loads((RECOVERY / name).read_bytes())


def case_index(rows):
    records = {row['case']: row for row in rows}
    assert len(records) == len(rows) == 273, 'Missing or duplicate case ID'
    return records


def main():
    prior = case_index(read_csv(EVIDENCE / 'support_273_receipts.csv'))
    current = case_index(read_csv(RECOVERY / 'receipts.csv'))
    changes = case_index(read_csv(RECOVERY / 'case_changes.csv'))
    assert prior.keys() == current.keys() == changes.keys()
    summary = read_json('summary.json')
    transitions = read_json('transitions.json')['observations']
    assert summary['cases'] == 273 and not summary['issues']
    assert Counter(row['kind'] for row in current.values()) == summary['kinds']
    assert sum(row['verified_earliest'] == 'True' for row in current.values()) == summary['verified_earliest']
    assert sum(row['verified_drive_minimum'] == 'True' for row in current.values()) == summary['verified_drive_min']
    assert max(float(row['peak_mib']) for row in current.values()) == summary['max_peak_mib']
    assert max(float(row['wall_s']) for row in current.values()) == summary['max_wall_s']
    cohorts = Counter()
    all_changes = Counter()
    target_changes = Counter()
    by_endpoint_result = defaultdict(Counter)
    for case, change in changes.items():
        row = current[case]
        assert change['prior'] == prior[case]['kind'] and change['current'] == row['kind']
        transition = change['prior'] + ' -> ' + change['current']
        all_changes[transition] += 1
        if change['was_flagged163'] == 'True':
            cohorts['flagged'] += 1
        if change['was_missing_endpoint153'] == 'True':
            cohorts['endpoints'] += 1
            target_changes[transition] += 1
            by_endpoint_result[change['endpoint_result']][transition] += 1
        if row['kind'] == 'route':
            assert row['verified_feasible'] == 'True' and row['unsupported_cell_hours'] == '0'
        if row['guard_cause']:
            assert row['kind'] == 'unresolved'
        else:
            assert float(row['wall_s']) < 30 and float(row['peak_mib']) <= 3072
    assert cohorts == {'flagged': 163, 'endpoints': 153}
    groups = transitions['groups']
    assert all_changes == groups['all'] and target_changes == groups['target153']
    assert all(values == groups[level] for level, values in by_endpoint_result.items())

    packets = read_csv(RECOVERY / 'packet_coverage.csv')
    assert len(packets) == len({row['current_export_sha256'] for row in packets}) == 18
    identities = read_json('packet_review.json')
    for column, key in [('current_supported', 'new_valid_cell_hours'), ('previous_supported', 'old_valid_cell_hours'),
                        ('gained', 'gained'), ('case_grid_cell_hours', 'denominator')]:
        assert sum(int(row[column]) for row in packets) == identities[key]
    for row in packets:
        assert int(row['current_supported']) == int(row['previous_supported']) + int(row['gained'])
        assert int(row['lost']) == 0 and float(row['maximum_probability_change_previously_supported']) == 0
    for entry in (RECOVERY / 'SHA256SUMS').read_text().splitlines():
        checksum, filename = entry.split(None, 1)
        assert hashlib.sha256((RECOVERY / filename).read_bytes()).hexdigest() == checksum, filename
    print(f'Verified {len(current)} case records, {cohorts["endpoints"]} endpoint cases, and {len(packets)} forecast windows.')


if __name__ == '__main__':
    main()
