"""Independent saved-output audit. Never invokes planner, simulator or owner analyzer."""
from pathlib import Path
import json, csv, hashlib, collections, statistics, subprocess, math
from datetime import datetime
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on')
ROOT=TASK/'work/audit-1c'
RUN=ROOT/'research/sipp-routing/known-footprint-contact-K-20261030'
OUT=TASK/'work/contact-campaign-review'
checks=[]
def check(name, value, detail=None):
    checks.append(dict(name=name,passed=bool(value),detail=detail))
def load(p): return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()
def dt(s): return datetime.fromisoformat(s)
rows=[json.loads(s) for s in (RUN/'EXECUTIONS.jsonl').read_text().splitlines()]
jobs=load(RUN/'JOBS.json'); bundle=load(RUN/'BUNDLE.json'); analysis=load(RUN/'ANALYSIS.json'); results=load(RUN/'RESULTS.json')
phase='095b8d174d2f203ea67bea5fdd8c69eb0633b2a0'; head='06ad9fe902d0c2077a7623f1d7f8e70b1e0dad4b'
actualhead=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
check('immutable_review_head',actualhead==head and not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
cases=load(ROOT/bundle['protocol']['original_cases']); cases=[x for x in cases if x['panel']=='Korean'] if isinstance(cases,list) else cases
print('CASES_TYPE',type(cases).__name__)
expected=[]
for i,b in enumerate(bundle['bindings']):
    c=b['original_case']
    for K in [4,8,16,32]:
        for rep,methods in [(1,['sweep','sipp']),(2,['sipp','sweep'])]:
            for method in methods: expected.append(dict(job_index=len(expected),case_index=i,mission=c['mission'],region=c['region'],K=K,repetition=rep,method=method))
check('exact_fixed320_schedule',len(bundle['bindings'])==20 and len(rows)==320 and jobs==expected and all(all(r.get(k)==v for k,v in j.items()) for r,j in zip(rows,expected)))
check('original_korean_case_membership',isinstance(cases,list) and [b['original_case'] for b in bundle['bindings']]==cases)
protocol=load(ROOT/'research/sipp-routing/KNOWN_FOOTPRINT_K_PROTOCOL.json')
check('protocol_and_producer_pins',protocol==bundle['protocol'] and sha(ROOT/'research/sipp-routing/KNOWN_FOOTPRINT_K_PROTOCOL.json')==bundle['protocol_sha256']==results['protocol_sha256'] and analysis['producer_sha256']==sha(ROOT/'research/sipp-routing/analyze_known_footprint_campaign.py'))
pins={**protocol['source_pins'],**protocol['evidence_pins']}; badpins=[p for p,h in pins.items() if sha(ROOT/p)!=h]
phase_diff=[p for p,h in pins.items() if hashlib.sha256(subprocess.check_output(['git','show',phase+':'+p],cwd=ROOT)).hexdigest()!=h]
check('all_source_prior_evidence_phase_and_current_bytes',not badpins and not phase_diff,dict(pins=len(pins),bad=badpins,phase_mismatch=phase_diff))
check('source_phase_identity_all_rows',bundle['source_phase_head']==phase and results['source_phase_head']==phase and analysis['source_phase_head']==phase and all(r['source_phase_head']==phase and r['source_hashes']==protocol['source_pins'] for r in rows))
manifest=load(RUN/'OUTPUT_SHA256.json'); actualfiles={str(p.relative_to(RUN)) for p in RUN.rglob('*') if p.is_file() and p.name!='OUTPUT_SHA256.json'}
check('complete_output_manifest',set(manifest)==actualfiles and all(sha(RUN/p)==h for p,h in manifest.items()),dict(count=len(manifest),actual=len(actualfiles)))
inputs={}
for b in bundle['bindings']:
 c=b['original_case']
 for k in ['graph','request']: inputs[c[k]]=c['input_sha256'][k]
 for k in ['NATIVE_METADATA.json','REPORT.json','HAZARD.json','constructed_arrays.npz']: inputs[str(Path(c['packet'])/k)]=c['input_sha256'][k]
 inputs[b['window']['npz']]=b['window']['npz_sha256'];inputs[b['topology']['source']['record']]=b['window']['record_sha256']
check('independent_original115_file_custody',len(inputs)==115 and inputs==load(RUN/'POST_RUN_INPUT_CUSTODY.json')['sha256'] and all(sha(p)==h for p,h in inputs.items()),dict(files=len(inputs),bytes=sum(Path(p).stat().st_size for p in inputs)))
check('preflight_bound_receipt',sha(RUN/'ORIGINAL_INPUT_PREFLIGHT.json')==bundle['preflight_sha256'] and load(RUN/'ORIGINAL_INPUT_PREFLIGHT.json')['status']=='PASS_ORIGINAL_INPUT_PREFLIGHT')
check('all320_raw_job_payloads_match_ledger',all(all(r.get(k)==v for k,v in load(RUN/('job-%03d.json'%r['job_index'])).items()) for r in rows))
check('bounded_child_control_all320',all(r['control']['stop'] is None and r['control']['exit_code']==0 and r['control']['owned_group_absent'] and r['complete_child_wall_s']==r['control']['elapsed_s'] and 0<=r['child_internal_wall_s']<=r['complete_child_wall_s']<30 and all(math.isfinite(r['control'][k]) and 0<=r['control'][k]<=3072 for k in ['sampled_rss_mib','reported_peak_rss_mib']) for r in rows))
check('serialized_nonoverlapping_lease_receipts',all(dt(r['lease_acquired_utc'])<dt(r['lease_released_utc']) for r in rows) and all(dt(a['lease_released_utc'])<=dt(b['lease_acquired_utc']) for a,b in zip(rows,rows[1:])))
unsupported={b['original_case']['mission'] for b in bundle['bindings'] if b['unsupported_endpoints']}
u=[r for r in rows if r['mission'] in unsupported]; search=[r for r in rows if r['search_started']]
check('unknown_endpoints224_null_solver_costs',len(unsupported)==14 and len(u)==224 and all(r['status']=='UNRESOLVED_RESTRICTED_SUPPORT' and not r['search_started'] and r['planner_wall_s'] is None and r['solver_metrics'] is None and r['independent_recheck'] is None for r in u))
checked=[r for r in rows if r['status']=='CHECKED_CONTACT_ROUTE_WITHIN_KNOWN_FOOTPRINT']; ex=[r for r in search if r not in checked]
check('72checked24restricted96search_records',len(checked)==72 and len(ex)==24 and len(search)==96 and all(r['status']=='UNRESOLVED_RESTRICTED_SUPPORT' and r['search_status'] in ['EXHAUSTED','PROVEN_INFEASIBLE','DISCONNECTED'] and r['arrival'] is None for r in ex))
request_ok=True
for r in rows:
 b=bundle['bindings'][r['case_index']];c=b['original_case']; text=r['original_request_utf8']
 request_ok &= hashlib.sha256(text.encode()).hexdigest()==c['input_sha256']['request'] and json.loads(text)==r['original_request'] and r['source']['trajectory_indices']==list(range(r['K'])) and r['source']['source_identity']['saved_original_indices']==list(range(r['K']))
 if r['planner_claim']:request_ok &= r['planner_claim']['original_request']==r['original_request']
check('all_original_requests_history_firstK_indices_preserved',request_ok)
check('all_contact_only_claim_boundaries',all(r['peak'] is None and r['dose'] is None and r['risk'] is None and r['full_policy_status']=='UNKNOWN' and r['physical_safety_claim'] is False and (not r['planner_claim'] or (r['planner_claim']['original_domain_optimality'] is False and r['planner_claim']['original_domain_refusal'] is False and r['planner_claim']['full_policy_status']=='UNKNOWN')) for r in rows))
rechecks=[json.loads(s) for s in (RUN/'INDEPENDENT_RECHECKS.jsonl').read_text().splitlines()]
check('72_separate_rechecks_match_original_rows',len(rechecks)==72 and [x['job_index'] for x in rechecks]==[r['job_index'] for r in checked] and all(x['independent_recheck']==r['independent_recheck'] and x['source']==r['source'] and x['original_request_sha256']==hashlib.sha256(r['original_request_utf8'].encode()).hexdigest() for x,r in zip(rechecks,checked)))
check('72_rechecks_all_K_members_full_dwell_finite_horizon',all(r['independent_recheck']['ok'] and not r['independent_recheck']['violations'] and r['independent_recheck']['arrival']==r['arrival'] and r['arrival']<=r['independent_recheck']['finish_including_dwell']<=3600 and len(r['independent_recheck']['per_member'])==r['K'] and [m['trajectory_index'] for m in r['independent_recheck']['per_member']]==list(range(r['K'])) and all(m['contact_pass'] and not m['violations'] and m['peak'] is None and m['dose'] is None and m['risk'] is None for m in r['independent_recheck']['per_member']) for r in checked))
lookup={(r['mission'],r['K'],r['repetition'],r['method']):r for r in rows}; pairs=[]; ratios=[]; childratios=[];barriers=True;repeats=True
for b in bundle['bindings']:
 mission=b['original_case']['mission']
 for K in [4,8,16,32]:
  for rep in [1,2]:
   a=lookup[mission,K,rep,'sweep'];z=lookup[mission,K,rep,'sipp']
   barriers &= a['source']==z['source']
   if a['planner_claim']: barriers &= a['planner_claim']['support_barriers']==z['planner_claim']['support_barriers']
   if mission in unsupported: verdict='BOTH_PRESEARCH_UNSUPPORTED_ENDPOINTS'
   elif a['status']==z['status']=='CHECKED_CONTACT_ROUTE_WITHIN_KNOWN_FOOTPRINT' and a['arrival']==z['arrival']:verdict='MATCHED_CHECKED_CONTACT_ARRIVAL'
   elif a['status']==z['status']=='UNRESOLVED_RESTRICTED_SUPPORT' and all(v['search_status'] in ['EXHAUSTED','PROVEN_INFEASIBLE','DISCONNECTED'] for v in [a,z]):verdict='MATCHED_RESTRICTED_EXHAUSTION'
   else:verdict='DISAGREE'
   pr=cr=None
   if mission not in unsupported:
    pr=z['planner_wall_s']/a['planner_wall_s'];cr=z['complete_child_wall_s']/a['complete_child_wall_s'];ratios.append(pr);childratios.append(cr)
   pairs.append((mission,K,rep,verdict,pr,cr))
  for method,counter in [('sipp','expansions'),('sweep','states_reached')]:
   a=lookup[mission,K,1,method];z=lookup[mission,K,2,method]
   if a['search_started']:repeats &= a['solver_metrics'][counter]==z['solver_metrics'][counter]
pc=list(csv.DictReader((RUN/'PAIRS.csv').open())); counts=dict(collections.Counter(p[3] for p in pairs))
check('160_pairs_exact_rederived_outcomes',len(pairs)==160 and counts=={'BOTH_PRESEARCH_UNSUPPORTED_ENDPOINTS':112,'MATCHED_CHECKED_CONTACT_ARRIVAL':36,'MATCHED_RESTRICTED_EXHAUSTION':12} and all((p['mission'],int(p['K']),int(p['repetition']),p['verdict'])==x[:4] and (p['planner_ratio_sipp_over_sweep']=='' if x[4] is None else float(p['planner_ratio_sipp_over_sweep'])==x[4]) and (p['complete_child_ratio_sipp_over_sweep']=='' if x[5] is None else float(p['complete_child_ratio_sipp_over_sweep'])==x[5]) for p,x in zip(pc,pairs)),counts)
check('same_pair_sources_barriers_and_repeat_counters',barriers and repeats)
rederived=dict(record_count=len(rows),pairs=len(pairs),missions=len(bundle['bindings']),execution_statuses=dict(collections.Counter(r['status'] for r in rows)),pair_verdicts=counts,unsupported_endpoint_missions=len(unsupported),unsupported_endpoint_records=len(u),search_started_records=len(search),checked_route_records=len(checked),independent_original_data_rechecks_passed=len(rechecks),joint_checked_search_pairs=36,joint_complete_search_pairs=len(ratios),median_planner_ratio_sipp_over_sweep=statistics.median(ratios),median_complete_child_ratio_sipp_over_sweep=statistics.median(childratios),sipp_slower_planner_pairs=sum(x>1 for x in ratios),max_complete_child_wall_s=max(r['complete_child_wall_s'] for r in rows),max_reported_child_peak_rss_mib=max(r['control']['reported_peak_rss_mib'] for r in rows))
check('all_analysis_headlines_rederived',all(analysis[k]==v for k,v in rederived.items()),rederived)
ec=list(csv.DictReader((RUN/'EXECUTIONS.csv').open()))
check('execution_csv_identity_outcomes_costs',len(ec)==320 and all(int(x['job_index'])==r['job_index'] and x['status']==r['status'] and x['arrival']==('' if r['arrival'] is None else str(r['arrival'])) and (x['planner_wall_s']=='' if r['planner_wall_s'] is None else float(x['planner_wall_s'])==r['planner_wall_s']) for x,r in zip(ec,rows)))
result=dict(scope='Bounded independent saved-output/source/control/receipt audit; no planner or model rerun; recheck receipts verified, geometric witnesses not replayed.',review_head=head,source_phase_head=phase,checks=checks,checks_passed=sum(x['passed'] for x in checks),checks_total=len(checks),failures=[x for x in checks if not x['passed']],rederived=rederived,inputs_sha256={str(p.relative_to(ROOT)):sha(p) for p in [RUN/'EXECUTIONS.jsonl',RUN/'ANALYSIS.json',RUN/'OUTPUT_SHA256.json',ROOT/'research/sipp-routing/run_known_footprint_campaign.py',ROOT/'research/sipp-routing/analyze_known_footprint_campaign.py']})
(OUT/'audit_06ad9fe9.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
raise SystemExit(bool(result['failures']))
