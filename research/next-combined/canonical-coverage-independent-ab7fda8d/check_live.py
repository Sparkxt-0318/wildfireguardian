"""Canonical LIVE coverage saved-metadata/custody review. Never reruns actual auditor."""
import ast,collections,datetime,gzip,hashlib,json,math,subprocess
from pathlib import Path
import pandas as pd
here=Path(__file__).resolve().parent
root=here.parent/'track-1b'
base=root/'research/forecast-v2'
prior=base/'review/provisional_coverage_F65'
checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def objsha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def need(ok,label):
 checks.append(dict(id=label,pass_check=bool(ok)))
 if not ok:raise ValueError(label)
def load(p):return json.loads(Path(p).read_text())
def metadata_pointer(value):
 p=root/value['path'];need(p.suffix in ['.json','.py','.md','.toml'],'metadata-only pointer extension '+value['path']);need(sha(p)==value['sha256'],'metadata pointer '+value['path']);return p
pins={
 'FIT_COVERAGE.json':'4c4330d841b4ac0ad0259ba04f781a5c386352da1e91358fbc2aee51276ca971',
 'executions/final_fit_coverage_audit_v2.json':'98981a151429d27ed0acde368a6bbf8725f78ae7855d0da3e332fbd397775358',
 'executions/final_fit_coverage_audit_v2.log':'a9aad7c533dcae1a265baa54cfbce0c6774f2fc72e7c9915084a7bf0dba1f045',
 'executions/final_software_gate_v2.json':'2823830161c045a3af96d8dde0540e0adcd422832167fa37061fc4643b615e7e',
 'scripts/audit_fit_coverage.py':'65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536',
 'review/provisional_coverage_F65/PREFLIGHT_RECEIPT.json':'6df0eaf4f3daf6e67c3cbe3c0cf7e5cd85f5498d1bf7e26fa19f66ceccedf8e7',
 'review/provisional_coverage_F65/COVERAGE_PROVISIONAL.json':'12ed2aae675e78a355312c24d56fd2183b313c0238c3de8a2723964e71c3bbd6',
 'review/provisional_coverage_F65/candidate_raw.json.gz':'5a45558a5b32c1a2350e52871fb010c828757c82c6e5bbee2e05efdf45987b29',
 'review/provisional_coverage_F65/PREFLIGHT.log':'a5e4ae58a2fd525ddc220090fe3547b7b0cb3ef34d3404d24c610f24f01bdfd0',
}
HEAD='ab7fda8d9d0a87df95c05406ae4505eccff52aac'
need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==HEAD,'exact committed canonical head')
for name,digest in pins.items():need(sha(base/name)==digest,'parent pin '+name)
need(sha(here.parent/'coverage-provisional-independent-review/REVIEW_PROVISIONAL.md')=='7d0e25ab8fa9164c2907051a456810dad6e6a86536c39b184e088747ad28e050','prior provisional report immutable')
need(sha(here.parent/'coverage-actual-recipe-repair/final_fit_coverage_audit_original.json')=='ce7727c10e68cce536dbb0f1a56b68add941a46fab8c244f12ddf23e527d5633','original actual HOLD preserved')
raw=load(base/'FIT_COVERAGE.json');r=load(base/'executions/final_fit_coverage_audit_v2.json');gate=load(base/'executions/final_software_gate_v2.json');provisional=json.loads(gzip.decompress((prior/'candidate_raw.json.gz').read_bytes()));pre=load(prior/'PREFLIGHT_RECEIPT.json')
changes=[]
def difference(a,b,path=''):
 if type(a)!=type(b):changes.append(dict(path=path,old=a,new=b));return
 if isinstance(a,dict):
  for k in sorted(a.keys()|b.keys()):
   if k not in a or k not in b:changes.append(dict(path=path+'/'+k,old=a.get(k),new=b.get(k)))
   else:difference(a[k],b[k],path+'/'+k)
 elif isinstance(a,list):
  if len(a)!=len(b):changes.append(dict(path=path,old_length=len(a),new_length=len(b)));return
  for i,(x,y) in enumerate(zip(a,b)):difference(x,y,path+'/'+str(i))
 elif a!=b:changes.append(dict(path=path,old=a,new=b))
