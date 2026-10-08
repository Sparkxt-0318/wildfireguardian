"""Author hybrid tests; numerical source samples supplement analytic enclosureproof."""
from pathlib import Path
from fractions import Fraction as F
import copy,hashlib,json,math,sys,time
import numpy as np
H=Path(__file__).resolve().parents[1];sys.path.insert(0,str(H/'candidate'))
from hybrid_radiation import HybridRadiationBounds,DEFAULT_SETTINGS
BASE=json.loads((H/'baseline/results/fresh_sources/20220304T060000Z/REPORT.json').read_text())['native_metadata']['construction']['assumptions']
rows=[]
def test(name,value,detail=None):
 rows.append({'test':name,'pass':bool(value),'detail':detail})
 if not value:
  (H/'results/hybrid_radiation_unit_failure.json').write_text(json.dumps(rows,indent=2));raise AssertionError(name+':'+str(detail))
def make(events=None,current=None,config=None,support=None,settings=None,affine=(10,0,0,0,10,0)):
 e=np.full((1,2,2),math.inf) if events is None else events
 c=np.zeros(e.shape[1:],bool) if current is None else current
 return HybridRadiationBounds(e,c,{**BASE,**(config or {})},affine,['s'],np.ones(e.shape[1:],bool) if support is None else support,settings)
def check(r,legs=None,**kw):
 legs=[{'start':0,'end':10,'p0':(15,15),'p1':(15,15),'kind':'DWELL'}] if legs is None else legs
 return r.trajectory_bound(legs,peak_budget_kw_m2=kw.pop('peak',10),dose_budget_kj_m2=kw.pop('dose',{'s':100}),incurred=kw.pop('incurred',{'s':0}),**kw)
def reference_flux(rect,p,h=5,density=18000):
 x0,x1,y0,y1=rect;x,y=p
 def a(u,v):return math.atan2(u*v,h*math.sqrt(u*u+v*v+h*h))
 return density*(a(x1-x,y1-y)-a(x0-x,y1-y)-a(x1-x,y0-y)+a(x0-x,y0-y))/(4*math.pi)
e=np.full((1,2,2),math.inf);e[0,0,0]=0;r=make(e)
for j,box in enumerate([(F(0),F(20),F(0),F(20)),(F(10),F(19),F(10),F(19)),(F(15),F(15),F(15),F(15))]):
 lo,hi=r._coefficients(box);cl,ch,_,_=r._radial(r._source_lo,r._source_hi,r._areas,box)
 test('coarse-intersection-'+str(j),lo[0]>=cl[0] and hi[0]<=ch[0])
 for x in [box[0],(box[0]+box[1])/2,box[1]]:
  for y in [box[2],(box[2]+box[3])/2,box[3]]:
   q=reference_flux((0,10,0,10),(float(x),float(y)));test('source-interior-'+str(j)+'-'+str(x)+'-'+str(y),lo[0]-1e-9<=q<=hi[0]+1e-9)
 test('explicit-absent-'+str(j),np.all(lo[1:]==0) and np.all(hi[1:]==0))
