"""Independent post-panel shadow integration checks; sealed numerics unchanged."""
from pathlib import Path
import sys,json,tempfile,copy,hashlib,time,resource,platform
from unittest.mock import patch
import numpy as np
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'candidate'),str(D/'review')]
import hybrid_shadow as m
from practical_reference import source_rectangles,source_phases,contact_oracle
from independent_mission import mission
REVIEW_STARTED=time.perf_counter();REVIEW_CPU=time.process_time()
base=json.loads((D/'baseline/PROTOCOL_FREEZE.json').read_text())['source_histories'][0]['config'];base={**base,'scenario_count':2}
g={'revision':'shadow-hand/1','nodes':[{'id':x,'x':20+i*3,'y':25,'waitable':True} for i,x in enumerate('abcd')], 'edges':[{'id':'e'+str(i),'u':'abcd'[i],'v':'abcd'[i+1],'travel_ticks':2} for i in range(3)],'forbidden_turns':[]}
req={'graph_revision':g['revision'],'hazard_version':'source-contract/1','position':{'node':'a'},'incoming_edge':None,'departure':0,'horizon':3600,'incurred':{'m0':0,'m1':0},'budgets':{'peak':10,'dose':{'m0':100,'m1':100}},'exposure_scope':'including_dwell','destinations':[{'node':'d','dwell':5,'open_intervals':[[0,3600]]}]}
legs=[{'kind':'EDGE','edge':'e0','start':0,'end':2},{'kind':'WAIT','node':'b','start':2,'end':4},{'kind':'EDGE','edge':'e1','start':4,'end':6},{'kind':'EDGE','edge':'e2','start':6,'end':8}]
primary={'status':'CONDITIONAL_OPTIMUM','legs':legs,'destination':'d','hazard_version':'source-contract/1','arbitrary_preserved':{'x':[1,2],'optimality':'original-only'}}
checks=[];failures=[]
def test(name,fn):
 try:detail=fn();checks.append({'name':name,'pass':True,'detail':detail})
 except Exception as e:checks.append({'name':name,'pass':False,'error':repr(e)});failures.append(name)
def packet(path,active=None,unknown=False):
 path.mkdir(exist_ok=True);ev=np.full((2,4,4),np.inf);cur=np.zeros((4,4),bool)
 if active is not None:cur[active]=True
 support=np.ones((2,4,4),bool)
 if unknown:support[0,0,0]=False
 np.savez(path/'constructed_arrays.npz',ignition_time_s=ev,current_active=cur,support=support)
 report={'mode':'research','native_metadata':{'construction':{'assumptions':base},'affine_transform':[10,0,0,0,10,0]},'rows':[{'request':{'incurred':{'m0':0,'m1':0}}}]};(path/'REPORT.json').write_text(json.dumps(report));return ev,cur,support
