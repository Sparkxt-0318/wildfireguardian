"""Bounded independent saved-metadata review of F65 provisional actual preflight.

No raw state/cache/raster/model/heldout arrays are opened. No auditor is rerun.
"""
import ast,collections,datetime,gzip,hashlib,json,math
from pathlib import Path
import pandas as pd
here=Path(__file__).resolve().parent;root=here.parent/'track-1b';base=root/'research/forecast-v2/review/provisional_coverage_F65';package=here.parent/'coverage-actual-recipe-repair/v2';checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def objsha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def need(ok,label):
 checks.append(dict(id=label,pass_check=bool(ok)))
 if not ok:raise ValueError(label)
def load(p):return json.loads(Path(p).read_text())
def metadata_pointer(value):
 p=root/value['path'];need(p.suffix in ['.json','.py','.md','.toml'],'metadata-only pointer extension '+value['path']);need(sha(p)==value['sha256'],'metadata pointer '+value['path']);return p
pins={'PREFLIGHT_RECEIPT.json':'6df0eaf4f3daf6e67c3cbe3c0cf7e5cd85f5498d1bf7e26fa19f66ceccedf8e7','COVERAGE_PROVISIONAL.json':'12ed2aae675e78a355312c24d56fd2183b313c0238c3de8a2723964e71c3bbd6','candidate_raw.json.gz':'5a45558a5b32c1a2350e52871fb010c828757c82c6e5bbee2e05efdf45987b29','PREFLIGHT.log':'a5e4ae58a2fd525ddc220090fe3547b7b0cb3ef34d3404d24c610f24f01bdfd0'}
for name,digest in pins.items():need(sha(base/name)==digest,'parent-pinned '+name)
r=load(base/'PREFLIGHT_RECEIPT.json');w=load(base/'COVERAGE_PROVISIONAL.json');raw_bytes=gzip.decompress((base/'candidate_raw.json.gz').read_bytes());raw=json.loads(raw_bytes)
need(hashlib.sha256(raw_bytes).hexdigest()==r['raw_diagnostic_sha256'],'decoded raw diagnostic hash')
need(r['raw_diagnostic_compressed_sha256']==pins['candidate_raw.json.gz'] and r['exposed_output_sha256']==pins['COVERAGE_PROVISIONAL.json'] and r['log_sha256']==pins['PREFLIGHT.log'],'receipt output pointers')
need(r['status']=='PROVISIONAL_AUDIT_EXECUTED_NO_ADMISSION' and r['exit_code']==0 and r['output_scope']=='REVIEW_ONLY_NO_LIVE_FIT_COVERAGE_REGISTRY_OR_INFERENCE','provisional execution status and scope')
need(r['candidate_sha256_before']==r['candidate_sha256_after']==r['executed_auditor']['sha256']==sha(root/r['executed_auditor']['path'])=='65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536','exact executing F65 bytes and bookends')
command=r['command'];need(command[1]==str((root/r['executed_auditor']['path']).resolve()) and Path(command[command.index('--model-root')+1]).resolve()==root.resolve(),'execution command source/root identity')
need(r['before_source_sha256']==r['after_source_sha256']==raw['source_sha256'] and len(raw['source_sha256'])==61 and r['all_61_sources_unchanged'] is True,'61 saved live dependency bookends')
for name,digest in r['after_source_sha256'].items():need(Path(name).suffix in ['.py','.json'] and sha(root/name)==digest,'still-current checked source '+name)
oldF='1753cf31b21be093e13d61a107e407cf41542e9ec6dbe4c8ced924f5a5320cf4'
need(raw['source_sha256']['research/forecast-v2/scripts/audit_fit_coverage.py']==oldF and w['old_main_source_named_as_checked_dependency'] is True and w['executed_auditor']==r['executed_auditor'],'checked F175 differs explicitly from executed F65')
need(w['status']=='PROVISIONAL_NOT_FOR_REGISTRY' and w['raw_candidate_status']==raw['status']=='PASS_COMPLETE_FIT_MEMBERSHIP','wrapper/raw status distinction')
stripped={k:v for k,v in w.items() if k not in ['executed_auditor','old_main_source_named_as_checked_dependency','qualification','raw_candidate_status']};stripped['status']='PASS_COMPLETE_FIT_MEMBERSHIP';need(stripped==raw,'wrapper preserves entire raw result without silent omission')
need(r['tested_payload']=='EXPOSED_PROVISIONAL_WRAPPER_NOT_RAW_CANDIDATE' and r['exposed_wrapper_old_main_refuses'] is True and r['raw_candidate_non_admission_tested'] is False,'raw nonadmission explicitly untested')
need(r['original_actual_hold_receipt_sha256']=='ce7727c10e68cce536dbb0f1a56b68add941a46fab8c244f12ddf23e527d5633' and sha(package.parent/'final_fit_coverage_audit_original.json')==r['original_actual_hold_receipt_sha256'],'original actual HOLD preserved')
need(all(not (root/'research/forecast-v2'/name).exists() for name in ['FIT_COVERAGE.json','MODEL_SELECTION.json','BLIND_REGISTRY.json']),'no live coverage selection or registry freeze')
queued,acquired,finished=[datetime.datetime.fromisoformat(r[k]) for k in ['queued_utc','acquired_utc','finished_utc']];need(queued<=acquired<finished and r['elapsed_seconds']>0 and abs((finished-acquired).total_seconds()-r['elapsed_seconds'])<.1,'saved lease chronology and elapsed consistency')
expected=raw['expected'];split=load(metadata_pointer(expected['split']));us=split['fit']['us_perimeter_and_kriged'];kr=split['fit']['korean_kriged_only'];folds=split['development_folds']['folds']
need(len(us)==23 and len(kr)==11 and expected['intended_us_fit_events']==us and expected['intended_kriged_fit_events']==us+kr,'complete fixed source-event populations')
need(set(folds)=={'2020','2021','2022'} and set(e for v in folds.values() for e in v)==set(us),'development fold partition')
ledger=expected['ledger'];need(set(ledger['perimeter'])==set(us) and set(ledger['kriged'])==set(us+kr),'all source-kind ledger keys including zero windows')
for kind,events in ledger.items():
 for event,entry in events.items():
  cases=entry['cases'];need(entry['sample_count']==len(cases),'ledger count '+kind+'/'+event)
  for case in cases:
   need(case['event']==event and case['kind']==kind and case['case_id']==objsha({k:v for k,v in case.items() if k!='case_id'}),'case descriptor identity '+case['case_id'])
   a,b=[pd.Timestamp(case[k]) for k in ['cutoff','endpoint']];need(a.tzinfo is not None and b.tzinfo is not None and a<b and (0<b.value-a.value<=48*3600*10**9 if kind=='perimeter' else b.value-a.value==12*3600*10**9),'case metadata clock '+case['case_id'])
