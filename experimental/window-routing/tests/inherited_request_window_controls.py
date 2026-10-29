"""Finite request-window and check-first controls; parent guarded execution only."""
from pathlib import Path
from fractions import Fraction as Q
from unittest import mock
import ast,hashlib,importlib.util,json,sys,tempfile,unittest
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
STACK=ROOT/'stack'
sys.path[:0]=[str(STACK/'phaseB'),str(STACK/'routing_candidate/baseline'),str(STACK/'routing_candidate/baseline/routing-package')]
import road_bounds as M
from hybrid_radiation import HybridRadiationBounds

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
B=load('wfg_deadline_baseline_bounds',HERE/'baseline_road_bounds.py')
O=load('wfg_deadline_independent_oracle',HERE/'oracle.py')
CONFIG=dict(version='wfg.hazard.construction/1',fuel_load_kg_m2=1,heat_of_combustion_j_kg=80000,consumed_fraction=1,burning_duration_s=4,initial_remaining_s=4,radiative_fraction=1,atmospheric_transmissivity=1,emission_height_m=4,receiver_height_m=1,horizon_s=30)
IDS=['a','b','c','d']
def fixture(window=(6,10),x0=1000,y0=1000,module=M,duration=4):
    arr=np.full((4,2,3),np.inf);current=np.zeros((2,3),dtype=bool);current[0,0]=True
    for s,last in enumerate((20,21,22,7)):
        arr[s].flat[1:]=[2,10,6,11,last]
    before=arr.copy();cur_before=current.copy()
    config={**CONFIG,'burning_duration_s':duration,'initial_remaining_s':duration}
    rb=HybridRadiationBounds(arr,current,config,(10,0,x0,0,-10,y0+20),IDS,np.ones((2,3),dtype=bool),evidence_class='RESEARCH_CONSTRUCTION')
    graph=dict(grid=dict(x0=x0,y0=y0,resolution=10,width=3,height=2),nodes=[dict(id='u',x=x0+5,y=y0+5),dict(id='v',x=x0+15,y=y0+5)],edges=[dict(id='uv',u='u',v='v',travel_ticks=1)])
    with tempfile.TemporaryDirectory(prefix='wfg-request-window-control-')as d:
        p=Path(d);(p/'constructed_arrays.npz').write_bytes(b'fixed coefficient-only fixture');(p/'REPORT.json').write_text('{}')
        kw={}if module is B else {'active_window':window}
        with mock.patch.object(HybridRadiationBounds,'from_case',return_value=rb):obj=module.RoadBoundModel(graph,p,**kw)
    assert np.array_equal(arr,before)and np.array_equal(current,cur_before)
    return obj,rb,arr,graph

def sources(arr,s,x0=1000,y0=1000):
    out=[]
    for i in range(6):
        row,col=divmod(i,3);r=(x0+col*10,x0+(col+1)*10,y0+(1-row)*10,y0+(2-row)*10)
        birth,expiry=(Q(0),Q(4))if i==0 else (Q(float(arr[s].flat[i])),Q(float(arr[s].flat[i]))+4)
        out.append(O.Source(r,3,20000,birth,expiry))
    return out

def stationary_truth(src,point,start,end):
    cuts={Q(start),Q(end)}
    for s in src:
        for t in (s.birth,s.expiry):
            if start<t<end:cuts.add(t)
    cuts=sorted(cuts);samples=[O.flux_at(src,point,t)for t in cuts];dose=O.Interval.point(0)
    for a,b in zip(cuts,cuts[1:]):
        value=O.flux_at(src,point,(a+b)/2);dose=dose+value*(b-a);samples.append(value)
    peak=O.Interval(max(v.lo for v in samples),max(v.hi for v in samples))
    return dose,peak

