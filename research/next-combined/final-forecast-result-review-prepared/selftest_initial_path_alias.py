"""Only marked synthetic bundles; no repository data/model/helper imports."""
import copy,hashlib,importlib.util,itertools,json,math,shutil,tempfile
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('independent_final_checker',Path(__file__).with_name('check_results.py'));C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
HERE=Path(__file__).resolve().parent;OBS=[]
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def probe(name,fn,refuse=False):
 try:v=fn();ok=not refuse and v is not False;result=dict(state='RETURNED',value=v)
 except (C.AuditError,ValueError,KeyError,FileNotFoundError) as e:ok=refuse;result=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 OBS.append(dict(id=name,pass_check=bool(ok),observed=result))
def calibration_metric_manual(y,p):
 # Threshold-group AP and pairwise AUC are independent of sklearn references.
 positives=sum(y);negatives=len(y)-positives;ap=None
 if positives:
  ap=0.;prior=0.
  for t in sorted(set(p),reverse=True):
   keep=[i for i,v in enumerate(p) if v>=t];tp=sum(y[i] for i in keep);recall=tp/positives;ap+=(recall-prior)*tp/len(keep);prior=recall
 auc=None if not positives or not negatives else sum((p[i]>p[j])+.5*(p[i]==p[j]) for i,a in enumerate(y) if a for j,b in enumerate(y) if not b)/(positives*negatives)
 return ap,auc
for i,(y,p) in enumerate([([0,1,0,1],[.2,.2,.8,.8]),([0,1,1,0,1],[0,.1,.5,.9,1]),([0,0],[0,.2]),([1,1],[.3,1])]):
 m=C.metrics(np.array(y),np.array(p));ap,auc=calibration_metric_manual(y,p)
 probe(f'manual_tied_or_degenerate_AP_{i}',lambda m=m,ap=ap:m['average_precision'] is None if ap is None else math.isclose(m['average_precision'],ap,abs_tol=1e-14))
 probe(f'manual_pairwise_AUC_{i}',lambda m=m,auc=auc:m['roc_auc'] is None if auc is None else math.isclose(m['roc_auc'],auc,abs_tol=1e-14))
 probe(f'manual_Brier_{i}',lambda m=m,y=y,p=p:math.isclose(m['brier'],sum((a-b)**2 for a,b in zip(y,p))/len(y),abs_tol=1e-14))
fire=np.array(['A','B','B','B']);y=np.array([1.,0.,0.,1.]);p=np.array([.8,.1,.4,.7]);ref=np.zeros(4);actual=C.fire_bootstrap(fire,y,p,ref,draws=127)
manual=[]
for draw in np.random.default_rng(C.SEED).integers(2,size=(127,2)):
 ids=[i for event in draw for i,f in enumerate(fire) if f==['A','B'][event]];manual.append(sum((p[i]-y[i])**2-(ref[i]-y[i])**2 for i in ids)/len(ids))
