"""Independent receipt/aggregation/metric audit. Imports no repository code.

Actual evidence is unreadable through this CLI without an explicit authorized
source head. This preparation is tested only against marked synthetic fixtures.
Checkpoint and fitted-baseline binary bytes are never loaded or hashed here.
"""
from __future__ import annotations
import argparse,hashlib,json,math,platform,re,subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score
VARIANTS=('base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base')
MODELS={'c651_mc','c651_meanfield','persistence','logistic','dilation_best',*(f'dilation_{k}h' for k in (1,2,4,8)),*(v+'_seed0' for v in VARIANTS)}
DRAWS,SEED=10000,20261030
LIMITS=['Independent saved-output arithmetic and custody only; no physical/field validity or blind2026 conclusion.',
 'Original source rasters, source-derived support envelopes and geometric truth are not replayed.',
 'Checkpoint and fitted-baseline binaries are not opened; their identity pointers are cross-checked.',
 'Pre-inference chronology still relies on the separately authorized frozen-registry/protocol review; finish timestamps alone do not prove inference start order.',
 'A pooled whole-fire bootstrap is conditional on the fixed models, admitted support and mapped labels; repeated intervals/cells are not independent fires.']
class AuditError(ValueError):pass
def need(condition,message):
 if not condition:raise AuditError(message)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as s:
  for block in iter(lambda:s.read(1<<20),b''):h.update(block)
 return h.hexdigest()
def objsha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def inside(root,value):
 p=Path(value);p=p if p.is_absolute() else root/p
 need(not any(q.is_symlink() for q in [p,*p.parents]),'symlink evidence path')
 p=p.resolve();need(p.is_relative_to(root.resolve()) and p.is_file(),'missing/outside evidence '+str(value));return p
def load(path):return json.loads(Path(path).read_text())
def identity(root,path):
 p=inside(root,path);return dict(path=str(p.relative_to(root.resolve())),sha256=sha(p))
def pointer(root,value):
 need(isinstance(value,dict) and set(value)=={'path','sha256'} and re.fullmatch('[0-9a-f]{64}',value.get('sha256','')),'malformed identity pointer')
 need(identity(root,value['path'])==value,'changed identity pointer '+value['path']);return inside(root,value['path'])
def compare(actual,expected,label='value'):
 if isinstance(expected,dict):
  need(isinstance(actual,dict),label+' needs object')
  for key,value in expected.items():need(key in actual,label+' missing '+key);compare(actual[key],value,label+'.'+key)
 elif isinstance(expected,list):
  need(isinstance(actual,list) and len(actual)==len(expected),label+' list size')
  for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,label+f'[{i}]')
 elif expected is None:need(actual is None,label+' must remain null')
 elif isinstance(expected,(bool,str,int)):need(type(actual) is type(expected) and actual==expected,label+' exact mismatch')
 else:need(type(actual) in (int,float) and math.isfinite(actual) and math.isclose(actual,float(expected),rel_tol=2e-10,abs_tol=2e-12),label+' numeric mismatch')
def metrics(y,p):
 y=np.asarray(y,float);p=np.asarray(p,float);need(y.ndim==p.ndim==1 and y.shape==p.shape and len(y)>0,'empty/nonvector metric population')
 need(np.isfinite(p).all() and ((p>=0)&(p<=1)).all() and np.isin(y,[0,1]).all(),'invalid metric values')
 n=len(y);bins=np.linspace(0,1,11);rows=[];ece=0.
 for i in range(10):
  use=(p>=bins[i])&((p<bins[i+1]) if i<9 else (p<=1));count=int(use.sum())
  mean=float(p[use].mean()) if count else None;freq=float(y[use].mean()) if count else None
  rows.append(dict(lower=float(bins[i]),upper=float(bins[i+1]),count=count,share=count/n,mean_prediction=mean,observed_frequency=freq))
  if count:ece+=count*abs(mean-freq)/n
 sq=float(np.mean((p-y)**2));reference=float(np.mean(y*y));clipped=np.minimum(np.maximum(p,1e-7),1-1e-7)
 return dict(entries=n,positives=int(y.sum()),brier=sq,bss_vs_persistence=1-sq/reference if reference else None,
  average_precision=float(average_precision_score(y,p)) if y.sum() else None,
  roc_auc=float(roc_auc_score(y,p)) if 0<y.sum()<n else None,ece_10_bins=ece,
  clipped_nll=float(np.mean(-y*np.log(clipped)-(1-y)*np.log1p(-clipped))),
  exact_zero_probability_positives=int(((p==0)&(y==1)).sum()),lowest_bin=rows[0],calibration=rows)
