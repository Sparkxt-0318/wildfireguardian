"""Independent synthetic ablation reporting repair audit; no actual study access."""
import ast,copy,hashlib,importlib.util,json,math,platform,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
import pytest
repo=Path(__file__).resolve().parents[2]/'audit-1b';sys.dont_write_bytecode=True
sys.path.insert(0,str(repo/'forecast'));sys.path.insert(0,str(repo/'research/forecast-v2/scripts'))
spec=importlib.util.spec_from_file_location('independent_ablation_repair',repo/'research/forecast-v2/scripts/report.py');R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
obs=[]
def probe(name,fn):
 try:v=fn();ok=bool(v);value=dict(state='RETURNED',value=v)
 except Exception as e:ok=False;value=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 obs.append(dict(id=name,pass_check=ok,observed=value))
def close(a,b):return abs(a-b)<1e-12
# The original exact equal-Brier/unequal-weight counterexample now refuses a paired inference.
for base_weight,candidate_weight in [(100.,50.),(100.,100.)]:
 with tempfile.TemporaryDirectory(prefix='wfg-repair-ablation-') as temp,pytest.MonkeyPatch.context() as mp:
  run=Path(temp);records={}
  for variant,weight in [('base',base_weight),('burnout',candidate_weight)]:
   path=run/R.F.intended_phase(variant,'fold','2020')['result'];path.parent.mkdir(parents=True);path.write_text('{}')
   records[variant]=dict(variant=variant,fold='2020',seed=0,validation_per_fire={'SYNTHETIC_FIRE':dict(brier=.1,weight=weight,clipped_nll=.2)},fit_seconds=1.,parameters=1)
  mp.setattr(R.F,'phase_result',lambda root,run,variant,stage,fold:(None,records[variant],None,None,None))
  value=R.ablation(run)
  probe(f'development_{base_weight}_{candidate_weight}_paired_fields_all_null',lambda:all(all(row[n] is None for n in ['difference_vs_base','interval_95','excludes_zero','fires_better_than_base']) and row['paired_status'].startswith('UNAVAILABLE_') for row in value.values()))
  probe(f'development_{base_weight}_{candidate_weight}_own_absolute_scores_retained',lambda:all(close(value[v]['pooled_brier'],.1) and close(value[v]['mean_fire_brier'],.1) and value[v]['own_support_weight']==w and value[v]['per_fire']['SYNTHETIC_FIRE']['weight']==w for v,w in [('base',base_weight),('burnout',candidate_weight)]))
