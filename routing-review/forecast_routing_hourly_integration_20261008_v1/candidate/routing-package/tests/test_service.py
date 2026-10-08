import unittest,copy
from routing.fixture import example
from routing.service import plan_with_return
from routing.session import RoutingSession

class ServiceTests(unittest.TestCase):
    def test_timeout_remains_unresolved_with_checked_return(self):
        x=example();q=x['request'];q['position']={'node':'A'};q['incoming_edge']='OA';q['departure']=2;q['incurred']={'m0':2,'m1':4};q['limits']['wall_s']=0
        r=plan_with_return(x['graph'],x['hazard'],q,[{'edge':'OA','from_fraction':0,'to_fraction':1}],'O',return_budget_s=1)
        self.assertEqual(r['escape']['status'],'TIMEOUT');self.assertFalse(r['primary_problem_resolved']);self.assertEqual(r['return_alternative']['status'],'CHECKED_ROUTE')
    def test_future_update_uses_accepted_asof_and_actual_progress(self):
        x=example();s=RoutingSession(x['graph']);s.accept_update(x['hazard'],x['request']['as_of']);s.plan(x['request'])
        h=copy.deepcopy(x['hazard']);h['version']=2;h['issued_at']=h['available_at']='2026-10-04T00:00:02+08:00'
        self.assertEqual(s.accept_update(h,h['available_at'])['status'],'ACCEPTED_UPDATE')
        self.assertEqual(s.set_progress({'node':'A'},'OA',2,{'m0':2,'m1':4},[{'edge':'OA','from_fraction':0,'to_fraction':1}])['status'],'PROGRESS_ACCEPTED')
        r=s.plan(x['request']);self.assertEqual(r['status'],'CONDITIONAL_OPTIMUM');self.assertEqual(r['request']['as_of'],h['available_at']);self.assertEqual(r['request']['incurred']['m1'],4)
    def test_replay_reset_cannot_show_old_guidance(self):
        from routing.replay import replay
        x=example();x['events']=[{'kind':'RESET'}];r=replay(x)
        self.assertEqual(r['status'],'RESET');self.assertIsNone(r['result'])
    def test_issue_time_regression_despite_higher_version_rejected(self):
        x=example();s=RoutingSession(x['graph']);s.accept_update(x['hazard'],x['request']['as_of']);h=copy.deepcopy(x['hazard']);h['version']=2;h['issued_at']='2026-10-03T23:59:59+08:00'
        self.assertEqual(s.accept_update(h,x['request']['as_of'])['status'],'STALE_UPDATE');self.assertEqual(s.hazard['version'],1)

if __name__=='__main__':unittest.main()
