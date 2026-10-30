"""Independent stored FARSITE custody, subset joins and arithmetic. No production helper imports."""
from pathlib import Path
import argparse,collections,datetime,fcntl,hashlib,importlib.util,json,math,subprocess,time,traceback
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score,roc_auc_score
OWN=Path(__file__).resolve().parent
WORK=OWN.parent
ROOT=WORK/'track-1b'
E=ROOT/'research/forecast-v2'
HEAD='691cc162bf2c0295cecc257a558ae0d583f9018e'
EXPECTED={'c651_mc','c651_meanfield','persistence','logistic','dilation_best',*(f'dilation_{h}h' for h in (1,2,4,8)),*(v+'_seed0' for v in ('base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base'))}
CHECKS=[];PINS={};NUMERIC=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,label):
 CHECKS.append(dict(check=label,passed=bool(ok)))
 if not ok:raise ValueError(label)
def load(p):return json.loads(Path(p).read_text())
def pin(p,expected=None):
 p=Path(p);value=sha(p)
 if expected is not None:need(value==expected,'hash '+str(p))
 PINS[str(p)]=value;return value
def ash(a):
 a=np.ascontiguousarray(a);return hashlib.sha256(str((a.shape,str(a.dtype))).encode()+a.tobytes()).hexdigest()
def compare(a,b,label='value'):
 if isinstance(b,dict):
  need(isinstance(a,dict),label+' object')
  for k,v in b.items():need(k in a,label+' missing '+k);compare(a[k],v,label+'.'+k)
 elif isinstance(b,list):
  need(isinstance(a,list) and len(a)==len(b),label+' list size')
  for i,(x,y) in enumerate(zip(a,b)):compare(x,y,label+'/'+str(i))
 elif b is None:need(a is None,label+' null')
 elif isinstance(b,(bool,str,int)):need(type(a) is type(b) and a==b,label+' exact')
 else:
  need(type(a) in (int,float) and math.isfinite(a) and math.isclose(a,float(b),rel_tol=2e-10,abs_tol=2e-12),label+' numeric')
  NUMERIC.append(dict(field=label,absolute_difference=abs(a-b)))
def duration_ok(start,end):return 0<(end.value-start.value)<=48*3600*10**9

def metric(y,p):
 y=np.asarray(y,np.float64);p=np.asarray(p,np.float64)
 need(y.ndim==p.ndim==1 and y.shape==p.shape and len(y)>0 and np.isin(y,[0,1]).all() and np.isfinite(p).all() and ((p>=0)&(p<=1)).all(),'metric admitted population')
 n=len(y);edges=np.linspace(0,1,11);rows=[]
 for i in range(10):
  use=(p>=edges[i])&((p<edges[i+1]) if i<9 else p<=1);count=int(use.sum())
  rows.append(dict(lower=float(edges[i]),upper=float(edges[i+1]),count=count,share=count/n,mean_prediction=float(p[use].mean()) if count else None,observed_frequency=float(y[use].mean()) if count else None))
 error=float(np.mean((p-y)**2));ref=float(np.mean(y*y));clipped=np.maximum(np.minimum(p,1-1e-7),1e-7)
 return dict(entries=n,positives=int(y.sum()),brier=error,bss_vs_persistence=1-error/ref if ref else None,average_precision=float(average_precision_score(y,p)) if y.sum() else None,roc_auc=float(roc_auc_score(y,p)) if 0<y.sum()<n else None,ece_10_bins=sum(r['count']*abs(r['mean_prediction']-r['observed_frequency']) for r in rows if r['count'])/n,clipped_nll=float(np.mean(-y*np.log(clipped)-(1-y)*np.log1p(-clipped))),exact_zero_probability_positives=int(((p==0)&(y==1)).sum()),lowest_bin=rows[0],calibration=rows)

