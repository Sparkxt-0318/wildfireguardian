"""Coordinator-authorized sealed three-engine fresh review.
No candidate or driver evaluators imported. Independent absolute-time contact,
mission/identity/budget checks, and diagnostic direct solid-angle quadrature.
Analytic proof audit supplies enclosure authority; sampled peaks do not certify.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse,json,hashlib,sys,time,resource,platform,collections,traceback
import numpy as np
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'review'))
from practical_reference import source_rectangles,source_phases,contact_oracle,absolute_clip
from independent_mission import mission,compare_trajectory,digest
from numerical_radiation_reference import integrate
START=time.perf_counter();CPU=time.process_time();report={}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def cost():return {'wall_s':time.perf_counter()-START,'cpu_s':time.process_time()-CPU,'process_lifetime_rss_mb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if platform.system()=='Darwin' else 1024),'scope':'Independent checking wall/CPU after module imports, including seal/source/raw reading and incremental reports; RSS covers process lifetime including imports. External launcher full work separately receipted.'}
def main():
 global report
 parser=argparse.ArgumentParser();parser.add_argument('--opened-by-coordinator',action='store_true');parser.add_argument('--panel',default='results/confirmation_v1');args=parser.parse_args()
 if not args.opened_by_coordinator:raise SystemExit('Explicit coordinator authorization required; flag alone is not authorization.')
 seal=read(D/'IMPLEMENTATION_FREEZE.json');assert seal['status']=='SEALED_BEFORE_CONFIRMATION_OUTCOMES'
 for p,h in seal['file_hashes'].items():assert sha(D/p)==h,p
 for gate in ['IMPLEMENTATION_GATE.json','DRIVER_GATE.json']:
  g=read(D/'review'/gate);assert g['status']=='GO'
  for p,h in g['hashes'].items():assert sha(D/p)==h,(gate,p)
 panel=D/args.panel;rows=read(panel/'ROWS.json');protocol=read(D/'PROTOCOL_FREEZE.json');sources=read(D/'SOURCE_HISTORY_FREEZE.json');controls=read(D/'CONTROL_HISTORY_FREEZE.json');opening=read(panel/'OPENING_RECORD.json');launches=read(panel/'LAUNCHES.json')
 assert opening['implementation_sha256']==sha(D/'IMPLEMENTATION_FREEZE.json') and opening['driver_gate_sha256']==sha(D/'review/DRIVER_GATE.json') and opening['opened_at_utc']>seal['timestamp'] and opening['no_post_open_tuning']
 expected={s['directory'].split('/')[-1]+'_'+q['id']+'_depart'+str(dep) for s in sources['fresh_source_histories'] for q in protocol['queries'] for dep in q['departure_alternatives_s']}|{'control_'+c['id'] for c in protocol['labelled_controls']}
 assert len(rows)==len(expected)==18 and {r['case']['id'] for r in rows}==expected
 assert len(launches)==54 and len({(x['case'],x['engine']) for x in launches})==54 and all(x['elapsed_s']>=0 for x in launches)
 assert sha(D/'PROTOCOL_FREEZE.json')==sources['protocol_sha256']==controls['protocol_sha256']
 report={'schema':'wfg.independent.hybrid.confirmation/1','opened_after_coordinator_authorization':True,'implementation_seal_sha256':sha(D/'IMPLEMENTATION_FREEZE.json'),'rows_sha256':sha(panel/'ROWS.json'),'cases':[],'failures':[],'active_case':None,'limitations':['Finite constructed source model and declared complete supported geometry only; assumptions are not observations or physical safety.','Direct Gauss16/32 integrals and sampled peaks are supplemental diagnostics without error-bound certification authority.','Caps/unsupported/TIMEOUT remain unresolved; fixed-witness rejects are not graph infeasibility, certificates are not network optimality.']}
 sourcecache={};stats={kind:{engine:collections.Counter() for engine in ('baseline','practical','hybrid')} for kind in ('incident','control')}
 for row in rows:
  case=row['case'];cid=case['id'];kind=case['kind'];report['active_case']=cid;path=D/case['source_directory']
  if kind=='incident':
   spec=next(s for s in sources['fresh_source_histories'] if s['directory']==case['source_directory']);graph=read(D/'sample/uljin_graph.json');assert sha(D/'sample/uljin_graph.json')==protocol['graph_sha256']==case['graph_file_sha256'];q=next(q for q in protocol['queries'] if '_'+q['id']+'_depart' in cid);dep=int(cid.rsplit('depart',1)[1]);assert dep in q['departure_alternatives_s'];ids=spec['scenario_ids'];assert case['seed']==spec['seed'] and case['cutoff']==spec['cutoff']
   expected_req={'graph_revision':graph['revision'],'position':{'node':q['origin']},'incoming_edge':None,'departure':dep,'horizon':3600,'destinations':[{'node':q['destination'],'dwell':120,'open_intervals':[[0,3600]]}],'incurred':{i:0 for i in ids},'budgets':{'peak':10,'dose':{i:100 for i in ids}},'exposure_scope':'including_dwell'}
   assert case['request']==expected_req and case['destination']==q['destination'] and case['legs']==[{**x,'start':x['start']+dep,'end':x['end']+dep} for x in q['legs']] and case['edge_count']==q['edge_count'] and case['radiation_settings_override'] is None
  else:
   assert kind=='control';spec=next(s for s in controls['controls'] if s['directory']==case['source_directory']);ids=spec['scenario_ids'];m=read(path/'MISSION.json');assert sha(path/'MISSION.json')==spec['mission_sha256']==case['mission_file_sha256'];graph=m['graph'];assert case['graph']==graph and case['request']==m['request'] and case['legs']==m['legs'] and case['destination']==m['destination'] and case['radiation_settings_override']==m['radiation_settings_override']
  assert sha(path/'constructed_arrays.npz')==case['source_history_sha256']==spec['source_history_sha256'] and sha(path/'REPORT.json')==case['report_sha256']==spec['report_sha256']
  if case['source_directory'] not in sourcecache:
   meta=read(path/'REPORT.json');cfg=meta['native_metadata']['construction']['assumptions'];assert cfg==spec['config'] and meta['mode']=='research' and list(meta['rows'][0]['request']['incurred'])==ids
   with np.load(path/'constructed_arrays.npz',allow_pickle=False) as z:ev=z['ignition_time_s'];cur=z['current_active'];sup=z['support'];sup=sup.all(axis=1) if sup.ndim==4 else sup
   assert ev.ndim==3 and ev.shape[0]==4 and cur.shape==ev.shape[1:] and cur.dtype==sup.dtype==np.bool_;assert not np.isnan(ev).any() and not (ev<0).any() and not np.isfinite(ev[:,cur]).any() and np.all(ev[np.isfinite(ev)]<3600)
   assert cfg['unknown_probability']==.5 and cfg['burning_duration_s']==cfg['initial_remaining_s']==300 and cfg['current_state']=='known_burned_active' and cfg['unknown_current_state']=='cold' and cfg['emission_height_m']==5 and cfg['receiver_height_m']==0 and cfg['fuel_load_kg_m2']==10 and cfg['heat_of_combustion_j_kg']==18000000 and cfg['radiative_fraction']==.3 and cfg['consumed_fraction']==.1 and cfg['atmospheric_transmissivity']==1
   if kind=='control':assert not np.isfinite(ev).any() and set(np.flatnonzero(cur))==set(spec['control']['current_cells']) and bool(sup.all())==spec['control'].get('support_complete',True)
   else:assert sup.all()
   rects=source_rectangles(meta['native_metadata']['affine_transform'],cur.shape);phases=source_phases(ev,cur,300,300);sourcecache[case['source_directory']]=(rects,phases,bool(sup.all()))
  rects,phases,complete=sourcecache[case['source_directory']];own=mission(graph,case['request'],case['legs'],case['destination'],ids,3600);assert own['edge_count']==case['edge_count']
  if 'trajectory' in row:compare_trajectory(row['trajectory'],own['trajectory'])
  refs=contact_oracle(own['trajectory'],rects,phases,ids);hascontact=any(x['contact'] for x in refs);checked={'case':cid,'kind':kind,'source_complete':complete,'exact_contact':refs,'independent_mission':{k:v for k,v in own.items() if k!='trajectory'},'engines':{}};enclosures=[]
  for engine in ('baseline','practical','hybrid'):
   worker=row.get(engine+'_worker',{});checked['engines'][engine]={};assert worker.get('engine',engine)==engine
   if worker.get('trajectory') is not None:compare_trajectory(worker['trajectory'],own['trajectory'])
   wc=worker.get('case')
   if wc is not None:
    assert wc['source_history_sha256']==case['source_history_sha256'] and wc['graph_canonical_sha256']==digest(graph) and wc['request']==case['request'] and wc['legs']==case['legs']
   for phase in ('cold','warm'):
    rec=row.get(engine,{}).get(phase)
    if rec is None:
     checked['engines'][engine][phase]={'primary_status':'UNRESOLVED','missing_phase':True}
     if phase=='cold':stats[kind][engine]['UNRESOLVED']+=1
     continue
    assert rec==worker['records'][phase];primary=rec['primary_status'];raw=rec['raw'];assert primary in {'CERTIFIED_ADMISSIBLE','DEFINITE_REJECT','UNRESOLVED'} and rec['primary_cap_s']==30
    if rec['elapsed_s']>=30 or rec['process_lifetime_rss_mb']>3072:assert primary=='UNRESOLVED'
    if engine=='baseline':
     rad=raw;contact=None;members=raw.get('per_member',[])
     if primary=='CERTIFIED_ADMISSIBLE':assert raw['status']=='CERTIFIED_ACCEPT' and raw['complete'] and raw['cap'] is None and not raw['unsupported_reasons'] and complete and not hascontact and {x['id'] for x in members}==set(ids) and all(x['support'] and x['contact_complete'] and x['bound_certified'] and not x['flame_contact'] for x in members)
     if primary=='DEFINITE_REJECT':
      assert raw['status']=='DEFINITE_REJECT';contact_ids=[x['id'] for x in members if x.get('flame_contact')];assert (contact_ids and all(refs[ids.index(i)]['contact'] for i in contact_ids)) or any(F(x['dose_lower_kj_m2'])>F(case['request']['budgets']['dose'][x['id']]) or F(x['peak_lower_kw_m2'])>10 for x in members)
    else:
     assert raw['fixed_path_only'] and not raw['global_optimality_or_infeasibility_claim'] and not raw['physical_validation'];contact=raw.get('contact');rad=raw.get('radiation');members=[] if not rad else rad.get('per_member',[])
     if contact:
      if contact['status']=='CLEAR':assert complete and not hascontact and contact['complete'] and contact['contact_clear']
      elif contact['status']=='DEFINITE_REJECT':
       assert hascontact;w=contact['witness'];mi=ids.index(w['member']);cell=w['source_cell'];li=w['segment_index'];t=F(w['time_exact']);clip=absolute_clip(own['trajectory'][li],rects[cell]);birth,end=phases[mi][cell];assert clip is not None and clip[0]<=t<=clip[1] and birth<=t<end and list(map(F,w['rectangle_exact']))==list(rects[cell]) and list(map(F,w['source_phase_interval_exact']))==[birth,end]
      else:assert contact['status']=='UNRESOLVED'
     if primary=='CERTIFIED_ADMISSIBLE':assert raw['status']=='CERTIFIED_ADMISSIBLE' and complete and not hascontact and contact['status']=='CLEAR' and rad['status']=='CERTIFIED_RADIATION' and rad['complete'] and rad['cap'] is None and not rad['unsupported_reasons'] and raw['source_identity']==case['source_history_sha256']+':'+case['report_sha256'] and raw['graph_identity']==digest(graph) and {x['id'] for x in members}==set(ids)
     if primary=='DEFINITE_REJECT' and not(contact and contact['status']=='DEFINITE_REJECT'):assert complete and rad and rad['status']=='DEFINITE_REJECT' and rad['complete'] and rad['cap'] is None and any(F(x['dose_lower_kj_m2'])>F(case['request']['budgets']['dose'][x['id']]) or F(x['peak_lower_kw_m2'])>10 for x in members)
    for x in members:
     assert F(x['dose_lower_kj_m2'])<=F(x['dose_upper_kj_m2']) and F(x['peak_lower_kw_m2'])<=F(x['peak_upper_kw_m2'])
     if primary=='CERTIFIED_ADMISSIBLE':assert F(x['dose_upper_kj_m2'])<=F(case['request']['budgets']['dose'][x['id']]) and F(x['peak_upper_kw_m2'])<=10
    if rad and rad.get('complete') and not rad.get('unsupported_reasons') and members:enclosures.append((engine,phase,members))
    checked['engines'][engine][phase]={'primary_status':primary,'elapsed_s':rec['elapsed_s'],'cpu_s':rec.get('cpu_s'),'rss_mb':rec['process_lifetime_rss_mb'],'contact':None if contact is None else contact['status'],'complete_enclosure':bool(rad and rad.get('complete')),'cap':None if not rad else rad.get('cap')}
    if phase=='cold':stats[kind][engine][primary]+=1
  if complete and enclosures:
   low=integrate(own['trajectory'],rects,phases,case['request']['incurred'],ids,order=16);high=integrate(own['trajectory'],rects,phases,case['request']['incurred'],ids,order=32);refby={x['id']:x for x in high};checked['supplemental_numerical_reference']=[{**x,'gauss16_vs32_dose_delta':abs(x['dose_kj_m2']-next(y['dose_kj_m2'] for y in low if y['id']==x['id'])),'convergence_is_not_proof':True} for x in high];comparisons=[]
   for engine,phase,members in enclosures:
    for x in members:
     v=refby[x['id']];assert x['dose_lower_kj_m2']-1e-8<=v['dose_kj_m2']<=x['dose_upper_kj_m2']+1e-8,(cid,engine,phase,x,v)
     assert v['sampled_peak_w_m2']<=x['peak_upper_kw_m2']*1000+1e-7,(cid,engine,phase,x,v)
    comparisons.append({'engine':engine,'phase':phase,'dose_and_sampled_peak_consistent':True,'sampled_lower_peak_comparison_not_a_proof':True})
   checked['diagnostic_enclosure_comparisons']=comparisons
  report['cases'].append(checked);report['cost']=cost();save(D/'review/CONFIRMATION_INDEPENDENT.json',report);print(cid,'independent',[(e,x['cold']['primary_status']) for e,x in checked['engines'].items()],flush=True)
 report['active_case']=None;report['passed_cases']=len(report['cases']);report['failed']=0;report['independent_cold_outcomes']={k:{e:dict(c) for e,c in v.items()} for k,v in stats.items()};report['cost']=cost();save(D/'review/CONFIRMATION_INDEPENDENT.json',report);print(json.dumps({'passed_cases':report['passed_cases'],'outcomes':report['independent_cold_outcomes'],'cost':report['cost']}))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  report.setdefault('failures',[]).append({'active_case':report.get('active_case'),'exception':repr(exc),'traceback':traceback.format_exc()});report['failed']=len(report['failures']);report['cost']=cost();save(D/'review/CONFIRMATION_INDEPENDENT_FAILURE.json',report);raise
