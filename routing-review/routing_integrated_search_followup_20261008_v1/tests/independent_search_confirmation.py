"""Frozen independent search-produced witness verification; no candidate imports.
Tiny controls prove centre optima/refusals. Large claims remain internal unless
structural disconnect is independently verified. Road certificates are separate.
"""
from pathlib import Path
from fractions import Fraction as F
from datetime import datetime,timezone
import sys,json,hashlib,argparse,time,resource,traceback,collections,math
import numpy as np
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'review'))
from search_reference import exhaustive,witness,issue,limits_ok
from practical_reference import source_rectangles,source_phases,contact_oracle,absolute_clip
from independent_mission import mission,compare_trajectory
from numerical_radiation_reference import integrate
START=time.perf_counter();CPU=time.process_time();report={}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def cost():return {'wall_s':time.perf_counter()-START,'CPU_s':time.process_time()-CPU,'lifetime_RSS_MiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if sys.platform=='darwin' else 1024),'scope':'Reference process after imports; external launcher full-work receipt separate.'}
def decision_record(rec):
 if rec is None:return {'status':'UNRESOLVED','reason':'MISSING_PHASE','wall_s':None,'CPU_s':None,'RSS_MiB':None}
 assert type(rec)is dict and type(rec.get('result'))is dict
 for key in ['complete_call_wall_s','complete_call_CPU_s','RSS_process_lifetime_MiB']:
  value=rec.get(key)
  assert value is None or(type(value)in [int,float] and math.isfinite(value)and value>=0),('invalid recorded cost',key,value)
 r=rec['result'];assert type(r.get('primary_search'))is dict and type(r.get('whole_road_check'))is dict
 assert r['primary_search_status']==r['primary_search']['status'];assert r['integrated_status']in ['UNRESOLVED','CERTIFIED_INTEGRATED_WITNESS','TIMEOUT_WITH_CHECKED_INTEGRATED_WITNESS','SEARCH_WITNESS_DEFINITELY_REJECTED_ON_ROAD']
 return {'status':r['primary_search_status'],'road_status':r['whole_road_check']['status'],'integrated_status':r['integrated_status'],'wall_s':rec.get('complete_call_wall_s'),'CPU_s':rec.get('complete_call_CPU_s'),'RSS_MiB':rec.get('RSS_process_lifetime_MiB')}
def structural_reachable(graph,request):
 if 'node'not in request['position']:return None
 outgoing={n['id']:[]for n in graph['nodes']};turns={tuple(x)for x in graph['forbidden_turns']}
 for e in graph['edges']:outgoing[e['u']].append(e)
 pending=[(request['position']['node'],request['incoming_edge'])];seen=set(pending);dest={d['node']for d in request['destinations']}
 while pending:
  n,inc=pending.pop()
  if n in dest:return True
  for e in outgoing[n]:
   nxt=(e['v'],e['id'])
   if(inc,e['id'])not in turns and nxt not in seen:seen.add(nxt);pending.append(nxt)
 return False

def source(graph,hazard,path):
 md=read(path/'NATIVE_METADATA.json');rep=read(path/'REPORT.json');assert canonical(md)==canonical(rep['native_metadata']);ids=[m['id']for m in hazard['members']];assert len(ids)==4 and len(set(ids))==4
 # Original hourly v2 namespace differs intentionally from constructor member IDs.
 if md.get('construction_id')is not None:
  detail=md['construction'];identity={'mode':md['mode'],'version':md['version'],'parent_sha256':md['parent_forecast_sha256'],'cutoff':datetime.fromisoformat(md['issued_at'].replace('Z','+00:00')).astimezone(timezone.utc).isoformat(),'construction':detail};assert hashlib.sha256(canonical(identity)).hexdigest()==md['construction_id'];assert ids==['construction:'+md['construction_id'][:20]+':'+str(i)for i in range(4)]
 else:assert ids==md['construction']['scenario_ids']
 if rep.get('rows'):assert list(rep['rows'][0]['request']['incurred'])==ids
 assert md['graph_revision']==graph['revision']==hazard['graph_revision'] and md['dt_s']==hazard['dt'] and md['shape']==[graph['grid']['height'],graph['grid']['width']]
 with np.load(path/'constructed_arrays.npz',allow_pickle=False)as z:
  ev=z['ignition_time_s'].copy();cur=z['current_active'].copy();sup=z['support'].copy();flux=z['flux_w_m2'].copy();flame=z['flame_contact'].copy()
 assert ev.ndim==3 and ev.shape[0]==4 and cur.shape==ev.shape[1:] and cur.dtype==sup.dtype==flame.dtype==np.bool_;assert not np.isnan(ev).any() and not(ev<0).any() and not np.isfinite(ev[:,cur]).any()
 # Check unchanged bridge's row reversal/units and masked unsupported placeholders.
 flip=md['affine_transform'][4]<0
 for i,m in enumerate(hazard['members']):
  support=sup[i];f=np.where(support,flux[i],0)/1000;contact=flame[i]
  if flip:support,f,contact=(a[:,::-1,:]for a in (support,f,contact))
  assert m['breakpoints']==md['breakpoints_s'] and np.array_equal(np.asarray(m['support']),support.reshape(len(m['breakpoints'])-1,-1)) and np.array_equal(np.asarray(m['flux']),f.reshape(len(m['breakpoints'])-1,-1)) and np.array_equal(np.asarray(m['flame']),contact.reshape(len(m['breakpoints'])-1,-1))
 cfg=md['construction']['assumptions'];rect=source_rectangles(md['affine_transform'],cur.shape);phase=source_phases(ev,cur,cfg['burning_duration_s'],cfg['initial_remaining_s']);complete=bool(sup.all());density=cfg['fuel_load_kg_m2']*cfg['heat_of_combustion_j_kg']*cfg['consumed_fraction']*cfg['radiative_fraction']*cfg['atmospheric_transmissivity']/cfg['burning_duration_s']
 return {'ids':ids,'rectangles':rect,'phases':phase,'complete':complete,'horizon':cfg['horizon_s'],'density':density,'height':cfg['emission_height_m']-cfg['receiver_height_m'],'hashes':{n:sha(path/n)for n in ['REPORT.json','NATIVE_METADATA.json','constructed_arrays.npz']}}

def verify_road(graph,hazard,request,w,road,src,reference_cache):
 if road['status']not in ['CERTIFIED_ADMISSIBLE','DEFINITE_REJECT','UNRESOLVED','NOT_RUN']:raise AssertionError('unknown road status')
 if src is None:
  assert road['status']=='UNRESOLVED' and road['reason'] in ['SOURCE_CONTRACT_UNAVAILABLE','INTEGRATION_BINDING_OR_ADMISSION_FAILURE','FINAL_AUTHORITY_FAILURE'];return {'physical_source':'UNAVAILABLE','road_decision':'UNRESOLVED'}
 if w is None:assert road['status']in ['UNRESOLVED','NOT_RUN'];return {'road_decision':road['status'],'no_checked_witness':True}
 req={**request,'graph_revision':graph['revision']};own=mission(graph,req,w['legs'],w['destination'],src['ids'],src['horizon']);contact=contact_oracle(own['trajectory'],src['rectangles'],src['phases'],src['ids']);hascontact=any(x['contact']for x in contact);tr=road.get('trajectory')
 if tr is not None:compare_trajectory(tr,own['trajectory'])
 c=road.get('contact');rad=road.get('radiation');members=[]if not rad else rad.get('per_member',[])
 if c and c['status']=='CLEAR':assert src['complete'] and not hascontact and c['complete'] and c['contact_clear']
 if c and c['status']=='DEFINITE_REJECT':
  assert hascontact;v=c['witness'];i=src['ids'].index(v['member']);cell=v['source_cell'];li=v['segment_index'];t=F(v['time_exact']);a,b=src['phases'][i][cell];cl=absolute_clip(own['trajectory'][li],src['rectangles'][cell]);assert cl is not None and cl[0]<=t<=cl[1] and a<=t<b and list(map(F,v['rectangle_exact']))==list(src['rectangles'][cell])
 if road['status']=='CERTIFIED_ADMISSIBLE':assert src['complete'] and not hascontact and c and c['status']=='CLEAR' and rad['status']=='CERTIFIED_RADIATION' and rad['complete'] and rad['cap']is None and not rad['unsupported_reasons'] and {m['id']for m in members}==set(src['ids']) and road['graph_identity']==hashlib.sha256(canonical(graph)).hexdigest() and road['source_identity']==src['hashes']['constructed_arrays.npz']+':'+src['hashes']['REPORT.json']
 if road['status']=='DEFINITE_REJECT'and not(c and c['status']=='DEFINITE_REJECT'):assert src['complete'] and rad and rad['complete'] and rad['status']=='DEFINITE_REJECT' and rad['cap']is None and any(F(m['dose_lower_kj_m2'])>F(request['budgets']['dose'][m['id']])or F(m['peak_lower_kw_m2'])>F(request['budgets']['peak'])for m in members)
 if rad and rad.get('complete')and not rad.get('unsupported_reasons')and members:assert len(members)==len(src['ids'])and[m['id']for m in members]==src['ids']
 for m in members:
  assert all(m.get(k)is not None for k in ['dose_lower_kj_m2','dose_upper_kj_m2','peak_lower_kw_m2','peak_upper_kw_m2']);assert F(m['dose_lower_kj_m2'])<=F(m['dose_upper_kj_m2'])and F(m['peak_lower_kw_m2'])<=F(m['peak_upper_kw_m2'])
  if road['status']=='CERTIFIED_ADMISSIBLE':assert F(m['dose_upper_kj_m2'])<=F(request['budgets']['dose'][m['id']])and F(m['peak_upper_kw_m2'])<=F(request['budgets']['peak'])
 diagnostic=None
 if src['complete']and rad and rad.get('complete')and not rad.get('unsupported_reasons')and members:
  key=hashlib.sha256(canonical([src['hashes'],graph,request,w['legs'],w['destination']])).hexdigest()
  if key not in reference_cache:
   lo=integrate(own['trajectory'],src['rectangles'],src['phases'],request['incurred'],src['ids'],density=src['density'],height=src['height'],order=16);hi=integrate(own['trajectory'],src['rectangles'],src['phases'],request['incurred'],src['ids'],density=src['density'],height=src['height'],order=32);reference_cache[key]={'gauss16':lo,'gauss32':hi,'diagnostics_not_proof':True}
  diagnostic=reference_cache[key]
  for m in members:
   v=next(v for v in diagnostic['gauss32']if v['id']==m['id']);assert m['dose_lower_kj_m2']-1e-8<=v['dose_kj_m2']<=m['dose_upper_kj_m2']+1e-8 and v['sampled_peak_w_m2']<=1000*m['peak_upper_kw_m2']+1e-7
 return {'road_decision':road['status'],'exact_contact':contact,'mission':{k:v for k,v in own.items()if k!='trajectory'},'diagnostic_reference':diagnostic,'sampled_quadrature_certificate_authority':False}

def main():
 global report
 a=argparse.ArgumentParser();a.add_argument('--opened-by-coordinator',action='store_true');a.add_argument('--panel',default='results/confirmation_v1');a.add_argument('--development',action='store_true');a.add_argument('--roster',default='CONFIRMATION_CASES.json');args=a.parse_args()
 if not args.development and not args.opened_by_coordinator:raise SystemExit('Coordinator authorization required; flag alone does not authorize another panel.')
 if args.development and args.roster=='CONFIRMATION_CASES.json':raise SystemExit('Development cannot open confirmation roster')
 seal=None
 if not args.development:
  seal=read(D/'IMPLEMENTATION_FREEZE.json')
  for p,h in seal['file_hashes'].items():assert sha(D/p)==h,p
  for name in ['IMPLEMENTATION_GATE.json','DRIVER_GATE.json']:
   gate=read(D/'review'/name);assert gate['status']=='GO'and gate['hashes']
   for p,h in gate['hashes'].items():assert sha(D/p)==h,p
 panel=D/args.panel;roster=read(D/args.roster);rows=read(panel/'ROWS.json');launches=read(panel/'LAUNCHES.json');expect={(c['id'],m)for c in roster for m in ['baseline','cache','heuristic','combined']};assert len(rows)==len(expect)and{(r['case']['id'],r['mode'])for r in rows}==expect and len(launches)==len(expect) and {(x['case'],x['mode'])for x in launches}==expect
 if seal:
  opening=read(panel/'OPENING_RECORD.json');assert opening['implementation_freeze_sha256']==sha(D/'IMPLEMENTATION_FREEZE.json')and opening['roster_sha256']==sha(D/args.roster)and opening['protocol_sha256']==sha(D/'PROTOCOL_FREEZE.json')and opening['all_reviewed_hashes_verified']and opening['no_post_open_tuning'];assert datetime.fromisoformat(seal['timestamp'])<=datetime.fromisoformat(opening['opened_at_UTC'])
 report={'schema':'wfg.independent.search-confirmation/1','development':args.development,'implementation_seal_sha256':None if seal is None else sha(D/'IMPLEMENTATION_FREEZE.json'),'rows_sha256':sha(panel/'ROWS.json'),'workers':[],'failures':[],'missing_phases':0,'reference_scope':'Known tiny exact centre-contract controls; incident search proof claims remain internal. Every returned checked route separately verified. Continuous road physics conditional on unchanged constructed source.'};cache={};sources={};refs={};cases={c['id']:c for c in roster}
 for row in rows:
  c=row['case'];assert c==cases[c['id']];report['active_worker']=[c['id'],row['mode']]
  if c['id']not in cache:
   if c['kind']=='reference':v=read(D/c['case_path']);g,h,q=v['graph'],v['hazard'],v['request'];s=None;refs[c['id']]=exhaustive(g,h,q);assert refs[c['id']]['status']==v['expected'].get('reference_status',v['expected']['center_status'])
   else:
    g,h,q=(read(D/c[k])for k in ['graph_path','hazard_path','request_path']);p=D/c['source_directory']
    if c['source_directory']not in sources:sources[c['source_directory']]=source(g,h,p)
    s=sources[c['source_directory']]
   cache[c['id']]=(g,h,q,s)
  g,h,q,s=cache[c['id']];worker={'case':c['id'],'kind':c['kind'],'mode':row['mode'],'phases':{},'launcher':row.get('launcher')}
  assert row.get('launcher')in launches and row['launcher']['case']==c['id']and row['launcher']['mode']==row['mode']
  for key in ['complete_process_wall_s','child_user_CPU_s','child_system_CPU_s']:
   value=row['launcher'].get(key);assert value is None or(type(value)in [int,float]and math.isfinite(value)and value>=0),('invalid launcher cost',key,value)
  for ph in ['cold','warm']:
   rec=row.get('records',{}).get(ph);worker['phases'][ph]=decision_record(rec)
   if rec is None:report['missing_phases']+=1;continue
   r=rec['result'];p=r['primary_search'];road=r['whole_road_check'];assert rec['search_limits_input']==q['limits'] and rec['center_hazard_sha256']==hashlib.sha256(canonical(h)).hexdigest();assert r['mode']==row['mode']and not r['physical_safety_claim']and not r['road_optimality_claim']and not r['routing_defaults_changed']
   if 'external_failure'not in r:assert r['limits_exactly_preserved']and r['search_resource_limits']==q['limits'];assert r['center_optimality_claim']==(p['status']=='CONDITIONAL_OPTIMUM')
   else:assert r['integrated_status']=='UNRESOLVED'and not r['center_optimality_claim']
   if p['status']in ['CONDITIONAL_OPTIMUM','CHECKED_ROUTE','PROVEN_INFEASIBLE','DISCONNECTED']:assert p['metrics']['wall_s']<q['limits']['wall_s']and p['metrics']['peak_rss_mb']<=q['limits'].get('rss_limit_mb',3072)
   w=None
   if p['status']in ['CONDITIONAL_OPTIMUM','CHECKED_ROUTE']:assert p['checker']['ok'];w=p
   elif p['status']=='TIMEOUT'and p.get('checked_incumbent'):
    w=p['checked_incumbent'];assert w['status']=='CHECKED_ROUTE'and w['checker']['ok']and not p['legs']and p['arrival']is None
   if w is not None:
    own=witness(g,h,q,w['legs'],w['destination']);assert own['ok']and float(own['arrival'])==w['arrival'];assert w['hazard_version']==h['version'];worker['phases'][ph]['center_witness']=own
    for mid,v in own['per_member'].items():assert F(w['checker']['per_member'][mid]['dose_exact'])==F(v['dose_exact'])and F(w['checker']['per_member'][mid]['peak'])==F(v['peak_exact'])
   if p['status']=='CONDITIONAL_OPTIMUM':assert all(all(all(x)for x in m['support'])for m in h['members'])
   if p['status']=='PROVEN_INFEASIBLE':assert all(all(all(x)for x in m['support'])for m in h['members'])and not p['metrics']['heap_entries'];worker['phases'][ph]['global_proof']='INDEPENDENT_TINY_REFERENCE'if c['kind']=='reference'else'INTERNAL_SEARCH_CLAIM_ONLY'
   if p['status']=='DISCONNECTED':assert structural_reachable(g,q)is False;worker['phases'][ph]['global_proof']='INDEPENDENT_STATIC_TURN_GRAPH'
   if c['kind']=='reference'and p['status']!='TIMEOUT'and'external_failure'not in r:
    v=read(D/c['case_path']);assert p['status']==v['expected']['center_status'];rr=refs[c['id']]
    if w is not None:assert float(rr['arrival'])==w['arrival']
    worker['phases'][ph]['center_global_reference']=rr
   worker['phases'][ph]['road_verification']=verify_road(g,h,q,w,road,s,cache.setdefault('radiation_reference_cache',{}))
   if road.get('secondary_road_result')is not None:worker['phases'][ph]['secondary_road_verification']=verify_road(g,h,q,w,road['secondary_road_result'],s,cache['radiation_reference_cache'])
   if r['integrated_status']in ['CERTIFIED_INTEGRATED_WITNESS','TIMEOUT_WITH_CHECKED_INTEGRATED_WITNESS']:assert road['status']=='CERTIFIED_ADMISSIBLE'and w is not None and ((p['status']=='TIMEOUT')==(r['integrated_status']=='TIMEOUT_WITH_CHECKED_INTEGRATED_WITNESS'))
   if r['integrated_status']=='SEARCH_WITNESS_DEFINITELY_REJECTED_ON_ROAD':assert road['status']=='DEFINITE_REJECT'and w is not None
  report['workers'].append(worker);report['cost']=cost();save(D/'review/CONFIRMATION_INDEPENDENT.json',report);print(c['id'],row['mode'],'independent',flush=True)
 report['active_worker']=None;report['verified_workers']=len(report['workers']);report['failed']=0;report['cost']=cost();save(D/'review/CONFIRMATION_INDEPENDENT.json',report);print(json.dumps({'verified_workers':report['verified_workers'],'missing_phases':report['missing_phases'],'cost':report['cost']}))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  report.setdefault('failures',[]).append({'exception':repr(exc),'traceback':traceback.format_exc()});report['cost']=cost();save(D/'review/CONFIRMATION_INDEPENDENT_FAILURE.json',report);raise