def paired(fires,y,p,q,draws=10000,seed=20261030):
 # Frozen producer preserves the saved dtype for squared-error reductions.
 names=np.unique(fires);errors=np.asarray([np.sum((p[fires==f]-y[fires==f])**2)-np.sum((q[fires==f]-y[fires==f])**2) for f in names]);counts=np.asarray([int((fires==f).sum()) for f in names],np.float64)
 indices=np.random.default_rng(seed).integers(0,len(names),size=(draws,len(names)));sampled=errors[indices].sum(1)/counts[indices].sum(1);lo,hi=np.quantile(sampled,[.025,.975]);per={str(f):float(e/n) for f,e,n in zip(names,errors,counts)}
 return dict(point_difference=float(errors.sum()/counts.sum()),percentile_95_interval=[float(lo),float(hi)],excludes_zero=bool(hi<0 or lo>0),fires=len(names),draws=draws,seed=seed,per_fire_difference=per,fires_favouring_candidate=int(sum(v<0 for v in per.values())),definition='candidate Brier minus reference Brier; negative favours the candidate; whole fires resampled')

def scores(entry):
 fire,y,pred=entry['fire'],entry['y'],entry['predictions'];fires=np.unique(fire);errors={name:np.asarray([np.sum((p[fire==f]-y[fire==f])**2) for f in fires]) for name,p in pred.items()};draw=np.random.default_rng(20261030).integers(0,len(fires),size=(10000,len(fires)));models={};pairs={}
 for name,p in pred.items():
  pooled=metric(y,p);each={str(f):metric(y[fire==f],p[fire==f]) for f in fires};wrong=int((((p==0)&(y==1))|((p==1)&(y==0))).sum());pooled['exact_nll']=dict(value=None if wrong else float((-np.log(p[y==1]).sum()-np.log1p(-p[y==0]).sum())/len(y)),infinite=bool(wrong),certainty_wrong_entries=wrong);models[name]=dict(pooled=pooled,per_fire=each)
 for name,p in pred.items():
  row=models[name]
  for ref,key in [('persistence','bss_vs_persistence'),('dilation_best','bss_vs_best_dilation')]:
   den=errors[ref].sum();row['pooled'][key]=float(1-errors[name].sum()/den) if den else None
   d=errors[ref][draw].sum(1);ok=d>0;value=1-errors[name][draw].sum(1)[ok]/d[ok]
   row[key+'_paired_fire_95_interval']=dict(interval=np.quantile(value,[.025,.975]).tolist() if len(value) else None,draws=10000,seed=20261030,undefined_zero_reference_draws=int((~ok).sum()),unit='whole fire, pooled error ratio')
   for f,per in row['per_fire'].items():
    d=models[ref]['per_fire'][f]['brier'];per[key]=1-per['brier']/d if d else None
   if name!=ref:pairs[name+'__vs__'+ref]=paired(fire,y,p,pred[ref])
 return dict(models=models,paired=pairs,fires=[str(f) for f in fires],entries=len(y),positives=int(y.sum()))

