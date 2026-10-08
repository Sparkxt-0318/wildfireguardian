"""Author development controls. No fresh confirmation data is read."""
from pathlib import Path
import copy
from dataclasses import FrozenInstanceError
from fractions import Fraction
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
D=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(D/'candidate'));sys.path.insert(0,str(D/'tests'))
import search_followup as sf
from routing import core
from reference_fixtures import fixtures

class SearchDevelopment(unittest.TestCase):
    def test_all_known_exact_controls_cold_and_warm(self):
        for case in fixtures():
            g,h,q=case['graph'],case['hazard'],case['request']
            q['objective']='earliest_arrival'
            untouched=core.solve(g,h,q)
            for mode in sf.MODES:
                with self.subTest(case=case['id'],mode=mode):
                    session=sf.SearchFollowup()
                    for warm in (False,True):
                        report=session.run(g,h,None,q,mode=mode)
                        p=report['primary_search']
                        self.assertEqual(p['status'],untouched['status'],report)
                        self.assertEqual(p['arrival'],untouched['arrival'])
                        self.assertEqual(p.get('per_member'),untouched.get('per_member'))
                        self.assertEqual(report['whole_road_check']['status'],'UNRESOLVED')
                        self.assertEqual(report['whole_road_check']['reason'],'SOURCE_CONTRACT_UNAVAILABLE')
                        self.assertEqual(report['integrated_status'],'UNRESOLVED')
                        self.assertFalse(report['road_optimality_claim'])
                        self.assertEqual(report['epoch_reused'],warm)
                        self.assertEqual(report['search_resource_limits'],q['limits'])
                        self.assertTrue(report['limits_exactly_preserved'])
                        self.assertGreaterEqual(report['combined_lifecycle_wall_s'],report['timing_s']['primary_search_including_solver_preprocessing_and_center_check'])

    def fixture(self):
        c=fixtures()[0];c['request']['objective']='earliest_arrival';return c['graph'],c['hazard'],c['request']

    def test_exact_relaxed_distances_against_simple_path_enumeration(self):
        g,h,q=self.fixture();g['edges'].append({'id':'DA','u':'D','v':'A','travel_ticks':7,'segments':[]})
        # Geometry irrelevant to this independent graph-distance reference.
        dist=core._lower_bounds(g,q['destinations'],h['dt'])
        outgoing={n['id']:[] for n in g['nodes']}
        for e in g['edges']:outgoing[e['u']].append(e)
        def reference(node,visited):
            if node=='D':return 0
            values=[e['travel_ticks']+reference(e['v'],visited|{node}) for e in outgoing[node] if e['v'] not in visited|{node}]
            return min(values,default=float('inf'))
        for n in outgoing:self.assertEqual(dist[n],reference(n,set()))
        self.assertTrue(all(type(d) is int for d in dist.values()))
        for e in g['edges']:self.assertLessEqual(dist[e['u']],e['travel_ticks']+dist[e['v']])

    def test_integer_envelope_and_fraction_boundary(self):
        g,h,q=self.fixture();sf._heuristic_envelope(g,h,q)
        for value in (.5,1.0,True):
            with self.subTest(dt=value):
                hh=copy.deepcopy(h);hh['dt']=value
                with self.assertRaises(ValueError):sf._heuristic_envelope(g,hh,q)
        gg=copy.deepcopy(g);gg['edges'][0]['travel_ticks']=2**53
        with self.assertRaises(ValueError):sf._heuristic_envelope(gg,h,q)
        # Float sum used previously could round 2**53+1 down to the accepted limit.
        gg=copy.deepcopy(g);gg['edges'][0]['travel_ticks']=2**53-4
        qq=copy.deepcopy(q);qq['horizon']=0.0;qq['departure']=1.0
        with self.assertRaises(ValueError):sf._heuristic_envelope(gg,h,qq)

    def test_epoch_ownership_and_request_freshness(self):
        g,h,q=self.fixture();epoch=sf.prepare_epoch(g,h,None)
        with self.assertRaises(FrozenInstanceError):epoch._hazard=b'{}'
        snapshot=epoch.graph_snapshot();snapshot['nodes'][0]['x']=999
        self.assertNotEqual(snapshot,epoch.graph_snapshot())
        snapshot=epoch.hazard_snapshot();snapshot['members'][0]['id']='wrong'
        self.assertNotEqual(snapshot,epoch.hazard_snapshot())
        session=sf.SearchFollowup(prepared_epoch=epoch)
        p=session.run(g,h,None,q)['primary_search'];self.assertEqual(p['status'],'CONDITIONAL_OPTIMUM')
        for key,value in [('hazard_version',2),('incurred',{'m0':101,'m1':0}),('incoming_edge','BM')]:
            qq=copy.deepcopy(q);qq[key]=value
            untouched=core.solve(g,h,qq)
            self.assertEqual(session.run(g,h,None,qq)['primary_search']['status'],untouched['status'])

    def test_reject_graph_hazard_content_and_replacement(self):
        for target in ('graph','hazard'):
            with self.subTest(target=target):
                g,h,q=self.fixture();epoch=sf.prepare_epoch(g,h,None)
                if target=='graph':g['nodes'][0]['waitable']=False
                else:h['members'][0]['flux'][0][0]=1
                report=sf.run_search(g,h,None,q,prepared_epoch=epoch)
                self.assertEqual(report['primary_search_status'],'NOT_RUN')
                self.assertIn('NEW_EPOCH_REQUIRED',report['external_failure']['reason'])
                self.assertFalse(report['center_optimality_claim'])
                new=sf.prepare_epoch(g,h,None)
                report=sf.run_search(g,h,None,q,prepared_epoch=new)
                self.assertNotEqual(report['primary_search_status'],'NOT_RUN')

    def test_full_source_packet_bridge_and_changes(self):
        g,h,q=self.fixture()
        # Explicit synthetic native interval packet only for source-binding checks.
        # No source event arrays exist, so this does not authorize road checking.
        shape=(len(h['members'][0]['breakpoints'])-1,4,6)
        md={'schema':'wfg.forecast.native-intervals/1','mode':'research','assumption_id':'synthetic:test',
            'parent_forecast_sha256':'0'*64,'original_support':{},'constructed_support':{},
            'graph_revision':g['revision'],'crs':g['crs'],'shape':[4,6],
            'affine_transform':[10,0,0,0,10,0], 'flux_units':'W/m2',
            'flux_semantics':'interval_upper_bound_incident_radiant_flux','flame_semantics':'contact_anywhere_during_interval',
            'present_fire_included':True,'present_fire_support':'explicit synthetic test',
            'physical_scope':'Synthetic binding test, no physical evidence','evidence_class':'LABELLED_FIXTURE',
            'source':'author development','time_origin':h['time_origin'],'issued_at':h['issued_at'],
            'available_at':h['available_at'],'breakpoints_s':h['members'][0]['breakpoints'],'dt_s':1,'version':1,
            'construction':{'scenario_ids':['m0','m1','m2','m3']}}
        arrays={'flux_w_m2':np.zeros((4,*shape)), 'flame_contact':np.zeros((4,*shape),bool),'support':np.ones((4,*shape),bool)}
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'REPORT.json').write_text(json.dumps({'native_metadata':md,'rows':[{'request':{'incurred':dict.fromkeys(['m0','m1','m2','m3'],0),'budgets':{'dose':dict.fromkeys(['m0','m1','m2','m3'],100)}}}]}))
            (p/'NATIVE_METADATA.json').write_text(json.dumps(md));np.savez(p/'constructed_arrays.npz',**arrays)
            hh=sf.convert(g,md,[{'id':m,**{k:a[i] for k,a in arrays.items()}}for i,m in enumerate(['m0','m1','m2','m3'])])
            epoch=sf.prepare_epoch(g,hh,p);epoch.validate_binding(g,hh,p)
            for name in sf.SOURCE_NAMES:
                old=(p/name).read_bytes();(p/name).write_bytes(old+b' ')
                with self.subTest(file=name):
                    with self.assertRaises(sf.EpochMismatch):epoch.validate_binding(g,hh,p)
                (p/name).write_bytes(old)
            changed=copy.deepcopy(hh);changed['members'][0]['flux'][0][0]=.001
            with self.assertRaises(sf.EpochMismatch):sf.prepare_epoch(g,changed,p)
            altered=copy.deepcopy(md);altered['version']=2;(p/'NATIVE_METADATA.json').write_text(json.dumps(altered))
            with self.assertRaises(sf.EpochMismatch):sf.prepare_epoch(g,hh,p)

    def test_mutation_after_center_search_fail_closed(self):
        g,h,q=self.fixture();real=__import__('routing.core_cached',fromlist=['solve_cached']).solve_cached
        def mutate(*args,**kwargs):
            result=real(*args,**kwargs);q['incurred']['m0']=1;return result
        with patch('routing.core_cached.solve_cached',mutate):report=sf.run_search(g,h,None,q)
        self.assertEqual(report['primary_search']['status'],'CONDITIONAL_OPTIMUM')
        self.assertEqual(report['integrated_status'],'UNRESOLVED')
        self.assertFalse(report['center_optimality_claim'])

    def test_timeout_primary_and_no_unchecked_incumbent(self):
        g,h,q=self.fixture();q['limits']['wall_s']=0
        for mode in sf.MODES:
            with self.subTest(mode=mode):
                result=sf.run_search(g,h,None,q,mode=mode)
                self.assertEqual(result['primary_search_status'],'TIMEOUT')
                self.assertIsNone(result['witness_origin'])
                self.assertEqual(result['integrated_status'],'UNRESOLVED')
        for cap in ('max_labels','max_expansions','frontier_width'):
            g,h,q=self.fixture();q['limits'][cap]=1
            for mode in sf.MODES:
                untouched=core.solve(g,h,{**q,'solver':'astar' if mode in ('heuristic','combined') else 'baseline'})
                result=sf.run_search(g,h,None,q,mode=mode)
                self.assertEqual(result['primary_search_status'],untouched['status'])
                self.assertEqual(result['primary_search']['reason'],untouched['reason'])

    def test_checker_cap_argument_contract(self):
        g,h,q=self.fixture()
        for cap in (True, False, -1, float('nan'), float('inf'), '30', None):
            with self.subTest(cap=repr(cap)):
                report=sf.run_search(g,h,None,q,checker_wall_s=cap)
                self.assertEqual(report['primary_search_status'],'NOT_RUN')
                self.assertIn('CHECKER_CAP',report['external_failure']['reason'])
        for enabled in (0,1,'yes',None):
            report=sf.run_search(g,h,None,q,check_witness=enabled)
            self.assertIn('CHECK_WITNESS_BOOLEAN',report['external_failure']['reason'])

    def test_original_real_v2_source_member_namespace(self):
        # Original timeout development packet, not a fresh confirmation case.
        source=D/'baseline/timeout_inputs/20220304T030000Z_baseline_difficult'
        g=json.loads((D/'sample/uljin_graph.json').read_text())
        h=json.loads((source/'HAZARD.json').read_text())
        report=json.loads((source/'REPORT.json').read_text());md=report['native_metadata']
        expected=['construction:'+md['construction_id'][:20]+':'+str(i) for i in range(4)]
        self.assertNotEqual(md['construction']['scenario_ids'],expected)
        self.assertEqual(sf._packet_member_ids(md,report,h),expected)
        epoch=sf.prepare_epoch(g,h,source);epoch.validate_binding(g,h,source)
        self.assertEqual([m['id'] for m in epoch.hazard_snapshot()['members']],expected)
        wrong_h=copy.deepcopy(h);wrong_h['members'].reverse()
        with self.assertRaises(sf.EpochMismatch):sf._packet_member_ids(md,report,wrong_h)
        wrong_report=copy.deepcopy(report)
        inc=wrong_report['rows'][0]['request']['incurred']
        wrong_report['rows'][0]['request']['incurred']=dict(reversed(list(inc.items())))
        with self.assertRaises(sf.EpochMismatch):sf._packet_member_ids(md,wrong_report,h)
        wrong_md=copy.deepcopy(md);wrong_md['construction_id']='f'*64
        with self.assertRaises(sf.EpochMismatch):sf._packet_member_ids(wrong_md,report,h)
        # Even a coherent ID relabeling must not forge original source provenance.
        forged_md=copy.deepcopy(md);forged_md['construction_id']='0'*64
        forged_ids=['construction:'+forged_md['construction_id'][:20]+':'+str(i) for i in range(4)]
        forged_h=copy.deepcopy(h);forged_report=copy.deepcopy(report)
        for i,m in enumerate(forged_h['members']):m['id']=forged_ids[i]
        for row in forged_report['rows']:
            req=row['request']
            req['incurred']=dict(zip(forged_ids,req['incurred'].values()))
            req['budgets']['dose']=dict(zip(forged_ids,req['budgets']['dose'].values()))
        with self.assertRaisesRegex(sf.EpochMismatch,'DIGEST_MISMATCH'):
            sf._packet_member_ids(forged_md,forged_report,forged_h)


    def test_settings_and_physics_implementation_invalidation(self):
        g,h,q=self.fixture();epoch=sf.prepare_epoch(g,h,None)
        with self.assertRaises(sf.EpochMismatch):
            epoch.validate_binding(g,h,None,{'receiver_span_m':17})
        actual=sf._implementation_bytes()
        with patch.object(sf,'_implementation_bytes',return_value=actual+(('changed_physics',b'changed'),)):
            with self.assertRaises(sf.EpochMismatch):epoch.validate_binding(g,h,None)
        session=sf.SearchFollowup(prepared_epoch=epoch)
        session._settings['receiver_span_m']=17
        result=session.run(g,h,None,q)
        self.assertEqual(result['primary_search_status'],'NOT_RUN')
        self.assertFalse(result['integrated_witness_available'])

    def test_checked_timeout_incumbent_is_secondary(self):
        g,h,q=self.fixture();solution=core.solve(g,h,q)
        incumbent={**solution,'status':'CHECKED_ROUTE'}
        primary={'status':'TIMEOUT','reason':'WALL_CLOCK_AFTER_CHECK','checked_incumbent':incumbent}
        with patch('routing.core_cached.solve_cached',return_value=primary):
            report=sf.run_search(g,h,None,q)
        self.assertEqual(report['primary_search_status'],'TIMEOUT')
        self.assertEqual(report['primary_search'],primary)
        self.assertEqual(report['witness_origin'],'EXPLICIT_CHECKED_TIMEOUT_INCUMBENT')
        self.assertFalse(report['center_optimality_claim'])
        self.assertFalse(report['integrated_witness_available'])
        unchecked={**incumbent,'checker':{'ok':False}}
        with patch('routing.core_cached.solve_cached',return_value={**primary,'checked_incumbent':unchecked}):
            report=sf.run_search(g,h,None,q)
        self.assertIsNone(report['witness_origin'])

    def test_nonjson_masks_rejected(self):
        g,h,q=self.fixture()
        for bad in (np.ma.array([1],mask=[True]),np.float64(1), (1,), {1:'x'}):
            qq=copy.deepcopy(q);qq['extra']=bad
            report=sf.run_search(g,h,None,qq)
            self.assertEqual(report['primary_search_status'],'NOT_RUN')
            self.assertEqual(report['integrated_status'],'UNRESOLVED')

if __name__=='__main__':unittest.main(verbosity=2)