# Optional None keyword semantics match inherited API, including completedsamebounds.
a=check(r);b=check(r,deadline=None);c=check(r,wall_s=None);d=check(r,wall_s=None,deadline=None)
test('optional-none',a['status']==b['status']==c['status']==d['status'] and a['per_member']==b['per_member']==c['per_member']==d['per_member'])
test('warm-analytic-reuse',b['analytic_corner_evaluations']==0 and b['analytic_source_bounds']==0 and b['cache_misses']==0)
# Full phase/dose/threshold statuses, notsampling certificates.
e[0,0,0]=5;r=make(e);a=check(r);q=reference_flux((0,10,0,10),(15,15))*5/1000
m=a['per_member'][0];test('phase-overlap',m['dose_lower_kj_m2']<=q<=m['dose_upper_kj_m2'])
a=check(r,[{'start':305,'end':306,'p0':(15,15),'p1':(15,15),'kind':'DWELL'}]);test('burnout',a['per_member'][0]['dose_upper_kj_m2']<1e-10)
r=make(e);a=check(r,incurred={'s':10});test('incurred-charged',a['per_member'][0]['dose_lower_kj_m2']>10)
a=check(r,dose={'s':q});test('complete-straddle',a['status']=='UNRESOLVED' and a['complete'])
a=check(r,dose={'s':0});test('lower-dose-reject',a['status']=='DEFINITE_REJECT')
a=check(r,[{'start':5,'end':15,'p0':(15,15),'p1':(15,15),'kind':'DWELL'}],peak=0);test('lower-peak-reject',a['status']=='DEFINITE_REJECT')
# Source snapshot immutable; each relevant change forces a new identity.
e=np.full((1,2,2),math.inf);e[0,0,0]=0;config=dict(BASE);current=np.zeros((2,2),bool);support=np.ones((2,2),bool)
r=HybridRadiationBounds(e,current,config,(10,0,0,0,10,0),['s'],support);a=check(r);identity=r.cache_identity
e[:]=math.inf;current[:]=True;config['radiative_fraction']=.2;support[:]=False;b=check(r)
test('caller-mutation-isolation',a['per_member']==b['per_member'] and identity==r.cache_identity)
for key in ['analytic_near_height_multiple','analytic_sparse_source_limit','analytic_sqrt_bits','analytic_atan_argument_bits','analytic_atan_terms','analytic_machin_terms','max_analytic_corner_evaluations','receiver_span_m','source_tiles_per_axis','near_distance_m','max_spatial_slabs','max_refinement_levels','wall_s']:
 old=DEFAULT_SETTINGS[key];changed=(old+1 if isinstance(old,int) else old*1.5)
 other=make(settings={key:changed});test('setting-cache-dependency-'+key,other.cache_identity!=make().cache_identity)
test('event-cache-dependency',make(e).cache_identity!=identity)
test('geometry-cache-dependency',make(affine=(11,0,0,0,10,0)).cache_identity!=make().cache_identity)
test('physics-cache-dependency',make(config={'radiative_fraction':.2}).cache_identity!=make().cache_identity)
test('support-cache-dependency',make(support=np.zeros((2,2),bool)).cache_identity!=make().cache_identity)
# Atomic combinedcache after analyticcap: no radial-only entry should becommitted.
e=np.full((1,2,2),math.inf);e[0,0,0]=0;r=make(e,settings={'max_analytic_corner_evaluations':1});a=check(r)
test('analytic-cap-unresolved',a['status']=='UNRESOLVED' and not a['complete'])
test('analytic-cap-atomic-cache',r.cache_info()['entries']==0)
r=make(e);a=check(r,deadline=time.perf_counter()-1);test('predeadline-unresolved',a['status']=='UNRESOLVED')
r=make();oldinfo=r.cache_info
def delayed():time.sleep(.05);return oldinfo()
r.cache_info=delayed;a=check(r,deadline=time.perf_counter()+.03)
test('postdeadline-unresolved',a['status']=='UNRESOLVED' and a.get('checked_record_status')=='CERTIFIED_RADIATION')
r=make(support=np.zeros((2,2),bool));a=check(r);test('unsupported-source-neveraccept',a['status']=='UNRESOLVED' and bool(a['unsupported_reasons']))
try:make(np.ma.array(e,mask=np.zeros(e.shape,bool)));test('masked-events',False)
except ValueError:test('masked-events',True)
# Entire interior peak source/receiver box, notendpoint-onlyacceptance.
r=make(e);a=check(r,[{'start':0,'end':2,'p0':(0,15),'p1':(20,15),'kind':'EDGE'}]);q=reference_flux((0,10,0,10),(5,15))/1000
test('interior-peak-enclosed',a['per_member'][0]['peak_upper_kw_m2']>=q)
# Numerical intersection inconsistency is caughtinside inheritedpass andcannotcertify.
r=make(e)
def incompatible(box):raise ArithmeticError('INCOMPATIBLE_SAME_LAW_ENCLOSURES')
r._coefficients=incompatible;a=check(r)
test('incompatible-enclosure-failclosed',a['status']=='UNRESOLVED' and not a['complete'] and 'ArithmeticError' in a['cap'],a)
(H/'results/hybrid_radiation_unit.json').write_text(json.dumps({'checks':len(rows),'all_pass':all(r['pass'] for r in rows),'implementation_sha256':hashlib.sha256((H/'candidate/hybrid_radiation.py').read_bytes()).hexdigest(),'scope':'author development tests; sample comparisons supplement analyticproof','rows':rows},indent=2));print(len(rows),'PASS')
