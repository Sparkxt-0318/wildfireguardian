"""Independent hybrid arithmetic, cache, source phase and cap checks. No fresh inputs."""
from pathlib import Path
from fractions import Fraction as F
import sys,json,time,resource,platform,copy,hashlib
from unittest.mock import patch
import numpy as np
sys.set_int_max_str_digits(0)
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'candidate'),str(D/'review')]
import hybrid_radiation as module
from hybrid_radiation import HybridRadiationBounds as Hybrid,DEFAULT_SETTINGS
from reference_rational import rectangle
from hybrid_reference import mission_enclosure
base=json.loads((D/'baseline/PROTOCOL_FREEZE.json').read_text())['source_histories'][0]['config'];base={**base,'scenario_count':2}
checks=[];failures=[];start=time.perf_counter();cpu=time.process_time()
def test(name,fn):
 try:detail=fn();checks.append({'name':name,'pass':True,'detail':detail})
 except Exception as exc:failures.append(name);checks.append({'name':name,'pass':False,'error':repr(exc)})
def fixture(shape=(2,2),current=(0,0),birth=None,cfg=None,affine=(10,0,0,0,10,0),settings=None,ids=('m0','m1'),support=True,evidence='RESEARCH_CONSTRUCTION'):
 ev=np.full((2,*shape),np.inf);cur=np.zeros(shape,bool)
 if current is not None:cur[current]=True
 if birth is not None:ev[0,0,0]=birth
 sup=np.ones((2,*shape),bool)
 if not support:sup[0,0,0]=False
 return Hybrid(ev,cur,{**base,**(cfg or {})},affine,ids,sup,settings,evidence),ev,cur,sup

def leg(kind,a,b,p=(15,5),end=None):return dict(kind=kind,start=F(a),end=F(b),p0=tuple(map(F,p)),p1=tuple(map(F,p if end is None else end)))
def tr(a=0,b=5,p=(15,5),end=None):return [leg('ISSUE',a,a,p),leg('EDGE',a,b,p,end),leg('DWELL',b,b,p if end is None else end)]
def call(engine,trajectory=None,inc=None,dose=None,**kw):return engine.trajectory_bound(trajectory or tr(),peak_budget_kw_m2=10,dose_budget_kj_m2={'m0':100,'m1':100} if dose is None else dose,incurred={'m0':0,'m1':0} if inc is None else inc,**kw)
for number,(point,box) in enumerate([((15,5),(14,16,4,6)),((5,5),(5,5,5,5)),((0,0),(0,0,0,0)),((20,20),(19,20,19,20)),((10,5),(10,10,5,5))]):
 def pointcheck(point=point,box=box):
  h,_,_,_=fixture();lo,hi=h._coefficients(tuple(map(F,box)));ref=rectangle((0,10,0,10),point,height=5);assert F(float(lo[0]))<=ref[0]*18000<=ref[1]*18000<=F(float(hi[0]));assert np.all(lo<=hi) and not lo.flags.writeable and not hi.flags.writeable;return {'lower_w':lo.tolist(),'upper_w':hi.tolist(),'analytic_sources':h._analytic_source_bounds}
 test('analytic radial compatible point enclosure '+str(number),pointcheck)
def centered():
 h,_,_,_=fixture(shape=(1,1),affine=(10,0,-5,0,10,-5));lo,hi=h._coefficients((F(0),)*4);assert F(float(lo[0]))<=3000<=F(float(hi[0]));return {'lower':float(lo[0]),'upper':float(hi[0])}
test('hand centred square3000W same source law',centered)
def noneapi():
 out=[]
 for kw in ({},{'wall_s':None},{'deadline':None},{'wall_s':None,'deadline':None}):
  h,_,_,_=fixture();r=call(h,**kw);assert r['status']=='CERTIFIED_RADIATION';out.append(r['status'])
 return out
test('inherited omitted explicitNone wall deadline API',noneapi)
def coldwarm():
 h,_,_,_=fixture();a=call(h);b=call(h);assert a['status']==b['status']=='CERTIFIED_RADIATION' and b['cache_hits']>0 and b['analytic_corner_evaluations']==0;return {'cold':a,'warm':b}
