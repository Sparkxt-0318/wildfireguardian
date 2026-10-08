"""Independent reference self-checks before new source/outcome opening."""
from pathlib import Path
from fractions import Fraction as F
import sys,json,time,resource,platform
sys.set_int_max_str_digits(0) # Trusted internally constructed proof fractions, never untrusted integer input.
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'review'))
from reference_rational import rectangle
from hybrid_reference import box,mission_enclosure
from practical_reference import absolute_clip,contact_oracle
start=time.perf_counter();cpu=time.process_time();checks=[];failures=[]
def test(name,fn):
 try:detail=fn();checks.append({'name':name,'pass':True,'detail':detail})
 except Exception as exc:failures.append(name);checks.append({'name':name,'pass':False,'error':repr(exc)})
def near(a,b):return a<=b<=a or abs(float(a-b))<1e-20
def centre():
 lo,hi=rectangle((-5,5,-5,5),height=5);assert lo<=F(1,6)<=hi and float(hi-lo)<1e-25;return {'exact':'1/6','lower':str(lo),'upper':str(hi)}
test('centred square hand solid angle1/6',centre)
for index,(rect,recv) in enumerate([((-5,5,-5,5),(-1,1,-1,1)),((0,10,0,10),(11,12,5,6)),((0,375,0,375),(374,377,376,380)),((0,375,0,375),(1500,1625,1500,1500)),((-1,1,-1,1),(-3,3,-3,3)),((-10,-1,3,12),(0,0,0,0))]):
 def points(rect=rect,recv=recv):
  lo,hi=box(rect,recv);xs=[F(recv[0]),F(recv[0]+recv[1],2),F(recv[1])];ys=[F(recv[2]),F(recv[2]+recv[3],2),F(recv[3])]
  for x in xs:
   for y in ys:
    a,b=rectangle(rect,receiver=(x,y));assert lo<=a<=b<=hi
  return {'points':9,'lower':str(lo),'upper':str(hi)}
 test('independent box contains point references '+str(index),points)
def leg(kind,a,b,p=(0,0),end=None):return dict(kind=kind,start=a,end=b,p0=p,p1=p if end is None else end)
def static():
 tr=[leg('ISSUE',0,0),leg('WAIT',0,2),leg('EDGE',2,4),leg('DWELL',4,10)];out=mission_enclosure(tr,[(-5,5,-5,5)], [[(F(2),F(5))],[None]],['active','absent'],{'active':7,'absent':100})
 a,b=out;assert F(a['dose_lower_kj_m2_exact'])<=16<=F(a['dose_upper_kj_m2_exact']);assert F(a['peak_lower_kw_m2_exact'])<=3<=F(a['peak_upper_kw_m2_exact']);assert F(b['dose_lower_kj_m2_exact'])==F(b['dose_upper_kj_m2_exact'])==100;return out
test('exact source event motion wait dwell incurred',static)
def endpoint():
 tr=[leg('ISSUE',0,0),leg('EDGE',0,10),leg('DWELL',10,10)];out=mission_enclosure(tr,[(-5,5,-5,5)], [[(F(10),F(20))]],['m'],{'m':0});assert F(out[0]['dose_upper_kj_m2_exact'])==0 and F(out[0]['peak_lower_kw_m2_exact'])<=3<=F(out[0]['peak_upper_kw_m2_exact']);return out
test('zero duration final ignition peak without dose',endpoint)
def burnout():
 tr=[leg('ISSUE',2,2),leg('DWELL',2,3)];out=mission_enclosure(tr,[(-5,5,-5,5)], [[(F(0),F(2))]],['m'],{'m':0});assert F(out[0]['dose_upper_kj_m2_exact'])==F(out[0]['peak_upper_kw_m2_exact'])==0;return out
test('half open burnout excludes issue at expiry',burnout)
for name,tr,phase,expected in [('future birth after departure segment',[leg('ISSUE',0,0),leg('EDGE',0,1,(0,0),(2,0))],(F(3),F(303)),False),('ignition at closed exit',[leg('EDGE',0,1,(0,0),(2,0))],(F(1,2),F(3)),True),('burnout exactly at entry',[leg('EDGE',0,1,(-1,0),(1,0))],(F(0),F(1,2)),False),('diagonal corner tangent',[leg('EDGE',0,2,(-1,1),(1,-1))],(F(0),F(3)),True),('final point ignition',[leg('DWELL',5,5,(0,0))],(F(5),F(6)),True)]:
 def contact(tr=tr,phase=phase,expected=expected):
  out=contact_oracle(tr,[(F(0),F(1),F(0),F(1))],[[phase]],['m']);assert out[0]['contact']==expected;return out
 test(name,contact)
r={'schema':'wfg.hybrid.independent.reference-development/1','fresh_sources_or_outcomes_opened':False,'passed':sum(x['pass'] for x in checks),'failed':len(failures),'checks':checks,'failures':failures,'wall_s':time.perf_counter()-start,'cpu_s':time.process_time()-cpu,'process_lifetime_rss_mb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if platform.system()=='Darwin' else 1024)}
(D/'review/REFERENCE_DEVELOPMENT.json').write_text(json.dumps(r,indent=2,default=str)+'\n');print(json.dumps({k:r[k] for k in ['passed','failed','failures','wall_s','cpu_s','process_lifetime_rss_mb']}));sys.exit(bool(failures))
