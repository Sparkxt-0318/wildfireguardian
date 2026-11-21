"""Round trip for fdyn/requests.py (orchestrator request): INSTANCE -> requests -> recovered INSTANCE fields."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fdyn import requests as R  # noqa: E402


def test_round_trip_instance_requests():
    inst = {'horizon_s': 18000, 'depart_offsets_s': [0, 1800, 3600], 'destination_window_s': [0, 18000],
            'limits': {'peak_kw_m2': 10, 'dose_kj_m2': 100},
            'origins': [{'origin_id': 'osm:node/1', 'entry_node': 'n1',
                         'destinations': [{'destination_id': 'd1', 'node': 'n7', 'dwell_s': 120},
                                          {'destination_id': 'd2', 'node': 'n9', 'dwell_s': 120}]},
                        {'origin_id': 'osm:node/2', 'entry_node': 'n2',
                         'destinations': [{'destination_id': 'd3', 'node': 'n8', 'dwell_s': 120}]}]}
    entry = {'region': 'r', 'start': '20250325T110000Z', 'horizon_h': 5, 'variant': 'kriged_mean', 'soundness': 's'}
    hazard = {'members': [{'id': 'ffb1:20250325T110000Z:abc:0'}], 'version': 1, 'time_origin': '2025-03-25T11:00:00+00:00'}
    out = R.requests_for(entry, inst, hazard, {'n1', 'n2', 'n7', 'n8', 'n9'})
    assert len(out) == 2 * 3
    back = {}
    for key, req in out:
        o = back.setdefault(key['origin_id'], {'entry_node': req['position']['node'], 'deps': [],
                                                'dests': [(d['node'], d['dwell'], d['open_intervals']) for d in req['destinations']]})
        o['deps'].append(req['departure'])
        assert req['horizon'] == inst['horizon_s'] and req['incoming_edge'] is None
        assert req['incurred'] == {'ffb1:20250325T110000Z:abc:0': 0}
        assert req['budgets'] == {'peak': 10, 'dose': {'ffb1:20250325T110000Z:abc:0': 100}}
        assert req['limits'] == R.REQUEST_LIMITS and req['hazard_version'] == 1
    for o in inst['origins']:
        b = back[o['origin_id']]
        assert b['entry_node'] == o['entry_node'] and b['deps'] == inst['depart_offsets_s']
        assert b['dests'] == [(d['node'], d['dwell_s'], [inst['destination_window_s']]) for d in o['destinations']]


def test_missing_node_is_refused():
    inst = {'horizon_s': 18000, 'depart_offsets_s': [0], 'destination_window_s': [0, 18000],
            'limits': {'peak_kw_m2': 10, 'dose_kj_m2': 100},
            'origins': [{'origin_id': 'o', 'entry_node': 'n1', 'destinations': [{'node': 'nX', 'dwell_s': 1}]}]}
    entry = {'region': 'r', 'start': 's', 'horizon_h': 5, 'variant': 'v', 'soundness': 's'}
    try:
        R.requests_for(entry, inst, {'members': [{'id': 'm'}], 'version': 1, 'time_origin': 't'}, {'n1'})
    except SystemExit as e:
        assert 'DESTINATION_NODE_NOT_IN_GRAPH' in str(e)
    else:
        raise AssertionError('missing destination node was not refused')
