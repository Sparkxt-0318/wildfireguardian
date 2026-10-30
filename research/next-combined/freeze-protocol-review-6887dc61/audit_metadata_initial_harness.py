"""Independent frozen JSON/Markdown reconciliation; never opens models or arrays."""
from pathlib import Path
from datetime import datetime,timedelta
import collections,hashlib,json,math,re,subprocess
ROOT=Path(__file__).resolve().parent
checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('duplicate JSON key '+k)
  d[k]=v
 return d
def load(n):return json.loads((ROOT/n).read_text(),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def note(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def utc(s):
 d=datetime.fromisoformat(s.replace('Z','+00:00'));assert d.tzinfo is not None;return d
S,R,H,C,U,K=map(load,['MODEL_SELECTION.json','BLIND_REGISTRY.json','FREEZE_HANDOFF.json','FIT_COVERAGE.json','PREASSESSMENT_US2024_TIMESTAMPS.json','PREASSESSMENT_KOREA2025_WINDOWS.json']);split=load('SPLIT.json');protocol=load('RUN_PROTOCOL.json');doc=(ROOT/'preregistration_blind_test.md').read_text();flat=' '.join(doc.split());pins=load('INPUT_SHA256.json')
variants=['base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base'];cp=S['checkpoints'];score=S['development_brier'];argmin=min(variants,key=lambda n:(score[n],variants.index(n)))
note('selection_fixed_argmin_and_rule',set(score)==set(variants) and all(type(x) in [int,float] and math.isfinite(x) for x in score.values()) and argmin==S['selected_variant']==H['selected_variant']=='d4_wind' and R['selected_model']=='d4_wind_seed0',dict(argmin=argmin,brier=score[argmin],criterion=S['criterion']))
note('all_seven_CP_metadata_equal_across_artifacts',set(cp)==set(variants) and len({v['sha256'] for v in cp.values()})==7 and all(cp[v]==H['checkpoints'][v]==R['models'][v+'_seed0']==C['variants'][v]['checkpoint'] for v in variants))
note('corrected_spotting_phase_only',cp['burnout_spotting']['path'].endswith('burnout_spotting_seed0_flaming_only/checkpoint.pt') and R['spotting_source_contract']['source_mode']=='flaming_only' and S['current_phase']==R['current_phase']==C['current_phase'])
note('eight_CP_identities_include_original_c651',len(R['models'])==8 and R['models']['c651_mc']['sha256']=='c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843' and set(R['models'])=={v+'_seed0' for v in variants}|{'c651_mc'})
note('baseline_metadata_equal_fixed8h',S['baselines']==R['baselines']==H['baselines'] and R['logistic']==S['baselines']['logistic'] and R['best_dilation_hours_per_cell']==H['best_dilation_hours_per_cell']==8)
table={label.strip():h for label,h in re.findall(r'^\|\s*(.*?)\s*\|\s*`([0-9a-f]{64})`\s*\|',doc,re.M)}
note('protocol_exact_CP_and_baseline_table',all(table.get(v+'_seed0'+(' (primary)' if v=='d4_wind' else ''))==cp[v]['sha256'] for v in variants) and table.get('c651_mc and c651_meanfield')==R['models']['c651_mc']['sha256'] and all(table.get(name)==S['baselines'][key]['sha256'] for name,key in [('logistic.pkl','logistic'),('logistic.json','logistic_parameters'),('dilation_choice.json','dilation_choice')]))
note('coverage_selection_registry_document_pins',S['fit_coverage']==R['fit_coverage']==dict(path='research/forecast-v2/FIT_COVERAGE.json',sha256=sha(ROOT/'FIT_COVERAGE.json')) and R['selection']==dict(path='research/forecast-v2/MODEL_SELECTION.json',sha256=sha(ROOT/'MODEL_SELECTION.json')) and R['producer_source_sha256']['forecast/documents/preregistration_blind_test.md']==sha(ROOT/'preregistration_blind_test.md') and sha(ROOT/'MODEL_SELECTION.json') in doc and sha(ROOT/'FIT_COVERAGE.json') in doc)
note('handoff_all_six_external_file_pins',all(H['files_sha256'].get(rel)==meta['sha256']==sha(ROOT/Path(rel).name) for rel,meta in pins.items() if Path(rel).name!='FREEZE_HANDOFF.json') and len(H['files_sha256'])==6)
note('current_development_membership21_and_hash',len(S['development_phases'])==len(C['development'])==21 and S['development_phases']==R['development_phases'] and digest(C['development'])==S['development_coverage_sha256']==R['development_coverage_sha256'])
note('final_result_execution_refs_equal',all(R['final_results'][v]==C['variants'][v]['fit_result'] and R['final_executions'][v]==C['variants'][v]['execution'] for v in variants))
note('pure_final3x1303_accounting_metadata',all(C['variants'][v]['sample_count']==1303 and len(C['variants'][v]['recorded_epochs'])==3 and [x['epoch'] for x in C['variants'][v]['recorded_epochs']]==[1,2,3] and all(x['optimizer_steps']==1303 and x['skipped_unsupported_intervals']==[] for x in C['variants'][v]['recorded_epochs']) and C['variants'][v]['schedule_evidence']=='SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED' for v in variants if v!='mixed_base'))
M=C['variants']['mixed_base'];expected={x['case_id'] for x in C['expected']['mixed_cases']};mixed_ok=True
for e,runtime,recorded in zip(M['epoch_optimized_and_unsupported'],M['runtime_membership']['epochs'],M['recorded_epochs']):
 attempted=runtime['attempted_case_ids'];optimized=e['optimized_case_ids'];skipped=[x['case']['case_id'] for x in e['skipped_samples']]
 mixed_ok &= len(attempted)==len(set(attempted))==4391 and set(attempted)==expected and len(optimized)==len(set(optimized))==4376 and len(skipped)==len(set(skipped))==15 and not set(optimized)&set(skipped) and set(optimized)|set(skipped)==expected and set(runtime['skipped_case_ids'])==set(skipped) and runtime['optimizer_steps']==recorded['optimizer_steps']==4376 and all(x['supported_positive_weight_cells']==0 and x['reference_positive_weight_cells']>0 and x['reason']=='no_supported_positive_weight_cells' for x in e['skipped_samples'])
note('mixed3x4391_attempt_partition4376plus15',M['sample_count']==4391 and len(M['epoch_optimized_and_unsupported'])==3 and mixed_ok and M['coverage_status']=='FULL_INPUT_ATTEMPTED_WITH_LOGGED_UNSUPPORTED')
note('fit_cohort_and_heldout_sets_disjoint',len(C['expected']['intended_us_fit_events'])==23 and set(C['expected']['intended_us_fit_events'])==set(split['fit']['us_2020_2023']) and not set(split['held_out']['us_2024'])&set(C['expected']['intended_us_fit_events']) and not set(split['held_out']['korea_2025'])&set(C['expected']['intended_kriged_fit_events']))
ucount=dict(collections.Counter(x['event'] for x in U['cases']));note('US273_exact_unique_metadata_cases',len(U['cases'])==len({(x['event'],x['cutoff'],x['endpoint']) for x in U['cases']})==U['case_count']==273 and len(ucount)==U['fire_count']==6 and set(ucount)==set(split['held_out']['us_2024']) and all(ucount[e]==U['per_fire'][e]['eligible_duration_intervals']==U['per_fire'][e]['catalog_time_available_intervals'] for e in ucount),ucount)
note('US_duration_exact_boundary_and_no_extra_exclusions',all(timedelta(0)<utc(x['endpoint'])-utc(x['cutoff'])<=timedelta(hours=48) and math.isclose(x['hours'],(utc(x['endpoint'])-utc(x['cutoff'])).total_seconds()/3600,abs_tol=1e-12) for x in U['cases']) and U['exclusions']==[] and U['float_vs_exact_48h_disagreement_events']==[] and all(U['matches_source_manifest_duration_counts'].values()))
reconstructed=[];proposed_ok=True
for event in K['event_metadata']:
 t0,start,end=map(utc,[event['t0_utc'],event['start_utc'],event['end_utc']]);want=[];proposals=[]
 for hours in range(math.floor(event['arrival_minimum_hours']),math.ceil(event['arrival_maximum_hours']),12):
  cutoff=(t0+timedelta(hours=hours)).replace(minute=0,second=0,microsecond=0);elapsed=(cutoff-t0).total_seconds()/3600
  reason='OUTSIDE_CATALOG_CUTOFF_WINDOW' if not start<=cutoff<=end else 'NO_INITIAL_MAPPED_CELL_FROM_TEMPORAL_MINIMUM' if elapsed<event['arrival_minimum_hours'] else None
  proposals.append((cutoff.isoformat(),float(hours),elapsed,reason))
  if reason is None:want.append(dict(event=event['event'],cutoff=cutoff.isoformat(),endpoint=(cutoff+timedelta(hours=12)).isoformat(),hours=12.0))
 proposed_ok &= [(x['cutoff'],x['proposed_start_hours'],x['elapsed_hours'],x['excluded_reason']) for x in event['proposed']]==proposals and [x['case'] for x in event['cases']]==want and len(want)==event['window_count'] and event['year']==t0.year==2025
 reconstructed.extend(want)
actual=[x['case'] for x in K['cases']];kcount=dict(collections.Counter(x['event'] for x in actual));note('KR33_reenumerated_only_from_frozen_timestamp_metadata',proposed_ok and actual==reconstructed and len(actual)==len(K['case_ids'])==len(set(K['case_ids']))==K['case_count']==33 and K['case_ids']==[x['case_id'] for x in K['cases']] and kcount==K['event_counts']=={'KFS_01':8,'KFS_04':14,'KFS_06':8,'KFS_13':3} and set(kcount)==set(split['held_out']['korea_2025']),kcount)
note('KR_no_endpoint_clipping',all(utc(x['endpoint'])-utc(x['cutoff'])==timedelta(hours=12) for x in actual),dict(endpoints_after_catalog_end=sum(utc(x['endpoint'])>utc(next(e['end_utc'] for e in K['event_metadata'] if e['event']==x['event'])) for x in actual)))
note('handoff306_current_case_counts_pinned',H['total_expected_current_cases']==U['case_count']+K['case_count']==306 and H['cohorts']['us2024']['expected_cases']==273 and H['cohorts']['us2024']['event_case_counts']==ucount and H['cohorts']['korea2025']['expected_cases']==33 and H['cohorts']['korea2025']['event_case_counts']==kcount and H['cohorts']['us2024']['metadata_only_membership_sha256']==sha(ROOT/'PREASSESSMENT_US2024_TIMESTAMPS.json') and H['cohorts']['korea2025']['metadata_only_membership_sha256']==sha(ROOT/'PREASSESSMENT_KOREA2025_WINDOWS.json'))
note('pre_inference_future_and_OSF_states_explicit',H['heldout_inference_started'] is False and H['external_OSF_registration'] is False and H['future_2026_execution']==R['execution_status']=='NOT_READY_FOR_2026_EXECUTION' and R['future_inputs_pinned'] is False and R['protocol_status']=='READY_FOR_OWNER_REGISTRATION' and R['documentary_clearance_contract']['machine_authentication'] is False)
note('chronology_selection_registry_handoff',utc(S['frozen_utc'])<utc(R['generated_utc'])<utc(H['frozen_utc']) and S['frozen_before_heldout_scoring'] is True and H['protocol_document_added_after_selection'] is True and H['registry_generated_after_protocol'] is True and S['frozen_utc'] in doc,dict(selection=S['frozen_utc'],registry=R['generated_utc'],handoff=H['frozen_utc']))
note('registry86_source_dependencies_no_self',len(R['producer_source_sha256'])==H['source_pins']==86 and 'research/forecast-v2/BLIND_REGISTRY.json' not in R['producer_source_sha256'] and 'research/forecast-v2/FREEZE_HANDOFF.json' not in R['producer_source_sha256'])
contents={n:(ROOT/n).read_text() for n in ['FIT_COVERAGE.json','MODEL_SELECTION.json','preregistration_blind_test.md','BLIND_REGISTRY.json','FREEZE_HANDOFF.json','PREASSESSMENT_US2024_TIMESTAMPS.json','PREASSESSMENT_KOREA2025_WINDOWS.json']};hashes={n:sha(ROOT/n) for n in contents};edges={n:[m for m in contents if hashes[m] in contents[n]] for n in contents};visiting=set();done=set()
def visit(n):
 if n in visiting:return False
 if n in done:return True
 visiting.add(n)
 for dep in edges[n]:
  if not visit(dep):return False
 visiting.remove(n);done.add(n);return True
note('acyclic_hash_dependencies_without_self_reference',all(n not in deps for n,deps in edges.items()) and all(visit(n) for n in contents),edges)
requirements={'fixed_future_deadline':'2027-12-31 23:59:00 UTC','all_fire_minimum_no_optional_stopping':'fewer than ten US fires qualify','primary_inconclusive':'primary test INCONCLUSIVE','no_favorable_early_stop':'There is no early stopping on a favourable score','whole_fire_bootstrap':'10,000 whole-fire bootstrap','fixed_bootstrap_seed':'seed 20261030','all_seven_reported':'All seven final variants are secondary comparisons','no_future_FARSITE_column':'has no FARSITE prediction column','separate_Korean_assessment':'Korean reconstruction results are never pooled with NIROPS mapped extents','no_posthoc_replacement':'no post-hoc replacement','fixed_MC_count':'1,024 trajectories, blocks of 32','clipped_NLL_limit':'floor 1e-7','explicit_replay_execution':'matching copied files alone are not proof of independent execution','documentary_human_only':'It never authenticates human independence','failed_cases_primary_closed':'Any failed or unavailable case prevents every complete- cohort primary promotion field','chronology_cannot_manufacture_blindness':'do not choose a later release to manufacture that chronology'}
note('protocol_frozen_metrics_cohorts_stopping_and_documentary_boundaries',all(v in flat for v in requirements.values()),{key:val in flat for key,val in requirements.items()})
note('current_and_future_commands_prescribed_not_executed',all(x in flat for x in ['audit_fit_coverage.py --model-root','run_campaign.py freeze --attempt 3','freeze_registry.py --model-root','blind_inventory.py --input-root','blind_test.py validate','blind_test.py run','blind_test.py score','blind_test.py finalize']) and 'first cohort HOLD never cancels second' in H['scoring_invocations'] and H['command_exit_codes']==[0,0])
note('no_authored_em_dash',chr(0x2014) not in doc)
result=dict(status='PASS_BOUNDED_FROZEN_METADATA_RECONCILIATION' if all(x['passed'] for x in checks) else 'HOLD_METADATA_FINDING',scope='Committed JSON/Markdown metadata only. No model/data/cache arrays, scorer, forecast, heldout output or source-code execution. Binary/source86/201 custody is separately verified by parent. No scientific or 2026 execution clearance.',commit='6887dc618253e6568c6cbbfd3c9a96f1d0d86b70',checks=checks,passed=sum(x['passed'] for x in checks),total=len(checks),failures=[x for x in checks if not x['passed']]);(ROOT/'AUDIT_METADATA.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(result['failures']))
