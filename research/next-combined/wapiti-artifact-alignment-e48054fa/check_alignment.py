"""Untimed immutable Wapiti artifact alignment only; never scores predictions."""
from pathlib import Path
from datetime import datetime,timezone
import collections,fcntl,hashlib,io,json,math,platform,resource,subprocess,sys,time
import numpy as np
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');REPO=TASK/'work/audit-1b';OUT=Path(__file__).resolve().parent
COMMIT='e48054fa420af0b0477070f496c88ebc16ed2b8a';FREEZE='6887dc618253e6568c6cbbfd3c9a96f1d0d86b70';EVENT='ID-BOF-000683_Wapiti_Wapiti';BASE='forecast/runs/20261030_perimeter_trained/execution_v3/heldout'
MANIFEST='research/forecast-v2/executions/current_us2024_Wapiti_complete.json';MANIFEST_SHA='e944d96f1b0568fb615a35482182133c13148cf4cc32d222a6dfe676f51e2507';AGG_SHA='5a8058068965de251d0716e9da37f7278d93272cda12514f92f7356196069563'
MODELS={'c651_mc','c651_meanfield','persistence','logistic','dilation_best',*(f'dilation_{n}h' for n in [1,2,4,8]),*(v+'_seed0' for v in ['base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base'])};P=['p_'+n for n in sorted(MODELS)];checks=[]
class AlignmentError(ValueError):pass
def need(value,reason):
 if not value:raise AlignmentError(reason)
def digest(b):return hashlib.sha256(b).hexdigest()
def array_sha(a):return digest(str((a.shape,str(a.dtype))).encode()+a.tobytes())
def blob(path,commit=COMMIT):return subprocess.check_output(['git','--no-replace-objects','-C',str(REPO),'show',commit+':'+path])
def note(name,value,detail=None):checks.append(dict(name=name,passed=bool(value),detail=detail));need(value,name)
def case_id(case):return digest(json.dumps(case,sort_keys=True).encode())[:24]
def exact(a,b):return a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
def arrays(data):
 with np.load(io.BytesIO(data),allow_pickle=False) as z:return {k:z[k] for k in z.files}
def case_schema(record,data):
 need(set(data)=={'row','col','y',*P},'CASE_16_MODEL_COLUMN_SCHEMA');rr,cc,y=data['row'],data['col'],data['y'];n=len(y)
 need(y.ndim==rr.ndim==cc.ndim==1 and y.shape==rr.shape==cc.shape and n>0,'CASE_VECTOR_SHAPES')
 need(rr.dtype.kind in 'iu' and cc.dtype.kind in 'iu' and np.isin(y,[0,1]).all(),'COORDINATE_OR_LABEL_DTYPE')
 shape=record['rectangle'];need(len(shape)==2 and all(type(v) is int and v>0 for v in shape),'RECTANGLE_SCHEMA')
 need((rr>=0).all() and (rr<shape[0]).all() and (cc>=0).all() and (cc<shape[1]).all(),'COORDINATE_BOUNDS')
 order=np.lexsort((cc,rr));need(np.array_equal(order,np.arange(n)) and len(set(zip(rr.tolist(),cc.tolist())))==n,'COORDINATE_ORDER_OR_DUPLICATES')
 mask=np.zeros(shape,bool);mask[rr,cc]=True;need(array_sha(mask)==record['scored_mask_sha256'],'SCORED_MASK_IDENTITY')
 need(record['scored_cells']==n and record['positives']==int(y.sum()) and record['scored_cells']+record['excluded_cells']==record['reference_cells'],'COUNT_OR_REFERENCE_PARTITION')
 for name in P:
  value=data[name];need(value.shape==y.shape and value.dtype.kind in 'bfiu' and np.isfinite(value).all() and ((value>=0)&(value<=1)).all(),'PROBABILITY_COLUMN_SCHEMA:'+name)
 return n

