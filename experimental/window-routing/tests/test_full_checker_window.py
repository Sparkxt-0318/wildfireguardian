"""Source-frozen synthetic controls; parent dispatch only, no field validation."""
from fractions import Fraction as F
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import time
import unittest
import numpy as np

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'stack/routing_candidate/baseline'
sys.path.insert(0,str(BASE))
from hybrid_radiation import HybridRadiationBounds
from hybrid_checker import HybridChecker
from road_exposure import outward_float

ORACLE_PATH=HERE/'oracle.py'
spec=importlib.util.spec_from_file_location('full_window_independent_oracle',ORACLE_PATH)
ORACLE=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ORACLE;spec.loader.exec_module(ORACLE)
IDS=('a','b','c','d')
ORIGIN='2026-01-01T00:00:00Z'
SETTINGS={'wall_s':10,'max_refinement_levels':1}


def fixture(x0=1000,y0=1000,res=100):
    events=np.full((4,4,4),np.inf)
    current=np.zeros((4,4),dtype=bool);current.ravel()[:12]=True
    events.reshape(4,16)[:,12]=2
    events.reshape(4,16)[:,13]=10
    events.reshape(4,16)[:,14]=6
    events.reshape(4,16)[:,15]=[20,21,22,7]
    config={'version':'wfg.hazard.construction/1','horizon_s':30,'burning_duration_s':4,
            'initial_remaining_s':4,'fuel_load_kg_m2':1,'heat_of_combustion_j_kg':80000,
            'consumed_fraction':1,'radiative_fraction':1,'atmospheric_transmissivity':1,
            'emission_height_m':4,'receiver_height_m':1}
    return events,current,config,(res,0,x0,0,-res,y0+4*res),np.ones((4,4),dtype=bool)


def model(window=None,**kw):
    events,current,config,affine,support=fixture(**kw)
    out=HybridRadiationBounds(events,current,config,affine,IDS,support,settings=SETTINGS)
    if window is not None:out._bind_request_window(window)
    return out


def point_leg(t0,t1=None,x=1005,y=1005):
    return {'kind':'DWELL','start':t0,'end':t0 if t1 is None else t1,'p0':[x,y],'p1':[x,y]}


def bound(m,legs,prior=0,dose=1000000,peak=1000000):
    return m.trajectory_bound(legs,incurred={mid:prior for mid in IDS},
        dose_budget_kj_m2={mid:dose for mid in IDS},peak_budget_kw_m2=peak,wall_s=10)


def packet(directory):
    events,current,config,affine,support=fixture()
    p=Path(directory)
    np.savez(p/'constructed_arrays.npz',ignition_time_s=events,current_active=current,support=support)
    report={'native_metadata':{'time_origin':ORIGIN,'affine_transform':list(affine),
        'construction':{'assumptions':config,'parent_forecast':{'cutoff_utc':ORIGIN}}},
        'rows':[{'request':{'as_of':ORIGIN,'departure':0,'incurred':dict.fromkeys(IDS,0)}}]}
    (p/'REPORT.json').write_text(json.dumps(report))
    return p


def mission(departure=6,horizon=10,x=1005):
    graph={'revision':'synthetic-full-window-1','nodes':[{'id':'s','x':x,'y':1005,'waitable':True},
         {'id':'d','x':x+10,'y':1005,'waitable':True}],
         'edges':[{'id':'e','u':'s','v':'d','travel_ticks':2}],'forbidden_turns':[]}
    request={'graph_revision':graph['revision'],'as_of':ORIGIN,'exposure_scope':'including_dwell',
       'position':{'node':'s'},'incoming_edge':None,'departure':departure,'horizon':horizon,
       'incurred':dict.fromkeys(IDS,0),'budgets':{'dose':dict.fromkeys(IDS,1000000),'peak':1000000},
       'destinations':[{'node':'d','dwell':1,'open_intervals':[[0,30]]}]}
    legs=[{'kind':'EDGE','edge':'e','start':departure,'end':departure+2}]
    return graph,request,legs,'d'


