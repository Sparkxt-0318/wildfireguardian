"""API lifecycle, mutation, and fresh forecast admission regression checks."""
import copy
from dataclasses import FrozenInstanceError
import math
import unittest
from unittest.mock import patch

from routing import PreparedGraph, ValidationError, prepare_graph, solve
from routing.fixture import example


def semantic(result):
    return {key: value for key, value in result.items() if key != 'metrics'}


class PreparedGraphTests(unittest.TestCase):
    def setUp(self):
        data = example()
        self.graph, self.hazard, self.request = (data[key] for key in ('graph', 'hazard', 'request'))
        self.prepared = prepare_graph(self.graph)

    def test_both_explicit_reuse_paths_preserve_full_results(self):
        for solver in ('baseline', 'dijkstra', 'astar'):
            self.request['solver'] = solver
            expected = semantic(solve(self.graph, self.hazard, self.request))
            self.assertEqual(expected, semantic(solve(self.prepared, self.hazard, self.request)))
            self.assertEqual(expected, semantic(solve(self.graph, self.hazard, self.request, prepared=self.prepared)))

    def test_original_and_exported_nested_mutation_cannot_change_snapshot(self):
        expected = semantic(solve(self.prepared, self.hazard, self.request))
        self.graph['nodes'][0]['waitable'] = True
        self.graph['edges'][0]['travel_ticks'] = 9
        self.graph['forbidden_turns'].append(['OA', 'AD'])
        exported = self.prepared.snapshot()
        exported['grid']['resolution'] = 100
        exported['nodes'].clear()
        exported['edges'][0]['segments'][0]['cell'] = 99
        self.assertEqual(expected, semantic(solve(self.prepared, self.hazard, self.request)))
        self.assertFalse(self.prepared.matches(self.graph))

    def test_frozen_public_state_and_no_mutable_storage(self):
        self.assertIsInstance(self.prepared._payload, bytes)
        self.assertEqual(self.prepared.encoded_size_bytes, len(self.prepared._payload))
        self.assertFalse(hasattr(self.prepared, '__dict__'))
        with self.assertRaises(FrozenInstanceError):
            self.prepared._payload = b'{}'
        with self.assertRaises(TypeError):
            type('BadPreparedGraph', (PreparedGraph,), {})

    def test_each_bound_component_change_is_rejected_even_with_same_revision(self):
        edits = [lambda g: g.update(revision='replacement'),
                 lambda g: g.update(crs='EPSG:5186'),
                 lambda g: g['grid'].update(x0=-1),
                 lambda g: g['nodes'][0].update(waitable=True),
                 lambda g: g['edges'][0].update(travel_ticks=3),
                 lambda g: g['edges'][0]['segments'][0].update(cell=7),
                 lambda g: g['forbidden_turns'].append(['OA', 'AD']),
                 lambda g: g.update(mid_edge_reversal=True),
                 lambda g: g.update(provenance={'source': 'changed'})]
        for edit in edits:
            with self.subTest(edit=edit):
                changed = copy.deepcopy(self.graph)
                edit(changed)
                self.assertFalse(self.prepared.matches(changed))
                result = solve(changed, self.hazard, self.request, prepared=self.prepared)
                self.assertEqual((result['status'], result['reason']), ('INVALID_INPUT', 'PREPARED_GRAPH_MISMATCH'))

    def test_numeric_representations_survive_and_bind_exactly(self):
        self.graph['extra'] = [2**53+1, float(2**53), -0.0, 1, 1.0]
        prepared = prepare_graph(self.graph)
        snapshot = prepared.snapshot()
        self.assertEqual(snapshot['extra'][0], 2**53+1)
        self.assertEqual([type(x) for x in snapshot['extra']], [int, float, float, int, float])
        self.assertEqual(math.copysign(1, snapshot['extra'][2]), -1)
        for index, replacement in [(0, float(2**53+1)), (2, 0.0), (3, 1.0)]:
            changed = copy.deepcopy(self.graph)
            changed['extra'][index] = replacement
            self.assertFalse(prepared.matches(changed))

    def test_object_key_order_is_irrelevant_and_array_order_binds(self):
        reordered = dict(reversed(list(self.graph.items())))
        self.assertTrue(self.prepared.matches(reordered))
        reordered = copy.deepcopy(self.graph)
        reordered['nodes'].reverse()
        self.assertFalse(self.prepared.matches(reordered))

    def test_constructor_cannot_bypass_graph_validation(self):
        self.graph['edges'][0]['segments'][0]['cell'] = 99
        for constructor in (prepare_graph, PreparedGraph):
            with self.assertRaises(ValidationError) as caught:
                constructor(self.graph)
            self.assertEqual(caught.exception.code, 'ROAD_ALIGNMENT')

    def test_non_json_values_are_rejected_only_by_optional_preparation(self):
        for value in ((1, 2), {1: 'coerced-key'}, float('nan'), float('inf')):
            changed = copy.deepcopy(self.graph)
            changed['extra'] = value
            with self.assertRaises(ValidationError) as caught:
                prepare_graph(changed)
            self.assertEqual(caught.exception.code, 'PREPARED_GRAPH_FORMAT')
            self.assertFalse(self.prepared.matches(changed))

    def test_validation_reused_only_for_graph_hazards_and_requests_stay_fresh(self):
        with patch('routing.validation.validate_graph', side_effect=AssertionError('graph revalidation')):
            result = solve(self.prepared, self.hazard, self.request)
            self.assertEqual(result['status'], 'CONDITIONAL_OPTIMUM')
        mutations = [lambda h, q: h.update(version=2),
                     lambda h, q: h.update(graph_revision='changed'),
                     lambda h, q: h['members'][0]['flux'][0].pop(),
                     lambda h, q: q.update(hazard_version=2),
                     lambda h, q: q['incurred'].update(new_member=0)]
        for mutate in mutations:
            h, q = copy.deepcopy(self.hazard), copy.deepcopy(self.request)
            mutate(h, q)
            self.assertEqual(semantic(solve(self.graph, h, q)), semantic(solve(self.prepared, h, q)))
        h = copy.deepcopy(self.hazard)
        h['members'][0]['flame'][0][0] = True
        self.assertEqual(solve(self.prepared, h, self.request)['status'], 'AT_ISSUE_FAILURE')

    def test_replacement_is_explicit_and_new_forecast_revision_is_required(self):
        self.graph['revision'] = 'new-revision'
        replacement = prepare_graph(self.graph)
        self.assertNotEqual(replacement.fingerprint, self.prepared.fingerprint)
        self.assertEqual(solve(replacement, self.hazard, self.request)['reason'], 'GRAPH_REVISION')
        self.hazard['graph_revision'] = self.graph['revision']
        self.assertEqual(solve(replacement, self.hazard, self.request)['status'], 'CONDITIONAL_OPTIMUM')

    def test_wall_cap_remains_unresolved_and_wrong_prepared_type_rejected(self):
        self.request['limits']['wall_s'] = 0
        self.assertEqual(solve(self.prepared, self.hazard, self.request)['status'], 'TIMEOUT')
        result = solve(self.graph, self.hazard, self.request, prepared=self.graph)
        self.assertEqual((result['status'], result['reason']), ('INVALID_INPUT', 'PREPARED_GRAPH_TYPE'))


if __name__ == '__main__':
    unittest.main()