def aggregate_alignment(aggregate,parts,records):
 need(set(aggregate)=={'row','col','y','interval','t1','hours',*P},'AGGREGATE_16_MODEL_COLUMN_SCHEMA')
 need(aggregate['t1'].tolist()==[r['case']['cutoff'] for r in records] and np.array_equal(aggregate['hours'],[r['case']['hours'] for r in records]),'AGGREGATE_T1_HOURS_ALIGNMENT')
 need(aggregate['t1'].dtype.kind in 'US' and aggregate['hours'].dtype.kind in 'fi','AGGREGATE_TIMESTAMP_HOURS_DTYPES')
 for name in ['row','col','y',*P]:
  expected=np.concatenate([part[name] for part in parts]);need(exact(aggregate[name],expected),'AGGREGATE_EXACT_CONCATENATION:'+name)
 interval=np.concatenate([np.full(r['scored_cells'],i) for i,r in enumerate(records)])
 need(aggregate['interval'].dtype.kind in 'iu' and np.array_equal(aggregate['interval'],interval),'AGGREGATE_INTERVAL_ALIGNMENT')
 return {name:str(aggregate[name].dtype) for name in aggregate}

def run():
 manifest_bytes=blob(MANIFEST);manifest=json.loads(manifest_bytes);note('preservation_manifest_byte_pin',digest(manifest_bytes)==MANIFEST_SHA)
 inventory_bytes=blob('research/forecast-v2/PREASSESSMENT_US2024_TIMESTAMPS.json',FREEZE);note('frozen_timestamp_inventory_byte_pin',digest(inventory_bytes)=='51d910392b5f47f20b57ba56a4b2d25bc9096d33ac1dd09361f32a925884028d')
 expected=[c for c in json.loads(inventory_bytes)['cases'] if c['event']==EVENT];ids=[case_id(c) for c in expected];saved={r['case_id']:r for r in manifest['completed_cases']}
 note('exact52_frozen_expected_case_ids',len(expected)==len(ids)==len(set(ids))==len(saved)==len(manifest['completed_cases'])==manifest['case_count']==52 and set(ids)==set(saved))
 frozen_bytes=blob(BASE+'/FROZEN_ASSESSMENT.json');frozen=json.loads(frozen_bytes);frozen_sha=digest(frozen_bytes)
 note('frozen_assessment_preservation_pointer',frozen_sha==manifest['frozen_assessment_sha256']=='67c400f31e93dec28175f0afd71a987f5e0fbf7437f81db85962bd4854fabcff')
 note('frozen_selection_registry_and_settings_links',frozen['selection_sha256']=='f5e763e7acd7a400d9fcdffec8092651c0cea1df4bcff8df4d05d24a865af73b' and frozen['registry']['sha256']=='bfe48d53c5e1fea2ce10dbf7f916a5042f8ab97f94bceedcf82ad2f884e1822e' and frozen['cohort']=='us2024' and frozen['trajectories']==1024 and frozen['trajectory_batch_size']==32 and frozen['seed']==0 and frozen['boundary']=='zero')
 note('preservation_is_explicitly_partial_nonpromotion',manifest['promotion_criteria_pass'] is False and manifest['expected_US_cases']==273 and manifest['expected_KR_windows']==33)
 records=[];parts=[];artifact_hashes={MANIFEST:digest(manifest_bytes),BASE+'/FROZEN_ASSESSMENT.json':frozen_sha};source_hash_fields=['initial_sha256','endpoint_sha256','environmental_snapshot_sha256','reference_mask_sha256','initial_age_sha256','residence_sha256']
 for cid,case in zip(ids,expected):
  receipt_path=f'{BASE}/cases/{cid}.json';pred_path=f'{BASE}/cases/{cid}.npz';receipt_bytes=blob(receipt_path);r=json.loads(receipt_bytes)
  need(digest(receipt_bytes)==saved[cid]['receipt_sha256'],'CASE_PRESERVED_RECEIPT_HASH')
  need(r['case']==case and r['case_id']==case_id(r['case'])==cid and r['receipt_version']=='wfg.forecast-assessment-case/2' and r['assessment_sha256']==frozen_sha,'CASE_IDENTITY_AND_SOURCE_LINK')
  need(r['status']=='SCORED','PRESERVED_CASE_PREDICTION_STATUS');need(all(isinstance(r.get(k),str) and len(r[k])==64 and all(c in '0123456789abcdef' for c in r[k]) for k in source_hash_fields),'CASE_SOURCE_HASH_FIELDS')
  cutoff=datetime.fromisoformat(case['cutoff']);need(r['weather_hour']==cutoff.replace(minute=0,second=0,microsecond=0).isoformat(),'CUTOFF_WEATHER_CLOCK_LINK')
  pred_bytes=blob(pred_path);need(digest(pred_bytes)==r['sha256']==saved[cid]['predictions_sha256'],'CASE_PREDICTION_HASH');data=arrays(pred_bytes);case_schema(r,data)
  records.append(r);parts.append(data);artifact_hashes[receipt_path]=digest(receipt_bytes);artifact_hashes[pred_path]=digest(pred_bytes)
 note('all52_case_receipt_and_prediction_hashes',True)
 note('all52_case_schema16_columns_coordinates_masks_counts_partitions',True)
 note('all52_case_source_links_and_cutoff_clock',True)
 aggregation=manifest['per_fire_aggregate'];aggregate_bytes=blob(aggregation['path']);note('closed_perfire_aggregate_hash_and_size',digest(aggregate_bytes)==aggregation['sha256']==AGG_SHA and len(aggregate_bytes)==aggregation['bytes']==17331815)
 aggregate=arrays(aggregate_bytes);dtypes=aggregate_alignment(aggregate,parts,records);artifact_hashes[aggregation['path']]=digest(aggregate_bytes)
 note('full52_case_to_perfire_exact_dtype_and_payload_concatenation',True)
 note('full52_interval_t1_hours_alignment',True)
 return dict(status='PASS_BOUNDED_IMMUTABLE_WAPITI_ARTIFACT_ALIGNMENT',scope='Only completed immutable Wapiti case/aggregate schema and byte/value alignment. No Brier, AP, AUC, NLL, ECE, rankings, calibration, probability means/histograms, figures, model load or forecast. No other cohort output opened. No source prediction/raster truth replay or scientific validation.',commit=COMMIT,frozen_inventory_commit=FREEZE,event=EVENT,cases_checked=52,model_columns=16,checks=checks,artifact_hashes=artifact_hashes,aggregate_dtypes=dtypes,full_cohort_metric_checker_run=False,full_cohort_census_run=False,promotion_criteria_pass=False,source_link_limit='Initial/endpoint/environment/residence/source-mask hashes are checked for receipt consistency and binding to the frozen assessment; raw scientific source arrays are not independently rehashed or replayed.',host=dict(python=platform.python_version(),numpy=np.__version__,platform=platform.platform()),checker_sha256=digest(Path(__file__).read_bytes()))
if __name__=='__main__':
 print('WAITING_HEAVY_AT_CASE_BOUNDARY_FOR_UNTIMED_ALIGNMENT',flush=True);start=time.monotonic()
 with Path('/tmp/wfg/HEAVY.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);acquired=datetime.now(timezone.utc).isoformat();print('ACQUIRED_HEAVY_ALIGNMENT',flush=True)
  try:result=run()
  except Exception as e:
   (OUT/'FAILURE.json').write_text(json.dumps(dict(error_type=type(e).__name__,error=str(e),checks=checks,scope='Artifact alignment only; no quality metric computed.'),indent=2)+'\n');raise
  finally:released=datetime.now(timezone.utc).isoformat()
 result['resource_control']=dict(lock='/tmp/wfg/HEAVY.lock',acquired_utc=acquired,released_utc=released,scope='Single advisory lease acquired between numerical cases; no process interrupted. Untimed functional audit, no latency claim.')
 (OUT/'ALIGNMENT_RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(status=result['status'],cases=result['cases_checked'],checks=len(checks),quality_metrics_computed=False)))