def fire_bootstrap(fire,y,p,reference,draws=DRAWS,seed=SEED):
 fires=sorted(set(fire.tolist()));errors=[];counts=[]
 for f in fires:
  ids=fire==f;errors.append(float(np.sum((p[ids]-y[ids])**2)-np.sum((reference[ids]-y[ids])**2)));counts.append(int(ids.sum()))
 chosen=np.random.default_rng(seed).integers(len(fires),size=(draws,len(fires)));errors=np.asarray(errors);counts=np.asarray(counts)
 values=errors[chosen].sum(1)/counts[chosen].sum(1);lo,hi=np.quantile(values,[.025,.975])
 each={f:float(e/n) for f,e,n in zip(fires,errors,counts)}
 return dict(point_difference=float(errors.sum()/counts.sum()),percentile_95_interval=[float(lo),float(hi)],excludes_zero=bool(hi<0 or lo>0),fires=len(fires),draws=draws,seed=seed,per_fire_difference=each,fires_favouring_candidate=sum(v<0 for v in each.values()))
def all_scores(entries):
 fire,y,pred=entries['fire'],entries['y'],entries['predictions'];fires=sorted(set(fire.tolist()));models={};paired={}
 sampled=np.random.default_rng(SEED).integers(len(fires),size=(DRAWS,len(fires)))
 errors={n:np.array([np.sum((p[fire==f]-y[fire==f])**2) for f in fires]) for n,p in pred.items()}
 for name,p in pred.items():
  pooled=metrics(y,p);each={f:metrics(y[fire==f],p[fire==f]) for f in fires};wrong=int((((p==0)&(y==1))|((p==1)&(y==0))).sum())
  exact=None if wrong else float((-np.log(p[y==1]).sum()-np.log1p(-p[y==0]).sum())/len(y));pooled['exact_nll']=dict(value=exact,infinite=bool(wrong),certainty_wrong_entries=wrong)
  record=dict(pooled=pooled,per_fire=each)
  for ref in ['persistence','dilation_best']:
   key='bss_vs_'+('best_dilation' if ref=='dilation_best' else 'persistence');den=errors[ref].sum();pooled[key]=float(1-errors[name].sum()/den) if den else None
   d=errors[ref][sampled].sum(1);ok=d>0;vals=1-errors[name][sampled].sum(1)[ok]/d[ok]
   record[key+'_paired_fire_95_interval']=dict(interval=np.quantile(vals,[.025,.975]).tolist() if len(vals) else None,draws=DRAWS,seed=SEED,undefined_zero_reference_draws=int((~ok).sum()))
   for f,row in each.items():
    denom=float(np.mean((pred[ref][fire==f]-y[fire==f])**2));row[key]=1-row['brier']/denom if denom else None
   if name!=ref:paired[name+'__vs__'+ref]=fire_bootstrap(fire,y,p,pred[ref])
  models[name]=record
 return dict(models=models,paired=paired,fires=fires,entries=len(y),positives=int(y.sum()))
