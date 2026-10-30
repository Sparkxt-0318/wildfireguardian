"""Bounded synthetic full-fit coverage recheck; no actual fit/model/study data.

Reuses pinned synthetic fixture constructors, then independently mutates exact
membership, counts, source bindings and evidence classes. No numerical fit or
shared heavy lease is executed. Historical source inference is not runtime IDs.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import platform
import subprocess
import sys
import tempfile
import pytest
sys.dont_write_bytecode=True


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def run(repo):
 sys.path.insert(0,str(repo/'forecast'))
 t=load('independent_fit_coverage_fixture',repo/'forecast/tests/test_blind_forecast_protocol.py')
 observations=[]
 def probe(name,fn,refuse=False,reason=None):
  try:
   value=fn();passed=not refuse and value is not False;observed=dict(state='RETURNED',value=value)
  except (ValueError,KeyError,TypeError,FileNotFoundError) as e:
   passed=refuse and (reason is None or reason in str(e));observed=dict(state='RAISED',type=type(e).__name__,reason=str(e))
  observations.append(dict(id=name,pass_check=bool(passed),observed=observed))
 with tempfile.TemporaryDirectory(prefix='wfg-fit-membership-review-') as td,pytest.MonkeyPatch.context() as mp:
  folder=Path(td).resolve();f=t.freezer.__wrapped__();fixture=t.freeze_inputs.__wrapped__(f,folder,mp)
  root,runroot,selection_path,comparator,selection=fixture
  m,_,_,inputs,caches,coverage_path,recorded=t.fit_coverage_state(f,fixture)
  cacheaudit=root/selection['cache_audit']['path']
  def audit():return m.audit_coverage(root,inputs,caches,runroot,cacheaudit)
  def build():return f.build_registry(root,runroot,selection_path,comparator)
  pristine={p:p.read_bytes() for p in folder.rglob('*') if p.is_file()}
  def restore():
   for p,raw in pristine.items():p.write_bytes(raw)
  def negative(name,change,fn=audit,reason=None):
   restore();change();probe(name,fn,True,reason);restore()
  def result_change(variant,fn):t.resign_result_receipt(f,root,runroot,variant,fn)
  good=audit();registry=build()
  probe('full_membership_registry_positive_control',lambda:good['status']=='PASS_COMPLETE_FIT_MEMBERSHIP' and len(good['expected']['perimeter_cases'])==4 and len(good['expected']['mixed_cases'])==12 and registry['execution_status']=='NOT_READY_FOR_2026_EXECUTION')
  probe('historical_inference_and_runtime_ID_classes_distinct',lambda:good['variants']['base']['runtime_membership'] is None and good['variants']['base']['schedule_evidence']=='SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED' and good['variants']['mixed_base']['schedule_evidence']=='RUNTIME_ATTEMPTED_IDS_BOUND_TO_IMMUTABLE_SOURCE_AND_PREFIT_INPUT_MANIFEST')
  probe('zero_window_kr_and_effective_last_argv_positive_controls',lambda:good['expected']['ledger']['kriged']['synthetic_kr_zero']['sample_count']==0 and good['variants']['base']['effective_arguments']['max_fit_intervals_per_fire']=='0')
  # The old phase is preserved exactly; a later comment is not attributed to its runtime.
  source=root/'forecast/wildfire/survival.py';raw=source.read_bytes();digest=sha(source);snapshot=root/'research/forecast-v2/source_snapshots'/digest/source.name;snapshot.parent.mkdir(parents=True);snapshot.write_bytes(raw);source.write_bytes(raw+b'\n# Later source metadata only.\n')
  historical=audit();probe('preserved_historical_phase_source_positive_control',lambda:historical['variants']['base']['source_schedule_contract']['survival_sha256']==digest and historical['source_sha256']['forecast/wildfire/survival.py']!=digest and historical['variants']['base']['runtime_membership'] is None);restore()

  negative('declared_event_omission_refused',lambda:result_change('base',lambda r:r.update(train_events=r['train_events'][:1])),build,'Completed fixed-policy full fit')
  def few_samples_all_events():
   for variant in f.VARIANTS:
    def change(r):
     r['train_samples']=1
     for h in r['fit']['history']:h['optimizer_steps']=1
    result_change(variant,change)
  negative('all_events_few_intervals_refused',few_samples_all_events,reason='Full recorded sample/epoch/optimizer')
  for tag,change in [('short_epoch',lambda r:r['fit']['history'][0].update(optimizer_steps=1)),('skip_record',lambda r:r['fit']['history'][0].update(skipped_unsupported_intervals=[{'event':'synthetic_fit'}]))]:
   negative(tag+'_refused',lambda ch=change:result_change('base',ch),reason='Full recorded sample/epoch/optimizer')

  def cache_mutation(mode):
   path=caches/'samples/perimeter_crop_first0_synthetic_fit.pkl';samples=pickle.loads(path.read_bytes())
   if mode=='missing_cache':path.unlink();return
   if mode=='omit':samples.pop()
   if mode=='duplicate':samples[1]=samples[0]
   if mode=='wrong_id':samples[0].t1='2020-01-01T01:00:00Z';samples[0].hours=11.
   path.write_bytes(pickle.dumps(samples,protocol=5));a=json.loads(cacheaudit.read_text());row=next(r for r in a['records'] if Path(r['cache'])==path);row.update(cache_sha256=sha(path),samples=len(samples),cached_value_identity=m.sample_list_identity(samples),recomputed_value_identity=m.sample_list_identity(samples));cacheaudit.write_text(json.dumps(a))
  for mode in ['omit','duplicate','wrong_id','missing_cache']:negative('cached_'+mode+'_refused_even_after_resigning',lambda mode=mode:cache_mutation(mode))
  def effective_cap():
   p=root/'research/forecast-v2/executions/a03_final_base.json';r=json.loads(p.read_text());r['command']+=['--intervals-per-epoch','1'];p.write_text(json.dumps(r))
  negative('last_argv_cap_overrides_prior_zero_and_refuses',effective_cap,reason='effective LAST')
  def wrong_source():
   p=root/'research/forecast-v2/executions/a03_final_base.json';r=json.loads(p.read_text());r['source_sha256']['forecast/wildfire/survival.py']='0'*64;p.write_text(json.dumps(r))
  negative('unavailable_historical_source_refused',wrong_source,reason='Exact immutable fit producer source')
  def wrong_actual_source():
   p=root/'forecast/wildfire/survival.py';p.write_text(p.read_text().replace('sample = train[index]','sample = train[0]'));rpath=root/'research/forecast-v2/executions/a03_final_base.json';r=json.loads(rpath.read_text());r['source_sha256']['forecast/wildfire/survival.py']=sha(p);rpath.write_text(json.dumps(r))
  negative('historical_source_train0_not_index_refused',wrong_actual_source,reason='actual indexed member')

  def runtime_mutation(mode):
   def change(r):
    if mode=='missing_ledger':r['fit'].pop('runtime_membership');return
    epoch=r['fit']['runtime_membership']['epochs'][0]
    if mode=='missing_id':epoch['attempted_case_ids'].pop()
    if mode=='duplicate_id':epoch['attempted_case_ids'][0]=epoch['attempted_case_ids'][1]
    if mode=='wrong_id':epoch['attempted_case_ids'][0]='f'*64
    if mode=='skip_id':epoch['skipped_case_ids']=epoch['attempted_case_ids'][:1]
    epoch['attempted_case_ids_sha256']=m.object_sha(epoch['attempted_case_ids'])
   result_change('mixed_base',change)
  for mode in ['missing_ledger','missing_id','duplicate_id','wrong_id','skip_id']:negative('mixed_runtime_'+mode+'_refused',lambda mode=mode:runtime_mutation(mode))
  negative('mixed_zero_window_key_cannot_disappear',lambda:result_change('mixed_base',lambda r:r['intended_kriged_fit_events'].remove('synthetic_kr_zero')))
  def missing_manifest_sample():
   def change(r):
    p=root/r['fit_input_manifest']['path'];v=json.loads(p.read_text());v['sample_cases'].pop();p.write_text(json.dumps(v));r['fit_input_manifest']['sha256']=sha(p);r['fit']['runtime_membership']['sample_manifest_sha256']=sha(p)
   result_change('mixed_base',change)
  negative('mixed_prefit_manifest_case_omission_refused',missing_manifest_sample,reason='Runtime prefit input manifest')
  def relabel_historical():
   r=json.loads(coverage_path.read_text());r['variants']['base']['schedule_evidence']='RUNTIME_ATTEMPTED_IDS_BOUND_TO_IMMUTABLE_SOURCE_AND_PREFIT_INPUT_MANIFEST';coverage_path.write_text(json.dumps(r));s=json.loads(selection_path.read_text());s['fit_coverage']['sha256']=sha(coverage_path);selection_path.write_text(json.dumps(s))
  negative('historical_inference_cannot_be_resigned_as_runtime_logging',relabel_historical,build,reason='Fit coverage no longer matches')
  def wrong_input_binding():
   s=json.loads(selection_path.read_text());s['input_manifests_sha256']['EXTRACTION_MANIFEST.json']='0'*64;selection_path.write_text(json.dumps(s))
  negative('coverage_and_selection_input_pins_must_match',wrong_input_binding,build,reason='same input manifests')
  # The original wire code is unchanged at9b; retain a control that no future execution follows local freeze.
  restore();last=build();probe('local_registry_freeze_does_not_authorize_future_execution',lambda:last['execution_status']=='NOT_READY_FOR_2026_EXECUTION' and last['documentary_clearance_contract']['machine_authentication'] is False)
 paths=['research/forecast-v2/scripts/freeze_registry.py','research/forecast-v2/scripts/audit_fit_coverage.py','research/forecast-v2/scripts/blind_test.py','forecast/tests/test_blind_forecast_protocol.py','forecast/wildfire/survival.py','research/forecast-v2/scripts/pipeline.py']
 return dict(source_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),scope=__doc__,host=platform.platform(),python=sys.version,script_sha256=sha(__file__),source_sha256={p:sha(repo/p) for p in paths},observations=observations,checks=len(observations),passed=sum(r['pass_check'] for r in observations),actual_study_inputs_or_models_accessed=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--track-b',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=run(a.track_b.resolve());result['status']='PASS_SCOPED_COMPLETE_MEMBERSHIP_REPAIR' if result['checks']==result['passed'] else 'FAIL_SCOPED_COMPLETE_MEMBERSHIP_REPAIR';a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([r for r in result['observations'] if not r['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