class FullCheckerWindowControls(unittest.TestCase):
    def test_01_exact_closed_window_half_open_activity_and_four_member_union(self):
        m=model((6,10))
        self.assertEqual(m._window_source_indices.tolist(),[13,14,15])
        self.assertFalse(m._window_source_mask[12])  # expiry equals departure
        self.assertTrue(m._window_source_mask[13])   # birth equals horizon
        self.assertTrue(m._window_source_mask[15])   # only member d active in window
        self.assertEqual(m._potential_count,16)
        self.assertFalse(m._window_source_mask.flags.writeable)
        self.assertFalse(m._window_source_indices.flags.writeable)

    def test_02_fractional_window_endpoint_rules(self):
        events=np.array([[[2.5,3.,3.5,8.]]]*4);current=np.zeros((1,4),dtype=bool)
        config=fixture()[2];config.update(burning_duration_s=.5,initial_remaining_s=.5,horizon_s=10)
        m=HybridRadiationBounds(events,current,config,(10,0,-40,0,-10,10),IDS,np.ones((1,4),bool),settings=SETTINGS)
        m._bind_request_window((F(3),F(7,2)))
        self.assertEqual(m._window_source_indices.tolist(),[1,2])
        self.assertEqual(m.request_window,(F(3),F(7,2)))

    def test_03_invalid_or_uncovered_windows_fail_closed(self):
        for value in ((-1,4),(7,6),(0,31),(True,4),(0,float('nan')),(0,),None):
            with self.subTest(value=repr(value)),self.assertRaises((ValueError,TypeError)):
                model()._bind_request_window(value)

    def test_04_native_axis_activity_events_geometry_and_partition_inputs_preserved(self):
        full=model();view=model((6,10))
        self.assertEqual(view._events,full._events);self.assertEqual(view._current,full._current)
        self.assertEqual(view._rectangles,full._rectangles);self.assertEqual(view._domain,full._domain)
        self.assertEqual(view._normalise.__self__.affine,full._normalise.__self__.affine)
        for attr in ('_birth','_expiry','_possible'):
            for a,b in zip(getattr(full,attr),getattr(view,attr)):
                np.testing.assert_array_equal(a,b);self.assertFalse(b.flags.writeable)
        box=tuple(map(F,(1005,1005,1005,1005)));lo,hi=view._coefficients(box)
        self.assertEqual(lo.shape,(16,));self.assertEqual(hi.shape,(16,))
        for i in range(13):self.assertEqual(lo[i],0);self.assertEqual(hi[i],outward_float(view._density/2,True))
        self.assertFalse(lo.flags.writeable);self.assertFalse(hi.flags.writeable)

    def test_05_sparse_policy_uses_global_potential_count(self):
        m=model((6,10));out=bound(m,[point_leg(6,9)])
        self.assertTrue(out['complete']);self.assertEqual(out['status'],'CERTIFIED_RADIATION')
        self.assertEqual(out['window_active_source_count'],3)
        self.assertEqual(out['hybrid_policy']['ever_active_source_count'],16)
        self.assertFalse(out['hybrid_policy']['sparse_realization'])
        self.assertEqual(out['analytic_source_bounds'],0)
        self.assertGreater(out['radial_tiled_sources'],0)

    def test_06_active_native_coefficients_equal_unwindowed_same_policy(self):
        full=model();view=model((6,10));box=tuple(map(F,(1005,1005,1005,1005)))
        oldlo,oldhi=full._coefficients(box);lo,hi=view._coefficients(box);idx=view._window_source_indices
        np.testing.assert_array_equal(lo[idx],oldlo[idx]);np.testing.assert_array_equal(hi[idx],oldhi[idx])
        self.assertLess(view._source_bounds,full._source_bounds)
        self.assertEqual(view._potential_count,full._potential_count)

    def test_07_signed_coordinates_enclose_independent_rational_point_reference(self):
        m=model((6,10),x0=-200,y0=-400,res=10);box=tuple(map(F,(-195,-195,-395,-395)))
        lo,hi=m._coefficients(box)
        for i in m._window_source_indices:
            ref=ORACLE.rectangle_coefficient(m._rectangles[i],box,m._h)*m._density
            self.assertLessEqual(F(float(lo[i])),ref.lo)
            self.assertGreaterEqual(F(float(hi[i])),ref.hi)
        self.assertIs(m._analytic_kernel.guard.__self__,m)

    def test_08_empty_selection_retains_prior_once_and_exact_budget_boundary(self):
        m=model((27,28));self.assertEqual(m._window_source_indices.tolist(),[])
        out=bound(m,[point_leg(27,28)],prior=25,dose=25,peak=0)
        self.assertEqual(out['status'],'CERTIFIED_RADIATION')
        for row in out['per_member']:
            self.assertEqual(row['dose_lower_kj_m2'],25);self.assertEqual(row['dose_upper_kj_m2'],25)
            self.assertEqual(row['peak_lower_kw_m2'],0);self.assertEqual(row['peak_upper_kw_m2'],0)
        reject=bound(m,[point_leg(27,28)],prior=25,dose=F(25)-F(1,1000000),peak=0)
        self.assertEqual(reject['status'],'DEFINITE_REJECT')

    def test_09_birth_at_horizon_instantaneous_peak_is_not_omitted(self):
        m=model((10,10));out=bound(m,[point_leg(10)],peak=0)
        self.assertEqual(out['status'],'DEFINITE_REJECT')
        self.assertTrue(all(row['peak_lower_kw_m2']>0 for row in out['per_member']))
        for row in out['per_member']:
            self.assertLessEqual(row['dose_lower_kj_m2'],0);self.assertGreaterEqual(row['dose_upper_kj_m2'],0)

    def test_10_out_of_window_queries_rejected_even_with_no_active_sources(self):
        for window,legs in (((6,10),[point_leg(5,6)]),((6,10),[point_leg(10,11)]),
                            ((6,10),[point_leg(6,7),point_leg(9,11)]),((27,28),[point_leg(26,27)])):
            with self.subTest(window=window,legs=legs),self.assertRaisesRegex(ValueError,'OUTSIDE_BOUND_WINDOW'):
                bound(model(window),legs)

    def test_11_factory_binds_after_final_report_clock_and_owns_fresh_kernel(self):
        with tempfile.TemporaryDirectory() as d:
            p=packet(d);full=HybridRadiationBounds.from_case(p,settings=SETTINGS)
            first=HybridRadiationBounds.from_case_for_window(p,(6,10),settings=SETTINGS)
            second=HybridRadiationBounds.from_case_for_window(p,(7,11),settings=SETTINGS)
            self.assertEqual(first._native_cache_identity,full.cache_identity)
            self.assertEqual(first.clock_contract,full.clock_contract)
            self.assertNotEqual(first.cache_identity,full.cache_identity)
            self.assertNotEqual(first.cache_identity,second.cache_identity)
            self.assertIsNot(first._analytic_kernel,second._analytic_kernel)
            self.assertIs(first._analytic_kernel.guard.__self__,first)
            self.assertIs(second._analytic_kernel.guard.__self__,second)
            self.assertEqual(first.cache_info()['request_window_s'],['6','10'])

    def test_12_binding_is_one_time_and_requires_unused_cache(self):
        m=model((6,10))
        with self.assertRaisesRegex(ValueError,'FRESH_UNUSED'):m._bind_request_window((7,11))
        used=model();used._coefficients(tuple(map(F,(1005,1005,1005,1005))))
        with self.assertRaisesRegex(ValueError,'FRESH_UNUSED'):used._bind_request_window((6,10))

    def test_13_window_or_cache_authority_mutation_fails_closed(self):
        first=model((6,10));first._request_window=(F(0),F(30))
        with self.assertRaisesRegex(ValueError,'EPOCH_CHANGED'):bound(first,[point_leg(6)])
        second=model((6,10));second.cache_identity='changed'
        with self.assertRaisesRegex(ValueError,'EPOCH_CHANGED'):second.cache_info()

    def test_14_actual_checker_reuses_same_window_and_replaces_changed_window(self):
        with tempfile.TemporaryDirectory() as d:
            checker=HybridChecker(packet(d),settings=SETTINGS)
            one=checker.check(*mission(),wall_s=10);old=checker._radiation
            self.assertEqual(one['status'],'CERTIFIED_ADMISSIBLE')
            self.assertFalse(one['cache_work']['radiation_object_reused'])
            two=checker.check(*mission(),wall_s=10)
            self.assertEqual(two['status'],'CERTIFIED_ADMISSIBLE');self.assertIs(checker._radiation,old)
            self.assertTrue(two['cache_work']['radiation_object_reused'])
            three=checker.check(*mission(7,11),wall_s=10)
            self.assertEqual(three['status'],'CERTIFIED_ADMISSIBLE');self.assertIsNot(checker._radiation,old)
            self.assertFalse(three['cache_work']['radiation_object_reused'])
            self.assertIs(checker._radiation._analytic_kernel.guard.__self__,checker._radiation)
            self.assertNotEqual(old.cache_identity,checker._radiation.cache_identity)

    def test_15_actual_checker_keeps_full_flame_contact_gate(self):
        with tempfile.TemporaryDirectory() as d:
            checker=HybridChecker(packet(d),settings=SETTINGS)
            out=checker.check(*mission(x=1205),wall_s=10)
            self.assertEqual(out['status'],'DEFINITE_REJECT')
            self.assertEqual(out['reason'],'FLAME_CONTACT_WITNESS');self.assertIsNone(checker._radiation)

    def test_16_actual_checker_prior_violation_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            checker=HybridChecker(packet(d),settings=SETTINGS);g,r,legs,dest=mission()
            r['incurred']=dict.fromkeys(IDS,25);r['budgets']['dose']=dict.fromkeys(IDS,F(25)-F(1,1000000))
            out=checker.check(g,r,legs,dest,wall_s=10)
            self.assertEqual(out['status'],'DEFINITE_REJECT');self.assertEqual(out['reason'],'RADIATION_LOWER_BOUND_VIOLATION')

    def test_17_actual_checker_source_mutation_requires_new_epoch(self):
        with tempfile.TemporaryDirectory() as d:
            p=packet(d);checker=HybridChecker(p,settings=SETTINGS)
            self.assertEqual(checker.check(*mission(),wall_s=10)['status'],'CERTIFIED_ADMISSIBLE')
            report=json.loads((p/'REPORT.json').read_text());report['untrusted_change']='changed'
            (p/'REPORT.json').write_text(json.dumps(report))
            out=checker.check(*mission(),wall_s=10)
            self.assertEqual(out['status'],'UNRESOLVED');self.assertEqual(out['reason'],'SOURCE_CONTENT_CHANGED_NEW_EPOCH_REQUIRED')

    def test_18_repository_stack_matches_verified_source_hashes(self):
        root=HERE.parent
        rows=json.loads((root/'SOURCE_SHA256.json').read_text())
        self.assertEqual(len(rows),52)
        for path,expected in rows.items():
            self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(),expected,path)


INHERITED_SPEC=importlib.util.spec_from_file_location('full_checker_inherited_request_window',HERE/'inherited_request_window_controls.py')
INHERITED=importlib.util.module_from_spec(INHERITED_SPEC);sys.modules[INHERITED_SPEC.name]=INHERITED;INHERITED_SPEC.loader.exec_module(INHERITED)

class InheritedRequestWindowControls(INHERITED.Controls):
    """All 14 logical controls run against this new stack, exactly once."""
    pass

if __name__=='__main__':unittest.main(verbosity=2)