def cohort(root,run,folder,events,selection,registry):
 directory=run/folder;a=load(directory/'ASSESSMENT.json');f=load(directory/'FROZEN_ASSESSMENT.json');fsha=sha(directory/'FROZEN_ASSESSMENT.json')
 need(a.get('receipt_version')=='wfg.forecast-assessment/2' and a.get('status') in ['COMPLETE','HOLD'],'assessment schema/status')
 need(a['events']==events and len(events)==len(set(events)),'missing/reordered declared cohort events')
 need(a['frozen_sha256']==fsha,'frozen assessment hash')
 need(f['selection_sha256']==sha(root/'research/forecast-v2/MODEL_SELECTION.json'),'frozen selection hash')
 need(f['registry']==identity(root,root/'research/forecast-v2/BLIND_REGISTRY.json'),'frozen registry hash')
 need(f['development_coverage_sha256']==selection['development_coverage_sha256'] and f['checkpoints']==selection['checkpoints'],'frozen development/models')
 need(f['current_phase']==selection['current_phase']==registry['current_phase'],'frozen current phase')
 need(f['cohort']==('us2024' if folder=='heldout' else 'korea2025'),'frozen cohort class')
 need(f['c651_sha256']==registry['models']['c651_mc']['sha256'] and f['logistic_sha256']==selection['baselines']['logistic']['sha256'],'frozen comparator/baseline pointers')
 need(f['perimeter_manifest_sha256']==selection['input_manifests_sha256']['perimeters/PERIMETER_MANIFEST.json'] and f['extraction_manifest_sha256']==selection['input_manifests_sha256']['EXTRACTION_MANIFEST.json'],'frozen input pointers')
 need(f['trajectories']==1024 and f['seed']==0 and f['trajectory_batch_size']==32 and f['boundary']=='zero','frozen assessment settings')
 cases=a['cases'];ids=[c['case_id'] for c in cases];need(len(ids)==len(set(ids)),'duplicate case IDs');grouped={e:[] for e in events};scored_ids=set();counts=Counter();timings=[]
 for record in cases:
  case=record['case'];event=case['event'];need(event in grouped,'unlisted case event');need(record['case_id']==hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()[:24],'case identity')
  need(record['assessment_sha256']==fsha and record['status'] in ['SCORED','UNAVAILABLE','FAILED'],'case source/status');need(load(directory/'cases'/f"{record['case_id']}.json")==record,'case JSON differs from assessment')
  grouped[event].append(record);counts[record['status']]+=1
  path=directory/'cases'/f"{record['case_id']}.npz"
  if record['status']=='SCORED':
   scored_ids.add(record['case_id']);need(path.is_file() and sha(path)==record['sha256'],'changed/missing scored NPZ')
   with np.load(path,allow_pickle=False) as d:arrays={k:d[k] for k in d.files}
   need(set(arrays)=={'y','row','col',*('p_'+n for n in MODELS)},'case columns must contain exactly all16 models')
   y,row,col=arrays['y'],arrays['row'],arrays['col'];need(y.ndim==row.ndim==col.ndim==1 and len(y)>0 and y.shape==row.shape==col.shape,'case vector shapes')
   need(row.dtype.kind in 'iu' and col.dtype.kind in 'iu' and np.isin(y,[0,1]).all(),'coordinate/label dtypes')
   shape=record['rectangle'];need(len(shape)==2 and (row>=0).all() and (row<shape[0]).all() and (col>=0).all() and (col<shape[1]).all(),'coordinate bounds')
   order=np.lexsort((col,row));need(np.array_equal(order,np.arange(len(row))) and len(set(zip(row.tolist(),col.tolist())))==len(row),'coordinate order/duplicates')
   mask=np.zeros(shape,bool);mask[row,col]=True;digest=hashlib.sha256(str((mask.shape,str(mask.dtype))).encode()+mask.tobytes()).hexdigest();need(record['scored_mask_sha256']==digest,'case full coordinate mask hash')
   need(record['scored_cells']==len(y) and record['positives']==int(y.sum()),'case counts')
   need(record['scored_cells']+record['excluded_cells']==record['reference_cells'],'case reference partition')
   for name in MODELS:
    p=arrays['p_'+name];need(p.shape==y.shape and p.dtype.kind in 'bfiu' and np.isfinite(p).all() and ((p>=0)&(p<=1)).all(),'probability shape/range '+name)
   record=dict(record,_arrays=arrays);grouped[event][-1]=record
  else:
   need(not path.exists(),'unscored case has prediction file')
   if record['status']=='UNAVAILABLE':
    need(record.get('scored_cells')==0,'unavailable nonzero count')
    empty=np.zeros(record['rectangle'],bool);need(record['scored_mask_sha256']==hashlib.sha256(str((empty.shape,str(empty.dtype))).encode()+empty.tobytes()).hexdigest(),'unavailable nonempty/changed mask identity')
   for key in ['brier','average_precision','roc_auc','ece_10_bins','clipped_nll']:
    need(record.get(key) is None,'unscored metric must stay null/absent')
 need({p.stem for p in (directory/'cases').glob('*.npz')}==scored_ids,'unlisted case predictions')
 need({p.stem for p in (directory/'cases').glob('*.json')}==set(ids),'unlisted/missing case records')
 failures=[r for r in cases if r['status']!='SCORED'];zero_events=[e for e in events if not grouped[e]]
 need(all(any(r.get('event')==e and r.get('reason') for r in a['failed_or_unavailable']) for e in zero_events),'missing zero-interval event reason')
 need(all(r in a['failed_or_unavailable'] for r in failures),'missing failure/unavailable ledger')
 need(all(r in failures or (r.get('event') in zero_events and r.get('reason')) for r in a['failed_or_unavailable']),'invented failure ledger')
 need((a['status']=='COMPLETE')==(not a['failed_or_unavailable']),'complete/HOLD status inconsistent')
 expected_timing={(e,i) for e,rows in grouped.items() for i,row in enumerate(rows) if row['status']=='SCORED'}
 need(len(a['timings'])==len(expected_timing) and {(row['event'],row['interval']) for row in a['timings']}==expected_timing,'complete scored timing records')
 expected_files={e+'.npz' for e,rows in grouped.items() if any(r['status']=='SCORED' for r in rows)}
 need(set(a['per_fire_files'])==expected_files=={p.name for p in directory.glob('*.npz')},'perfire inclusion/hash list')
 fire_parts=[];y_parts=[];pred_parts={n:[] for n in sorted(MODELS)}
 for event,records in grouped.items():
  admitted=[(i,r) for i,r in enumerate(records) if r['status']=='SCORED']
  if not admitted:continue
  p=directory/(event+'.npz');need(sha(p)==a['per_fire_files'][p.name],'perfire hash')
  with np.load(p,allow_pickle=False) as d:data={k:d[k] for k in d.files}
  need(set(data)=={'row','col','y','interval','t1','hours',*('p_'+n for n in MODELS)},'aggregate columns')
  need(data['t1'].tolist()==[r['case']['cutoff'] for r in records] and np.array_equal(data['hours'],[r['case']['hours'] for r in records]),'aggregate interval metadata')
  for column in ['row','col','y',*('p_'+n for n in sorted(MODELS))]:
   expected=np.concatenate([r['_arrays'][column] for _,r in admitted]);need(data[column].dtype==expected.dtype and np.array_equal(data[column],expected),'aggregate exact entries '+column)
  interval=np.concatenate([np.full(r['scored_cells'],i) for i,r in admitted]);need(data['interval'].dtype.kind in 'iu' and np.array_equal(data['interval'],interval),'aggregate interval membership')
  fire_parts.append(np.full(len(data['y']),event));y_parts.append(data['y'])
  for name in MODELS:pred_parts[name].append(data['p_'+name])
 entries=None if not y_parts else dict(fire=np.concatenate(fire_parts),y=np.concatenate(y_parts).astype(np.float64),predictions={n:np.concatenate(pred_parts[n]).astype(np.float64) for n in sorted(MODELS)})
 return a,f,entries,dict(assessment_status=a['status'],events=len(events),cases=len(cases),statuses=dict(counts),scored_fires=len(fire_parts),entries=0 if entries is None else len(entries['y']))