test('warm immutable geometry and analytic corners reused',coldwarm)
def exactevents():
 h,_,_,_=fixture(shape=(1,1),current=None,birth=2,affine=(10,0,-5,0,10,-5));trajectory=[leg('ISSUE',0,0,(0,0)),leg('WAIT',0,2,(0,0)),leg('EDGE',2,4,(0,0)),leg('DWELL',4,310,(0,0))];r=call(h,trajectory,inc={'m0':7,'m1':100});a,b=r['per_member'];assert a['dose_lower_kj_m2']<=907<=a['dose_upper_kj_m2'] and b['dose_lower_kj_m2']==b['dose_upper_kj_m2']==100;assert a['peak_lower_kw_m2']<=3<=a['peak_upper_kw_m2'];return r
test('exact phase overlap full wait motion dwell incurred',exactevents)
def endpoint():
 h,_,_,_=fixture(shape=(1,1),current=None,birth=5,affine=(10,0,-5,0,10,-5));r=call(h,tr(p=(0,0)));a=r['per_member'][0];assert a['dose_upper_kj_m2']<1e-12 and a['peak_lower_kw_m2']<=3<=a['peak_upper_kw_m2'];return r
test('right endpoint ignition peak included zero dose',endpoint)
def burnout():
 h,_,_,_=fixture(shape=(1,1),affine=(10,0,-5,0,10,-5),cfg={'initial_remaining_s':2});r=call(h,tr(a=2,b=3,p=(0,0)));assert all(a['peak_upper_kw_m2']==a['dose_upper_kj_m2']==0 for a in r['per_member']);return r
test('source burnout half open excludes issue at expiry',burnout)
def absence():
 h,_,_,_=fixture(current=None);r=call(h,inc={'m0':100,'m1':0},dose={'m0':100,'m1':0});assert r['status']=='CERTIFIED_RADIATION' and h._potential_count==0 and all(a['peak_upper_kw_m2']==0 for a in r['per_member']);return r
test('explicit absent source exact equality heterogeneous budget',absence)
def unsupported():
 h,_,_,_=fixture(current=None,support=False);r=call(h);assert r['status']=='UNRESOLVED' and not r['complete'] and r['unsupported_reasons'];return r
test('unknown source support cannot supply certificate',unsupported)
def cap():
 h,_,_,_=fixture(settings={'max_analytic_corner_evaluations':1});r=call(h);assert r['status']=='UNRESOLVED' and 'CORNER_CAP' in r['cap'] and len(h._cache)==0;again=call(h);assert again['status']=='UNRESOLVED' and len(h._cache)==0;return [r,again]
test('partial analytic cap never commits radialonly cache',cap)
def spatialcap():
 h,_,_,_=fixture(settings={'max_spatial_slabs':1});r=call(h,tr(end=(19,5)));assert r['status']=='UNRESOLVED' and r['cap']=='SPATIAL_SLAB_CAP';return r
test('spatial cap not acceptance from incomplete bounds',spatialcap)
def expired():
 h,_,_,_=fixture();r=call(h,deadline=time.perf_counter()-1);assert r['status']=='UNRESOLVED' and not r['complete'];return r
test('expired shared deadline refuses before any enclosure',expired)
def finalcap():
 h,_,_,_=fixture();r=call(h)
 with patch('radiation_bounds.RadiationBounds.trajectory_bound',return_value=copy.deepcopy(r)),patch.object(module.time,'perf_counter',side_effect=[0.,0.,31.]):late=call(h,deadline=30)
 assert late['status']=='UNRESOLVED' and late['checked_record_status']=='CERTIFIED_RADIATION' and late['cap']=='WALL_CAP_AFTER_HYBRID_RECORD';return late
test('late hybrid metadata cannot primary certify',finalcap)
def callerarrays():
 h,ev,cur,sup=fixture();a=call(h);ev[:]=0;cur[:]=False;sup[:]=False;b=call(h);assert a['per_member']==b['per_member'] and b['status']=='CERTIFIED_RADIATION';return b
