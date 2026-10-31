"""Independent future numerical-support controls; synthetic arrays only."""
import ast,copy,hashlib,importlib.util,json,platform,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
repo=Path(__file__).resolve().parents[1]/'audit-1b';sys.path.insert(0,str(repo/'forecast'));sys.path.insert(0,str(repo/'research/forecast-v2/scripts'))
path=repo/'research/forecast-v2/scripts/blind_test.py';spec=importlib.util.spec_from_file_location('independent_future_numeric',path);B=importlib.util.module_from_spec(spec);sys.modules[spec.name]=B;spec.loader.exec_module(B)
observations=[]
def probe(name,fn,refuse=False,reason=None):
 try:v=fn();ok=not refuse and v is not False;result=dict(state='RETURNED',value=v)
 except (ValueError,TypeError,RuntimeError,IndexError) as e:ok=refuse and (reason is None or reason in str(e));result=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 observations.append(dict(id=name,pass_check=bool(ok),observed=result))
shape=(3,3);initial=np.zeros(shape,bool);initial[0,0]=True
names=['c651_meanfield',*(v+'_seed0' for v in B.VARIANTS)]
def fixture():
 sample=SimpleNamespace(initial=initial.copy(),score_mask=np.ones(shape,bool),environment=np.ones((2,*shape)),hours=1.,event_id='SYNTHETIC_ONLY')
 values={n:np.full(shape,.25) for n in names};valids={n:np.ones(shape,bool) for n in names};logistic=np.full(shape,.2);features=np.ones((9,2));gradient=np.zeros((2,*shape));calls=[]
 def forecast(model,given,**kw):
  assert given is sample and kw==dict(use_burnout=model!='c651_meanfield',use_spotting=model!='c651_meanfield')
  calls.append(model);return torch.tensor(values[model]),torch.tensor(valids[model])
 def feats(given,columns,terrain):assert given is sample and terrain is gradient;return features
 def predict(model,given,columns,terrain):assert given is sample and terrain is gradient;return logistic
 runtime=(SimpleNamespace(sample_forecast=forecast,logistic_features=feats,logistic_predict=predict),SimpleNamespace(names=['a','b'],terrain_gradient=lambda event:gradient),SimpleNamespace(predictor='c651_meanfield'),{n:n for n in names[1:]},object())
 return SimpleNamespace(runtime=runtime,sample=sample,values=values,valids=valids,logistic=logistic,features=features,calls=calls)
def derive(f):return B.deterministic_fields(f.runtime,f.sample,dict(best_dilation_hours_per_cell=4))
f=fixture();pred,mask=derive(f)
probe('positive_exact8cell_reference_and_complete_model_calls',lambda:np.array_equal(mask,~initial) and set(f.calls)==set(names) and 'c651_meanfield' not in pred and 'c651_mc' not in pred)
for target in names:
 for label,bad in [('nan',np.nan),('positive_inf',np.inf),('negative_inf',-np.inf),('below_zero',-.01),('above_one',1.01)]:
  f=fixture();f.values[target][0,1]=bad
  probe('declared_valid_'+target+'_'+label+'_refuses',lambda f=f:derive(f),True,'model numerical failure')
for label,bad in [('nan',np.nan),('positive_inf',np.inf),('negative_inf',-np.inf),('below_zero',-.01),('above_one',1.01)]:
 f=fixture();f.logistic[0,1]=bad;probe('finite_features_logistic_'+label+'_refuses',lambda f=f:derive(f),True,'logistic numerical failure')
for target in ['c651_meanfield','base_seed0']:
 f=fixture();f.values[target][0,1]=np.nan;f.valids[target][0,1]=False;_,mask=derive(f)
 probe('declared_invalid_'+target+'_nan_legitimate_exclusion',lambda mask=mask:mask.sum()==7 and not mask[0,1])
for label,bad_valid in [('float',np.ones(shape,float)),('integer',np.ones(shape,int)),('wrong_shape',np.ones((3,2),bool))]:
 f=fixture();f.valids['base_seed0']=bad_valid;probe('neural_mask_'+label+'_refuses',lambda f=f:derive(f),True,'model numerical failure')
