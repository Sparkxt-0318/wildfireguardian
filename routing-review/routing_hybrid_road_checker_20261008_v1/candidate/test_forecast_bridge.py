import json
from copy import deepcopy
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'routing-package'))
from forecast_bridge import convert, inspect_mentor_export, IntegrationError
from routing.core import solve
from routing.independent import check_route, exhaustive
from routing.session import RoutingSession


def native(case, north_up=True):
    g,h=case['graph'],case['hazard']; grid=g['grid']
    r=grid['resolution']; height,width=grid['height'],grid['width']
    bp=h['members'][0]['breakpoints']
    md={'schema':'wfg.forecast.native-intervals/1','graph_revision':g['revision'],
        'crs':g['crs'],'shape':[height,width],
        'affine_transform':[r,0,grid['x0'],0,-r if north_up else r,
                            grid['y0']+height*r if north_up else grid['y0']],
        'flux_units':'W/m2','flux_semantics':'piecewise_constant_incident_radiant_flux',
        'flame_semantics':'piecewise_constant_flame_contact','present_fire_included':True,
        'physical_scope':'Labelled fixture; explicit cellwise radiant proxy, no physical-safety claim',
        'evidence_class':'LABELLED_FIXTURE','source':'integration regression fixture',
        'time_origin':h['time_origin'],'issued_at':h['issued_at'],'available_at':h['available_at'],
        'breakpoints_s':bp,'dt_s':h['dt'],'version':h['version'],
        'unsupported_channels':h['unsupported_channels']}
    members=[]
    for m in h['members']:
        a={'id':m['id']}
        for dst,src in [('flux_w_m2','flux'),('flame_contact','flame'),('support','support')]:
            ar=np.asarray(m[src]).reshape(len(bp)-1,height,width).copy()
            if dst=='flux_w_m2':ar=ar.astype(float)*1000
            if north_up:ar=ar[:,::-1,:]
            a[dst]=ar
        members.append(a)
    return md,members


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.case=json.loads((ROOT/'routing-package/fixtures/example.json').read_text())
        self.md,self.members=native(self.case)

    def rejection(self,code,md=None,members=None):
        with self.assertRaises(IntegrationError) as exc:
            convert(self.case['graph'],md or self.md,members or self.members)
        self.assertEqual(code,exc.exception.code)

    def test_orientation_units_support_and_input_immutability(self):
        # Different north/south values detect a row inversion hidden by uniform fixtures.
        self.members[0]['flux_w_m2'][0]=np.arange(8).reshape(2,4)*1000.0
        self.members[0]['support'][0,0,3]=False
        self.members[0]['flux_w_m2'][0,0,3]=np.nan
        before=self.members[0]['flux_w_m2'].copy()
        h=convert(self.case['graph'],self.md,self.members)
        self.assertEqual(h['members'][0]['flux'][0],[4.0,5.0,6.0,7.0,0.0,1.0,2.0,0.0])
        self.assertEqual(h['members'][0]['support'][0],[True,True,True,True,True,True,True,False])
        np.testing.assert_equal(self.members[0]['flux_w_m2'],before)

    def test_north_and_south_up_are_equivalent(self):
        a=convert(self.case['graph'],*native(self.case,True))
        b=convert(self.case['graph'],*native(self.case,False))
        self.assertEqual(a['members'],b['members'])

    def test_probability_is_not_flame(self):
        del self.members[0]['flame_contact'];self.members[0]['probability']=np.zeros((1,2,4))
        self.rejection('FLAME_FIELD_MISSING')

    def test_mean_flux_is_not_interval_flux(self):
        self.md['flux_semantics']='interval_mean_incident_radiant_flux'
        self.rejection('TEMPORAL_FLUX_SEMANTICS')

    def test_present_fire_is_mandatory(self):
        self.md['present_fire_included']=False
        self.rejection('PRESENT_FIRE_MISSING')

    def test_supported_nan_rejected(self):
        self.members[0]['flux_w_m2'][0,0,0]=np.nan
        self.rejection('FLUX_VALUES')

    def test_negative_and_infinite_flux_rejected_even_when_masked(self):
        for value in [-1,np.inf]:
            with self.subTest(value=value):
                self.members[0]['flux_w_m2'][0,0,0]=value
                self.members[0]['support'][0,0,0]=False
                self.rejection('FLUX_VALUES')

    def test_numeric_mask_is_not_boolean(self):
        self.members[0]['flame_contact']=self.members[0]['flame_contact'].astype(int)
        self.rejection('BOOLEAN_MASK')

    def test_member_identity_duplicates_rejected(self):
        self.members[1]['id']=self.members[0]['id'];self.rejection('MEMBER_ID')

    def test_grid_crs_and_rotation_mismatch_rejected(self):
        for key,value,code in [('crs','EPSG:5070','CRS_ALIGNMENT'),
                ('shape',[1,8],'GRID_ALIGNMENT'),
                ('affine_transform',[10,1,0,0,-10,20],'GRID_ALIGNMENT'),
                ('graph_revision','other','GRAPH_REVISION')]:
            with self.subTest(key=key):
                md=deepcopy(self.md);md[key]=value;self.rejection(code,md=md)

    def test_bad_intervals_and_naive_times_rejected(self):
        md=deepcopy(self.md);md['breakpoints_s']=[0,0];self.rejection('BREAKPOINTS',md=md)
        md=deepcopy(self.md);md['available_at']='2026-10-04';self.rejection('TIME_METADATA',md=md)

    def test_native_roundtrip_routes_and_exhaustive_references(self):
        cases=json.loads((ROOT/'routing-package/fixtures/evaluation_cases.json').read_text())['cases']
        records=[]
        for case in cases:
            with self.subTest(case=case['id']):
                h=convert(case['graph'],*native(case))
                a=solve(case['graph'],case['hazard'],case['request'])
                b=solve(case['graph'],h,case['request'])
                self.assertEqual(a['status'],b['status'])
                self.assertEqual(a.get('arrival'),b.get('arrival'))
                self.assertEqual(a.get('per_member'),b.get('per_member'))
                ref=exhaustive(case['graph'],h,case['request'])
                # The graph-aware search names structural disconnection explicitly;
                # timed-walk exhaustion certifies the same absence as infeasibility.
                expected='PROVEN_INFEASIBLE' if a['status']=='DISCONNECTED' else a['status']
                self.assertEqual(expected,ref['status'])
                if b.get('destination'):
                    checked=check_route(case['graph'],h,case['request'],b['legs'],b['destination'])
                    self.assertTrue(checked['ok'])
                records.append({'id':case['id'],'baseline':a['status'],'adapted':b['status'],
                                'reference':ref['status'],'arrival':b.get('arrival')})
        (ROOT.parent/'audit'/'bridge_reference_rows.json').write_text(json.dumps(records,indent=2))

    def test_flame_and_dose_change_route_selection(self):
        base=convert(self.case['graph'],self.md,self.members)
        a=solve(self.case['graph'],base,self.case['request'])
        h=deepcopy(base)
        for m in h['members']:m['flame'][0][1]=True
        b=solve(self.case['graph'],h,self.case['request'])
        self.assertEqual(a['arrival'],4.0);self.assertEqual(b['arrival'],6.0)
        checked=check_route(self.case['graph'],h,self.case['request'],a['legs'],a['destination'])
        self.assertFalse(checked['ok']);self.assertIn('FLAME_CONTACT',checked['codes'])
        # Separate dose-only rejection: peak remains below its cap and flame is false.
        h=deepcopy(base);req=deepcopy(self.case['request'])
        req['budgets']['dose']={'m0':15.0,'m1':15.0}
        for m in h['members']:m['flux'][0][1]=9.0
        b=solve(self.case['graph'],h,req)
        self.assertEqual(b['arrival'],6.0)
        checked=check_route(self.case['graph'],h,req,a['legs'],a['destination'])
        self.assertIn('DOSE_BUDGET',checked['codes'])
        self.assertNotIn('PEAK_BUDGET',checked['codes']);self.assertNotIn('FLAME_CONTACT',checked['codes'])

    def test_unknown_support_cannot_become_global_certificate(self):
        for m in self.members:m['support'][:]=False;m['flux_w_m2'][:]=np.nan
        h=convert(self.case['graph'],self.md,self.members)
        out=solve(self.case['graph'],h,self.case['request'])
        self.assertNotIn(out['status'],['CONDITIONAL_OPTIMUM','PROVEN_INFEASIBLE'])

    def test_serialized_forecast_update_preserves_history_and_rejects_stale_commit(self):
        h=convert(self.case['graph'],self.md,self.members)
        session=RoutingSession(self.case['graph'],prepare=True)
        self.assertEqual(session.accept_update(h,self.case['request']['as_of'])['status'],'ACCEPTED_UPDATE')
        req=deepcopy(self.case['request']);req['incurred']={'m0':1.0,'m1':2.0}
        old=session.plan(req);self.assertTrue(session.commit(old))
        md=deepcopy(self.md);md['version']=2
        updated=convert(self.case['graph'],md,self.members)
        self.assertEqual(session.accept_update(updated,req['as_of'])['status'],'ACCEPTED_UPDATE')
        self.assertFalse(session.commit(old))
        new=session.plan(req);self.assertTrue(session.commit(new))
        self.assertEqual(new['request']['incurred'],{'m0':1.0,'m1':2.0})
        self.assertEqual(session.accept_update(h,req['as_of'])['status'],'STALE_UPDATE')

    def test_incomplete_native_mentor_export_reports_separate_blockers(self):
        report=inspect_mentor_export({}, {'expected_heat_flux_w_m2':np.full((2,4),np.nan)})
        self.assertFalse(report['ready_for_existing_router'])
        codes={r['code'] for r in report['blockers']}
        self.assertTrue({'FLAME_FIELD_MISSING','PRESENT_FIRE_MISSING','TEMPORAL_FLUX_SEMANTICS','THERMAL_SUPPORT_INCOMPLETE'} <= codes)

    def test_cli_routes_checked_fixture_on_raw_and_prepared_paths(self):
        outputs=[]
        for prepared in (False,True):
            command=[sys.executable,'-B',str(ROOT/'integrate.py'),'route',
                     '--graph',str(ROOT/'example_native/graph.json'),
                     '--request',str(ROOT/'example_native/request.json'),
                     '--bundle',str(ROOT/'example_native/bundle.json')]
            if prepared:command.append('--prepare-graph')
            run=subprocess.run(command,capture_output=True,text=True,check=True)
            out=json.loads(run.stdout);self.assertTrue(out['integration_checker']['ok'])
            self.assertEqual(out['integration_evidence_class'],'LABELLED_FIXTURE')
            self.assertFalse(out['physical_safety_claim']);outputs.append(out)
        for key in ['status','arrival','legs','per_member']:
            self.assertEqual(outputs[0][key],outputs[1][key])

    def test_cli_rejects_array_path_escape_before_reading(self):
        from integrate import load_bundle
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'bundle.json'
            p.write_text(json.dumps({'metadata':self.md,'members':[{'id':'m0','arrays_file':'../secret.npz'}]}))
            with self.assertRaises(IntegrationError) as exc:load_bundle(p)
            self.assertEqual(exc.exception.code,'ARRAY_PATH')


if __name__=='__main__':unittest.main(verbosity=2)
