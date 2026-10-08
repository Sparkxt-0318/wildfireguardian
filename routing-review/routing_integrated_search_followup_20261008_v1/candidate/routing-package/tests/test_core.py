import copy
import random
from fractions import Fraction
import unittest

from routing.core import solve, evaluate_occupancy
from routing.independent import exhaustive


def fixture():
    grid = {'x0': 0, 'y0': 0, 'resolution': 1, 'width': 4, 'height': 1}
    nodes = [{'id': 'n'+str(i), 'x': i+.25, 'y': .5, 'waitable': False} for i in range(3)]
    edges = []
    for i in range(2):
        eid, rid = 'e'+str(i)+str(i+1), 'e'+str(i+1)+str(i)
        edges.append({'id': eid, 'u': 'n'+str(i), 'v': 'n'+str(i+1), 'travel_ticks': 1,
                      'segments': [{'cell': i, 'start': 0, 'end': .75}, {'cell': i+1, 'start': .75, 'end': 1}], 'reverse_edge': rid})
        edges.append({'id': rid, 'u': 'n'+str(i+1), 'v': 'n'+str(i), 'travel_ticks': 1,
                      'segments': [{'cell': i+1, 'start': 0, 'end': .25}, {'cell': i, 'start': .25, 'end': 1}], 'reverse_edge': eid})
    graph = {'revision': 'test1', 'crs': 'EPSG:5179', 'grid': grid, 'nodes': nodes,
             'edges': edges, 'forbidden_turns': [], 'mid_edge_reversal': False}
    iso = '2026-10-04T00:00:00+00:00'
    hazard = {'schema': 'wfg.routing.edgegrid/1', 'version': 1, 'graph_revision': 'test1',
              'crs': graph['crs'], 'grid': grid, 'dt': 1, 'time_origin': iso,
              'issued_at': iso, 'available_at': iso, 'valid_from': 0, 'valid_until': 10,
              'evidence_class': 'LABELLED_FIXTURE', 'provenance': {'source': 'unit fixture', 'interpretation': 'labelled incident heat flux'},
              'channels': ['flame_contact', 'incident_heat_flux'], 'unsupported_channels': [],
              'members': [{'id': 'm0', 'breakpoints': [0, 10], 'flux': [[0]*4],
                           'flame': [[False]*4], 'support': [[True]*4]}]}
    request = {'position': {'node': 'n0'}, 'incoming_edge': None, 'departure': 0, 'horizon': 10,
               'destinations': [{'node': 'n2', 'dwell': 0, 'open_intervals': [[0, 10]]}],
               'incurred': {'m0': 0}, 'hazard_version': 1, 'as_of': iso,
               'objective': 'earliest_arrival', 'exposure_scope': 'route_only',
               'budgets': {'peak': 100, 'dose': {'m0': 100}},
               'limits': {'wall_s': 2, 'max_labels': 10000, 'max_expansions': 10000, 'frontier_width': 100},
               'solver': 'baseline'}
    return graph, hazard, request


