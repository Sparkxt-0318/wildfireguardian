"""Independent final admission recheck, with valid controls before targeted refusals."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import pickle
import platform
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import numpy as np
import pandas as pd
import torch


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def main(root):
 a=load('independent_repaired_assessment',root/'research/forecast-v2/scripts/score_cohorts.py')
 b=load('independent_repaired_blind',root/'research/forecast-v2/scripts/blind_test.py')
 observations=[]
 def check(name,fn,refuse=False):
  try:
   value=fn();good=not refuse and value is not False;out=dict(state='RETURNED',value=value)
  except (ValueError,TypeError,KeyError,AttributeError,FileNotFoundError) as e:
   good=refuse;out=dict(state='RAISED',type=type(e).__name__,reason=str(e))
  observations.append(dict(id=name,pass_check=good,observed=out))
 with tempfile.TemporaryDirectory(prefix='independent-blind-repair-') as td:
  d=Path(td).resolve()
  # The original cache probe must regard constructor refusal as a successful guard.
  eroot,cache=d/'environment',d/'cache';eroot.mkdir();cache.mkdir()
  (eroot/'events.json').write_text('[{"id":"synthetic"}]')
  np.savez(cache/'synthetic_20260101T00.npz',raw=np.full((1,1,2),123456.,np.float32),names=['invented'])
  check('original_unauthenticated_cache_refused',lambda:a.P.Environment(eroot,cache),refuse=True)
  # Valid source binding and every guard exercised independently, without an early model-set failure.
  s=SimpleNamespace(initial=np.array([[True,False],[False,False]]),endpoint=np.array([[True,True],[False,True]]),score_mask=np.array([[False,True],[True,True]]),environment=np.zeros((2,2,2),np.float32),initial_age_hours=np.zeros((2,2)),residence_hours=np.ones((2,2)),t1='2024-01-01T00:00:00Z')
  mask=s.score_mask.copy();rows,cols=np.nonzero(mask);path=d/'case.npz'
  arrays=dict(row=rows,col=cols,y=s.endpoint[mask].astype(np.int8),**{'p_'+n:np.full(3,.25) for n in a.EXPECTED_MODELS})
  def admitted(mutation=None,receipt_mutation=None):
   values={k:v.copy() for k,v in arrays.items()}
   if mutation: mutation(values)
   np.savez(path,**values)
   r=dict(receipt_version='wfg.forecast-assessment-case/2',**a.source_identity(s),sha256=sha(path),scored_mask_sha256=a.array_sha(mask),scored_cells=3,positives=2)
   if receipt_mutation:receipt_mutation(r)
   a.validate_entries(path,r,s,mask);return True
  check('assessment_valid_16_model_control',lambda:len(a.EXPECTED_MODELS)==16 and admitted())
  for field in a.source_identity(s):
   check('assessment_receipt_'+field,lambda f=field:admitted(receipt_mutation=lambda r:r.update({f:'different'})),refuse=True)
  changes={
   'fractional_row':lambda v:v.update(row=v['row'].astype(float)+.25),
   'integral_float_row':lambda v:v.update(row=v['row'].astype(float)),
   'out_of_range_col':lambda v:v['col'].__setitem__(0,100000),
   'negative_row':lambda v:v['row'].__setitem__(0,-1),
   'reordered_coordinates':lambda v:v.update({k:x[::-1] for k,x in v.items()}),
   'duplicate_coordinate':lambda v:(v['row'].__setitem__(1,v['row'][0]),v['col'].__setitem__(1,v['col'][0])),
   'subset':lambda v:v.update({k:x[:-1] for k,x in v.items()}),
   'wrong_label':lambda v:v['y'].__setitem__(0,0),
   'missing_model':lambda v:v.pop('p_c651_mc'),
   'extra_model':lambda v:v.update(p_unregistered=np.zeros(3)),
   'nonfinite_probability':lambda v:v['p_c651_mc'].__setitem__(0,np.nan),
   'probability_above_one':lambda v:v['p_c651_mc'].__setitem__(0,1.1),
   'probability_shape':lambda v:v.update(p_c651_mc=np.zeros((3,1)))}
  for name,change in changes.items():check('assessment_'+name,lambda f=change:admitted(mutation=f),refuse=True)
  check('assessment_wrong_complete_mask_hash',lambda:admitted(receipt_mutation=lambda r:r.update(scored_mask_sha256='changed')),refuse=True)
  check('assessment_wrong_count',lambda:admitted(receipt_mutation=lambda r:r.update(scored_cells=2)),refuse=True)

  # Fresh numerical NaN must not shrink the source-derived support and then be admitted.
  old_sf,old_mc,old_lr,old_lf=a.sample_forecast,a.P.c651_monte_carlo,a.P.logistic_predict,a.P.logistic_features
  a.sample_forecast=lambda *args,**kw:(torch.full((2,2),.2),torch.ones((2,2),dtype=torch.bool))
  a.P.c651_monte_carlo=lambda *args:(np.array([[.2,np.nan],[.2,.2]]),np.ones((2,2),bool))
  a.P.logistic_predict=lambda *args:np.full((2,2),.2)
  a.P.logistic_features=lambda *args:np.ones((4,1))
  env=SimpleNamespace(names=('fixture',),terrain_gradient=lambda *args:(np.zeros((2,2)),np.zeros((2,2))))
  s.event_id='synthetic';s.hours=12.
  c651=SimpleNamespace(predictor=object());models={v+'_seed0':object() for v in a.VARIANT_SET}
  # This positive control must reach deterministic support and all16 outputs.
  a.P.c651_monte_carlo=lambda *args:(np.full((2,2),.2),np.ones((2,2),bool))
  def fresh_valid_control():
   expected=a.deterministic_support(s,env,c651,models,None)
   values,current,_=a.predict_case(s,env,c651,models,None,4)
   return set(values)==a.EXPECTED_MODELS and int(current.sum())==3 and np.array_equal(current,expected)
  check('fresh_full_support_16_model_positive_control',fresh_valid_control)
  a.P.c651_monte_carlo=lambda *args:(np.array([[.2,np.nan],[.2,.2]]),np.ones((2,2),bool))
  try:
   deterministic=a.deterministic_support(s,env,c651,models,None)
   predictions,freshmask,_=a.predict_case(s,env,c651,models,None,4)
   values=dict(row=np.nonzero(freshmask)[0],col=np.nonzero(freshmask)[1],y=s.endpoint[freshmask].astype(np.int8),**{'p_'+n:v[freshmask] for n,v in predictions.items()})
   freshpath=d/'fresh-nan.npz';np.savez(freshpath,**values)
   record=dict(receipt_version='wfg.forecast-assessment-case/2',**a.source_identity(s),sha256=sha(freshpath),scored_mask_sha256=a.array_sha(freshmask),scored_cells=int(freshmask.sum()),positives=int(s.endpoint[freshmask].sum()))
   a.validate_entries(freshpath,record,s,freshmask)
   result=dict(state='ADMITTED',deterministic_cells=int(deterministic.sum()),fresh_cells=int(freshmask.sum()),nonfinite_mc_cell_excluded=bool(deterministic[0,1] and not freshmask[0,1]))
   good=np.array_equal(freshmask,deterministic)
  except (ValueError,TypeError,KeyError) as e:good='numerical failure' in str(e);result=dict(state='RAISED',reason=str(e))
  finally:a.sample_forecast,a.P.c651_monte_carlo,a.P.logistic_predict,a.P.logistic_features=old_sf,old_mc,old_lr,old_lf
  observations.append(dict(id='fresh_mc_nonfinite_cannot_trim_deterministic_support',pass_check=bool(good),observed=result))

  # Real validation/scoring code with temporary pins; mock only numerical runtime.
  repo,inputs=d/'repo',d/'inputs';repo.mkdir();(inputs/'environment').mkdir(parents=True)
  b.REPO=repo
  closure=['forecast/wildfire/example.py','research/forecast-v2/scripts/pipeline.py','research/forecast-v2/scripts/blind_test.py','research/forecast-v2/SPLIT.json']
  for rel in closure:
   p=repo/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic source identity only')
  checkpoint=repo/'checkpoint.pt';checkpoint.write_bytes(b'fixture checkpoint, never deserialized');b.C651_SHA=sha(checkpoint)
  baseline=repo/'baseline.pkl';baseline.write_bytes(pickle.dumps(None))
  model=dict(path='checkpoint.pt',sha256=sha(checkpoint))
  registry=dict(status='FROZEN',models={n:dict(model) for n in b.MODEL_NAMES},logistic=dict(path='baseline.pkl',sha256=sha(baseline)),selected_model='base_seed0',best_dilation_hours_per_cell=4,producer_source_sha256={rel:sha(repo/rel) for rel in closure})
  rp,cp=repo/'registry.json',repo/'cohort.json';b.write(rp,registry)
  events=[dict(id='synthetic',year=2026,country='US',t0_utc='2026-01-01T00:00:00Z',start_utc='2026-01-01T00:00:00Z',end_utc='2026-01-03T00:00:00Z',height=1,width=4)]
  b.write(inputs/'environment/events.json',events)
  terrain=inputs/'baseline-terrain/synthetic/elevation_m_375m.tif';terrain.parent.mkdir(parents=True);terrain.write_bytes(b'never opened by mocked numerical runtime')
  states=inputs/'perimeters/synthetic/states.npz';states.parent.mkdir(parents=True)
  np.savez(states,times=np.array(['2026-01-01T00:00:00Z','2026-01-02T00:00:00Z']),states=np.array([[[1,0,0,0]],[[1,1,0,1]]],np.uint8))
  cohort=dict(registry_sha256=sha(rp),source_release_utc='2027-01-01T00:00:00Z',registration=dict(url='https://osf.io/synthetic',registered_utc='2026-12-01T00:00:00Z',registry_sha256=sha(rp)),input_sha256={str(p.relative_to(inputs)):sha(p) for p in inputs.rglob('*') if p.is_file()})
  cohort['cases'],_=b.reference_cases(inputs,cohort);b.write(cp,cohort)
  class Environment:
   def __init__(self,*args):self.names=('synthetic',)
   def at(self,*args):return np.zeros((1,1,4),np.float32)
   def residence(self,*args):return None
   def terrain_gradient(self,*args):return np.zeros((1,4)),np.zeros((1,4))
  support=np.array([[True,True,True,False]])
  calls={'mc':0}
  def mc(*args):calls['mc']+=1;return np.full((1,4),.2),support.copy()
  numerical=SimpleNamespace(Environment=Environment,load_structured=lambda *args:object(),sample_forecast=lambda *args,**kw:(torch.full((1,4),.2),torch.from_numpy(support)),c651_monte_carlo=mc,logistic_predict=lambda *args:np.full((1,4),.2))
  b.load_pipeline=lambda:numerical;b.load_model=lambda *args,**kw:SimpleNamespace(predictor=object());b.heavy_lock=lambda:(d/'synthetic.lock').open('a+')
  entries=d/'predictions';args=SimpleNamespace(registry=rp,cohort=cp,model_root=repo,input_root=inputs,out=entries)
  b.run(args);args.entries=entries;args.out=d/'metrics.json'
  pristine=json.loads((entries/'RECEIPT.json').read_text());r=pristine['cases'][0];npz=entries/r['file'];pristine_npz=npz.read_bytes()
  def blind_score(change_arrays=None,change_receipt=None):
   receipt=copy.deepcopy(pristine);npz.write_bytes(pristine_npz)
   if change_arrays:
    with np.load(npz) as f:values={k:f[k].copy() for k in f.files}
    change_arrays(values);np.savez(npz,**values);receipt['cases'][0]['sha256']=sha(npz)
   if change_receipt:change_receipt(receipt)
   b.write(entries/'RECEIPT.json',receipt);b.score(args)
   result=json.loads(args.out.read_text());return result['complete_cohort_pass'] and calls['mc']==1
  check('blind_valid_source_bound_control',lambda:blind_score())
  for name,change in changes.items():
   # Assessment uses c651_mc too; all variants exist in blind modelset except c651_meanfield.
   check('blind_'+name,lambda f=change:blind_score(change_arrays=f),refuse=True)
  for tag,change in {
   'source_identity':lambda r:r['validated_identity'].update(producer_source_sha256={}),
   'checkpoint_identity':lambda r:r['validated_identity']['model_sha256'].update(base_seed0='bad'),
   'input_identity':lambda r:r['validated_identity'].update(input_sha256={}),
   'old_receipt':lambda r:r.pop('receipt_version'),
   'case_metadata':lambda r:r['cases'][0]['case'].update(reference_kind='korean_arrival_reconstruction')}.items():
   check('blind_receipt_'+tag,lambda f=change:blind_score(change_receipt=f),refuse=True)
  # Direct score must revalidate, even when a top receipt is re-signed.
  old=cp.read_bytes();bad=copy.deepcopy(cohort);bad['cases'][0]['year']=1999;b.write(cp,bad)
  check('original_direct_score_year1999_refused',lambda:blind_score(change_receipt=lambda r:r.update(cohort_sha256=sha(cp))),refuse=True);cp.write_bytes(old)
  for tag,pth in [('source',repo/closure[0]),('checkpoint',checkpoint),('input',inputs/'environment/events.json')]:
   old=pth.read_bytes();pth.write_bytes(b'changed bytes')
   check('blind_current_'+tag+'_changed',lambda:blind_score(),refuse=True);pth.write_bytes(old)
  result=dict(fires=list(range(10)),models={},paired={})
  for name,pred in [('base_seed0',.02),('persistence',0.),('dilation_best',0.)]:result['models'][name]=dict(pooled=dict(lowest_bin=dict(count=10,mean_prediction=pred,observed_frequency=.02)))
  for ref in ['persistence','dilation_best']:result['paired']['base_seed0__vs__'+ref]=dict(percentile_95_interval=[-.02,-.01])
  def promotion_check():
   x=b.primary_decision(result,'base_seed0',complete=False)
   return not any(x['brier_comparisons_pass'].values()) and not any(x[k] for k in ['complete_cohort_pass','calibration_pass','minimum_fire_count_pass','statistical_superiority_criteria_pass']) and all(x['descriptive_subset_criteria']['brier_comparisons'].values())
  check('original_incomplete_cohort_all_promotion_flags_false',promotion_check)
  # Execute-path baseline identity on a complete synthetic frozen-selection setup.
  a.REPO=repo;a.HERE=repo/'research/forecast-v2/scripts/score_cohorts.py';a.HERE.write_text('synthetic scoring identity')
  a.P.C651=checkpoint;a.P.C651_SHA256=sha(checkpoint)
  run=repo/'executed_run';(run/'baselines').mkdir(parents=True)
  frozenbase=repo/'frozen_baselines';frozenbase.mkdir()
  frozenfiles={}
  for name,filename,raw in [('logistic','logistic.pkl',pickle.dumps('frozen')),('logistic_parameters','logistic.json',b'{}'),('dilation_choice','dilation_choice.json',b'{"best_hours_per_cell":4}')]:
   p=frozenbase/filename;p.write_bytes(raw);frozenfiles[name]=dict(path=str(p.relative_to(repo)),sha256=sha(p))
  (run/'baselines/logistic.pkl').write_bytes(pickle.dumps('different executed baseline'))
  (run/'baselines/dilation_choice.json').write_text('{"best_hours_per_cell":8}')
  for rel in ['EXTRACTION_MANIFEST.json','BASELINE_TERRAIN_MANIFEST.json','perimeters/PERIMETER_MANIFEST.json']:
   p=inputs/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
  a.write(repo/'research/forecast-v2/GEOMETRY_AUDIT.json',dict(source_manifest_sha256=sha(inputs/'perimeters/PERIMETER_MANIFEST.json')))
  selection=dict(frozen_before_heldout_scoring=True,checkpoints={n:dict(model) for n in a.VARIANT_SET},baselines=frozenfiles,input_manifests_sha256={rel:sha(inputs/rel) for rel in ['EXTRACTION_MANIFEST.json','BASELINE_TERRAIN_MANIFEST.json','perimeters/PERIMETER_MANIFEST.json']})
  a.write(repo/'research/forecast-v2/MODEL_SELECTION.json',selection)
  def execution_identity():
   x=a.identities(SimpleNamespace(data=inputs,run=run,cohort='us2024'))
   return dict(loaded_logistic_equals_frozen=x['logistic_sha256']==frozenfiles['logistic']['sha256'],loaded_dilation_equals_frozen=x['dilation_choice_sha256']==frozenfiles['dilation_choice']['sha256'])
  # First authenticate matching actual files; then change each selected baseline independently.
  for row in frozenfiles.values():
   p=repo/row['path'];(run/'baselines'/p.name).write_bytes(p.read_bytes())
  check('executed_baselines_matching_frozen_positive_control',lambda:all(execution_identity().values()))
  for name,row in frozenfiles.items():
   p=repo/row['path'];actual=run/'baselines'/p.name;old=actual.read_bytes();actual.write_bytes(b'different executed bytes')
   check('executed_baseline_'+name+'_changed',execution_identity,refuse=True);actual.write_bytes(old)
  (run/'baselines/logistic.pkl').write_bytes(pickle.dumps('different executed baseline'))
  (run/'baselines/dilation_choice.json').write_text('{"best_hours_per_cell":8}')
  try:
   x=execution_identity();passed=all(x.values());obs=dict(state='RETURNED',value=x)
  except (ValueError,KeyError,TypeError) as e:passed=True;obs=dict(state='RAISED',type=type(e).__name__,reason=str(e))
  observations.append(dict(id='fresh_assessment_executed_baselines_match_frozen_selection',pass_check=passed,observed=obs))
 paths=['research/forecast-v2/scripts/score_cohorts.py','research/forecast-v2/scripts/blind_test.py','research/forecast-v2/scripts/pipeline.py','forecast/wildfire/baselines.py','forecast/documents/preregistration_blind_test.md']
 return dict(scope='Independent synthetic guard tests and mocked numerical producers only; no actual study inputs/predictions/scores inspected. This does not imply actual caches were corrupted.',track_head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),host=platform.platform(),python=sys.version,numpy=np.__version__,torch=torch.__version__,script_sha256=sha(__file__),source_sha256={p:sha(root/p) for p in paths},checks=len(observations),passed=sum(r['pass_check'] for r in observations),observations=observations)


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--track-b',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
 result=main(args.track_b.resolve());result['status']='PASS_SCOPED_ADMISSION_REPAIR' if result['checks']==result['passed'] else 'FAIL_TARGETED_REPAIR_OR_NEW_ADMISSION'
 args.out.write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:None)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([r for r in result['observations'] if not r['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