probe('manual_unequal_fire_cluster_bootstrap',lambda:np.allclose(actual['percentile_95_interval'],np.quantile(manual,[.025,.975]),rtol=0,atol=1e-14))
def make(root,outcome):
 evidence=root/'research/forecast-v2';run=root/'synthetic_run';write(root/'SYNTHETIC_ONLY.json',dict(schema='wfg.synthetic-final-result-audit/1'));(root/'synthetic_source.py').write_text('# Synthetic source pin only.\n')
 split=dict(held_out=dict(us_2024=[f'US_{i}' for i in range(6)],korean_2025=[f'KR_{i}' for i in range(4)]));write(evidence/'SPLIT.json',split)
 checkpoints={v:dict(path=f'synthetic_run/final/{v}_seed0'+('_flaming_only' if v=='burnout_spotting' else '')+'/checkpoint.pt',sha256=str(i+1)*64) for i,v in enumerate(C.VARIANTS)}
 development={f'{v}_{f}':dict(variant=v,fold=f) for f in ['2020','2021','2022'] for v in C.VARIANTS}
 coverage=dict(status='PASS_COMPLETE_FIT_MEMBERSHIP',variants={v:dict(checkpoint=p) for v,p in checkpoints.items()},development=development);write(evidence/'FIT_COVERAGE.json',coverage)
 phases=[dict(phase_id=f'{v}_{f}') for f in ['2020','2021','2022','final'] for v in C.VARIANTS];phase=dict(phases=phases)
 baseline=dict(path='synthetic_run/baselines/logistic.pkl',sha256='a'*64)
 selection=dict(frozen_before_heldout_scoring=True,checkpoints=checkpoints,selected_variant='base',development_brier={v:.1+i*.01 for i,v in enumerate(C.VARIANTS)},fit_coverage=C.identity(root,evidence/'FIT_COVERAGE.json'),development_coverage_sha256=C.objsha(development),current_phase=phase,baselines=dict(logistic=baseline),input_manifests_sha256={'EXTRACTION_MANIFEST.json':'b'*64,'perimeters/PERIMETER_MANIFEST.json':'c'*64})
 write(evidence/'MODEL_SELECTION.json',selection)
 registry=dict(status='FROZEN',selected_model='base_seed0',selection=C.identity(root,evidence/'MODEL_SELECTION.json'),fit_coverage=selection['fit_coverage'],development_coverage_sha256=selection['development_coverage_sha256'],current_phase=phase,models={'c651_mc':dict(path='never_open/checkpoint.pt',sha256='d'*64),**{v+'_seed0':p for v,p in checkpoints.items()}},producer_source_sha256={'synthetic_source.py':C.sha(root/'synthetic_source.py')});write(evidence/'BLIND_REGISTRY.json',registry)
 report=dict(model_selection_sha256=C.sha(evidence/'MODEL_SELECTION.json'),primary_candidate=dict(variant='base',checkpoint_sha256=checkpoints['base']['sha256']),ablation={v:dict(mean_fire_brier=selection['development_brier'][v],difference_vs_base=None,interval_95=None,excludes_zero=None,fires_better_than_base=None) for v in C.VARIANTS})
 for folder,key,score_key,ablation_key,label in [('heldout','us_2024','heldout','heldout_ablation','US2024 mapped extent'),('korean2025','korean_2025','korean2025_secondary_reconstruction','korean2025_secondary_ablation','Korean2025 reconstruction')]:
  d=run/folder;f=dict(selection_sha256=C.sha(evidence/'MODEL_SELECTION.json'),registry=C.identity(root,evidence/'BLIND_REGISTRY.json'),development_coverage_sha256=selection['development_coverage_sha256'],checkpoints=checkpoints,current_phase=phase,trajectories=1024,seed=0,trajectory_batch_size=32,boundary='zero',cohort='us2024' if folder=='heldout' else 'korea2025',c651_sha256='d'*64,logistic_sha256='a'*64,perimeter_manifest_sha256='c'*64,extraction_manifest_sha256='b'*64);write(d/'FROZEN_ASSESSMENT.json',f);fsha=C.sha(d/'FROZEN_ASSESSMENT.json')
  cases=[];perfire={};allfire=[];ally=[];allp={n:[] for n in sorted(C.MODELS)};timings=[]
  for i,event in enumerate(split['held_out'][key]):
   arrays_by_interval=[]
   for j in range(2):
    case=dict(event=event,cutoff=f"{2024 if folder=='heldout' else 2025}-01-0{j+1}T00:00:00+00:00",endpoint=f"{2024 if folder=='heldout' else 2025}-01-0{j+1}T12:00:00+00:00",hours=12.)
    cid=hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()[:24];scored=outcome=='complete' or outcome=='partial' and (i+j)%3==0
    record=dict(case=case,case_id=cid,assessment_sha256=fsha,status='SCORED' if scored else 'UNAVAILABLE',rectangle=[3,4],reference_cells=12)
    if scored:
     n=2+i%3;y=np.array([k%2 for k in range(n)],np.int8);row=np.zeros(n,int);col=np.arange(n);mask=np.zeros((3,4),bool);mask[row,col]=True
     pred={name:np.where(y,.6,.02).astype(np.float32) for name in C.MODELS}
     pred['persistence']=np.zeros(n);pred['dilation_best']=np.where(y,.4,.03);pred['c651_mc']=np.where(y,.5,.01)
     arr=dict(y=y,row=row,col=col,**{'p_'+name:p for name,p in pred.items()});path=d/'cases'/f'{cid}.npz';path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,**arr)
     record.update(sha256=C.sha(path),scored_cells=n,positives=int(y.sum()),excluded_cells=12-n,scored_mask_sha256=hashlib.sha256(str((mask.shape,str(mask.dtype))).encode()+mask.tobytes()).hexdigest());arrays_by_interval.append((j,arr));timings.append(dict(event=event,interval=j))
    else:record.update(scored_cells=0,reason='SYNTHETIC unavailable support')
    write(d/'cases'/f'{cid}.json',record);cases.append(record)
   if arrays_by_interval:
    payload={k:np.concatenate([a[k] for _,a in arrays_by_interval]) for k in arrays_by_interval[0][1]};payload.update(interval=np.concatenate([np.full(len(a['y']),j) for j,a in arrays_by_interval]),t1=np.array([r['case']['cutoff'] for r in cases[-2:]]),hours=np.array([12.,12.]));path=d/(event+'.npz');np.savez_compressed(path,**payload);perfire[path.name]=C.sha(path)
    allfire.append(np.full(len(payload['y']),event));ally.append(payload['y'])
    for name in C.MODELS:allp[name].append(payload['p_'+name])
  failed=[r for r in cases if r['status']!='SCORED'];a=dict(receipt_version='wfg.forecast-assessment/2',status='COMPLETE' if not failed else 'HOLD',events=split['held_out'][key],frozen_sha256=fsha,cases=cases,failed_or_unavailable=failed,per_fire_files=perfire,timings=timings);write(d/'ASSESSMENT.json',a)
  entries=None if not ally else dict(fire=np.concatenate(allfire),y=np.concatenate(ally).astype(float),predictions={name:np.concatenate(ps).astype(float) for name,ps in allp.items()});s=dict(models={},paired={},fires=[],entries=0,positives=None) if entries is None else C.all_scores(entries)
  s.update(assessment_status=a['status'],declared_fires=a['events'],unscored_outcomes=failed,metric_status='UNAVAILABLE_NO_SCORED_ENTRIES' if entries is None else 'COMPLETE_DECLARED_COHORT' if a['status']=='COMPLETE' else 'DESCRIPTIVE_SUPPORTED_SUBSET')
  ab=dict(cohort=label,assessment_status=a['status'],frozen_assessment_sha256=fsha,per_fire_files=perfire,complete_cohort_pass=bool(a['status']=='COMPLETE' and entries is not None),promotion_criteria_pass=False,unscored_outcomes=failed,variants={},assessment_receipt_sha256=C.sha(d/'ASSESSMENT.json'),status='UNAVAILABLE_NO_SCORED_ENTRIES' if entries is None else 'AVAILABLE_COMPLETE_DECLARED_COHORT' if a['status']=='COMPLETE' else 'DESCRIPTIVE_SUPPORTED_SUBSET')
  if entries is not None:ab['variants']={v:dict(model=v+'_seed0',reference='base_seed0',**C.fire_bootstrap(entries['fire'],entries['y'],entries['predictions'][v+'_seed0'],entries['predictions']['base_seed0'])) for v in C.VARIANTS[1:]}
  report[score_key]=s;report[ablation_key]=ab
  if folder=='heldout':
   report['retrospective_superiority_gate']=C.gate(s,'base_seed0',a)
   if entries is not None:
    p=entries['predictions']['c651_mc'];report[score_key]['models']['c651_mc']['pooled'].update(brier_mc_variance_corrected=s['models']['c651_mc']['pooled']['brier']-float(np.mean(p*(1-p)))/1023,mc_trajectories=1024)
 write(evidence/'RESULTS.json',report);return root,run,evidence/'RESULTS.json'
