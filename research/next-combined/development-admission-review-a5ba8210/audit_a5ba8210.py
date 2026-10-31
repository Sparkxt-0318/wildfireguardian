"""Independent synthetic development admission audit; no actual study data/model access."""
import copy, hashlib, importlib.util, json, pickle, platform, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[1]/'audit-1b'
sys.path.insert(0,str(REPO/'forecast'))
sys.path.insert(0,str(REPO/'research/forecast-v2/scripts'))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
t=load('independent_a5_fixture',REPO/'forecast/tests/test_blind_forecast_protocol.py')
observations=[]
def probe(name,fn,refuse=False):
 try:
  v=fn(); ok=not refuse and v is not False; result=dict(state='RETURNED',value=v)
 except (ValueError,KeyError,TypeError,FileNotFoundError,RuntimeError) as e:
  ok=refuse; result=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 observations.append(dict(id=name,pass_check=bool(ok),observed=result))
with tempfile.TemporaryDirectory(prefix='wfg-independent-a5-development-') as temp,pytest.MonkeyPatch.context() as mp:
 folder=Path(temp).resolve(); f=t.freezer.__wrapped__(); fixture=t.freeze_inputs.__wrapped__(f,folder,mp)
 root,run,sp,comparator,selection=fixture
 m,_,_,inputs,caches,_,record=t.fit_coverage_state(f,fixture)
 audit_path=root/'research/forecast-v2/CACHE_AUDIT.json'
 def audit():return m.audit_coverage(root,inputs,caches,run,audit_path)
 def build():return f.build_registry(root,run,sp,comparator)
 registry=build()
 probe('complete21_phase_registry_positive',lambda:len(record['development'])==21 and registry['development_coverage_sha256']==m.object_sha(record['development']))
 probe('all_prefixes_and_kind_order_positive',lambda:all(p['training']['sample_count']==(15 if p['intended_phase']['variant']=='mixed_base' else 6) and p['validation']['sample_count']==3 and all(c['kind']=='perimeter' for c in p['validation']['cases']) and (p['intended_phase']['variant']!='mixed_base' or [c['kind'] for c in p['training']['cases']]==['perimeter']*6+['kriged']*9) for p in record['development'].values()))
 probe('historical_cap160_is_source_default_and_nonbinding',lambda:all(p['budget']['effective_arguments']['intervals_per_epoch']=='160' and p['budget']['argument_origins']['intervals_per_epoch']=='IMMUTABLE_ARGPARSE_DEFAULT' and p['budget']['interval_cap_status']=='NONBINDING_CAP' for p in record['development'].values()))
 probe('source_inference_not_runtime_observations',lambda:all(p['runtime_membership'] is None and 'NO_RUNTIME_IDS_RECORDED' in p['schedule_evidence'] for p in record['development'].values()))
 pristine={p:p.read_bytes() for p in folder.rglob('*') if p.is_file()}
 def restore():
  for p in list(folder.rglob('*')):
   if p.is_file() and p not in pristine:p.unlink()
  for p,raw in pristine.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 phase=m.intended_phase('burnout_spotting','fold','2020');rp=run/phase['result'];ep=root/f"research/forecast-v2/executions/a05_{phase['job_suffix']}.json"
 def change(result_fn=None,receipt_fn=None):
  value=json.loads(rp.read_text()); receipt=json.loads(ep.read_text())
  if result_fn:result_fn(value)
  rp.write_text(json.dumps(value));receipt['output_sha256']=sha(rp)
  if receipt_fn:receipt_fn(receipt)
  ep.write_text(json.dumps(receipt))
 def negative(name,mutate,fn=build):
  restore();probe(name,lambda:(mutate(),fn())[1],True);restore()
 # Original independently discovered compound under-budget mechanism.
 negative('original_resigned_underbudget_and_small_samples_refused',lambda:change(lambda r:r.update(train_samples=1,validation_samples=2),lambda r:r['command'].extend(['--epochs','1','--max-fit-intervals-per-fire','1','--intervals-per-epoch','1'])))
 for name,option,value in [('epochs','--epochs','2'),('first_prefix','--max-fit-intervals-per-fire','2'),('binding_cap','--intervals-per-epoch','1'),('batch','--samples-per-step','2'),('hidden','--hidden','8'),('learning_rate','--lr','.004')]:
  negative('last_'+name+'_refused',lambda option=option,value=value:change(receipt_fn=lambda r:r['command'].extend([option,value])),lambda:m.phase_result(root,run,'burnout_spotting','fold','2020'))
 negative('equals_syntax_last_duplicate_refused',lambda:change(receipt_fn=lambda r:r['command'].extend(['--epochs','3','--epochs=1'])),lambda:m.phase_result(root,run,'burnout_spotting','fold','2020'))
 negative('missing_balancing_flag_refused',lambda:change(receipt_fn=lambda r:r['command'].remove('--balance')),lambda:m.phase_result(root,run,'burnout_spotting','fold','2020'))
 negative('missing_epoch_refused',lambda:change(lambda r:r['fit']['history'].pop()),lambda:m.phase_result(root,run,'burnout_spotting','fold','2020'))
 negative('missing_training_event_refused',lambda:change(lambda r:r['train_events'].pop()),lambda:m.phase_result(root,run,'burnout_spotting','fold','2020'))
 def consistent_small():
  def tiny(r):
   r.update(train_samples=1,validation_samples=2)
   for h in r['fit']['history']:h['optimizer_steps']=1
  change(tiny)
 negative('resigned_consistent_counts_cannot_replace_exact_membership',consistent_small,audit)
 # Re-sign the cache audit as well; the independent full source prefix still wins.
 def first_cache(mode):
  p=next(caches.glob('samples/perimeter_crop_first3_*.pkl'));samples=pickle.loads(p.read_bytes())
  if mode=='omit':samples.pop()
  else:samples.reverse()
  p.write_bytes(pickle.dumps(samples,protocol=5));a=json.loads(audit_path.read_text());r=next(r for r in a['records'] if Path(r['cache'])==p)
  r.update(cache_sha256=sha(p),samples=len(samples),cached_value_identity=m.sample_list_identity(samples),recomputed_value_identity=m.sample_list_identity(samples));audit_path.write_text(json.dumps(a))
 negative('resigned_first3_cache_omission_refused',lambda:first_cache('omit'),audit)
 negative('resigned_first3_cache_reordering_refused',lambda:first_cache('reverse'),audit)
 def selection_digest():
  s=json.loads(sp.read_text());s['development_coverage_sha256']='0'*64;sp.write_text(json.dumps(s))
 negative('selection_requires_development_digest',selection_digest)
 def clock_disagreement():
  event=record['expected']['intended_us_fit_events'][0];p=inputs/f'perimeters/{event}/states.npz'
  with np.load(p,allow_pickle=False) as d:arrays={k:d[k] for k in d.files}
  stamps=[pd.Timestamp(v) for v in arrays['times']]
  stamps=[stamps[0],stamps[0]+pd.Timedelta(hours=48)+pd.Timedelta(nanoseconds=1)]
  arrays['times']=np.array([v.isoformat() for v in stamps]); arrays['states']=arrays['states'][:2]
  np.savez_compressed(p,**arrays);manifest=inputs/'perimeters/PERIMETER_MANIFEST.json';value=json.loads(manifest.read_text());value['events'][event]['states_sha256']=sha(p);manifest.write_text(json.dumps(value))
 negative('48hours_plus1ns_refuses_whole_artifact',clock_disagreement,lambda:m.expected_membership(root,inputs))
 # New cap zero is admitted literally, historical cap remains 160.
 change(receipt_fn=lambda r:r['command'].extend(['--intervals-per-epoch','0']))
 value=audit();probe('new_zero_cap_and_other_historical160_preserved',lambda:value['development'][phase['phase_id']]['budget']['interval_cap_status']=='UNRESTRICTED_CAP_ZERO' and value['development']['base_fold2020_seed0']['budget']['effective_arguments']['intervals_per_epoch']=='160');restore()
 probe('new12_a06_paths_distinct_from_original_a04',lambda:len({m.comparison_case_relative(i,m.comparison_suffix(6)) for i in range(12)})==12 and all(m.comparison_case_relative(i,'_a06')!=m.comparison_case_relative(i,m.comparison_suffix(4)) for i in range(12)))
 registry_path=root/'research/forecast-v2/BLIND_REGISTRY.json';registry_path.write_text(json.dumps(registry))
 relocated=folder/'relocated-root';shutil.copytree(root,relocated);shutil.rmtree(inputs);shutil.rmtree(caches)
 admitted=m.saved_registry_admission(relocated,relocated/run.relative_to(root),relocated/sp.relative_to(root),selection,relocated/registry_path.relative_to(root))
 probe('saved_admission_relocated_without_training_roots',lambda:admitted['development_coverage_sha256']==registry['development_coverage_sha256'] and not inputs.exists() and not caches.exists())
paths=['research/forecast-v2/scripts/audit_fit_coverage.py','research/forecast-v2/scripts/pipeline.py','research/forecast-v2/scripts/run_campaign.py','research/forecast-v2/scripts/freeze_registry.py','research/forecast-v2/scripts/score_cohorts.py','forecast/tests/test_development_fit_coverage.py','forecast/tests/test_blind_forecast_protocol.py']
value=dict(schema='wfg.independent-development-admission-audit/1',source_head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),script_sha256=sha(__file__),source_sha256={p:sha(REPO/p) for p in paths},host=platform.platform(),checks=len(observations),passed=sum(x['pass_check'] for x in observations),observations=observations,actual_study_inputs_or_models_accessed=False,training_executed=False,status='PASS' if all(x['pass_check'] for x in observations) else 'HOLD')
out=Path(__file__).with_suffix('.json');out.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');print(json.dumps({k:value[k] for k in ['status','checks','passed']}));print(json.dumps([x for x in observations if not x['pass_check']],indent=2));raise SystemExit(0 if value['status']=='PASS' else 1)
