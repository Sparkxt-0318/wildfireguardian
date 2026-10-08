import copy
import json
from pathlib import Path
import unittest

from routing.independent import check_route, exhaustive

CASES = json.loads((Path(__file__).parents[1] / 'fixtures/evaluation_cases.json').read_text())['cases']


class IndependentTests(unittest.TestCase):
    def test_frozen_cases(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                result = exhaustive(case['graph'], case['hazard'], case['request'], max_walks=5000)
                self.assertEqual(result['status'], case['expected']['status'])
                self.assertEqual(result['arrival'], case['expected']['arrival'])
                if result['legs'] or result['arrival'] is not None:
                    self.assertTrue(check_route(case['graph'], case['hazard'], case['request'], result['legs'], result['destination'])['ok'])

    def test_walk_cap_is_unresolved(self):
        c = CASES[0]
        result = exhaustive(c['graph'], c['hazard'], c['request'], max_walks=1)
        self.assertEqual(result['status'], 'UNRESOLVED')

    def test_route_structure_and_illegal_wait(self):
        c = CASES[0]
        for legs in ([{'kind': 'WAIT', 'node': 'n0', 'start': 0, 'end': 4}],
                     [{'kind': 'EDGE', 'edge': 'e01', 'start': 1, 'end': 2, 'from_fraction': 0, 'to_fraction': 1}],
                     [{'kind': 'EDGE', 'edge': 'e01', 'start': 0, 'end': float('nan'), 'from_fraction': 0, 'to_fraction': 1}]):
            self.assertEqual(check_route(c['graph'], c['hazard'], c['request'], legs, 'n2')['status'], 'INVALID_ROUTE')

    def test_wait_at_destination_is_not_admission(self):
        c = copy.deepcopy(CASES[0])
        c['graph']['nodes'][0]['waitable'] = True
        c['request']['destinations'] = [{'node': 'n0', 'dwell': 0, 'open_intervals': [[1, 10]]}]
        result = check_route(c['graph'], c['hazard'], c['request'], [{'kind': 'WAIT', 'node': 'n0', 'start': 0, 'end': 1}], 'n0')
        self.assertEqual(result['status'], 'INVALID_ROUTE')

    def test_exact_interior_flux_dose(self):
        c = copy.deepcopy(CASES[0])
        c['request']['destinations'] = [{'node': 'n1', 'dwell': 0, 'open_intervals': [[0, 10]]}]
        c['hazard']['members'][0]['flux'] = [[4, 8, 0]]
        leg = {'kind': 'EDGE', 'edge': 'e01', 'start': 0, 'end': 1, 'from_fraction': 0, 'to_fraction': 1}
        result = check_route(c['graph'], c['hazard'], c['request'], [leg], 'n1')
        self.assertTrue(result['ok'])
        self.assertEqual(result['per_member']['m0']['dose'], 5)
        self.assertEqual(result['per_member']['m0']['peak'], 8)

    def test_closure_endpoint_right_continuity(self):
        c = copy.deepcopy(CASES[0])
        c['request']['destinations'] = [{'node': 'n1', 'dwell': 0, 'open_intervals': [[0, 10]]}]
        m = c['hazard']['members'][0]
        m['breakpoints'] = [0, 1, 10]
        m['flux'] = [[0]*3, [0]*3]
        m['flame'] = [[False]*3, [False, True, False]]
        m['support'] = [[True]*3, [True]*3]
        leg = {'kind': 'EDGE', 'edge': 'e01', 'start': 0, 'end': 1, 'from_fraction': 0, 'to_fraction': 1}
        result = check_route(c['graph'], c['hazard'], c['request'], [leg], 'n1')
        self.assertIn('FLAME_CONTACT', result['codes'])

    def test_partial_reverse_and_turn(self):
        c = copy.deepcopy(CASES[0])
        c['graph']['mid_edge_reversal'] = True
        c['request']['position'] = {'edge': 'e01', 'fraction': .25}
        c['request']['incoming_edge'] = 'e01'
        c['request']['destinations'] = [{'node': 'n0', 'dwell': 0, 'open_intervals': [[0, 10]]}]
        leg = {'kind': 'EDGE', 'edge': 'e10', 'start': 0, 'end': 1, 'from_fraction': .75, 'to_fraction': 1}
        self.assertTrue(check_route(c['graph'], c['hazard'], c['request'], [leg], 'n0')['ok'])
        c['graph']['forbidden_turns'] = [['e01', 'e10']]
        self.assertFalse(check_route(c['graph'], c['hazard'], c['request'], [leg], 'n0')['ok'])

    def test_multiple_resources_cannot_scalar_dominate(self):
        # Equal scalar prefix dose, different member vectors. Only lower m0
        # prefix survives the downstream m0 charge. This is a development
        # counterexample and does not change the frozen evaluation JSON.
        c = copy.deepcopy(CASES[0])
        g, h, r = c['graph'], c['hazard'], c['request']
        g['grid']['height'] = 2
        g['nodes'] = [{'id':name, 'x':x, 'y':y, 'waitable':False} for name,x,y in
                      [('n0',.25,.5), ('n1',1.25,.5), ('n2',.25,1.5), ('n3',1.25,1.5), ('n4',2.25,1.5)]]
        def e(name,u,v,cells,cut):
            return {'id':name,'u':u,'v':v,'travel_ticks':1,'segments':[{'cell':cells[0],'start':0,'end':cut},{'cell':cells[1],'start':cut,'end':1}]}
        g['edges'] = [e('a','n0','n1',[0,1],.75),e('b','n0','n2',[0,3],.5),e('c','n1','n3',[1,4],.5),e('d','n2','n3',[3,4],.75),e('e','n3','n4',[4,5],.75)]
        h['grid'] = copy.deepcopy(g['grid'])
        h['members'] = [{'id':mid,'breakpoints':[0,10],'flux':[flux],'flame':[[False]*6],'support':[[True]*6]} for mid,flux in [('m0',[0,8,0,0,0,8]),('m1',[0,0,0,4.8,0,0])]]
        r['incurred'] = {'m0':0,'m1':0}
        r['budgets']['dose'] = {'m0':7,'m1':7}
        r['destinations'][0]['node'] = 'n4'
        result = exhaustive(g,h,r,1000)
        self.assertEqual(result['arrival'],3)
        self.assertEqual([leg['edge'] for leg in result['legs']],['b','d','e'])
        self.assertEqual(result['per_member']['m0']['dose'],2)
        self.assertAlmostEqual(result['per_member']['m1']['dose'],6)

    def test_future_multitick_edge_survives_empty_layer(self):
        c = copy.deepcopy(CASES[0])
        c['graph']['edges'][0]['travel_ticks'] = 3
        result = exhaustive(c['graph'],c['hazard'],c['request'],1000)
        self.assertEqual(result['arrival'],4)

    def test_fraction_one_normalized_endpoint_admission(self):
        c = copy.deepcopy(CASES[0])
        c['request'].update(position={'edge':'e01','fraction':1},incoming_edge='e01')
        c['request']['destinations'][0]['node'] = 'n1'
        result = check_route(c['graph'],c['hazard'],c['request'],[],'n1')
        self.assertTrue(result['ok'])
        self.assertEqual(result['arrival'],0)


if __name__ == '__main__':
    unittest.main()