perimeter=[c for e in us for c in ledger['perimeter'][e]['cases']];mixed=perimeter+[c for e in us+kr for c in ledger['kriged'][e]['cases']]
need(perimeter==expected['perimeter_cases'] and mixed==expected['mixed_cases'] and len(perimeter)==1303 and len(mixed)==4391,'independent metadata full ordered membership 1303+3088')
for kind,cases in [('perimeter',perimeter),('mixed',mixed)]:need(expected[kind+'_membership_sha256']==objsha(sorted(c['case_id'] for c in cases)) and len({c['case_id'] for c in cases})==len(cases),'full unique membership digest '+kind)
audit=load(metadata_pointer(raw['cache_audit']));need(audit['status']=='PASS_NO_CONSUMED_VALUES_CHANGED' and audit['mismatches']==[] and audit['producer_unchanged_during_audit'] is True,'saved cache source-authentication status')
need(audit['environment_caches']==4296 and audit['active_sample_caches']==114 and audit['obsolete_sample_caches']==34,'saved cache denominators')
rows={str(Path(row['cache']).resolve()):row for row in audit['records'] if row['kind']=='sample-list'}
need(len(raw['cache_files'])==len(raw['development_cache_files'])==57,'57 full and57 prefix cache identity records')
for family,first in [('cache_files',0),('development_cache_files',3)]:
 for kind,events in ledger.items():
  for event,entry in events.items():
   prefix='perimeter_crop' if kind=='perimeter' else 'kriged_utc_v2';name=f'samples/{prefix}_first{first}_{event}.pkl';cases=entry['cases'] if not first else entry['cases'][:first]
   if name not in raw[family]:need(entry.get('reason')=='REGION_ABSENT_UNDER_EXISTING_RECIPE' and not cases,'explicit unavailable cache absence '+name);continue
   record=raw[family][name];source=rows[str((Path(raw['cache_root'])/name).resolve())]
   need(record['case_ids']==[c['case_id'] for c in cases] and record['sample_count']==len(cases),'cache metadata exact case prefix '+name)
   need(source['status']=='MATCHES_RECOMPUTED_SOURCES' and record['sha256']==source['cache_sha256'] and record['sample_values_sha256']==source['cached_value_identity']==source['recomputed_value_identity'],'cache/value source receipt consistency '+name)
