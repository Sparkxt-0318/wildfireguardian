"""Standalone wrapper invariants on separate hand development fixtures."""
from pathlib import Path
import sys,json,time,tempfile,copy,hashlib,resource,platform
import numpy as np
from unittest.mock import patch
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'candidate')]
from hybrid_checker import HybridChecker
from mission_contract import graph_digest
REVIEW_STARTED=time.perf_counter();REVIEW_CPU=time.process_time()
base=json.loads((D/'baseline/PROTOCOL_FREEZE.json').read_text())['source_histories'][0]['config'];base={**base,'scenario_count':2}
g={'revision':'wrapper-hand/1','nodes':[{'id':x,'x':20+i*3,'y':25,'waitable':True} for i,x in enumerate('abcd')],
   'edges':[{'id':'e'+str(i),'u':'abcd'[i],'v':'abcd'[i+1],'travel_ticks':2} for i in range(3)],'forbidden_turns':[]}
req={'graph_revision':g['revision'],'position':{'node':'a'},'incoming_edge':None,'departure':0,'horizon':3600,'incurred':{'m0':0,'m1':0},'budgets':{'peak':10,'dose':{'m0':100,'m1':100}},'exposure_scope':'including_dwell','destinations':[{'node':'d','dwell':5,'open_intervals':[[0,3600]]}]}
legs=[{'kind':'EDGE','edge':'e0','start':0,'end':2},{'kind':'WAIT','node':'b','start':2,'end':4},{'kind':'EDGE','edge':'e1','start':4,'end':6},{'kind':'EDGE','edge':'e2','start':6,'end':8}]
checks=[];failures=[]
def test(name,fn):
 try:r=fn();checks.append({'name':name,'pass':True,'detail':r})
 except Exception as e:failures.append({'name':name,'error':str(e)});checks.append({'name':name,'pass':False,'error':str(e)})
def packet(path,active=None,unknown=False):
 path.mkdir(exist_ok=True);e=np.full((2,4,4),np.inf);c=np.zeros((4,4),bool)
 if active is not None:c[active]=True
 s=np.ones((2,4,4),bool)
 if unknown:s[0,0,0]=False
 np.savez(path/'constructed_arrays.npz',ignition_time_s=e,current_active=c,support=s)
 report={'mode':'research','native_metadata':{'construction':{'assumptions':base},'affine_transform':[10,0,0,0,10,0]},'rows':[{'request':{'incurred':{'m0':0,'m1':0}}}]}
 (path/'REPORT.json').write_text(json.dumps(report))