def gate(scores,primary,assessment):
 refs=['persistence','dilation_best'];names=[primary,*refs];available=bool(scores['models']);comparisons={r:None for r in refs};gaps={n:None for n in names};cal=None
 if available:
  for n in names:
   b=scores['models'][n]['pooled']['lowest_bin'];gaps[n]=abs(b['mean_prediction']-b['observed_frequency']) if b['count'] else None
  comparisons={r:scores['paired'][primary+'__vs__'+r]['percentile_95_interval'][1]<0 for r in refs};cal=gaps[primary] is not None and all(gaps[r] is not None and gaps[primary]<=gaps[r] for r in refs)
 complete=assessment['status']=='COMPLETE' and bool(scores['entries'])
 return dict(criteria_pass=bool(complete and available and cal and all(comparisons.values())),brier_comparisons_pass={r:bool(complete and v) for r,v in comparisons.items()},lowest_bin_absolute_gaps=gaps,calibration_pass=bool(complete and cal),complete_cohort_pass=complete,descriptive_subset_criteria=dict(brier_comparisons=comparisons,calibration=cal))
def check_ablation(actual,entries,a,cohort_name):
 complete=a['status']=='COMPLETE' and entries is not None
 compare(actual,dict(cohort=cohort_name,assessment_status=a['status'],complete_cohort_pass=complete,promotion_criteria_pass=False,unscored_outcomes=a['failed_or_unavailable']))
 need(actual['per_fire_files']==a['per_fire_files'] and actual['frozen_assessment_sha256']==a['frozen_sha256'],'paired ablation provenance')
 if entries is None:need(not actual['variants'] and actual['status']=='UNAVAILABLE_NO_SCORED_ENTRIES','empty ablation must stay unavailable');return
 need(set(actual['variants'])==set(VARIANTS)-{'base'},'six paired fixed variants')
 for v in VARIANTS[1:]:compare(actual['variants'][v],dict(model=v+'_seed0',reference='base_seed0',**fire_bootstrap(entries['fire'],entries['y'],entries['predictions'][v+'_seed0'],entries['predictions']['base_seed0'])),v+' ablation')