f=fixture();f.values['c651_meanfield']=np.ones((3,2));probe('c651_prediction_shape_refuses',lambda:derive(f),True,'model numerical failure')
f=fixture();f.sample.score_mask[0,1]=False;f.values['c651_meanfield'][0,1]=np.nan;probe('unstored_c651_failure_outside_final_scoremask_still_refuses',lambda:derive(f),True,'model numerical failure')
f=fixture();f.valids['base_seed0'][0,1]=False;f.values['mixed_base_seed0'][0,1]=np.nan;probe('one_model_failure_cannot_hide_behind_other_unknown_mask',lambda:derive(f),True,'model numerical failure')
f=fixture();f.valids['base_seed0'][0,1]=False;f.logistic[0,1]=np.nan;probe('logistic_failure_cannot_hide_behind_neural_unknown_mask',lambda:derive(f),True,'logistic numerical failure')
for bad_output in [np.nan,.7]:
 f=fixture();f.features[1,0]=np.nan;f.logistic[0,1]=bad_output;_,mask=derive(f)
 probe('logistic_input_unknown_support_independent_of_output_'+str(bad_output),lambda mask=mask:mask.sum()==7 and not mask[0,1])
f=fixture();f.sample.environment[0,1,1]=np.nan;_,mask=derive(f);probe('unknown_input_environment_excluded_independently',lambda:mask.sum()==7 and not mask[1,1])
# The future custody/registration paths are structurally unchanged.
old=subprocess.check_output(['git','-C',str(repo),'show','cc801d07^:research/forecast-v2/scripts/blind_test.py'],text=True);new=path.read_text()
def function(source,name):return ast.dump(next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
for name in ['validate','validation_identity','load_pipeline','load_runtime','run','score','finalize','primary_decision']:
 probe('unchanged_auth_call_path_'+name,lambda name=name:function(old,name)==function(new,name))
old_inventory=subprocess.check_output(['git','-C',str(repo),'show','cc801d07^:research/forecast-v2/scripts/blind_inventory.py'],text=True)
new_inventory=(repo/'research/forecast-v2/scripts/blind_inventory.py').read_text()
expected=old_inventory.replace('PROPOSED_ADAPTER_REQUIRES_OWNER_ADOPTION_AND_SOURCE_PINNING','WIRED_REQUIRES_PRE_ACCESS_REGISTRATION').replace('This independent adapter is not wired into the frozen blind scorer.','This adapter is wired into the blind scorer; independent external clearance remains unverified.')
probe('inventory_only_two_documentary_strings_changed',lambda:expected==new_inventory)
with pytest.MonkeyPatch.context() as mp:
 mp.setattr(B,'validate',lambda *a:({},dict(_documentary_clearance=None),{}))
 mp.setattr(B,'load_runtime',lambda *a:(_ for _ in ()).throw(AssertionError('must not load runtime')))
 probe('missing_external_clearance_refuses_before_runtime',lambda:B.run(SimpleNamespace(registry=None,cohort=None,model_root=None,input_root=None)),True,'NOT_READY_FOR_2026_EXECUTION')
original=Path(__file__).resolve().parents[1]/'future-numerical-repair';manifest=json.loads((original/'FUTURE_NUMERICAL_REPAIR.json').read_text())
probe('all_owner_four_source_pins_exact',lambda:all(hashlib.sha256((repo/p).read_bytes()).hexdigest()==row['sha256'] for p,row in manifest['files'].items()))
probe('original_failure_evidence_byte_preserved',lambda:all(hashlib.sha256((original/p).read_bytes()).hexdigest()==value for p,value in manifest['evidence_sha256'].items()))
result=dict(source_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),source_sha256={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in manifest['files']},script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),host=platform.platform(),checks=len(observations),passed=sum(x['pass_check'] for x in observations),observations=observations,actual_study_inputs_or_models_accessed=False,training_executed=False,shared_heavy_lease=False,status='PASS_SCOPED_FUTURE_NUMERICAL_GUARD' if all(x['pass_check'] for x in observations) else 'HOLD')
Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([x for x in observations if not x['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
