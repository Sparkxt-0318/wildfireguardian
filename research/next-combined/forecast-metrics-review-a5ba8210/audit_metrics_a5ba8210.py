"""Independent tiny-array scoring/gate controls, no study input/model access."""
import copy,hashlib,importlib.util,itertools,json,math,platform,subprocess,sys
from pathlib import Path
import numpy as np
repo=Path(__file__).resolve().parents[1]/'audit-1b';sys.dont_write_bytecode=True
sys.path.insert(0,str(repo/'forecast'));sys.path.insert(0,str(repo/'research/forecast-v2/scripts'))
from wildfire import baselines as B
spec=importlib.util.spec_from_file_location('independent_metric_report_checks',repo/'research/forecast-v2/scripts/report.py');R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
obs=[]
def probe(name,fn):
 try:v=fn(); passed=bool(v);value=dict(state='RETURNED',value=v)
 except Exception as e:passed=False;value=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 obs.append(dict(id=name,pass_check=passed,observed=value))
def close(a,b):return a is None and b is None or a is not None and b is not None and abs(a-b)<1e-12
# Manual AP integrates successive complete tied threshold groups, AUC enumerates pairs.
def manual(y,p):
 n=len(y); pos=sum(y);neg=n-pos
 brier=sum((a-b)**2 for a,b in zip(y,p))/n if n else None
 ap=None
 if pos:
  ap=0.;prior=0.
  for threshold in sorted(set(p),reverse=True):
   selected=[i for i,v in enumerate(p) if v>=threshold];tp=sum(y[i] for i in selected);recall=tp/pos
   ap+=(recall-prior)*tp/len(selected);prior=recall
 auc=None if not pos or not neg else sum((p[i]>p[j])+.5*(p[i]==p[j]) for i,a in enumerate(y) if a for j,b in enumerate(y) if not b)/(pos*neg)
 nll=sum(-math.log(max(1e-7,min(1-1e-7,b))) if a else -math.log1p(-max(1e-7,min(1-1e-7,b))) for a,b in zip(y,p))/n if n else None
 ece=0.
 for lower,upper in zip(B.BINS[:-1],B.BINS[1:]):
  selected=[i for i,b in enumerate(p) if b>=lower and (b<upper or upper==1 and b<=upper)]
  if selected:ece+=abs(sum(p[i] for i in selected)-sum(y[i] for i in selected))/n
 return brier,ap,auc,nll,ece if n else None
arrays=[([0,1,0,1],[.2,.2,.8,.8]),([0,1,1,0,1],[0,.1,.5,.9,1]),([0,0,0],[0,.5,1]),([1,1,1],[0,.5,1]),([],[]),([1,0,1,0],[.25,.25,.25,.25])]
for index,(y,p) in enumerate(arrays):
 expected=manual(y,p);scored=B.score(np.array(y,float),np.array(p,float))
 for key,value in zip(['brier','average_precision','roc_auc','clipped_nll','ece_10_bins'],expected):probe(f'manual_metric_{index}_{key}',lambda key=key,value=value,scored=scored:close(scored[key],value))
probe('binary_persistence_brier_prevalence_and_bss',lambda:B.score(np.array([0.,1.,0.,1.]),np.zeros(4))['brier']==.5 and B.score(np.array([0.,1.,0.,1.]),np.zeros(4))['bss_vs_persistence']==0 and B.score(np.zeros(2),np.zeros(2))['bss_vs_persistence'] is None)
probe('tied_scores_ap_prevalence_auc_half',lambda:B.score(np.array([0.,1.,0.,1.]),np.full(4,.1))['average_precision']==.5 and B.score(np.array([0.,1.,0.,1.]),np.full(4,.1))['roc_auc']==.5)
for name,p in [('nan',[np.nan]),('negative',[-.1]),('above_one',[1.1])]:
 try:B.score(np.array([0.]),np.array(p));value=False
 except ValueError:value=True
 probe('probability_'+name+'_refuses',lambda value=value:value)
# Unequal fire sizes distinguish whole-fire paired pooling from equal-fire mean/cell bootstrap.
fire=np.array(['A','B','B','B','C','C']);y=np.array([1.,0.,0.,1.,0.,1.]);p=np.array([.9,.2,.5,.6,.8,.4]);ref=np.zeros(6);draws=127;seed=20261030
actual=B.paired_fire_bootstrap(fire,y,p,ref,draws=draws,seed=seed)
clusters=[np.where(fire==name)[0].tolist() for name in ['A','B','C']]
manual_values=[]
for sampled in np.random.default_rng(seed).integers(0,3,size=(draws,3)):
 indices=[i for cluster in sampled for i in clusters[cluster]]
 manual_values.append(sum((p[i]-y[i])**2-(ref[i]-y[i])**2 for i in indices)/len(indices))