def row_join(current,aggregate,record,initial,endpoint,fp,fv,reference_valid,start,end):
 rr,cc,y=[current[k] for k in ['row','col','y']];shape=initial.shape
 need(rr.dtype.kind in 'iu' and cc.dtype.kind in 'iu' and rr.ndim==cc.ndim==y.ndim==1 and rr.shape==cc.shape==y.shape and len(y)>0,'current coordinate shape/dtype')
 need((rr>=0).all() and (cc>=0).all() and (rr<shape[0]).all() and (cc<shape[1]).all() and (np.diff(rr.astype(np.int64)*shape[1]+cc.astype(np.int64))>0).all(),'current ordered distinct source cells')
 need(not initial[rr,cc].any() and np.array_equal(y,endpoint[rr,cc]),'current unburned initial and exact endpoint labels')
 mask=np.zeros(shape,bool);mask[rr,cc]=True
 compare({k:record[k] for k in ['initial_sha256','endpoint_sha256','rectangle','scored_mask_sha256','scored_cells','positives']},dict(initial_sha256=ash(initial),endpoint_sha256=ash(endpoint),rectangle=list(shape),scored_mask_sha256=ash(mask),scored_cells=len(y),positives=int(y.sum())),'current source label identity')
 indices=[i for i,t in enumerate(aggregate['t1']) if pd.Timestamp(str(t))==start];need(len(indices)==1,'unique aggregate cutoff join');interval=indices[0];need(abs(float(aggregate['hours'][interval])-(end-start).total_seconds()/3600)<1e-9,'exact aggregate endpoint duration')
 cols={'row','col','y',*('p_'+n for n in EXPECTED)}
 need(set(current)==cols and {n for n in aggregate if n.startswith('p_')}=={'p_'+n for n in EXPECTED},'fixed16 current columns')
 use_agg=aggregate['interval']==interval
 for k in sorted(cols):need(np.array_equal(current[k],aggregate[k][use_agg]),'exact current/aggregate row join '+k)
 use=fv[rr,cc]&reference_valid[rr,cc];need(use.any(),'nonempty FARSITE intersection')
 pred={n:current['p_'+n][use].copy() for n in sorted(EXPECTED)}
 for name,p in pred.items():need(p.shape==y[use].shape and np.isfinite(p).all() and ((p>=0)&(p<=1)).all(),'valid current subset '+name)
 pred['farsite_scenario']=fp[rr[use],cc[use]].copy()
 return dict(fire=np.full(int(use.sum()),record['case']['event']),y=y[use].copy(),predictions=pred),hashlib.sha256(np.column_stack([rr[use],cc[use]]).tobytes()).hexdigest()

