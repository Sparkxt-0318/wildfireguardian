"""Replay only original Wapiti mapped labels and cutoff occupancy, not predictions."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import fcntl,hashlib,io,json,math,platform,re,subprocess
import numpy as np
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');REPO=TASK/'work/audit-1b';OUT=Path(__file__).resolve().parent
COMMIT='e48054fa420af0b0477070f496c88ebc16ed2b8a';FREEZE='6887dc618253e6568c6cbbfd3c9a96f1d0d86b70';EVENT='ID-BOF-000683_Wapiti_Wapiti';BASE='forecast/runs/20261030_perimeter_trained/execution_v3/heldout';DATA=TASK/'work/data/forecast-v2';checks=[]
class SourceLabelError(ValueError):pass
class UnresolvedMapping(SourceLabelError):pass
def need(x,why):
 if not x:raise SourceLabelError(why)
def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()
def array_sha(a):return sha_bytes(str((a.shape,str(a.dtype))).encode()+a.tobytes())
def blob(rel,commit=COMMIT):return subprocess.check_output(['git','--no-replace-objects','-C',str(REPO),'show',commit+':'+rel])
def note(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail));need(ok,name)
def timestamp(v):
 s=v.decode() if isinstance(v,bytes) else str(v);fraction=re.search(r'\.(\d+)',s)
 if fraction and len(fraction[1])>6 and any(c!='0' for c in fraction[1][6:]):raise UnresolvedMapping('SUBMICROSECOND_TIMESTAMP_MAPPING_NOT_IMPLEMENTED')
 try:d=datetime.fromisoformat(s.replace('Z','+00:00'))
 except ValueError as e:raise UnresolvedMapping('SOURCE_TIMESTAMP_FORMAT_UNSUPPORTED') from e
 # P uses pandas.to_datetime(..., utc=True); this is its declared naive-UTC policy.
 if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
 return d.astimezone(timezone.utc)
def source_join(record,rr,cc,y,times,states):
 lookup={t:i for i,t in enumerate(times)};need(len(lookup)==len(times),'AMBIGUOUS_DUPLICATE_SOURCE_TIMESTAMPS')
 case=record['case'];start,end=timestamp(case['cutoff']),timestamp(case['endpoint']);need(start in lookup and end in lookup,'EXACT_CASE_TIMESTAMPS_ABSENT_FROM_SOURCE');i,j=lookup[start],lookup[end]
 need(j==i+1 and timedelta(0)<end-start<=timedelta(hours=48),'CASE_NOT_EXACT_ELIGIBLE_CONSECUTIVE_SOURCE_INTERVAL')
 need(math.isclose(case['hours'],(end-start).total_seconds()/3600,rel_tol=0,abs_tol=1e-12),'SOURCE_DURATION_ALIGNMENT')
 initial,endpoint=states[i],states[j];need(list(initial.shape)==record['rectangle'],'FULL_ORIGINAL_GRID_RECTANGLE_ALIGNMENT')
 need(array_sha(initial)==record['initial_sha256'] and array_sha(endpoint)==record['endpoint_sha256'],'FULL_SOURCE_INITIAL_ENDPOINT_HASH_ALIGNMENT')
 reference=~initial;need(array_sha(reference)==record['reference_mask_sha256'] and int(reference.sum())==record['reference_cells'],'FULL_SOURCE_REFERENCE_MASK_ALIGNMENT')
 need(rr.dtype.kind in 'iu' and cc.dtype.kind in 'iu' and rr.ndim==cc.ndim==y.ndim==1 and rr.shape==cc.shape==y.shape,'SCORED_COORDINATE_VECTOR_SCHEMA')
 need((rr>=0).all() and (rr<initial.shape[0]).all() and (cc>=0).all() and (cc<initial.shape[1]).all(),'FULL_GRID_COORDINATE_BOUNDS')
 need(not initial[rr,cc].any(),'SAVED_SCORED_COORDINATE_ALREADY_INITIAL_BURN')
 need(np.array_equal(y,endpoint[rr,cc]),'SAVED_LABEL_DIFFERS_FROM_ORIGINAL_ENDPOINT')
 return i,j

def run():
 fbytes=blob(BASE+'/FROZEN_ASSESSMENT.json');frozen=json.loads(fbytes);note('known_frozen_assessment',sha_bytes(fbytes)=='67c400f31e93dec28175f0afd71a987f5e0fbf7437f81db85962bd4854fabcff')
 for rel,pin in [('research/forecast-v2/scripts/score_cohorts.py','88bb3839c6923737b8c815aceec9d2fd4e91aba777447b4c86bfada51164b4c2'),('research/forecast-v2/scripts/pipeline.py','88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67'),('forecast/wildfire/survival.py','c70db8adea511efb4c17dc5b39941e07b25502b620481ce82ceeb6d07e70bc5b')]:note('pinned_mapping_source:'+rel,sha_bytes(blob(rel))==frozen['source_sha256'][rel]==pin)
 manifest_path=DATA/'perimeters/PERIMETER_MANIFEST.json';manifest_bytes=manifest_path.read_bytes();note('original_manifest_bytes_before_array_open',sha_bytes(manifest_bytes)==frozen['perimeter_manifest_sha256']=='ec85525ebe90091036e77bd517abc563c385e81db0ae53ecc30c6d4cb3c019c6');manifest=json.loads(manifest_bytes)
 inventory_bytes=blob('research/forecast-v2/PREASSESSMENT_US2024_TIMESTAMPS.json',FREEZE);note('frozen_timestamp_inventory_bytes',sha_bytes(inventory_bytes)=='51d910392b5f47f20b57ba56a4b2d25bc9096d33ac1dd09361f32a925884028d');inventory=json.loads(inventory_bytes);wanted=[r for r in inventory['cases'] if r['event']==EVENT]
 source_path=DATA/'perimeters'/EVENT/'states.npz';source_sha=sha_file(source_path);note('original_Wapiti_file_bytes_before_array_open',source_sha==manifest['events'][EVENT]['states_sha256']==inventory['per_fire'][EVENT]['states_sha256']=='74a135ab4ceec9408314d037b045c16e4cc8b4f635c44c3655cbbc06fc6668dc')
 with np.load(source_path,allow_pickle=False) as source:
  raw_times=source['times'];raw_states=source['states'];need(raw_states.ndim==3 and len(raw_times)==len(raw_states) and np.isin(raw_states,[0,1]).all(),'DECLARED_ORIGINAL_STATES_TIME_GRID_SCHEMA');states=raw_states.astype(bool);times=[timestamp(x) for x in raw_times]
 note('source_timestamp_indices_unambiguous',len(times)==len(set(times)) and all(a<b for a,b in zip(times,times[1:])))
 preserved_bytes=blob('research/forecast-v2/executions/current_us2024_Wapiti_complete.json');note('immutable_completed_case_manifest',sha_bytes(preserved_bytes)=='e944d96f1b0568fb615a35482182133c13148cf4cc32d222a6dfe676f51e2507');preserved=json.loads(preserved_bytes);saved={r['case_id']:r for r in preserved['completed_cases']}
 rows=[]
 for case in wanted:
  cid=sha_bytes(json.dumps(case,sort_keys=True).encode())[:24];need(cid in saved,'EXPECTED_COMPLETED_CASE_NOT_PRESERVED');rbytes=blob(f'{BASE}/cases/{cid}.json');need(sha_bytes(rbytes)==saved[cid]['receipt_sha256'],'IMMUTABLE_CASE_RECEIPT_HASH');r=json.loads(rbytes);need(r['case']==case and r['case_id']==cid and r['assessment_sha256']==sha_bytes(fbytes),'CASE_FROZEN_IDENTITY_BINDING')
  pbytes=blob(f'{BASE}/cases/{cid}.npz');need(sha_bytes(pbytes)==r['sha256']==saved[cid]['predictions_sha256'],'IMMUTABLE_ENTRIES_HASH')
  # No p_* member is accessed or decompressed; only original labels/coordinates.
  with np.load(io.BytesIO(pbytes),allow_pickle=False) as entries:rr,cc,y=entries['row'],entries['col'],entries['y']
  i,j=source_join(r,rr,cc,y,times,states);rows.append(dict(case_id=cid,cutoff=case['cutoff'],endpoint=case['endpoint'],source_cutoff_index=i,source_endpoint_index=j,full_initial_endpoint_hashes_match=True,reference_mask_hash_matches=True,all_saved_coordinates_initially_unburned=True,all_saved_y_match_original_endpoint=True))
 note('all52_frozen_expected_completed_cases_replayed',len(rows)==len(wanted)==len(saved)==52 and {r['case_id'] for r in rows}==set(saved))
 note('all52_full_source_mask_hashes_and_coordinate_labels_match',True)
 return dict(status='PASS_BOUNDED_WAPITI_ORIGINAL_MAPPED_LABEL_REPLAY',scope='Original mapped-label/cutoff alignment only. No model probability member decoded, no forecast/model/scorer/native execution, quality metric, histogram/mean, ranking, calibration or figure. No other fire/cohort output opened. Not physical truth, survey coverage completeness or model-prediction replay.',snapshot_commit=COMMIT,inventory_commit=FREEZE,event=EVENT,cases_checked=52,original_input=dict(path=str(source_path),sha256=source_sha,manifest_sha256=sha_bytes(manifest_bytes),source_time_count=len(times),source_grid_shape=list(states.shape[1:])),mapping_evidence=dict(score_cohorts='268-269: crop=False;314-316: full-mask np.nonzero row/col and endpoint labels',pipeline='224-249: original states[i]/states[j], score mask ~initial, cropped only if crop=True',survival='153-174: passive PerimeterSample dataclass'),checks=checks,case_replay=rows,limit='Only saved scored coordinates and full recorded initial/endpoint/reference arrays are replayed; environmental, residence/age arrays and model common-validity masks are not recomputed. Raw polygon-to-grid construction and coverage truth remain outside this review.',full_metric_checker_run=False,full306_census_run=False,promotion_criteria_pass=False,host=dict(python=platform.python_version(),numpy=np.__version__,platform=platform.platform()),checker_sha256=sha_file(Path(__file__)))
if __name__=='__main__':
 print('WAITING_HEAVY_FOR_ORIGINAL_LABEL_JOIN_AT_CASE_BOUNDARY',flush=True)
 with Path('/tmp/wfg/HEAVY.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);acquired=datetime.now(timezone.utc).isoformat();print('ACQUIRED_HEAVY_SOURCE_LABEL_JOIN',flush=True)
  try:result=run()
  except Exception as e:
   (OUT/'FAILURE.json').write_text(json.dumps(dict(status='UNRESOLVED_MAPPING' if isinstance(e,UnresolvedMapping) else 'SOURCE_LABEL_REPLAY_REFUSED',error_type=type(e).__name__,error=str(e),checks=checks),indent=2)+'\n');raise
  finally:released=datetime.now(timezone.utc).isoformat()
 result['resource_control']=dict(acquired_utc=acquired,released_utc=released,lock='/tmp/wfg/HEAVY.lock',scope='One advisory lease between numerical cases; no process changed or interrupted. Untimed consistency check, no performance claim.');(OUT/'SOURCE_LABEL_RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(status=result['status'],cases=result['cases_checked'],checks=len(checks),probability_members_decoded=False,quality_metrics_computed=False)))
