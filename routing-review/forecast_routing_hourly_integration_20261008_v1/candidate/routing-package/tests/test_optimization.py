import copy,json,unittest
from pathlib import Path
from routing.core import solve
from routing.optimization import solve as pruned
from routing.independent import exhaustive
from routing.fixture import example

class SuffixTests(unittest.TestCase):
    def test_frozen_contract_equivalence(self):
        cases=json.loads((Path(__file__).resolve().parents[1]/'fixtures/evaluation_cases.json').read_text())['cases']
        for c in cases:
            with self.subTest(case=c['id']):
                a=solve(c['graph'],c['hazard'],c['request']);b=pruned(c['graph'],c['hazard'],c['request'])
                self.assertEqual((a['status'],a['arrival']),(b['status'],b['arrival']))
    def test_turn_dead_suffix_and_original_witness(self):
        x=example();g=x['graph'];g['forbidden_turns']=[['OB','BD'],['OB','BO']]
        a=solve(g,x['hazard'],x['request']);b=pruned(g,x['hazard'],x['request'])
        self.assertEqual(a['arrival'],b['arrival']);self.assertTrue(b['checker']['ok'])
        self.assertLess(b['metrics']['edges_after'],b['metrics']['edges_before'])
    def test_preparation_cap_is_unresolved(self):
        x=example();x['request']['limits']['wall_s']=0
        self.assertEqual(pruned(x['graph'],x['hazard'],x['request'])['status'],'TIMEOUT')

if __name__=='__main__':unittest.main()