def call(c,graph=g,request=req,walk=legs,**kw):return c.check(graph,request,walk,'d',expected_graph_revision=g['revision'],expected_graph_sha256=graph_digest(g),**kw)
with tempfile.TemporaryDirectory(prefix='wrapper-hand-',dir=D/'review') as tmp:
 path=Path(tmp);packet(path)
 def empty():
  c=HybridChecker(path);a=call(c);b=call(c);assert a['status']==b['status']=='CERTIFIED_ADMISSIBLE' and b['radiation']['cache_hits']>0;return {'cold':a,'warm':b}
 test('full three-edge wait dwell cold warm',empty)
 def masked():
  r=copy.deepcopy(req);r['incurred']['m0']=np.ma.array(0,mask=True);out=call(HybridChecker(path),request=r);assert out['status']=='UNRESOLVED';return out
 test('masked history refuses certificate',masked)
 def member():
  r=copy.deepcopy(req);r['incurred']['m0']=99;r['budgets']['dose']={'m0':100,'m1':0};out=call(HybridChecker(path),request=r);assert out['status']=='CERTIFIED_ADMISSIBLE';return out
 test('member budget mapping through wrapper',member)
 def rss():
  with patch('hybrid_checker.rss_mb',return_value=3073):r=call(HybridChecker(path))
  assert r['status']=='UNRESOLVED' and r['reason']=='RSS_LIMIT' and r['checked_result']['status']=='CERTIFIED_ADMISSIBLE';return r
 test('RSS late certificate primary unresolved',rss)
 def expired():
  r=call(HybridChecker(path),deadline=time.perf_counter()-1);assert r['status']=='UNRESOLVED';return r
 test('deadline before preparation',expired)
 def late():
  import hybrid_checker as module
  value=[0.]
  def rss():value[0]=31.;return 1.
  with patch.object(module.time,'perf_counter',lambda:value[0]),patch.object(module,'rss_mb',rss):r=call(HybridChecker(path),deadline=30)
  assert r['status']=='UNRESOLVED' and r['reason']=='WALL_CAP_AFTER_CHECK';return r
 test('deadline crossed during finalization',late)
 def graphmut():
  c=HybridChecker(path);a=call(c);changed=copy.deepcopy(g);changed['nodes'][0]['x']=21;b=call(c,graph=changed);assert a['status']=='CERTIFIED_ADMISSIBLE' and b['status']=='UNRESOLVED';return b
 test('changed graph content cannot reuse bound epoch',graphmut)
 def suppliednewhash():
  c=HybridChecker(path);a=call(c);changed=copy.deepcopy(g);changed['nodes'][0]['x']=21
  b=c.check(changed,req,legs,'d',expected_graph_revision=g['revision'],expected_graph_sha256=graph_digest(changed))
  assert a['status']=='CERTIFIED_ADMISSIBLE' and b['status']=='UNRESOLVED' and b['reason']=='GRAPH_CONTENT_CHANGED_NEW_EPOCH_REQUIRED';return b
 test('supplying new graph hash cannot override owned epoch',suppliednewhash)
 def requestmut():
  c=HybridChecker(path);r=copy.deepcopy(req);a=call(c,request=r);original=c._radiation.trajectory_bound
  def change(*a,**k):out=original(*a,**k);r['incurred']['m0']=100;return out
  c._radiation.trajectory_bound=change;b=call(c,request=r);assert b['status']=='UNRESOLVED' and b['reason']=='MISSION_AUTHORITY_CHANGED_DURING_CHECK';return b
 test('request mutation during checking refuses certificate',requestmut)
 def sourcemut():
  c=HybridChecker(path);a=call(c);report=path/'REPORT.json';text=report.read_text();report.write_text(text+'\n');b=call(c);report.write_text(text);assert a['status']=='CERTIFIED_ADMISSIBLE' and b['status']=='UNRESOLVED' and b['reason']=='SOURCE_CONTENT_CHANGED_NEW_EPOCH_REQUIRED';return b
 test('changed source content cannot reuse epoch',sourcemut)
 packet(path,unknown=True)
 def unknown():
  r=call(HybridChecker(path));assert r['status']=='UNRESOLVED' and r['contact']['status']=='UNRESOLVED' and 'radiation' not in r;return r
 test('unknown support never authorizes clearance',unknown)
 packet(path,active=(2,2))
 def contactfirst():
  r=call(HybridChecker(path));assert r['status']=='DEFINITE_REJECT' and r['radiation']['status']=='NOT_RUN_CONTACT_REJECT';return r
 test('contact first rejects without heat arithmetic',contactfirst)
def finalmetadata():
 c=HybridChecker(D/'baseline/results/fresh_controls/budget_equality_no_activity')
 with patch('hybrid_checker.rss_mb',return_value=1),patch('hybrid_checker.time.perf_counter',side_effect=[0.,0.,0.,31.]):r=c._finish({'status':'CERTIFIED_ADMISSIBLE'},0.,30.,{})
 assert r['status']=='UNRESOLVED' and r['reason']=='WALL_CAP_DURING_FINALIZATION' and r['elapsed_s']==31;return r