def quantile(values,q):
 values=sorted(values);loc=(len(values)-1)*q;i=math.floor(loc);j=math.ceil(loc);return values[i]+(values[j]-values[i])*(loc-i)
expected_interval=[quantile(manual_values,q) for q in [.025,.975]]
probe('wholefire_unequal_size_point',lambda:close(actual['point_difference'],float(np.mean((p-y)**2-(ref-y)**2))))
probe('wholefire_unequal_size_ci_manual',lambda:np.allclose(actual['percentile_95_interval'],expected_interval,rtol=0,atol=1e-14))
probe('wholefire_metadata_and_repeatability',lambda:actual['fires']==3 and actual['draws']==draws and actual['seed']==seed and actual==B.paired_fire_bootstrap(fire,y,p,ref,draws=draws,seed=seed))
# Exact NLL and BSS undefined resampling accounting, tiny complete entries only.
entries=dict(fire=fire,y=y,interval=np.arange(6),predictions=dict(candidate=p,persistence=ref,dilation_best=np.array([1.,0.,0.,0.,0.,1.])))
scored=R.detailed_scores(entries,draws=draws,seed=seed)
probe('detailed_bss_uses_same_pooled_errors',lambda:close(scored['models']['candidate']['pooled']['bss_vs_persistence'],1-float(np.sum((p-y)**2))/float(np.sum((ref-y)**2))))
probe('exact_nll_certainty_wrong_preserved',lambda:scored['models']['persistence']['pooled']['exact_nll']['infinite'] and scored['models']['persistence']['pooled']['exact_nll']['value'] is None and scored['models']['persistence']['pooled']['exact_nll']['certainty_wrong_entries']==3)
zero_entries=dict(fire=np.array(['A','B']),y=np.zeros(2),interval=np.arange(2),predictions=dict(candidate=np.array([.1,.2]),persistence=np.zeros(2),dilation_best=np.zeros(2)))
zero=R.detailed_scores(zero_entries,draws=draws,seed=seed)['models']['candidate']
probe('zero_reference_bss_and_draws_explicitly_undefined',lambda:zero['pooled']['bss_vs_persistence'] is None and zero['bss_vs_persistence_paired_fire_95_interval']['interval'] is None and zero['bss_vs_persistence_paired_fire_95_interval']['undefined_zero_reference_draws']==draws)
# Independent gate truth table. Numerical scores below are deliberate synthetic metadata.
models={n:dict(pooled=dict(lowest_bin=dict(count=10,mean_prediction=.02,observed_frequency=.02))) for n in ['candidate','persistence','dilation_best']}
base=dict(models=models,paired={f'candidate__vs__{n}':dict(percentile_95_interval=[-.2,-.01]) for n in ['persistence','dilation_best']},entries=100)
def gate(s=base,a={'status':'COMPLETE'},selection=True):return R.retrospective_gate(s,'candidate',a,selection)['criteria_pass']
probe('gate_all_prerequisites_positive',gate)
for name,mutation in [('persistence_ci',lambda s:s['paired']['candidate__vs__persistence'].update(percentile_95_interval=[-.2,.01])),('dilation_ci',lambda s:s['paired']['candidate__vs__dilation_best'].update(percentile_95_interval=[-.2,.01])),('touching_zero',lambda s:s['paired']['candidate__vs__dilation_best'].update(percentile_95_interval=[-.2,0.])),('worse_calibration',lambda s:s['models']['candidate']['pooled']['lowest_bin'].update(mean_prediction=.05)),('empty_lowest_bin',lambda s:s['models']['candidate']['pooled']['lowest_bin'].update(count=0)),('empty_entries',lambda s:s.update(entries=0))]:
 altered=copy.deepcopy(base);mutation(altered);probe('gate_'+name+'_closed',lambda altered=altered:not gate(altered))
probe('gate_hold_subset_closed',lambda:not gate(a={'status':'HOLD'}))
probe('gate_no_frozen_selection_closed',lambda:not gate(selection=False))
probe('dilation_training_tie_fixed_slowest',lambda:B.choose_dilation({1:.2,2:.1,4:.1,8:.1})==8)
paths=['forecast/wildfire/baselines.py','research/forecast-v2/scripts/report.py','research/forecast-v2/scripts/pipeline.py','research/forecast-v2/scripts/score_cohorts.py']
result=dict(source_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),host=platform.platform(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_sha256={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths},checks=len(obs),passed=sum(x['pass_check'] for x in obs),observations=obs,actual_study_inputs_or_models_accessed=False,training_executed=False,status='PASS_SCOPED_ARITHMETIC_AND_GATES' if all(x['pass_check'] for x in obs) else 'HOLD')
Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([x for x in obs if not x['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