roots=[]
with tempfile.TemporaryDirectory(prefix='wfg-final-result-checker-synthetic-') as temp:
 for outcome in ['complete','partial','empty']:
  bundle=make(Path(temp)/outcome,outcome);roots.append(bundle)
  probe(outcome+'_synthetic_bundle_positive',lambda bundle=bundle:C.audit(*bundle,synthetic=True)['status']=='PASS_INDEPENDENT_SAVED_RESULT_AUDIT')
  if outcome!='complete':
   result=C.load(bundle[2]);probe(outcome+'_primary_gate_closed',lambda result=result:result['retrospective_superiority_gate']['criteria_pass'] is False)
 root,run,result_path=roots[0];pristine={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
 def restore():
  for p in root.rglob('*'):
   if p.is_file() and p not in pristine:p.unlink()
  for p,data in pristine.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 def negative(name,mutate):
  restore();probe(name,lambda:(mutate(),C.audit(root,run,result_path,synthetic=True))[1],True);restore()
 def result_change(fn):r=C.load(result_path);fn(r);write(result_path,r)
 negative('wrong_Brier_report_refuses',lambda:result_change(lambda r:r['heldout']['models']['base_seed0']['pooled'].update(brier=.999)))
 negative('wrong_AP_report_refuses',lambda:result_change(lambda r:r['heldout']['models']['base_seed0']['pooled'].update(average_precision=.123)))
 negative('wrong_bootstrap_CI_refuses',lambda:result_change(lambda r:r['heldout']['paired']['base_seed0__vs__persistence'].update(percentile_95_interval=[-.9,-.8])))
 negative('wrong_ablation_CI_refuses',lambda:result_change(lambda r:r['heldout_ablation']['variants']['burnout'].update(percentile_95_interval=[-.9,-.8])))
 negative('false_ablation_promotion_refuses',lambda:result_change(lambda r:r['heldout_ablation'].update(promotion_criteria_pass=True)))
 negative('invented_development_effect_refuses',lambda:result_change(lambda r:r['ablation']['burnout'].update(difference_vs_base=-.1)))
 negative('changed_source_pin_refuses',lambda:(root/'synthetic_source.py').write_text('# Changed\n'))
 negative('changed_case_bytes_refuses',lambda:next((run/'heldout/cases').glob('*.npz')).write_bytes(b'changed'))
 negative('unlisted_case_prediction_refuses',lambda:(run/'heldout/cases/unlisted.npz').write_bytes(b'unlisted'))
 negative('missing_perfire_array_refuses',lambda:next((run/'heldout').glob('*.npz')).unlink())
 def assessment_mutate(fn):p=run/'heldout/ASSESSMENT.json';a=C.load(p);fn(a);write(p,a)
 negative('duplicate_case_identity_refuses',lambda:assessment_mutate(lambda a:a['cases'].append(a['cases'][0])))
 negative('omitted_US_fire_refuses',lambda:assessment_mutate(lambda a:a['events'].pop()))
 negative('wrong_registry_pointer_refuses',lambda:result_change(lambda r:r.update(model_selection_sha256='0'*64)))
 # Re-sign a wrong aggregation to ensure file hashes alone do not admit it.
 def aggregation_mutate():
  a=C.load(run/'heldout/ASSESSMENT.json');name=next(iter(a['per_fire_files']));p=run/'heldout'/name
  with np.load(p,allow_pickle=False) as d:arr={k:d[k] for k in d.files}
  arr['interval'][0]=1;np.savez_compressed(p,**arr);a['per_fire_files'][name]=C.sha(p);write(run/'heldout/ASSESSMENT.json',a)
 negative('resigned_wrong_interval_aggregation_refuses',aggregation_mutate)
 probe('unapproved_actual_mode_refuses_before_result_access',lambda:C.audit(Path(temp)/'does-not-exist',Path(temp)/'no-run',Path(temp)/'no-results'),True)
 result=dict(status='PASS_SYNTHETIC_PREPARATION' if all(o['pass_check'] for o in OBS) else 'HOLD',checks=len(OBS),passed=sum(o['pass_check'] for o in OBS),observations=OBS,actual_heldout_inputs_outputs_or_models_accessed=False,production_metric_report_helpers_imported=False,checker_sha256=C.sha(HERE/'check_results.py'),selftest_sha256=C.sha(__file__))
 write(HERE/'SELFTEST.json',result);print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([o for o in OBS if not o['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