class CoreTests(unittest.TestCase):
    def test_matched_solvers_and_exhaustive(self):
        graph, hazard, request = fixture()
        for solver in ['baseline', 'dijkstra', 'astar']:
            request['solver'] = solver
            result = solve(graph, hazard, request)
            self.assertEqual(result['status'], 'CONDITIONAL_OPTIMUM')
            self.assertEqual(result['arrival'], 2)
            self.assertTrue(result['checker']['ok'])
        self.assertEqual(exhaustive(graph, hazard, request, max_walks=5000)['arrival'], 2)

    def test_origin_destination_and_incurred(self):
        graph, hazard, request = fixture()
        request['destinations'][0]['node'] = 'n0'
        request['incurred']['m0'] = 7
        result = solve(graph, hazard, request)
        self.assertEqual(result['arrival'], 0)
        self.assertEqual(result['legs'], [])
        self.assertEqual(result['per_member']['m0']['dose'], 7)

    def test_queued_edge_arrivals_survive_empty_layers(self):
        graph, hazard, request = fixture()
        graph['edges'][0]['travel_ticks'] = 3
        self.assertEqual(solve(graph, hazard, request)['arrival'], 4)

    def test_cycle_is_required_for_new_admission(self):
        graph, hazard, request = fixture()
        graph['nodes'][0]['waitable'] = True
        request['destinations'] = [{'node': 'n0', 'dwell': 0, 'open_intervals': [[1, 10]]}]
        result = solve(graph, hazard, request)
        self.assertEqual(result['arrival'], 2)
        self.assertEqual([x['kind'] for x in result['legs']], ['EDGE', 'EDGE'])

    def test_turn_context_and_no_wait_admission(self):
        graph, hazard, request = fixture()
        graph['nodes'][0]['waitable'] = True
        graph['forbidden_turns'] = [['e10', 'e01']]
        request['incoming_edge'] = 'e10'
        request['destinations'] = [{'node': 'n2', 'dwell': 0, 'open_intervals': [[0, 10]]}]
        self.assertEqual(solve(graph, hazard, request)['status'], 'DISCONNECTED')

    def test_partial_residual_and_explicit_reversal(self):
        graph, hazard, request = fixture()
        request['position'] = {'edge': 'e01', 'fraction': .4}
        request['incoming_edge'] = 'e01'
        request['destinations'][0]['node'] = 'n1'
        result = solve(graph, hazard, request)
        self.assertEqual(result['arrival'], 1)
        self.assertEqual(result['legs'][0]['from_fraction'], .4)
        graph['mid_edge_reversal'] = True
        request['destinations'][0]['node'] = 'n0'
        result = solve(graph, hazard, request)
        self.assertEqual(result['arrival'], 1)
        self.assertEqual(result['legs'][0]['edge'], 'e10')
        graph['forbidden_turns'] = [['e01', 'e10']]
        # Turning through another node may legally restore incoming context.
        self.assertEqual(solve(graph, hazard, request)['arrival'], 4)
        graph['forbidden_turns'].append(['e21', 'e10'])
        self.assertEqual(solve(graph, hazard, request)['status'], 'DISCONNECTED')

    def test_dwell_scope_and_accumulated_dose(self):
        graph, hazard, request = fixture()
        hazard['members'][0]['flux'] = [[1]*4]
        request['incurred']['m0'] = 3
        request['destinations'] = [{'node': 'n1', 'dwell': 2, 'open_intervals': [[0, 10]]}]
        request['budgets']['dose']['m0'] = 4
        result = solve(graph, hazard, request)
        self.assertEqual(result['arrival'], 1)
        self.assertEqual(result['per_member']['m0']['dose'], 4)
        request['exposure_scope'] = 'including_dwell'
        self.assertEqual(solve(graph, hazard, request)['status'], 'PROVEN_INFEASIBLE')

    def test_right_continuous_endpoint_flame(self):
        graph, hazard, request = fixture()
        m = hazard['members'][0]
        m.update(breakpoints=[0, 1, 10], flux=[[0]*4, [0]*4],
                 flame=[[False]*4, [False, True, False, False]], support=[[True]*4, [True]*4])
        self.assertEqual(solve(graph, hazard, request)['status'], 'PROVEN_INFEASIBLE')

    def test_missing_support_withholds_global_claims(self):
        graph, hazard, request = fixture()
        hazard['members'][0]['support'][0][3] = False
        self.assertEqual(solve(graph, hazard, request)['status'], 'CHECKED_ROUTE')
        graph['edges'] = []
        self.assertEqual(solve(graph, hazard, request)['status'], 'DISCONNECTED')

    def test_caps_and_at_issue_failure_are_distinct(self):
        graph, hazard, request = fixture()
        request['limits']['max_labels'] = 1
        self.assertEqual(solve(graph, hazard, request)['status'], 'TIMEOUT')
        request['limits']['wall_s'] = 0
        self.assertEqual(solve(graph, hazard, request)['status'], 'TIMEOUT')
        request['limits']['wall_s'] = 2
        request['incurred']['m0'] = 101
        self.assertEqual(solve(graph, hazard, request)['status'], 'AT_ISSUE_FAILURE')

    def test_exact_dose_piecewise_and_point_contact(self):
        graph, hazard, request = fixture()
        m = hazard['members'][0]
        m.update(breakpoints=[0, .5, 10], flux=[[2]*4, [6]*4],
                 flame=[[False]*4, [False]*4], support=[[True]*4, [True]*4])
        result = evaluate_occupancy(graph, hazard, [{'cell': 0, 'start': 0, 'end': 1}])
        self.assertEqual(result['per_member']['m0'], {'dose': 4, 'dose_exact': Fraction(4), 'peak': 6})
        m['flame'][1][1] = True
        result = evaluate_occupancy(graph, hazard, [{'cell': 1, 'start': .5, 'end': .5}])
        self.assertIn('FLAME_CONTACT', result['codes'])

    def test_temporal_two_member_search_matches_walk_oracle(self):
        rng = random.Random(71004)
        for case in range(40):
            graph, hazard, request = fixture()
            request['horizon'] = 4
            for n in graph['nodes']:
                n['waitable'] = bool(rng.randrange(2))
            for e in graph['edges']:
                e['travel_ticks'] = rng.randrange(1, 3)
            for mid in ['m0', 'm1']:
                member = {'id': mid, 'breakpoints': [0, 1, 2, 3, 4, 10],
                          'flux': [[rng.randrange(7) for _ in range(4)] for _ in range(5)],
                          'flame': [[False]*4]+[[rng.random() < .08 for _ in range(4)] for _ in range(4)],
                          'support': [[True]*4 for _ in range(5)]}
                if mid == 'm0':
                    hazard['members'] = [member]
                else:
                    hazard['members'].append(member)
                request['incurred'][mid] = rng.randrange(3)
                request['budgets']['dose'][mid] = rng.randrange(3, 21)
            expected = exhaustive(graph, hazard, request, max_walks=5000)
            self.assertNotEqual(expected['status'], 'UNRESOLVED')
            for solver in ['baseline', 'dijkstra', 'astar']:
                request['solver'] = solver
                result = solve(graph, hazard, request)
                with self.subTest(case=case, solver=solver):
                    self.assertEqual(result['arrival'], expected['arrival'])
                    self.assertEqual(result['status'], expected['status'])

    def test_grid_boundary_intermediate_endpoint_closure_and_support(self):
        graph, hazard, request = fixture()
        graph['nodes'] = graph['nodes'][:2]
        graph['nodes'][1]['x'] = 1
        graph['edges'] = graph['edges'][:2]
        for edge in graph['edges']:
            edge['segments'] = [{'cell': 0, 'start': 0, 'end': 1}]
        # Both positive-length traversals occupy cell0; the turnaround node's
        # coordinate lies in cell1. It must still be checked at the endpoint.
        request['destinations'] = [{'node': 'n0', 'dwell': 0, 'open_intervals': [[2, 10]]}]
        hazard['members'][0]['flame'][0][1] = True
        self.assertEqual(solve(graph, hazard, request)['status'], 'PROVEN_INFEASIBLE')
        hazard['members'][0]['flame'][0][1] = False
        hazard['members'][0]['support'][0][1] = False
        self.assertEqual(solve(graph, hazard, request)['status'], 'UNSUPPORTED')
        request['position'] = {'edge': 'e01', 'fraction': .5}
        request['incoming_edge'] = 'e01'
        # Interior position itself is in cell0, not an unsupported endpoint.
        self.assertNotEqual(solve(graph, hazard, request)['reason'], 'AT_ISSUE_MISSING_SUPPORT')

    def test_positive_dose_cannot_disappear_into_large_incurred(self):
        graph, hazard, request = fixture()
        hazard['members'][0]['flux'] = [[.1]*4]
        request['incurred']['m0'] = 1e16
        request['budgets']['dose']['m0'] = 1e16
        for solver in ['baseline', 'dijkstra', 'astar']:
            request['solver'] = solver
            self.assertEqual(solve(graph, hazard, request)['status'], 'PROVEN_INFEASIBLE')
        request['destinations'] = [{'node': 'n0', 'dwell': 0, 'open_intervals': [[0, 10]]}]
        self.assertEqual(solve(graph, hazard, request)['arrival'], 0)

    def test_binary_decimal_budget_boundary_is_exact(self):
        graph, hazard, request = fixture()
        hazard['members'][0]['flux'] = [[.1]*4]
        request['destinations'] = [{'node': 'n1', 'dwell': 0, 'open_intervals': [[0, 10]]}]
        request['incurred']['m0'] = .2
        request['budgets']['dose']['m0'] = .3
        # Fraction(.1)+Fraction(.2) is greater than Fraction(.3).
        self.assertEqual(solve(graph, hazard, request)['status'], 'PROVEN_INFEASIBLE')
        request['budgets']['dose']['m0'] = .30000000000000004
        self.assertEqual(solve(graph, hazard, request)['arrival'], 1)


if __name__ == '__main__':
    unittest.main()
