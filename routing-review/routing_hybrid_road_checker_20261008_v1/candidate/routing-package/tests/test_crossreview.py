"""D-authored DEVELOPMENT attacks; none are additions to the frozen17 set.

Oracle: separately authored C timed-walk enumeration, never candidate costs,
dominance, or labels. Numeric boundary assertions use a direct rational fact.
"""
from copy import deepcopy
from fractions import Fraction
import random
import unittest

from routing.fixture import example
from routing.core import solve
from routing.independent import exhaustive
from routing.session import RoutingSession
from routing.fallback import checked_return
from routing.validation import validate_graph, validate_request, ValidationError, chord_segments


class IndependentCrossReview(unittest.TestCase):
    def data(self):
        f = example()
        return tuple(f[k] for k in ('graph', 'hazard', 'request'))

    def test_positive_exposure_cannot_disappear_into_huge_incurrence(self):
        g, h, r = self.data()
        for m in h['members']:
            m['flux'] = [[.1] * 8]
        r['incurred'] = {'m0': 1e16, 'm1': 1e16}
        r['budgets']['dose'] = deepcopy(r['incurred'])
        # Exact rational fact about the represented .1: all positive travel
        # exceeds an already fully spent budget, however small its increment.
        self.assertGreater(Fraction.from_float(.1) * 4, 0)
        for mode in ('baseline', 'dijkstra', 'astar'):
            r['solver'] = mode
            self.assertEqual(solve(g, h, r)['status'], 'PROVEN_INFEASIBLE')
        self.assertEqual(exhaustive(g, h, r)['status'], 'PROVEN_INFEASIBLE')

    def test_exact_fractional_interpolation_dose(self):
        g, h, r = self.data()
        fraction = 1 / 3
        r.update(position={'edge': 'OA', 'fraction': fraction}, incoming_edge='OA')
        r['destinations'] = [{'node': 'A', 'dwell': 0, 'open_intervals': [[0, 30]]}]
        for e in g['edges']:
            if e['id'] == 'OA':
                e['travel_ticks'] = 7
        for m in h['members']:
            m['flux'] = [[1, 3, 0, 0, 0, 0, 0, 0]]
        r['budgets']['dose'] = {'m0': 100, 'm1': 100}
        # Manual exact integral from .333... to the declared .5 raster cut:
        # 5seconds*((.5-f)/(1-f))*1 + remaining duration*3.
        cell0_duration = 5 * (Fraction(.5) - Fraction(fraction)) / (1 - Fraction(fraction))
        exact = cell0_duration + (5 - cell0_duration) * 3
        result = solve(g, h, r)
        self.assertEqual(result['status'], 'CONDITIONAL_OPTIMUM')
        self.assertEqual(result['arrival'], 5)
        self.assertEqual(result['per_member']['m0']['dose_exact'], str(exact))

    def test_coordinate_cell_at_grid_boundary_gets_endpoint_check(self):
        g, h, r = self.data()
        g['nodes'][1]['x'] = 10
        by = {n['id']: n for n in g['nodes']}
        g['edges'] = [e for e in g['edges'] if e['id'] in {'OA', 'AO', 'AD', 'DA'}]
        for e in g['edges']:
            e['segments'] = chord_segments(g['grid'], by[e['u']], by[e['v']])
        # OA's positive-duration cell is0, while A's coordinate cell is1.
        self.assertEqual(g['edges'][0]['segments'], [{'cell': 0, 'start': 0., 'end': 1.}])
        for m in h['members']:
            m['flame'][0][1] = True
        self.assertEqual(solve(g, h, r)['status'], 'PROVEN_INFEASIBLE')
        self.assertEqual(exhaustive(g, h, r)['status'], 'PROVEN_INFEASIBLE')

    def test_diagonal_interior_cutpoint_checks_coordinate_cell(self):
        g, h, r = self.data()
        g['edges'] = [e for e in g['edges'] if e['id'] in {'OB', 'BD'}]
        for e in g['edges']:
            e.pop('reverse_edge', None)
        # BD travels (15,15)->(25,5). At interior (20,10), row1,col2
        # gives cell6, although positive-length chord cells are5 and2.
        self.assertEqual((int(10 / 10) * 4 + int(20 / 10)), 6)
        for m in h['members']:
            m['flame'][0][6] = True
        self.assertEqual(solve(g, h, r)['status'], 'PROVEN_INFEASIBLE')
        self.assertEqual(exhaustive(g, h, r)['status'], 'PROVEN_INFEASIBLE')

    def test_same_node_cannot_rewrite_turn_context_without_travel(self):
        g, h, r = self.data()
        g['forbidden_turns'] = [['BO', 'OA'], ['BO', 'OB']]
        r['incoming_edge'] = 'BO'
        s = RoutingSession(g)
        s.accept_update(h, r['as_of'])
        self.assertEqual(s.plan(r)['status'], 'DISCONNECTED')
        rejected = s.set_progress({'node': 'O'}, 'AO', 0,
                                  {'m0': 0, 'm1': 0}, [])
        self.assertEqual(rejected['status'], 'INVALID_INPUT')
        self.assertEqual(s.plan(r)['status'], 'DISCONNECTED')

    def test_malformed_public_session_and_return_fail_closed(self):
        g, h, r = self.data()
        s = RoutingSession(g)
        s.accept_update(h, r['as_of'])
        for bad in (None, [], 3, True):
            with self.subTest(bad=bad):
                self.assertEqual(s.plan(bad)['status'], 'INVALID_INPUT')
                self.assertFalse(s.commit(bad))
                self.assertEqual(checked_return(g, h, bad, [], 'O')['status'], 'INVALID_INPUT')
        self.assertEqual(checked_return(g, None, r, [], 'O')['status'], 'INVALID_INPUT')

    def test_unrepresentable_integer_travel_is_fail_closed(self):
        g, h, r = self.data()
        g['edges'][0]['travel_ticks'] = 10 ** 400
        for mode in ('baseline', 'dijkstra', 'astar'):
            r['solver'] = mode
            result = solve(g, h, r)
            self.assertIn(result['status'], {'INVALID_INPUT', 'UNSUPPORTED'})
            self.assertEqual(result['certificate_conditions'], [])

    def test_overflowing_progress_history_and_mapping_fail_closed(self):
        g, h, r = self.data()
        s = RoutingSession(g)
        s.accept_update(h, r['as_of'])
        result = s.set_progress({'node': 'O'}, None, 0,
                                {'m0': 10 ** 400, 'm1': 0}, [])
        self.assertEqual(result['status'], 'INVALID_INPUT')
        result = checked_return(g, h, r,
            [{'edge': 'OA', 'from_fraction': 0, 'to_fraction': 10 ** 400}], 'O')
        self.assertEqual(result['status'], 'INVALID_INPUT')
        s.plan(r)
        h2 = deepcopy(h)
        h2['version'] = 2
        h2['members'][1]['id'] = 'new'
        result = s.accept_update(h2, r['as_of'], {'m0': 10 ** 400, 'new': 10 ** 400})
        self.assertEqual(result['status'], 'UNSUPPORTED')

    def test_boolean_request_version_and_nonfinite_memory_cap_rejected(self):
        g, h, r = self.data()
        r['hazard_version'] = True
        with self.assertRaises(ValidationError):
            validate_request(g, h, r)
        r['hazard_version'] = 1
        for bad in (float('nan'), float('inf'), -1, True, '3072'):
            r['limits']['rss_limit_mb'] = bad
            with self.subTest(cap=bad), self.assertRaises(ValidationError):
                validate_request(g, h, r)

    def test_decimal_near_lattice_never_proves_infeasibility(self):
        g, h, r = self.data()
        h['dt'] = .1
        r['horizon'] = .3
        r['destinations'][0]['dwell'] = 0
        for e in g['edges']:
            e['travel_ticks'] = 1 if e['id'] == 'OA' else 2
        for m in h['members']:
            m['flux'] = [[0] * 8]
        for mode in ('baseline', 'dijkstra', 'astar'):
            r['solver'] = mode
            result = solve(g, h, r)
            self.assertIn(result['status'], {'UNSUPPORTED', 'INVALID_INPUT'})
            self.assertEqual(result['certificate_conditions'], [])

    def test_dyadic_lattice_retains_exact_boundary_arrival(self):
        g, h, r = self.data()
        h['dt'] = .125
        r['horizon'] = .375
        r['destinations'][0]['dwell'] = 0
        for e in g['edges']:
            e['travel_ticks'] = 1 if e['id'] == 'OA' else 2
        for m in h['members']:
            m['flux'] = [[0] * 8]
        self.assertEqual(solve(g, h, r)['arrival'], .375)

    def test_grid_tolerance_cannot_admit_positive_occupancy_gap(self):
        g, h, r = self.data()
        segments = g['edges'][0]['segments']
        segments[0]['end'] -= 1e-10
        segments[1]['start'] += 1e-10
        try:
            admitted = validate_graph(g)
        except ValidationError:
            return
        # An implementation may canonicalize verified coordinate cuts, but
        # passing through an actual positive-duration gap is unacceptable.
        parts = admitted['edges'][0]['segments']
        self.assertEqual(parts[0]['end'], parts[1]['start'])

    def test_return_zero_wall_budget_is_timeout(self):
        g, h, r = self.data()
        r.update(position={'node': 'A'}, incoming_edge='OA', departure=2,
                 incurred={'m0': 2, 'm1': 4})
        r['limits']['wall_s'] = 0
        result = checked_return(g, h, r,
            [{'edge': 'OA', 'from_fraction': 0, 'to_fraction': 1}], 'O')
        self.assertEqual(result['status'], 'TIMEOUT')

    def test_exhausted_label_capacity_is_never_infeasibility(self):
        g, h, r = self.data()
        r['limits']['max_labels'] = 1
        for mode in ('baseline', 'dijkstra', 'astar'):
            r['solver'] = mode
            result = solve(g, h, r)
            self.assertEqual(result['status'], 'TIMEOUT')
            self.assertEqual(result['solver_status'], 'INCOMPLETE_CAP')
            self.assertEqual(result['certificate_conditions'], [])

    def test_incomparable_member_labels_trigger_frontier_cap(self):
        g, h, r = self.data()
        g['nodes'].append({'id': 'E', 'x': 35., 'y': 5., 'waitable': False})
        by = {n['id']: n for n in g['nodes']}
        for e in g['edges']:
            e['travel_ticks'] = 1
            e.pop('reverse_edge', None)
        g['edges'] = [e for e in g['edges'] if e['id'] in {'OA', 'OB', 'AD', 'BD'}]
        g['edges'].append({'id': 'DE', 'u': 'D', 'v': 'E', 'travel_ticks': 1,
            'segments': chord_segments(g['grid'], by['D'], by['E'])})
        for n in g['nodes']:
            n['waitable'] = False
        h['members'][0]['flux'] = [[0, 8, 0, 0, 0, 0, 0, 0]]
        h['members'][1]['flux'] = [[0, 0, 0, 0, 0, 8, 0, 0]]
        r['budgets']['dose'] = {'m0': 100, 'm1': 100}
        r['destinations'] = [{'node': 'E', 'dwell': 0, 'open_intervals': [[0, 30]]}]
        r['limits']['frontier_width'] = 1
        for mode in ('baseline', 'dijkstra', 'astar'):
            r['solver'] = mode
            result = solve(g, h, r)
            self.assertEqual(result['status'], 'TIMEOUT')
            self.assertEqual(result['reason'], 'FRONTIER_WIDTH')
            self.assertEqual(result['certificate_conditions'], [])

    def test_return_charges_actual_incurred_history_at_new_departure(self):
        g, h, r = self.data()
        r.update(position={'node': 'A'}, incoming_edge='OA', departure=2,
                 incurred={'m0': 2, 'm1': 4})
        history = [{'edge': 'OA', 'from_fraction': 0, 'to_fraction': 1}]
        r['budgets']['dose']['m1'] = 7
        result = checked_return(g, h, r, history, 'O')
        self.assertEqual(result['status'], 'UNSUPPORTED')
        self.assertIn('DOSE_BUDGET', result['codes'])
        self.assertNotEqual(result['status'], 'PROVEN_INFEASIBLE')

    def test_async_result_cannot_commit_after_rejected_update(self):
        g, h, r = self.data()
        s = RoutingSession(g)
        s.accept_update(h, r['as_of'])
        result = s.plan(r)
        bad = deepcopy(h)
        bad['version'] = 2
        bad['members'][0]['flux'][0][0] = float('nan')
        self.assertEqual(s.accept_update(bad, r['as_of'])['status'], 'REJECTED_UPDATE')
        self.assertFalse(s.commit(result))
        fresh = s.plan(r)
        self.assertEqual(fresh['guidance_version_label'], 'OLDER_ACCEPTED_VERSION')
        self.assertTrue(s.commit(fresh))

    def test_fresh_cyclic_three_member_development_cases(self):
        rng = random.Random(40461004)
        for case in range(36):
            g, h, r = self.data()
            r['horizon'] = 6
            r['destinations'][0].update(dwell=rng.randrange(3),
                open_intervals=[[rng.randrange(4), 8]])
            for n in g['nodes']:
                n['waitable'] = bool(rng.randrange(2))
            for e in g['edges']:
                e['travel_ticks'] = rng.randrange(1, 4)
            h['members'] = []
            r['incurred'] = {}
            r['budgets']['dose'] = {}
            for mid in ('alpha', 'beta', 'gamma'):
                h['members'].append({'id': mid, 'breakpoints': [0, 2, 4, 30],
                    'flux': [[rng.randrange(7) for _ in range(8)] for _ in range(3)],
                    'flame': [[False] * 8] + [[rng.random() < .04 for _ in range(8)] for _ in range(2)],
                    'support': [[True] * 8 for _ in range(3)]})
                r['incurred'][mid] = rng.randrange(3)
                r['budgets']['dose'][mid] = rng.randrange(4, 30)
            expected = exhaustive(g, h, r, max_walks=20000)
            self.assertNotEqual(expected['status'], 'UNRESOLVED')
            for mode in ('baseline', 'dijkstra', 'astar'):
                r['solver'] = mode
                actual = solve(g, h, r)
                with self.subTest(case=case, solver=mode):
                    self.assertEqual(actual['arrival'], expected['arrival'])
                    self.assertEqual(actual['status'], expected['status'])


if __name__ == '__main__':
    unittest.main()