# Parse fixed executable constants without importing/running its implementation.
module=ast.parse((root/r['executed_auditor']['path']).read_text());constants={n.targets[0].id:ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='_RECIPE_SOURCE_VERSIONS'}['_RECIPE_SOURCE_VERSIONS']
def phase_source(record):
 phase=record['intended_phase'];p=record['producer_source_sha256'];contract=record['source_schedule_contract']['producer_version'];digest=objsha(p)
 need(digest in constants and phase['phase_id'] in constants[digest] and contract['closure_sha256']==digest and contract['verified_source_files']==len(p) and contract['intended_phase']==phase['phase_id'],'fixed phase producer profile '+phase['phase_id'])
 execution=load(metadata_pointer(record['execution']));need(execution['exit_code']==0 and execution['source_sha256']==p,'execution source receipt '+phase['phase_id']);metadata_pointer(record['fit_result'])
def membership(record,cases,label):
 ids=[c['case_id'] for c in cases];need(record['cases']==cases and record['sample_count']==len(ids) and record['ordered_ids_sha256']==objsha(ids) and record['membership_sha256']==objsha(sorted(ids)),'independent metadata member reconstruction '+label);return ids
need(len(raw['development'])==21 and set(raw['variants'])=={'base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base'},'21development plus7final intended phases')
dev_summary=[]
for phase_id,record in raw['development'].items():
 phase=record['intended_phase'];variant=phase['variant'];fold=phase['fold'];train_events=[e for key,events in folds.items() if key!=fold for e in events];val_events=folds[fold]
 train=[c for e in train_events for c in ledger['perimeter'][e]['cases'][:3]]
 if variant=='mixed_base':train += [c for e in train_events+kr for c in ledger['kriged'][e]['cases'][:3]]
 validation=[c for e in val_events for c in ledger['perimeter'][e]['cases'][:3]]
 need(record['train_events']==train_events and record['validation_events']==val_events,'fold event order '+phase_id);ids=membership(record['training'],train,'train/'+phase_id);membership(record['validation'],validation,'validation/'+phase_id)
 args=record['budget']['effective_arguments'];need(all(int(args[k])==v for k,v in [('epochs',3),('seed',0),('max_fit_intervals_per_fire',3),('samples_per_step',1),('hidden',16)]) and float(args['lr'])==.003 and record['budget']['balanced'] is True,'fixed declared development budget '+phase_id)
 cap=int(args['intervals_per_epoch']);need((cap==0 and record['budget']['interval_cap_status']=='UNRESTRICTED_CAP_ZERO') or (cap>=len(ids)>0 and record['budget']['interval_cap_status']=='NONBINDING_CAP'),'literal nonbinding cap '+phase_id)
 need(record['runtime_membership'] is None and record['schedule_evidence']=='SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED' and len(record['epochs'])==3,'historical inference qualification '+phase_id)
 for index,epoch in enumerate(record['epochs'],1):
  skipped=epoch['source_derived_skipped_samples'];skipids=[p['case']['case_id'] for p in skipped];optimized=epoch['source_derived_optimized_case_ids'];need(epoch['epoch']==index and epoch['optimizer_steps']==len(optimized)>0 and set(optimized).isdisjoint(skipids) and len(optimized)+len(skipids)==len(ids) and set(optimized)|set(skipids)==set(ids),'complete inferred epoch partition '+phase_id+'/'+str(index))
  expected_logs=collections.Counter((p['case']['event'],pd.Timestamp(p['case']['cutoff']).isoformat(),p['reason']) for p in skipped);actual_logs=collections.Counter((p['event'],pd.Timestamp(p['cutoff']).isoformat(),p['reason']) for p in epoch['actual_logged_skips']);need(expected_logs==actual_logs and 'NO_RUNTIME_CASE_IDS' in epoch['evidence'],'source-bound logged skip accounting '+phase_id+'/'+str(index))
 phase_source(record);dev_summary.append(dict(phase=phase_id,training=len(ids),validation=len(validation),cap=cap,skips=[len(e['source_derived_skipped_samples']) for e in record['epochs']]))