def audit_actual():
 auth=load(WORK/'FINAL_CANONICAL_SAVED_REVIEW_AUTHORIZATION_V2.json');need(auth['status']=='AUTHORIZED_READ_ONLY_CANONICAL_REVIEW' and 'SAVED_FARSITE_ROW_RECONCILIATION' in auth['allowed'] and auth['authorized_source_head']==HEAD,'explicit root saved FARSITE authorization')
 need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==HEAD,'frozen authorized source head')
 artifact=E/'FARSITE_SCORES.json';pin(artifact,'f0aa554c2312f3e177eb5d2a165e4aa50a986c3e883beda56510b201bcb3f6e2');pin(E/'scripts/audit_farsite.py','6edb769fbcb9a7977e2689f7de337ed327feabd5dadd9983f3cec3443e04a6db');out=load(artifact)
 receipt_path=E/'executions/final_farsite_saved_scenarios.json';pin(receipt_path,'3b0076e5b456574ac144ffc6ad76b8c099ccc435b33c1c209ac3e386b2e48a50');receipt=load(receipt_path);cmd=receipt['command'];data=Path(cmd[cmd.index('--data')+1]);assessment=Path(cmd[cmd.index('--assessment')+1]);need(cmd[1]==str(E/'scripts/audit_farsite.py') and Path(cmd[cmd.index('--out')+1])==artifact,'exact canonical source/output command');need(receipt['exit_code']==0 and receipt['status']=='COMPLETE_COMMAND' and receipt['changed_protected_files']==[],'saved FARSITE execution bookends')
 pin(ROOT/receipt['log'],receipt['log_sha256']);need(load(ROOT/receipt['log'])==dict(cases=30,scored=True),'saved command log')
 skipped_binary_pins=[]
 for relative,digest in receipt['frozen_files_sha256'].items():
  if Path(relative).suffix in ['.pt','.pkl']:skipped_binary_pins.append(relative);continue
  pin(ROOT/relative,digest)
 selection=load(E/'MODEL_SELECTION.json');registry=load(E/'BLIND_REGISTRY.json');frozen=load(assessment/'FROZEN_ASSESSMENT.json');assessed=load(assessment/'ASSESSMENT.json')
 pin(assessment/'ASSESSMENT.json',out['assessment_sha256']);pin(assessment/'FROZEN_ASSESSMENT.json',out['frozen_assessment_sha256']);pin(E/'BLIND_REGISTRY.json',frozen['registry']['sha256']);pin(E/'MODEL_SELECTION.json',frozen['selection_sha256']);pin(E/'SPLIT.json',frozen['split_sha256'])
 need(frozen['cohort']=='us2024' and frozen['trajectories']==1024 and frozen['seed']==0 and frozen['boundary']=='zero' and registry['selection']==dict(path='research/forecast-v2/MODEL_SELECTION.json',sha256=sha(E/'MODEL_SELECTION.json')),'frozen cohort/settings/selection identities')
 need(registry['selected_model']==selection['selected_variant']+'_seed0' and frozen['checkpoints']==selection['checkpoints'] and frozen['c651_sha256']==registry['models']['c651_mc']['sha256'] and frozen['development_coverage_sha256']==selection['development_coverage_sha256'],'frozen model/development pointers')
 for source,digest in frozen['source_sha256'].items():pin(ROOT/source,digest)
 for name,digest in registry['producer_source_sha256'].items():pin(ROOT/name,digest)
 pin(data/'EXTRACTION_MANIFEST.json',frozen['extraction_manifest_sha256']);pin(data/'perimeters/PERIMETER_MANIFEST.json',frozen['perimeter_manifest_sha256']);perimeter_manifest=load(data/'perimeters/PERIMETER_MANIFEST.json');pin(data/'FARSITE_INPUTS_EXTRACTION.json',out['source_input_manifest_sha256']);extraction=load(data/'FARSITE_INPUTS_EXTRACTION.json')
 source_rows={row['path']:row for row in extraction['files']};need(len(source_rows)==len(extraction['files'])==78,'all78 distinct historical scenario raster identities')
 for row in extraction['files']:need(row['historical_input_identity_matches'] is True,'stored historical input match flag');pin(data/row['path'],row['sha256'])
 catalog={r['id']:r for r in load(data/'environment/events.json')};events=load(E/'SPLIT.json')['held_out']['us_2024'];need(assessed['events']==events and len(events)==6 and assessed['frozen_sha256']==sha(assessment/'FROZEN_ASSESSMENT.json'),'exact six-event assessment population')
 need(out['assessment_status']==assessed['status']=='COMPLETE' and out['assessment_complete'] is True and out['assessment_unscored_outcomes']==assessed['failed_or_unavailable']==[] and out['current_case_admission_pass'] is True and out['rejected_current_cases']==[],'saved current assessment/admission status')
 by_time={};aggregates={};source_states={}
 for record in assessed['cases']:
  c=record['case'];key=(c['event'],pd.Timestamp(c['cutoff']),pd.Timestamp(c['endpoint']));need(key not in by_time,'unique current interval identity');by_time[key]=record
 for event in events:
  p=assessment/(event+'.npz');pin(p,assessed['per_fire_files'][p.name]);need(receipt['canonical_artifacts_sha256'][str(p.relative_to(ROOT))]==sha(p),'canonical execution aggregate pin '+event)
  with np.load(p,allow_pickle=False) as a:aggregates[event]={k:a[k] for k in a.files}
  p=data/'perimeters'/event/'states.npz';pin(p,perimeter_manifest['events'][event]['states_sha256'])
  with np.load(p,allow_pickle=False) as a:source_states[event]=([pd.Timestamp(t) for t in pd.to_datetime(a['times'],utc=True)],a['states'])
 history=data/'historical_observed/20261013_observed_merged/cases';dirs=sorted(p for p in history.iterdir() if p.is_dir());need(len(dirs)==30 and [p.name for p in dirs]==[r['case_id'] for r in out['cases']],'all30 ordered stored scenario directories retained')
 entries=[];case_summary=[];unavailable=[];native_raw_paths=[];dtype_summary=collections.defaultdict(set)
 for directory,row in zip(dirs,out['cases']):
  report=load(directory/'report.json');protocol=load(directory/'protocol.json');manifest=load(directory/'combined_case_manifest.json')
  for name,digest in manifest.items():pin(directory/name,digest)
  for name,key in [('report.json','report_sha256'),('protocol.json','protocol_sha256'),('combined_case_manifest.json','combined_case_manifest_sha256'),('reference.npz','reference_sha256'),('farsite_prediction.npz','farsite_prediction_sha256')]:pin(directory/name,row[key])
  event=protocol['event'];start,end=pd.Timestamp(protocol['cutoff']),pd.Timestamp(protocol['endpoint']);grid=catalog[event];need(row['event']==event and pd.Timestamp(row['cutoff'])==start and pd.Timestamp(row['endpoint'])==end and grid['country']=='US' and grid['year']==2024 and event in events,'exact historical event/time/population')
  case_seed=int.from_bytes(hashlib.sha256(json.dumps([0,event,start.isoformat()],separators=(',',':')).encode()).digest()[:8],'little')
  need(protocol['n_samples']==1024 and protocol['case_seed']==case_seed and protocol['trajectory_batch_size']==32 and protocol['boundary']=='zero' and protocol['environment_policy']=='repeated_current' and pd.Timestamp(protocol['environmental_snapshot_time_utc'])==start.floor('h') and abs(protocol['hours']-(end-start).total_seconds()/3600)<1e-9,'stored protocol settings/seed/time')
  context=report['farsite_input_manifest'];need(context['original_shape']==[grid['height'],grid['width']] and context['original_epsg']==grid['epsg'] and np.array_equal(context['original_transform'],grid['transform']),'source rectangle/crs/transform identity')
  for src in context['source_files']:
   relative='farsite-inputs/'+src['path'].split('/data/environment/')[-1]
   need(relative in source_rows and source_rows[relative]['sha256']==src['sha256'],'case historical source raster pin '+relative)
  times,states=source_states[event];i,j=times.index(start),times.index(end);need(j==i+1,'consecutive source survey pair');initial=states[i].astype(bool);endpoint=states[j].astype(bool)
  with np.load(directory/'reference.npz',allow_pickle=False) as ref:
   need(np.array_equal(ref['burned_area'][:,0].astype(bool),np.stack([initial,endpoint])),'stored exact initial/endpoint extents');reference_valid=ref['burned_area_valid'][0,0]&ref['burned_area_valid'][1,0]&ref['pixel_valid'][0]
  with np.load(directory/'farsite_prediction.npz',allow_pickle=False) as f:
   fp=f['probability'][0,0];fv=f['valid'][0,0];arrival=f['arrival_minutes'];metadata=json.loads(str(f['metadata_json']))
  need(fp.shape==fv.shape==initial.shape==reference_valid.shape==arrival.shape and fv.dtype==reference_valid.dtype==bool and np.isin(fp[fv],[0,1]).all() and metadata['observed_initial'] is True,'native deterministic shape/validity')
  execution=report['farsite_execution'];clock=report['native_clock_verification'];minutes=(end-start).total_seconds()/60
  need(execution['elapsed_minutes']==clock['duration_minutes']==minutes==metadata['exact_duration_minutes'] and execution['native_clock_verification']==clock and execution['arrival_units']=='minutes since simulation cutoff' and execution['endpoint_selection']=='0 <= arrival <= '+str(float(minutes)),'recorded finite native horizon exact endpoint')
  need(metadata['no_burn_value']==execution['header']['nodata_value']==-9999 and metadata['arrival_units']=='minutes' and metadata['arrival_origin_time_utc']==start.timestamp() and metadata['arrival_endpoint']=='inclusive_at_exact_cutoff_plus_hours' and metadata['initial_ignition_policy']=='observed_initial_burn_union_simulated_arrivals_including_zero' and metadata['method']=='farsite_deterministic' and metadata['scenario_count']==1,'saved arrival/censor/initial convention')
  need(np.isfinite(arrival[fv]).all() and not ((arrival[fv]<0)&(arrival[fv]!=-9999)).any(),'saved arrival valid finite or explicit censor');expected_fp=(~initial)&(arrival!=-9999)&(arrival>=0)&(arrival<=minutes);need(np.array_equal(fp[fv],expected_fp[fv]),'saved native endpoint occupancy from arrival/censor')
  compare(row['native_horizon'],dict(status='AVAILABLE',reason=None,native_horizon_minutes=float(minutes),endpoint_minutes=float(minutes),native_timings_sha256=execution['timings_sha256'],native_arrival_sha256=execution['arrival_sha256'],no_burn_value=metadata['no_burn_value']),'native horizon '+directory.name)
  for kind in ['arrival_file','timings_file']:native_raw_paths.append(dict(case=directory.name,kind=kind,path=execution[kind],present_at_recorded_path=Path(execution[kind]).is_file()))
  need(row['initial_and_endpoint_equal_current_source'] is True and row['consecutive_survey_pair'] is True and row['source_raster_identities_verified'] is True and row['historical_m548_predictions_admitted'] is False and row['native_executable_sha256']==report['models'][1]['sha256'],'stored row qualification flags')
  need(context['boundary_padding_cells']==1 and 'fuel99' in context['boundary_policy'] and 'spatially summarized' in row['weather'] and 'fuel99' in row['boundary'],'weather and boundary differences retained')
  record=by_time.get((event,start,end));eligible=duration_ok(start,end)
  if not eligible:
   need(row['status']=='UNAVAILABLE' and row['reason']=='HISTORICAL_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY' and row['cells']==0 and record is None and 'current_case' not in row,'out of48h retained without invented current match')
   need(minutes==4489 and row['frozen_cohort_eligibility']==dict(status='UNAVAILABLE',reason=row['reason']),'4489minute unavailable eligibility retained');unavailable.append({k:row[k] for k in ['case_id','event','cutoff','endpoint','status','reason']});case_summary.append(dict(case_id=row['case_id'],status=row['status'],minutes=minutes,cells=0));continue
  need(row['frozen_cohort_eligibility']==dict(status='ELIGIBLE',reason=None) and record is not None and record['status']=='SCORED' and row['current_case']==record,'eligible exact current receipt join')
  cid=record['case_id'];p=assessment/'cases'/(cid+'.json');pin(p,row['current_case_receipt_sha256']);need(load(p)==record,'exact individual receipt JSON');p=assessment/'cases'/(cid+'.npz');pin(p,row['current_prediction_sha256']);need(record['sha256']==sha(p)==receipt['canonical_artifacts_sha256'][str(p.relative_to(ROOT))],'current prediction execution hash')
  with np.load(p,allow_pickle=False) as a:current={k:a[k] for k in a.files}
  entry,coordsha=row_join(current,aggregates[event],record,initial,endpoint,fp,fv,reference_valid,start,end)
  need(row['status']=='SCORED_COMMON_SUBSET' and row['cells']==len(entry['y']) and row['exact_row_col_sha256']==coordsha,'exact admitted common-cell subset '+directory.name)
  entries.append(entry);case_summary.append(dict(case_id=row['case_id'],current_case_id=cid,event=event,status=row['status'],minutes=minutes,cells=len(entry['y']),positives=int(entry['y'].sum()),row_col_sha256=coordsha))
  for n,p in entry['predictions'].items():dtype_summary[n].add(str(p.dtype))
 need(len(entries)==out['scored_cases']==out['scored_case_count']==29 and len(unavailable)==1 and out['skipped_unavailable_cases']==unavailable,'29scored plus one retained unavailable row')
 need(out['stored_case_count']==out['total_historical_cases']==30 and out['stored_fire_count']==6 and out['all_stored_cases_scored'] is False and out['native_execution_this_command'] is False and out['superiority_criteria_pass'] is False and out['execution_status']=='NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY' and out['status']=='HOLD' and out['metric_status']=='DESCRIPTIVE_AVAILABLE_MATCHED_SUBSET' and out['measurement_status']=='AVAILABLE_DESCRIPTIVE_MATCHED_SUBSET','descriptive HOLD/nonexecution/nonpromotion envelope')
 need('spatially summarized' in out['configuration_differences']['weather'] and 'fuel99' in out['configuration_differences']['boundary'] and 'one deterministic' in out['configuration_differences']['stochasticity'] and 'incomplete' in out['coverage'],'configuration and incomplete-cohort qualifications retained')
 combined=dict(fire=np.concatenate([e['fire'] for e in entries]),y=np.concatenate([e['y'] for e in entries]),predictions={n:np.concatenate([e['predictions'][n] for e in entries]) for n in entries[0]['predictions']})
 need(set(combined['predictions'])==EXPECTED|{'farsite_scenario'} and len(combined['y'])==288999 and int(combined['y'].sum())==2636,'complete17column288999entry population')
 computed=scores(combined);need(set(out['scores'])==set(computed) and set(out['scores']['models'])==set(computed['models']) and set(out['scores']['paired'])==set(computed['paired']),'all17 models and32 paired metric records')
 compare(out['scores'],computed,'all independent saved FARSITE subset metrics')
 (OWN/'RECOMPUTED_SCORES.json').write_text(json.dumps(computed,indent=2,allow_nan=False)+'\n')
 for path,digest in list(PINS.items()):need(sha(Path(path))==digest,'review end byte bookend '+path)
 return dict(status='PASS_INDEPENDENT_STORED_FARSITE_RECONCILIATION',checks=len(CHECKS),passed=sum(c['passed'] for c in CHECKS),checks_detail=CHECKS,source_head=HEAD,artifact_sha256=sha(artifact),pins=PINS,cases=case_summary,entries=len(combined['y']),positives=int(combined['y'].sum()),models=len(computed['models']),paired_comparisons=len(computed['paired']),prediction_dtypes={k:sorted(v) for k,v in dtype_summary.items()},comparison_policy=dict(rel_tol=2e-10,abs_tol=2e-12),largest_absolute_numeric_difference=max((x['absolute_difference'] for x in NUMERIC),default=0),missing_original_native_file_references=[x for x in native_raw_paths if not x['present_at_recorded_path']],model_binary_pins_not_rehashed=skipped_binary_pins,model_binaries_loaded=False,native_executions=False,training_or_inference=False,source_raster_values_loaded=False,raw_historical_m548_predictions_loaded=False,limitations=['Reconstructs saved stored source extents, native arrival/censor occupancy, reference masks, current common-cell joins and saved metrics only. No new native execution or physical truth is authenticated.','Historical native ASC/timings file hashes remain source-recorded receipts when their exact recorded paths are absent; saved NPZ arrival arrays are checked independently.','Original scenario input rasters are hash authenticated, not numerically re-rendered into FARSITE landscapes/weather or compared to physical observations.','Historical M548 prediction bytes are hashed solely for the original combined case manifest, never loaded or scored.','Model/checkpoint/fitted-baseline binary identities are pointer-checked, not loaded or rehashed.','Intervals repeat six fires; whole-fire bootstrap is conditional on fixed predictions, admitted mapped-extent labels and this 29-case subset. No full-cohort superiority, futureblind or physical validation.'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--actual',action='store_true');args=p.parse_args();need(args.actual,'explicit actual mode required')
 queued=datetime.datetime.now(datetime.timezone.utc).isoformat();print('QUEUED',queued,flush=True)
 with open('/tmp/wfg/HEAVY.lock','a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);acquired=datetime.datetime.now(datetime.timezone.utc).isoformat();print('ACQUIRED',acquired,flush=True);started=time.monotonic()
  try:result=audit_actual();code=0
  except Exception as e:result=dict(status='HOLD_INDEPENDENT_STORED_FARSITE_REVIEW',error_type=type(e).__name__,reason=str(e),checks=len(CHECKS),passed=sum(c['passed'] for c in CHECKS),traceback=traceback.format_exc(),pins=PINS);code=1
  result.update(queued_utc=queued,acquired_utc=acquired,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,checker_sha256=sha(__file__))
  (OWN/'ACTUAL_REVIEW.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed','elapsed_seconds']}),flush=True)
  fcntl.flock(lock,fcntl.LOCK_UN)
 return code
if __name__=='__main__':raise SystemExit(main())
