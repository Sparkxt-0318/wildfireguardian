"""Bounded cache lane controls. Uses known tiny fixtures only, no fresh panel.
Run with candidate/routing-package on sys.path (main also configures paths).
"""
import copy
from fractions import Fraction
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(D/'candidate/routing-package'))
spec = importlib.util.spec_from_file_location('preserved_core_tests', D/'candidate/routing-package/tests/test_core.py')
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
from routing import core, core_cached
from routing.search_geometry_cache import SearchGeometryCache
from routing.prepared import PreparedGraph


class CacheDevelopment(unittest.TestCase):
    def assert_same_decision(self, expected, actual):
        for k in ('status','reason','solver_status','legs','arrival','destination','per_member','certificate_conditions'):
            self.assertEqual(expected[k], actual[k], k)
        for k in ('labels','expansions','dominated','peak_frontier','edge_candidates','wait_candidates','occupancy_evaluations'):
            self.assertEqual(expected['metrics'][k], actual['metrics'][k], k)

    def test_all_four_modes_and_warm_exact_semantics(self):
        g,h,q=old.fixture()
        for solver in ('baseline','dijkstra','astar'):
            q['solver']=solver
            expected=core.solve(g,h,q)
            self.assert_same_decision(expected,core_cached.solve_cached(g,h,q,cache_enabled=False))
            cache=SearchGeometryCache(g)
            self.assert_same_decision(expected,core_cached.solve_cached(g,h,q,geometry_cache=cache))
            self.assert_same_decision(expected,core_cached.solve_cached(g,h,q,geometry_cache=cache))

    def test_known_seventeen_reference_controls_all_four_modes(self):
        sys.path.insert(0,str(D/'tests'))
        from reference_fixtures import fixtures
        for case in fixtures():
            g,h,q=case['graph'],case['hazard'],case['request']
            for solver in ('baseline','astar'):
                q['solver']=solver
                expected=core.solve(g,h,q)
                for enabled in (False,True):
                    self.assert_same_decision(expected,core_cached.solve_cached(g,h,q,cache_enabled=enabled))

    def test_fixed_state_caps_match_untouched_core(self):
        for name,value in [('max_labels',1),('max_expansions',1),('frontier_width',1)]:
            g,h,q=old.fixture();q['limits'][name]=value
            expected=core.solve(g,h,q)
            for enabled in (False,True):
                self.assert_same_decision(expected,core_cached.solve_cached(g,h,q,cache_enabled=enabled))

    def test_hand_exact_forward_and_reverse_closure(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g)
        self.assertEqual(cache.occupancies('e01',2,6),[
            {'cell':0,'start':Fraction(2),'end':Fraction(5)},
            {'cell':1,'start':Fraction(5),'end':Fraction(6)},
            {'cell':0,'start':Fraction(2),'end':Fraction(2)},
            {'cell':1,'start':Fraction(5),'end':Fraction(5)},
            {'cell':1,'start':Fraction(6),'end':Fraction(6)}])
        expected=core.edge_occupancies(g['edges'][1],Fraction(1,7),Fraction(8,7),graph=g)
        self.assertEqual(cache.occupancies('e10',Fraction(1,7),Fraction(8,7)),expected)

    def test_partial_point_and_repeated_time_affine_exactness(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g)
        for e in g['edges']:
            for f,t in ((0,1),(Fraction(1,3),1),(Fraction(3,4),Fraction(3,4)),(1,1)):
                for a,b in ((0,0),(2,7),(Fraction(1,7),Fraction(15,7))):
                    self.assertEqual(cache.occupancies(e['id'],a,b,f,t),core.edge_occupancies(e,a,b,f,t,g))
        self.assertEqual(cache.cache_info()['entries'],len(g['edges'])*4)
        self.assertGreater(cache.cache_info()['hits'],0)

    def test_owned_graph_and_output_mutation_do_not_change_templates(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g);original=cache.occupancies('e01',0,1)
        snap=cache.snapshot();snap['nodes'][0]['x']=99
        g['nodes'][0]['x']=99
        original[0]['cell']=99
        self.assertEqual(cache.occupancies('e01',0,1)[0]['cell'],0)
        self.assertFalse(cache.matches(g));self.assertEqual(cache.snapshot()['nodes'][0]['x'],.25)

    def test_every_full_graph_content_dependency_changes_binding(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g)
        mutations=[lambda x:x.update(revision='replacement'),lambda x:x.update(crs='other'),
          lambda x:x['grid'].update(x0=.1),lambda x:x['grid'].update(y0=.1),
          lambda x:x['grid'].update(width=5),lambda x:x['grid'].update(height=2),lambda x:x['grid'].update(resolution=2),
          lambda x:x['nodes'][0].update(x=.3),lambda x:x['nodes'][0].update(y=.3),
          lambda x:x['nodes'][0].update(waitable=True),lambda x:x['nodes'][0].update(id='changed'),
          lambda x:x['edges'][0].update(travel_ticks=2),lambda x:x['edges'][0].update(id='changed'),
          lambda x:x['edges'][0].update(u='n2'),lambda x:x['edges'][0].update(reverse_edge=None),
          lambda x:x['edges'][0]['segments'][0].update(end=.5),lambda x:x.update(forbidden_turns=[['e10','e01']]),
          lambda x:x.update(mid_edge_reversal=True),lambda x:x.update(ignored_extra='still bound')]
        for change in mutations:
            changed=copy.deepcopy(g);change(changed)
            self.assertFalse(cache.matches(changed))
        g['edges'][0]['travel_ticks']=2
        out=core_cached.solve_cached(g,h,q,geometry_cache=cache)
        self.assertEqual((out['status'],out['reason']),('INVALID_INPUT','GEOMETRY_CACHE_MISMATCH'))
        self.assertEqual(cache.cache_info()['entries'],0)

    def test_no_source_request_exposure_or_incumbent_cache(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g)
        first=core_cached.solve_cached(g,h,q,geometry_cache=cache)
        h2=copy.deepcopy(h);h2['members'][0]['flux']=[[101]*4]
        rejected=core_cached.solve_cached(g,h2,q,geometry_cache=cache)
        self.assertEqual(rejected['status'],'AT_ISSUE_FAILURE')
        q2=copy.deepcopy(q);q2['incurred']['m0']=101
        self.assertEqual(core_cached.solve_cached(g,h,q2,geometry_cache=cache)['status'],'AT_ISSUE_FAILURE')
        h3=copy.deepcopy(h);h3['members'][0]['support'][0][0]=False
        self.assertEqual(core_cached.solve_cached(g,h3,q,geometry_cache=cache)['status'],'UNSUPPORTED')
        h4=copy.deepcopy(h);h4['members'][0]['flame'][0][0]=True
        self.assertEqual(core_cached.solve_cached(g,h4,q,geometry_cache=cache)['status'],'AT_ISSUE_FAILURE')
        q3=copy.deepcopy(q);q3['destinations'][0]['node']='n1'
        self.assertEqual(core_cached.solve_cached(g,h,q3,geometry_cache=cache)['arrival'],1)
        second=core_cached.solve_cached(g,h,q,geometry_cache=cache)
        self.assert_same_decision(first,second)
        self.assertEqual(first['metrics']['cost_cache_misses'],second['metrics']['cost_cache_misses'])
        self.assertGreater(second['metrics']['geometry_cache_search']['hits'],0)
        self.assertEqual(second['metrics']['geometry_cache_search']['misses'],0)

    def test_prepared_and_geometry_cache_require_exact_graph(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g);prepared=PreparedGraph(g)
        self.assert_same_decision(core.solve(g,h,q),core_cached.solve_cached(prepared,h,q,geometry_cache=cache))
        changed=copy.deepcopy(g);changed['nodes'][0]['waitable']=True
        out=core_cached.solve_cached(changed,h,q,prepared=prepared,geometry_cache=cache)
        self.assertEqual(out['reason'],'PREPARED_GRAPH_MISMATCH')

    def test_invalid_types_and_no_hidden_cache_reset(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g)
        for kwargs,reason in (({'cache_enabled':1},'GEOMETRY_CACHE_FLAG'),({'geometry_cache':{}},'GEOMETRY_CACHE_TYPE'),({'cache_enabled':False,'geometry_cache':cache},'GEOMETRY_CACHE_DISABLED_WITH_OWNER')):
            self.assertEqual(core_cached.solve_cached(g,h,q,**kwargs)['reason'],reason)

    def test_failed_template_not_installed(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g)
        with patch.object(core,'edge_occupancies',side_effect=ArithmeticError('diagnostic injected failure')):
            with self.assertRaises(ArithmeticError):cache.occupancies('e01',0,1)
        self.assertEqual(cache.cache_info()['entries'],0)
        self.assertEqual(cache.occupancies('e01',0,1),core.edge_occupancies(g['edges'][0],0,1,graph=g))

    def test_finalization_deadline_retains_checked_witness(self):
        g,h,q=old.fixture();cache=SearchGeometryCache(g);clock=[0];count=[0]
        real=SearchGeometryCache.cache_info
        def inspected(owner):
            count[0]+=1
            info=real(owner)
            if count[0]==2:clock[0]=10
            return info
        with patch.object(core_cached.time,'perf_counter',lambda:clock[0]),patch.object(SearchGeometryCache,'cache_info',inspected):
            out=core_cached.solve_cached(g,h,q,geometry_cache=cache)
        self.assertEqual((out['status'],out['reason']),('TIMEOUT','WALL_CLOCK_DURING_FINALIZATION'))
        self.assertTrue(out['checked_incumbent']['checker']['ok'])
        self.assertEqual(out['legs'],[]);self.assertEqual(out['metrics']['wall_s'],10)

    def test_after_check_cap_remains_unresolved_with_checked_incumbent(self):
        g,h,q=old.fixture();clock=[0];real=core_cached.check_route
        def checked(*args):
            result=real(*args);clock[0]=10;return result
        with patch.object(core_cached.time,'perf_counter',lambda:clock[0]),patch.object(core_cached,'check_route',checked):
            out=core_cached.solve_cached(g,h,q)
        self.assertEqual((out['status'],out['reason']),('TIMEOUT','WALL_CLOCK_AFTER_CHECK'))
        self.assertTrue(out['checked_incumbent']['checker']['ok'])

    def test_zero_deadline_charges_preparation(self):
        g,h,q=old.fixture();q['limits']['wall_s']=0
        out=core_cached.solve_cached(g,h,q)
        self.assertEqual(out['status'],'TIMEOUT');self.assertGreater(out['metrics']['wall_s'],0)
        self.assertGreater(out['metrics']['timing_s']['geometry_cache_binding'],0)

    def test_label_work_partition_and_local_cost_hit_geometry_skip(self):
        # Delayed opening induces repeated edge/time alternatives on a cycle.
        g,h,q=old.fixture();g['nodes'][0]['waitable']=True
        q['destinations']=[{'node':'n2','dwell':0,'open_intervals':[[8,10]]}]
        expected=core.solve(g,h,q)
        eager=core_cached.solve_cached(g,h,q,cache_enabled=False)
        lazy=core_cached.solve_cached(g,h,q)
        self.assert_same_decision(expected,eager);self.assert_same_decision(expected,lazy)
        m=lazy['metrics'];self.assertGreater(m['cost_cache_hits'],0)
        self.assertLess(m['geometry_calls'],eager['metrics']['geometry_calls'])
        self.assertEqual(m['generated_labels'],m['labels']+m['dominated']+m['dose_rejected_labels']+m['cap_rejected_labels'])
        self.assertEqual(m['geometry_cache_search']['misses'],len(g['edges']))
        self.assertEqual(m['expanded_labels'],m['expansions'])


def load_tests(loader, tests, pattern):
    suite=unittest.TestSuite();suite.addTests(loader.loadTestsFromTestCase(CacheDevelopment))
    # Run the unchanged original core suite twice through our wrapper. This
    # includes its existing40 small seeded exhaustive comparisons; no new sweep.
    for enabled in (False,True):
        class OriginalThroughWrapper(old.CoreTests):
            def setUp(self):
                self.previous=old.solve
                old.solve=lambda *a,**kw:core_cached.solve_cached(*a,cache_enabled=enabled,**kw)
            def tearDown(self):old.solve=self.previous
        # Bind the flag now rather than close over the final loop value.
        flag=enabled
        def set_up(self,flag=flag):
            self.previous=old.solve
            old.solve=lambda *a,**kw:core_cached.solve_cached(*a,cache_enabled=flag,**kw)
        OriginalThroughWrapper.setUp=set_up
        suite.addTests(loader.loadTestsFromTestCase(OriginalThroughWrapper))
    return suite

if __name__=='__main__':unittest.main(verbosity=2)