final_summary=[]
for variant,record in raw['variants'].items():
 cases=mixed if variant=='mixed_base' else perimeter;ids=[c['case_id'] for c in cases]
 need(record['sample_count']==len(ids) and record['membership_sha256']==objsha(sorted(ids)),'full final membership '+variant);need(len(record['recorded_epochs'])==3,'three final epochs '+variant)
 if variant!='mixed_base':
  need(record['runtime_membership'] is None and 'NO_RUNTIME_IDS_RECORDED' in record['schedule_evidence'] and all(e['epoch']==i and e['optimizer_steps']==len(ids) and not e['skipped_unsupported_intervals'] for i,e in enumerate(record['recorded_epochs'],1)),'pure complete source-inferred optimizer epochs '+variant)
 else:
  epochs=record['runtime_membership']['epochs'];parts=record['epoch_optimized_and_unsupported'];need(len(epochs)==len(parts)==3,'three mixed runtime ledgers')
  for i,(epoch,part,history) in enumerate(zip(epochs,parts,record['recorded_epochs']),1):
   attempted=epoch['attempted_case_ids'];skipped=epoch['skipped_case_ids'];optimized=part['optimized_case_ids'];proofs=part['skipped_samples']
   need(epoch['epoch']==i and len(attempted)==len(set(attempted))==len(ids) and set(attempted)==set(ids) and epoch['attempted_case_ids_sha256']==objsha(attempted),'complete mixed attempted identities '+str(i))
   need(len(skipped)==len(set(skipped))==15 and set(skipped)=={p['case']['case_id'] for p in proofs} and optimized==[v for v in attempted if v not in set(skipped)] and part['optimized_case_ids_sha256']==objsha(optimized),'mixed disjoint identity partition '+str(i))
   need(epoch['optimizer_steps']==history['optimizer_steps']==len(optimized)==4376 and len(history['skipped_unsupported_intervals'])==15,'4376updates plus15explicitunsupported '+str(i))
   need('NOT_RUNTIME_LOGGED' in part['optimized_identity_evidence'] and all('NOT_PER_OPTIMIZER_MASK_REPLAY' in p['evidence'] for p in proofs),'mixed inference versus mask replay qualification '+str(i))
 phase_source(record);final_summary.append(dict(variant=variant,samples=len(ids),optimizer_steps=[e['optimizer_steps'] for e in record['recorded_epochs']],unsupported=[len(e['skipped_unsupported_intervals']) for e in record['recorded_epochs']]))
result=dict(status='PASS_BOUNDED_PROVISIONAL_METADATA_REVIEW',checks=len(checks),passed=sum(c['pass_check'] for c in checks),checks_detail=checks,artifact_sha256=pins,raw_diagnostic_uncompressed_sha256=hashlib.sha256(raw_bytes).hexdigest(),executed_auditor=r['executed_auditor'],checked_live_auditor_dependency=oldF,development=dev_summary,final=final_summary,raw_non_admission_tested=False,original_actual_hold_preserved=True,actual_member_or_cache_value_replay=False,actual_auditor_rerun=False,raw_input_model_heldout_arrays_accessed=False,limitations=['Receipt/custody and internally source-bound membership metadata only; no independent actual source/cache/member-value replay.','Candidate65 executed while live175 was a checked dependency. A fresh live-main audit remains mandatory after the authorized source boundary.','Only the exposed provisional wrapper has a documented old-main refusal; the compressed raw PASS payload is a diagnostic, and its nonadmission was not tested.','Historical IDs remain source-derived; optimized mixed IDs are inferred from runtime attempts minus runtime skipped IDs, not separately logged optimizer IDs or per-step mask replay.'])
(here/'REVIEW_PROVISIONAL.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}))