difference(provisional,raw)
F='research/forecast-v2/scripts/audit_fit_coverage.py'
need(changes==[dict(path='/source_sha256/'+F,old='1753cf31b21be093e13d61a107e407cf41542e9ec6dbe4c8ced924f5a5320cf4',new=pins['scripts/audit_fit_coverage.py'])],'canonical differs only by authorized live F65 provenance')
need(raw['status']=='PASS_COMPLETE_FIT_MEMBERSHIP' and r['status']=='PASS' and r['exit_code']==0,'canonical PASS status and execution exit')
need(r['output_sha256']==pins['FIT_COVERAGE.json'] and r['log_sha256']==pins['executions/final_fit_coverage_audit_v2.log'] and r['software_gate_sha256']==pins['executions/final_software_gate_v2.json'],'canonical receipt output log and software-gate identities')
need(load(base/'executions/final_fit_coverage_audit_v2.log')==dict(status=raw['status'],artifact=str((base/'FIT_COVERAGE.json').resolve()),sha256=pins['FIT_COVERAGE.json']),'canonical raw log output identity')
command=r['command']
need(command[1]==str((root/F).resolve()) and not any('candidate' in v for v in command),'canonical executes exact live F65 command')
args={'--model-root':root,'--input-root':Path(raw['input_root']),'--cache-root':Path(raw['cache_root']),'--run-root':Path(raw['run_root']),'--cache-audit':root/raw['cache_audit']['path'],'--out':base/'FIT_COVERAGE.json'}
for flag,value in args.items():need(command.count(flag)==1 and Path(command[command.index(flag)+1]).resolve()==value.resolve(),'canonical command pointer '+flag)
need(len(raw['source_sha256'])==61 and raw['source_sha256'][F]==pins['scripts/audit_fit_coverage.py'],'all61 current canonical source identities include live F65')
for name,digest in raw['source_sha256'].items():need(Path(name).suffix in ['.py','.json'] and sha(root/name)==digest,'current canonical61 source '+name)
need(r['changed_source']==r['changed_gate_source']==[],'saved canonical bookend attestation contains no changed source')
need(set(r['source_sha256'])=={'forecast/wildfire/survival.py',F,'research/forecast-v2/scripts/pipeline.py'} and all(raw['source_sha256'][k]==v for k,v in r['source_sha256'].items()),'canonical critical source receipt equals coverage closure')
need(r['software_gate_source_sha256']==gate['source_sha256'] and len(gate['source_sha256'])==201,'canonical custody references exact201 software-gate sources')
for name,digest in gate['source_sha256'].items():need(Path(name).suffix in ['.py','.json','.toml'] and sha(root/name)==digest,'current saved software-gate source '+name)
need(gate['status']=='PASS' and gate['changed_source_during_gate']==[] and gate['protected_path_changes']==[] and gate['c651_matches_frozen_default'] is True,'saved software and protected/default gate flags')
need({c['name'] for c in gate['checks']}=={'pytest','release'} and all(c['exit_code']==0 for c in gate['checks']),'saved software checks passed')
for c in gate['checks']:
 need(sha(root/c['log'])==c['log_sha256'],'software raw log identity '+c['name'])
 log=(root/c['log']).read_text();need(('3507 passed' in log if c['name']=='pytest' else '367' in log),'software raw log declared denominator '+c['name'])
q,a,f=[datetime.datetime.fromisoformat(r[k]) for k in ['queued_utc','acquired_utc','finished_utc']]
need(q<=a<f and abs((f-a).total_seconds()-r['elapsed_seconds'])<.1 and r['elapsed_seconds']>0,'canonical saved lease chronology and elapsed')
need(datetime.datetime.fromisoformat(gate['finished_utc'])<a,'canonical fresh audit after software gate completed')
need(all(not (base/name).exists() for name in ['MODEL_SELECTION.json','BLIND_REGISTRY.json']),'selection and registry not yet present at review')
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
module=ast.parse((root/'research/forecast-v2/scripts/audit_fit_coverage.py').read_text());constants={n.targets[0].id:ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='_RECIPE_SOURCE_VERSIONS'}['_RECIPE_SOURCE_VERSIONS']
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

for name,digest in pins.items():need(sha(base/name)==digest,'pins unchanged at review end '+name)
result=dict(status='PASS_BOUNDED_CANONICAL_COVERAGE_METADATA_CUSTODY_REVIEW',source_head=HEAD,checks=len(checks),passed=sum(c['pass_check'] for c in checks),checks_detail=checks,artifact_sha256=pins,canonical_vs_provisional_changes=changes,development=dev_summary,final=final_summary,actual_member_or_cache_value_replay=False,actual_auditor_rerun=False,raw_input_model_heldout_arrays_accessed=False,source_window_evidence='Saved canonical receipt attests unchanged three critical sources and 201 gate sources; independently rehashed current61 and201 maps, not independently observed both historical runtime bookends.',limits=['Canonical source/custody, saved ledger and membership metadata only; no independent actual array/cache/value replay.','Historical pure and development IDs remain source inferred. Mixed optimized IDs are attempted minus runtime skipped, not separately logged optimizer identities or per-step mask replay.','Prior source-only99 and provisional9612 predicate reviews remain separate. Raw provisional nonadmission remains untested; canonical fresh live command supplies its own provenance.','No selection or registry was present during review. Their freeze and heldout authorization remain separate.'])
(here/'CHECKS.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','source_head','checks','passed','canonical_vs_provisional_changes']},indent=2))