test('deadline crossed while appending final metadata',finalmetadata)
def settings_epoch():
 with tempfile.TemporaryDirectory(prefix='settings-hand-',dir=D/'review') as t:
  p=Path(t);packet(p);c=HybridChecker(p);assert call(c)['status']=='CERTIFIED_ADMISSIBLE';c.settings={**dict(c.settings),'analytic_atan_terms':21};out=call(c);assert out['status']=='UNRESOLVED' and out['reason']=='SETTINGS_CONTENT_CHANGED_NEW_EPOCH_REQUIRED';return out
test('settings replacement refuses owned epoch',settings_epoch)
def directory_epoch():
 with tempfile.TemporaryDirectory(prefix='directory-hand-',dir=D/'review') as t:
  a=Path(t)/'a';b=Path(t)/'b';packet(a);packet(b);c=HybridChecker(a);assert call(c)['status']=='CERTIFIED_ADMISSIBLE';c.directory=b;out=call(c);assert out['status']=='UNRESOLVED' and out['reason']=='CASE_DIRECTORY_CHANGED_NEW_EPOCH_REQUIRED';return out
test('directory replacement refuses owned epoch even same contents',directory_epoch)
def settings_mutate_during():
 with tempfile.TemporaryDirectory(prefix='during-hand-',dir=D/'review') as t:
  p=Path(t);packet(p);c=HybridChecker(p);assert call(c)['status']=='CERTIFIED_ADMISSIBLE';original=c._radiation.trajectory_bound
  def mutate(*a,**kw):out=original(*a,**kw);c.settings={**dict(c.settings),'analytic_atan_terms':21};return out
  c._radiation.trajectory_bound=mutate;out=call(c);assert out['status']=='UNRESOLVED' and out['reason']=='SETTINGS_OR_DIRECTORY_CHANGED_DURING_CHECK';return out
test('settings mutation during check refuses certificate',settings_mutate_during)
def cacheinspection_late():
 import hybrid_checker as m
 with tempfile.TemporaryDirectory(prefix='cache-late-',dir=D/'review') as t:
  p=Path(t);packet(p);c=HybridChecker(p);assert call(c)['status']=='CERTIFIED_ADMISSIBLE';value=[0.];original=c._radiation.cache_info
  def late():out=original();value[0]=31.;return out
  c._radiation.cache_info=late
  with patch.object(m.time,'perf_counter',side_effect=lambda:value[0]):out=call(c,deadline=30)
  assert out['status']=='UNRESOLVED';return out
test('cache inspection cost charged to shared cap',cacheinspection_late)
def cache_arithmetic():
 with tempfile.TemporaryDirectory(prefix='arithmetic-hand-',dir=D/'review') as t:
  p=Path(t);packet(p);c=HybridChecker(p);assert call(c)['status']=='CERTIFIED_ADMISSIBLE'
  def broken():raise ArithmeticError('HAND_CACHE_ARITHMETIC_FAILURE')
  c._radiation.cache_info=broken;out=call(c);assert out['status']=='UNRESOLVED' and out['reason']=='HAND_CACHE_ARITHMETIC_FAILURE';return out
test('arithmetic failure in cache metadata fails closed',cache_arithmetic)
report={'schema':'wfg.independent.hybrid.wrapper-development/1','checks':checks,'passed':sum(x['pass'] for x in checks),'failed':len(failures),'failures':failures,'fresh_opened':False,'wall_s':time.perf_counter()-REVIEW_STARTED,'cpu_s':time.process_time()-REVIEW_CPU,'process_lifetime_rss_mb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if platform.system()=='Darwin' else 1024),'source_sha256':hashlib.sha256((D/'candidate/hybrid_checker.py').read_bytes()).hexdigest()}
(D/'review/WRAPPER_DEVELOPMENT.json').write_text(json.dumps(report,indent=2,default=str)+'\n');print(json.dumps({'passed':report['passed'],'failed':report['failed'],'failures':failures}));sys.exit(bool(failures))