test('caller array mutation cannot poison immutable source',callerarrays)
def dependencies():
 h,_,_,_=fixture();before=h.cache_identity;identities={}
 changes={'events':{'current':None,'birth':2},'current':{'current':None},'support':{'support':False},'geometry':{'affine':(10,0,1,0,10,0)},'member_ids':{'ids':('a','b')},'duration':{'cfg':{'burning_duration_s':301}},'remaining':{'cfg':{'initial_remaining_s':299}},'height':{'cfg':{'emission_height_m':6}},'density':{'cfg':{'fuel_load_kg_m2':11}},'full_config':{'cfg':{'unknown_probability':.4}},'evidence':{'evidence':'OTHER_LABEL'},'horizon':{'cfg':{'horizon_s':3500}},'receiver_span':{'settings':{'receiver_span_m':17}},'tiling':{'settings':{'source_tiles_per_axis':7}},'near_radius':{'settings':{'near_distance_m':601}},'sparse_policy':{'settings':{'analytic_sparse_source_limit':9}},'analytic_radius':{'settings':{'analytic_near_height_multiple':17}},'sqrt_bits':{'settings':{'analytic_sqrt_bits':81}},'atan_bits':{'settings':{'analytic_atan_argument_bits':55}},'atan_terms':{'settings':{'analytic_atan_terms':21}},'pi_terms':{'settings':{'analytic_machin_terms':31}},'corner_cap':{'settings':{'max_analytic_corner_evaluations':65535}},'slab_cap':{'settings':{'max_spatial_slabs':4095}},'refinement_cap':{'settings':{'max_refinement_levels':1}},'wall_cap':{'settings':{'wall_s':29}}}
 for name,kw in changes.items():obj,_,_,_=fixture(**kw);assert obj.cache_identity!=before,name;identities[name]=obj.cache_identity
 return identities
test('every source geometry law support settings dependency binds cache',dependencies)
def requestnotcached():
 h,_,_,_=fixture(current=None);a=call(h);b=call(h,inc={'m0':101,'m1':0});assert a['status']=='CERTIFIED_RADIATION' and b['status']=='DEFINITE_REJECT';return {'first':a['status'],'second':b['status']}
test('changed request incurred reevaluates despite geometrycache',requestnotcached)
def interior():
 h,_,_,_=fixture(shape=(2,2),current=(0,0));t=tr(p=(0,11),end=(10,11));r=call(h,t);ends=[rectangle((0,10,0,10),p)[1]*18000 for p in [(0,11),(10,11)]];mid=rectangle((0,10,0,10),(5,11))[0]*18000;assert mid>max(ends) and r['per_member'][0]['peak_upper_kw_m2']*1000>=float(mid);return r
test('interior heat maximum not endpoint acceptance',interior)
def dense_distant():
 h,ev,cur,sup=fixture(shape=(3,3));cur[:]=True;h=Hybrid(ev,cur,base,(10,0,0,0,10,0),('m0','m1'),sup)
 lo,hi=h._coefficients((F(700),F(700),F(700),F(700)));ref=rectangle((0,10,0,10),(700,700));assert h._potential_count==9 and h._analytic_source_bounds==0 and h._radial_tile_sources==0 and h._source_bounds==9 and np.all(lo>0) and np.all(hi>=lo);assert F(float(lo[0]))<=ref[0]*18000<=ref[1]*18000<=F(float(hi[0]));return {'all_sources':9,'analytic':0,'tiles':0,'lower_sum_w':float(sum(lo)),'upper_sum_w':float(sum(hi))}
test('dense distant branch retains every positive source',dense_distant)
r={'schema':'wfg.hybrid.independent.bounds-development/1','fresh_sources_or_outcomes_opened':False,'passed':sum(x['pass'] for x in checks),'failed':len(failures),'checks':checks,'failures':failures,'wall_s':time.perf_counter()-start,'cpu_s':time.process_time()-cpu,'process_lifetime_rss_mb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if platform.system()=='Darwin' else 1024),'candidate_sha256':hashlib.sha256((D/'candidate/hybrid_radiation.py').read_bytes()).hexdigest()}
(D/'review/BOUNDS_DEVELOPMENT.json').write_text(json.dumps(r,indent=2,default=str)+'\n');print(json.dumps({k:r[k] for k in ['passed','failed','failures','wall_s','cpu_s','process_lifetime_rss_mb']}));sys.exit(bool(failures))