with tempfile.TemporaryDirectory(prefix='shadow-independent-',dir=D/'review') as tmp:
 path=Path(tmp);ev,cur,sup=packet(path);binding=m.bind_witness_context(path,g,req)
 own=mission(g,req,legs,'d',['m0','m1'],3600);assert not any(x['contact'] for x in contact_oracle(own['trajectory'],source_rectangles([10,0,0,0,10,0],cur.shape),source_phases(ev,cur,300,300),['m0','m1']))
 def call(p=primary,graph=g,request=req,b=binding,adapter=None,**kw):
  frozen=copy.deepcopy(p);out=(adapter or m.HybridShadowWitnessAdapter(path)).check(p,graph,request,binding=b,enabled=True,**kw);assert out['primary_result']==frozen and p==frozen and out['primary_search_outcome_unchanged'] and not out['default_replacement'] and not out['search_optimality_or_infeasibility_from_shadow'] and not out['physical_validation'];return out
 def valid():
  a=m.HybridShadowWitnessAdapter(path);c=call(adapter=a);w=call(adapter=a);assert c['shadow_status']==w['shadow_status']=='CERTIFIED_ADMISSIBLE' and w['shadow_check']['radiation']['cache_hits']>0;assert c['primary_search_status']=='CONDITIONAL_OPTIMUM';return {'cold':c,'warm':w}
 test('conditional-optimum witness shadow cold warm primary untouched',valid)
 def timeout():
  p={'status':'TIMEOUT','checked_incumbent':{**primary,'status':'CHECKED_ROUTE'},'labels':777,'proof':None};out=call(p);assert out['shadow_status']=='CERTIFIED_ADMISSIBLE' and out['primary_search_status']=='TIMEOUT' and out['witness_origin']=='checked_incumbent_secondary_to_TIMEOUT';return out
 test('timeout checked incumbent remains timeout with secondary certificate',timeout)
 def facade():
  p={'status':'OTHER_FACADE_FIELD','escape':{**primary,'status':'CHECKED_ROUTE'},'members':{'m0':1}};out=call(p);assert out['shadow_status']=='CERTIFIED_ADMISSIBLE' and out['primary_search_status']=='CHECKED_ROUTE';return out
 test('facade escape primary report preserved',facade)
 def disabled():
  with patch.object(m,'bind_witness_context',side_effect=AssertionError('source accessed')),patch.object(m,'HybridChecker',side_effect=AssertionError('checker used')):out=m.HybridShadowWitnessAdapter(path/'not-found').check(primary,g,req)
  assert out['shadow_status']=='DISABLED' and out['shadow_check'] is None and out['primary_result']==primary;return out
 test('default optout no source reads checker creation',disabled)
 def invalid_optin():
  out=m.HybridShadowWitnessAdapter(path).check(primary,g,req,binding=binding,enabled=1);assert out['shadow_status']=='UNRESOLVED';return out
 test('nonboolean optin refuses',invalid_optin)
 for name,p in [('timeout no incumbent',{'status':'TIMEOUT','legs':legs,'destination':'d'}),('unverified timeout incumbent',{'status':'TIMEOUT','checked_incumbent':primary}),('unsupported primary status',{'status':'UNRESOLVED','legs':legs,'destination':'d'}),('primary UNSUPPORTED preserved',{'status':'UNSUPPORTED','reason':'missing-data','legs':legs,'destination':'d'}),('missing destination',{'status':'CHECKED_ROUTE','legs':legs}),('mismatched hazard version',{**primary,'hazard_version':'other'})]:
  def run(p=p):out=call(p);assert out['shadow_status']=='UNRESOLVED';return out
  test(name,run)
 def no_binding():out=call(b=None);assert out['shadow_status']=='UNRESOLVED';return out
 test('enabled requires pre-router full binding',no_binding)
 def changed_req():
  r=copy.deepcopy(req);r['incurred']['m0']=5;out=call(request=r);assert out['shadow_status']=='UNRESOLVED' and 'BINDING' in out['shadow_check']['reason'];return out
 test('original binding refuses changed incurred request',changed_req)
 def memberbudgets():
  r=copy.deepcopy(req);r['incurred']['m0']=100;r['budgets']['dose']={'m0':100,'m1':0};out=call(request=r,b=m.bind_witness_context(path,g,r));assert out['shadow_status']=='CERTIFIED_ADMISSIBLE';return out
 test('individual budgets and exact incurred equality retained',memberbudgets)
 def aboveinc():
  r=copy.deepcopy(req);r['incurred']['m0']=101;out=call(request=r,b=m.bind_witness_context(path,g,r));assert out['shadow_status']=='DEFINITE_REJECT';return out
 test('incurred above budget rejects independently of route',aboveinc)
 def dwell():
  r=copy.deepcopy(req);r['destinations'][0]['dwell']=4000;out=call(request=r,b=m.bind_witness_context(path,g,r));assert out['shadow_status']=='UNRESOLVED';return out
 test('mandatory dwell crossing horizon never omitted',dwell)
 def partial():
  r=copy.deepcopy(req);r['position']={'edge':'e0','fraction':0.5};out=call(request=r,b=m.bind_witness_context(path,g,r));assert out['shadow_status']=='UNRESOLVED';return out
 test('unsupported initial partial-edge stays unresolved',partial)
 def endwait():
  p=copy.deepcopy(primary);p['legs'].append({'kind':'WAIT','node':'d','start':8,'end':9});out=call(p);assert out['shadow_status']=='UNRESOLVED';return out
 test('final destination WAIT not inherited admission',endwait)
 def turn():
  graph=copy.deepcopy(g);graph['forbidden_turns']=[['e0','e1']];out=call(graph=graph,b=m.bind_witness_context(path,graph,req));assert out['shadow_status']=='UNRESOLVED';return out
 test('incoming turn context retained across wait',turn)
 def graph_epoch():
  a=m.HybridShadowWitnessAdapter(path);assert call(adapter=a)['shadow_status']=='CERTIFIED_ADMISSIBLE';graph=copy.deepcopy(g);graph['nodes'][0]['x']=21;out=call(graph=graph,b=m.bind_witness_context(path,graph,req),adapter=a);assert out['shadow_status']=='UNRESOLVED' and out['shadow_check']['reason']=='GRAPH_CONTENT_CHANGED_NEW_EPOCH_REQUIRED';return out
 test('new binding cannot override owned graph epoch',graph_epoch)
 def source_epoch():
  a=m.HybridShadowWitnessAdapter(path);assert call(adapter=a)['shadow_status']=='CERTIFIED_ADMISSIBLE';p=path/'REPORT.json';old=p.read_text();p.write_text(old+'\n')
  try:out=call(b=m.bind_witness_context(path,g,req),adapter=a);assert out['shadow_status']=='UNRESOLVED' and out['shadow_check']['reason']=='SOURCE_CONTENT_CHANGED_NEW_EPOCH_REQUIRED';return out
  finally:p.write_text(old)
 test('new binding cannot override owned source epoch',source_epoch)
 def cap():
  with patch.object(m,'HybridChecker',side_effect=AssertionError('checker called')):out=call(wall_s=0)
  assert out['shadow_status']=='UNRESOLVED';return out
 test('zero deadline includes binding and preparation',cap)
 class Fake:
  def __init__(self,*a):pass
  def check(self,*a,**k):return {'status':'CERTIFIED_ADMISSIBLE','scope':'fake cap/mutation regression only'}
 def shared():
  calls=[]
  class Capture(Fake):
   def check(self,*a,**k):calls.append(k);return super().check(*a,**k)
  with patch.object(m,'HybridChecker',Capture):out=call(wall_s=30,deadline=time.perf_counter()+2)
  assert out['shadow_status']=='CERTIFIED_ADMISSIBLE' and calls[0]['deadline']<=time.perf_counter()+2 and calls[0]['wall_s']==30;return out
 test('binding extraction checker share separate absolute deadline',shared)
 def late():
  values=iter([0,0,0,0,0,31])
  with patch.object(m,'HybridChecker',Fake),patch.object(m.time,'perf_counter',side_effect=lambda:next(values)):out=call()
  assert out['shadow_status']=='UNRESOLVED' and out['shadow_check']['reason']=='SHADOW_CAP_DURING_FINALIZATION' and out['shadow_check']['checked_result']['status']=='CERTIFIED_ADMISSIBLE';return out
 test('post-emission late certificate remains secondary unresolved',late)
 def changed_primary():
  p=copy.deepcopy(primary);snapshot=copy.deepcopy(p)
  class Mutator(Fake):
   def check(self,*a,**k):p['status']='TIMEOUT';return super().check(*a,**k)
  with patch.object(m,'HybridChecker',Mutator):out=m.HybridShadowWitnessAdapter(path).check(p,g,req,binding=binding,enabled=True)
  assert out['primary_result']==snapshot and out['shadow_status']=='UNRESOLVED' and out['shadow_check']['reason']=='SHADOW_AUTHORITY_CHANGED_DURING_CHECK';return out
 test('primary changed concurrently refuses shadow authority',changed_primary)
 def changed_request():
  r=copy.deepcopy(req)
  class Mutator(Fake):
   def check(self,*a,**k):r['incurred']['m0']=5;return super().check(*a,**k)
  with patch.object(m,'HybridChecker',Mutator):out=m.HybridShadowWitnessAdapter(path).check(primary,g,r,binding=binding,enabled=True)
  assert out['shadow_status']=='UNRESOLVED' and out['shadow_check']['reason']=='SHADOW_AUTHORITY_CHANGED_DURING_CHECK';return out
 test('request changed concurrently refuses shadow authority',changed_request)
 ev,cur,sup=packet(path,active=(2,2));binding=m.bind_witness_context(path,g,req)
 def contact():
  out=call(b=binding);assert out['shadow_status']=='DEFINITE_REJECT' and out['primary_search_status']=='CONDITIONAL_OPTIMUM';own=mission(g,req,legs,'d',['m0','m1'],3600);assert any(x['contact'] for x in contact_oracle(own['trajectory'],source_rectangles([10,0,0,0,10,0],cur.shape),source_phases(ev,cur,300,300),['m0','m1']));return out
 test('exact contact rejects shadow primary report untouched',contact)
 packet(path,unknown=True);binding=m.bind_witness_context(path,g,req)
 def unknown():out=call(b=binding);assert out['shadow_status']=='UNRESOLVED' and out['shadow_check']['contact']['status']=='UNRESOLVED';return out
 test('unknown source support cannot enter certified shadow',unknown)
r={'schema':'wfg.independent.hybrid-shadow.development/1','stage':'PRE_OPENING_HAND_DEVELOPMENT_ONLY','implementation_seal_sha256':'UNSEALED_DEVELOPMENT','wall_s':time.perf_counter()-REVIEW_STARTED,'cpu_s':time.process_time()-REVIEW_CPU,'process_lifetime_rss_mb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if platform.system()=='Darwin' else 1024),'adapter_sha256':hashlib.sha256((D/'candidate/hybrid_shadow.py').read_bytes()).hexdigest(),'reviewer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checks':checks,'passed':sum(x['pass'] for x in checks),'failed':len(failures),'failures':failures,'fake_cases_scope':'Only resource/deadline/authority behavior; physical certificates tested with real sealed checker and independent contact fixture.'}
(D/'review/SHADOW_DEVELOPMENT.json').write_text(json.dumps(r,indent=2,default=str)+'\n');print(json.dumps({'passed':r['passed'],'failed':r['failed'],'failures':failures}));sys.exit(bool(failures))