# Frozen primary criterion and heldout gates are byte-structurally unchanged.
old=subprocess.check_output(['git','-C',str(repo),'show','a5ba8210:research/forecast-v2/scripts/report.py'],text=True)
current=(repo/'research/forecast-v2/scripts/report.py').read_text()
def function(source,name):return ast.dump(next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
for name in ['primary_candidate','detailed_scores','retrospective_gate','load_assessment','load_report_inputs','assessment_scores']:
 probe('unchanged_'+name,lambda name=name:function(old,name)==function(current,name))
# Manual paired bootstrap over unequal-size whole fires on identical array positions.
fire=np.array(['A','B','B','B','C','C']);y=np.array([1.,0.,0.,1.,0.,1.]);base=np.array([.8,.1,.5,.4,.2,.9]);candidate=np.array([.9,.2,.5,.6,.8,.4])
pred={v+'_seed0':candidate.copy() if v=='burnout' else base.copy() for v in R.F.VARIANTS}
entries=dict(fire=fire,y=y,interval=np.arange(6),predictions=pred)
assessment=dict(status='COMPLETE',frozen_sha256='0'*64,per_fire_files={'SYNTHETIC.npz':'1'*64},failed_or_unavailable=[])
paired=R.heldout_ablation(entries,assessment,'SYNTHETIC_US_COMMON_CELL_FIXTURE');row=paired['variants']['burnout']
clusters=[np.where(fire==name)[0].tolist() for name in ['A','B','C']];draws=10000;seed=20261030;values=[]
for sampled in np.random.default_rng(seed).integers(0,3,size=(draws,3)):
 indices=[i for k in sampled for i in clusters[k]]
 values.append(sum((candidate[i]-y[i])**2-(base[i]-y[i])**2 for i in indices)/len(indices))
def quantile(values,q):
 values=sorted(values);loc=(len(values)-1)*q;i=math.floor(loc);j=math.ceil(loc);return values[i]+(values[j]-values[i])*(loc-i)
expected=[quantile(values,q) for q in [.025,.975]]
probe('heldout_manual_common_cell_point',lambda:close(row['point_difference'],float(np.mean((candidate-y)**2-(base-y)**2))))
probe('heldout_manual_wholefire_ci',lambda:np.allclose(row['percentile_95_interval'],expected,rtol=0,atol=1e-14))
probe('heldout_fixed_seed_draws_fires',lambda:row['seed']==seed and row['draws']==draws and row['fires']==3 and set(row['per_fire_difference'])=={'A','B','C'})
probe('heldout_secondary_never_promotes',lambda:paired['promotion_criteria_pass'] is False and paired['complete_cohort_pass'] is True and paired['per_fire_files']==assessment['per_fire_files'])
probe('all_six_fixed_variants_and_aliases_retained',lambda:set(paired['variants'])==set(R.F.VARIANTS)-{'base'} and all(paired['variants'][v]['model']==v+'_seed0' and paired['variants'][v]['reference']=='base_seed0' for v in paired['variants']))
hold=copy.deepcopy(assessment);hold.update(status='HOLD',failed_or_unavailable=[dict(status='UNAVAILABLE',reason='synthetic missing support')]);partial=R.heldout_ablation(entries,hold,'SYNTHETIC_US_COMMON_CELL_FIXTURE')
probe('hold_supported_subset_never_promotes',lambda:partial['status']=='DESCRIPTIVE_SUPPORTED_SUBSET' and partial['complete_cohort_pass'] is False and partial['promotion_criteria_pass'] is False and partial['unscored_outcomes']==hold['failed_or_unavailable'])
empty=R.heldout_ablation(None,hold,'SYNTHETIC_US_COMMON_CELL_FIXTURE')
probe('empty_has_no_scores_or_promotion',lambda:empty['status']=='UNAVAILABLE_NO_SCORED_ENTRIES' and not empty['variants'] and empty['promotion_criteria_pass'] is False)
missing=copy.deepcopy(entries);missing['predictions'].pop('ellipse_seed0');absent=R.heldout_ablation(missing,assessment,'SYNTHETIC_US_COMMON_CELL_FIXTURE')
probe('missing_fixed_alias_unavailable',lambda:absent['status']=='UNAVAILABLE_MISSING_FIXED_VARIANT_PREDICTIONS' and not absent['variants'] and absent['promotion_criteria_pass'] is False)
korea=R.heldout_ablation(entries,hold,'Korean2025 reconstruction')
probe('korean_reconstruction_scope_distinct',lambda:korea['cohort']=='Korean2025 reconstruction' and paired['cohort']=='SYNTHETIC_US_COMMON_CELL_FIXTURE' and korea['promotion_criteria_pass'] is False)
# Pure report panels use only synthetic manual numbers and are retained for visual review.
plt=R.style();out=Path(__file__).parent/'figures';R.figure_ablation(plt,partial,out/'hold','SYNTHETIC FIXTURE')
R.figure_ablation(plt,dict(variants={},reason='No authenticated held-out common-cell predictions are available'),out/'unavailable','SYNTHETIC FIXTURE')
hold_svg=(out/'hold/fig03_ablation_forest_plot.svg').read_text();unavailable_svg=(out/'unavailable/fig03_ablation_forest_plot.svg').read_text()
probe('hold_plot_has_subset_label_and_correct_population',lambda:'HOLD: supported subset only' in hold_svg and 'Pooled common-cell Brier minus base' in hold_svg and 'development Brier' not in hold_svg)
probe('no_authenticated_heldout_plot_is_unavailable',lambda:'UNAVAILABLE' in unavailable_svg and 'own support' in unavailable_svg)
result=dict(source_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),report_source_sha256=hashlib.sha256(current.encode()).hexdigest(),checks=len(obs),passed=sum(x['pass_check'] for x in obs),observations=obs,host=platform.platform(),actual_study_inputs_or_models_accessed=False,training_executed=False,scope='Synthetic reporting arithmetic/precondition controls only; heldout helper arrays are explicitly synthetic and their documentary hashes are dummy identities, not an authentication claim.',status='PASS_SCOPED_ABLATION_REPAIR' if all(x['pass_check'] for x in obs) else 'HOLD')
Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([x for x in obs if not x['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