def audit(root,run,results,synthetic=False,authorized_source_head=None):
 root,run,results=Path(root).resolve(),Path(run).resolve(),Path(results).resolve()
 if synthetic:need(load(root/'SYNTHETIC_ONLY.json').get('schema')=='wfg.synthetic-final-result-audit/1','synthetic marker required')
 else:
  need(authorized_source_head is not None,'actual review requires explicit root authorization')
  head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip();need(head==authorized_source_head,'authorized actual source head changed')
 need(run.is_relative_to(root) and results.is_relative_to(root),'run/results outside model root')
 evidence=root/'research/forecast-v2';selection_path=evidence/'MODEL_SELECTION.json';registry_path=evidence/'BLIND_REGISTRY.json'
 s=load(selection_path);r=load(registry_path);split=load(evidence/'SPLIT.json');reported=load(results)
 need(s.get('frozen_before_heldout_scoring') is True and set(s['checkpoints'])==set(VARIANTS),'seven frozen checkpoints required')
 need(s['selected_variant']==min(VARIANTS,key=lambda v:(s['development_brier'][v],VARIANTS.index(v))),'selection differs from frozen development criterion')
 need(r['status']=='FROZEN' and r['selected_model']==s['selected_variant']+'_seed0' and r['selection']==identity(root,selection_path),'registry selection identity')
 need(r['fit_coverage']==s['fit_coverage'],'registry coverage identity');coverage=load(pointer(root,s['fit_coverage']))
 need(s['development_coverage_sha256']==r['development_coverage_sha256']==objsha(coverage['development']),'development proof digest')
 need(coverage['status']=='PASS_COMPLETE_FIT_MEMBERSHIP' and set(coverage['variants'])==set(VARIANTS) and len(coverage['development'])==21,'complete coverage ledger')
 for v in VARIANTS:need(r['models'][v+'_seed0']==s['checkpoints'][v]==coverage['variants'][v]['checkpoint'],'model identity pointer disagreement')
 need(set(r['models'])=={'c651_mc',*(v+'_seed0' for v in VARIANTS)},'eight registry model aliases')
 need('flaming_only' in Path(s['checkpoints']['burnout_spotting']['path']).parent.name,'uncorrected spotting model pointer')
 for p,digest in r['producer_source_sha256'].items():need(Path(p).suffix in ['.py','.json','.toml','.md'] and sha(inside(root,p))==digest,'registered source changed '+p)
 phases=s['current_phase']['phases'];need(len(phases)==28 and len({p['phase_id'] for p in phases})==28 and s['current_phase']==r['current_phase'],'fixed phase inventory')
 need(reported['model_selection_sha256']==sha(selection_path) and reported['primary_candidate']['variant']==s['selected_variant'],'report selection identity')
 need(reported['primary_candidate']['checkpoint_sha256']==s['checkpoints'][s['selected_variant']]['sha256'],'report selected checkpoint pointer')
 for v in VARIANTS:
  row=reported['ablation'][v];need(row['mean_fire_brier']==s['development_brier'][v] and all(row[k] is None for k in ['difference_vs_base','interval_95','excludes_zero','fires_better_than_base']),'development effects must remain unavailable without changing selection')
 summaries={}
 for folder,key,n,score_key,ablation_key,label in [('heldout','us_2024',6,'heldout','heldout_ablation','US2024 mapped extent'),('korean2025','korean_2025',4,'korean2025_secondary_reconstruction','korean2025_secondary_ablation','Korean2025 reconstruction')]:
  events=split['held_out'][key];need(len(events)==n and len(set(events))==n,'fixed cohort fire count')
  a,f,entries,summary=cohort(root,run,folder,events,s,r);actual=reported[score_key]
  compare(actual,dict(assessment_status=a['status'],declared_fires=events,unscored_outcomes=a['failed_or_unavailable']))
  if entries is None:compare(actual,dict(models={},paired={},fires=[],entries=0,positives=None,metric_status='UNAVAILABLE_NO_SCORED_ENTRIES'));scored=dict(models={},paired={},entries=0)
  else:
   scored=all_scores(entries);need(set(actual['models'])==MODELS and set(actual['paired'])==set(scored['paired']),'reported metric model/comparison coverage');compare(actual,scored,folder+' independent metrics')
   compare(actual,dict(metric_status='COMPLETE_DECLARED_COHORT' if a['status']=='COMPLETE' else 'DESCRIPTIVE_SUPPORTED_SUBSET'))
  check_ablation(reported[ablation_key],entries,a,label);need(reported[ablation_key]['assessment_receipt_sha256']==sha(run/folder/'ASSESSMENT.json'),'ablation assessment receipt hash')
  if folder=='heldout':
   compare(reported['retrospective_superiority_gate'],gate(scored,s['selected_variant']+'_seed0',a),'primary gate')
   if entries is not None:
    p=entries['predictions']['c651_mc'];expected=scored['models']['c651_mc']['pooled']['brier']-float(np.mean(p*(1-p)))/(f['trajectories']-1);compare(actual['models']['c651_mc']['pooled'],dict(brier_mc_variance_corrected=expected,mc_trajectories=1024),'MC finite sample diagnostic')
  summaries[folder]=summary
 expected_status='HOLD' if any(s['assessment_status']=='HOLD' for s in summaries.values()) else 'GENERATED_PENDING_VISUAL_QA'
 need(reported['report_status']==expected_status,'global report status')
 figure_names={'fig01_reliability_all_models','fig02_per_fire_brier_paired','fig03_ablation_forest_plot','fig04_meanfield_vs_mc_rmse_by_horizon','fig05_example_forecast_vs_perimeter'}
 need(set(reported['figure_evidence'])==figure_names,'all five figure ledgers required')
 for name,item in reported['figure_evidence'].items():
  need(set(item['files_sha256'])=={'png','svg'},'paired PNG/SVG figure identities')
  for extension,digest in item['files_sha256'].items():need(sha(results.parent/'figures'/(name+'.'+extension))==digest,'changed figure bytes '+name)
 expected_available=summaries['heldout']['entries']>0
 fig03=reported['figure_evidence']['fig03_ablation_forest_plot'];need(fig03['cohort']=='US2024 mapped extent' and fig03['source']=='heldout_ablation' and fig03['promotion_criteria_pass'] is False and fig03['metric_data_available'] is expected_available,'ablation figure scope/availability')
 return dict(status='PASS_INDEPENDENT_SAVED_RESULT_AUDIT',synthetic_only=synthetic,authorized_source_head=authorized_source_head,selection_sha256=sha(selection_path),registry_sha256=sha(registry_path),results_sha256=sha(results),cohorts=summaries,limits=LIMITS,model_binary_bytes_accessed=False,host=platform.platform())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model-root',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--synthetic-only',action='store_true');p.add_argument('--authorized-source-head');a=p.parse_args()
 try:result=audit(a.model_root,a.run,a.results,a.synthetic_only,a.authorized_source_head);code=0
 except Exception as e:result=dict(status='HOLD_INDEPENDENT_RESULT_AUDIT',error_type=type(e).__name__,reason=str(e),limits=LIMITS);code=1
 result['checker_sha256']=sha(__file__);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result));return code
if __name__=='__main__':raise SystemExit(main())