class Controls(unittest.TestCase):
    def test_exact_closed_window_half_open_phase_boundaries(self):
        self.assertTrue(M.phase_meets_window(Q(10),Q(14),(Q(6),Q(10))))
        self.assertFalse(M.phase_meets_window(Q(2),Q(6),(Q(6),Q(10))))
        self.assertFalse(M.phase_meets_window(Q(3,2),Q(11,2),(Q(11,2),Q(11,2))))
        self.assertTrue(M.phase_meets_window(Q(11,2),Q(13,2),(Q(11,2),Q(11,2))))
        self.assertFalse(M.phase_meets_window(Q(0),Q(0),None))
    def test_window_validation_and_readonly_public_property(self):
        for w in ((-1,10),(10,6),(6,31),(True,10),'610',(6,)):
            with self.subTest(window=w),self.assertRaises((ValueError,TypeError)):M.source_window(w,Q(30))
        m,*_=fixture()
        with self.assertRaises(AttributeError):m.active_window=(0,30)
    def test_union_selection_retains_native_columns_without_mutating_source(self):
        m,rb,arr,g=fixture();self.assertEqual(m.pot.tolist(),[2,3,5]);self.assertEqual(m.full_pot.tolist(),list(range(6)));self.assertTrue(rb._potential.all());self.assertIs(m.rb,rb);self.assertIsNot(m.adaptive.rb,rb)
        self.assertFalse(m.adaptive.rb._potential.flags.writeable);self.assertEqual(np.flatnonzero(m.adaptive.rb._potential).tolist(),[2,3,5]);self.assertEqual(m.adaptive.pot.tolist(),[2,3,5]);self.assertFalse(m.pot.flags.writeable)
        at_remaining,*_=fixture((4,4));self.assertNotIn(0,at_remaining.pot);self.assertIn(1,at_remaining.pot)
    def test_empty_selection_returns_exact_zero_in_all_exposure_modes(self):
        m,*_=fixture((27,28));self.assertEqual(m.P,0);self.assertEqual(m.full_pot.size,6)
        for mode in ('lo','hi','zero'):
            v=m.view(mode);self.assertEqual(v.node('u',27,28),tuple((Q(0),0.)for _ in IDS));self.assertEqual(v.edge('uv',27,28),tuple((Q(0),0.)for _ in IDS))
        a,b=m.coefficients(np.asarray([[1005.,1005.,1005.,1005.]]));self.assertEqual(a.shape,b.shape);self.assertEqual(a.shape,(1,0))
    def test_every_public_query_rejects_outside_window_including_zero(self):
        m,*_=fixture()
        for mode in ('lo','hi','zero'):
            v=m.view(mode)
            for start,end in ((Q(6)-Q(1,2**60),6),(10,Q(10)+Q(1,2**60)),(8,7)):
                calls=[lambda:v.edge('uv',start,end),lambda:v.edge_plain('uv',start,end),lambda:v.node('u',start,end),lambda:v.node_plain('u',start,end),lambda:v.partial('uv',start,end,0,1),lambda:v.gap_probe([dict(cell=0,start=start,end=end)])]
                for call in calls:
                    with self.subTest(mode=mode,start=start,end=end),self.assertRaises(M.Unsupported):call()
    def test_cache_epoch_binds_exact_window_and_column_identity(self):
        a,*_=fixture((Q(6),Q(10)));b,*_=fixture(('6','10'));c,*_=fixture((6,11))
        self.assertEqual(a.identity,b.identity);self.assertIs(a._coef,b._coef);self.assertNotEqual(a.identity,c.identity);self.assertIsNot(a._coef,c._coef)
        self.assertNotEqual(a.column_identity,c.column_identity);self.assertEqual(a.window_key(),['6','10'])
        a._window=(Q(0),Q(30))
        with self.assertRaisesRegex(M.Unsupported,'BOUND_SOURCE_WINDOW_CHANGED'):a.view('zero').node('u',6,7)
    def test_original_full_geometry_partition_event_cuts_and_contacts_preserved(self):
        scoped,*_=fixture();full,*_=fixture(None);old,*_=fixture(module=B)
        self.assertTrue(np.array_equal(scoped.n_default,old.n_default));self.assertTrue(np.array_equal(scoped.dist,old.dist));self.assertEqual(scoped.cuts,old.cuts);self.assertEqual(scoped.cell_intervals,old.cell_intervals);self.assertEqual(scoped.gaps,old.gaps)
        self.assertTrue(np.array_equal(full.pot,old.pot));self.assertEqual(full.cuts,old.cuts)
    def test_four_members_stationary_dose_and_peak_contain_independent_point_oracle(self):
        m,rb,arr,g=fixture();lo=m.view('lo').node('u',6,10);hi=m.view('hi').node('u',6,10)
        for s in range(4):
            dose,peak=stationary_truth(sources(arr,s),(1005,1005),Q(6),Q(10))
            with self.subTest(member=s):
                self.assertLessEqual(lo[s][0]*1000,dose.lo);self.assertGreaterEqual(hi[s][0]*1000,dose.hi);self.assertLessEqual(Q(lo[s][1])*1000,peak.lo);self.assertGreaterEqual(Q(hi[s][1])*1000,peak.hi)
    def test_instantaneous_horizon_birth_not_dropped(self):
        m,rb,arr,g=fixture((10,10));self.assertEqual(m.pot.tolist(),[2,5]);value=m.view('hi').node('u',10,10)
        for s in range(4):
            exact=O.flux_at(sources(arr,s),(1005,1005),Q(10));self.assertGreater(exact.lo,0);self.assertEqual(value[s][0],0);self.assertGreaterEqual(Q(value[s][1])*1000,exact.hi)
    def test_fractional_native_expiry_and_rounding_gaps_retained(self):
        expiry=Q(2)+Q(.1);m,*_=fixture((Q(2),expiry),duration=.1);full,*_=fixture(None,duration=.1)
        self.assertEqual(m.pot.tolist(),[1]);self.assertTrue(m.gaps);self.assertEqual(m.gaps,full.gaps);self.assertEqual(m.cell_intervals,full.cell_intervals)
        self.assertGreater(m.view('hi').node('u',Q(2),expiry)[0][0],0)
        point,*_=fixture((expiry,expiry),duration=.1);self.assertEqual(point.P,0);self.assertEqual(point.view('hi').node('u',expiry,expiry),tuple((Q(0),0.)for _ in IDS))
    def test_unfiltered_positive_domain_coefficients_regress_bit_identically(self):
        full,*_=fixture(None);old,*_=fixture(module=B);Bxs=np.asarray([[1035.,1035.,1005.,1005.],[1005.,1005.,1005.,1005.]])
        for a,b in zip(full.coefficients(Bxs),old.coefficients(Bxs)):self.assertTrue(np.array_equal(a,b))
    def test_signed_window_fixture_contains_independent_oracle(self):
        m,rb,arr,g=fixture(x0=-1030,y0=-1020);lo=m.view('lo').node('u',6,10);hi=m.view('hi').node('u',6,10)
        dose,peak=stationary_truth(sources(arr,3,-1030,-1020),(-1025,-1015),Q(6),Q(10));self.assertLessEqual(lo[3][0]*1000,dose.lo);self.assertGreaterEqual(hi[3][0]*1000,dose.hi);self.assertGreaterEqual(Q(hi[3][1])*1000,peak.hi);self.assertGreater(m.stats['analytic_domain_skips'],0)
    def test_general_check_first_preserves_mandatory_checker_and_limits(self):
        old=ast.parse((HERE/'baseline_prior_worker.py').read_text());new=ast.parse((STACK/'phaseB/rda_worker_v1_1.py').read_text());find=lambda tree,name:next(x for x in ast.walk(tree)if isinstance(x,ast.FunctionDef)and x.name==name)
        self.assertEqual(ast.dump(find(old,'whole_road')),ast.dump(find(new,'whole_road')))
        consider=find(new,'consider');calls=[x.func.id for x in ast.walk(consider)if isinstance(x,ast.Call)and isinstance(x.func,ast.Name)];self.assertIn('whole_road',calls);self.assertNotIn('lo_prefilter',calls)
        get=lambda tree:ast.literal_eval(next(x.value for x in tree.body if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='ALLOCATION'for t in x.targets)))
        oa,na=get(old),get(new)
        for k,v in oa.items():
            if k!='version':self.assertEqual(v,na[k])
        self.assertEqual(na['Z_optional_prefilter'],'SKIPPED_FOR_ALL_Z_WITNESSES')
    def test_copy_changes_only_five_files_and_retains_prior_kernel_repair(self):
        files=[p for p in STACK.rglob('*')if p.is_file()];self.assertEqual(len(files),52);old=json.loads((HERE/'baseline_source_sha256.json').read_text());changed=[str(p.relative_to(STACK))for p in files if hashlib.sha256(p.read_bytes()).hexdigest()!=old[str(p.relative_to(STACK))]]
        self.assertEqual(sorted(changed),sorted(['phaseB/rda_worker_v1_1.py','phaseB/road_bounds.py','routing_candidate/baseline/radiation_bounds.py','routing_candidate/baseline/hybrid_radiation.py','routing_candidate/baseline/hybrid_checker.py']))
if __name__=='__main__':unittest.main()
