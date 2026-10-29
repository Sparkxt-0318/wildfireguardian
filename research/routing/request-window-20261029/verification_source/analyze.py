"""Recompute publication gates and metrics from sealed actual records."""
from pathlib import Path
from fractions import Fraction as Q
from collections import Counter,defaultdict
import csv,hashlib,json,statistics as S
ROOT=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,why):
 if not x:raise RuntimeError(why)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def witness(raw):
 r=raw['result'];route=r if r.get('destination')is not None else r.get('checked_incumbent')
 return None if route is None else{k:route[k]for k in ('legs','arrival','destination','per_member')}
def interval(v):
 lo,hi=Q(v['lower']),Q(v['upper']);need(0<=lo<=hi and Q(v['width'])==hi-lo,'INTERVAL_SCHEMA');return lo,hi
m=read(ROOT/'MANIFEST.json');seal=read(ROOT/'reference/VERIFICATION_INPUTS.json');batch=read(ROOT/'reference/VERIFICATION_BATCH.json')
need(batch['status']=='COMPLETE'and len(batch['records'])==len(seal['groups']),'ALL_REFERENCE_CONTEXTS_COMPLETE')
for p,h in seal['source_sha256'].items():need(sha(p)==h,'SOURCE_CHANGED:'+p)
for n in ('CAMPAIGN_RECEIPT.json','VERIFICATION_RECEIPT.json'):
 g=read(ROOT/'coordination'/n);need(g['returncode']==0 and g['cleanup_verified']and g['lease_release']=='RELEASED'and not g['surviving_observed_owned_processes'],'BATCH_CUSTODY')
grades={}
for rec in batch['records']:
 p=ROOT/'reference/grades'/(str(rec['index']).zfill(2)+'.json');need(sha(p)==rec['grade_sha256'],'GRADE_HASH');need(rec['returncode']==0 and not rec['hard_timeout']and not rec['memory_cap']and not rec['memory_sampling_error'],'GRADE_LEAF_CAP')
 grades[rec['context']]=read(p)
context_map={r['index']:r['context']for r in seal['rows']};rows=[];mission=defaultdict(list);thermal=0;unique_thermal=0;all_records=0;capped=0
for k,g in grades.items():
 if g['route_present']:
  proved=[]
  for b in g['thermal_members']:
   dlo,dhi=interval(b['dose_kj_m2']);plo,phi=interval(b['peak_kw_m2']);flag=dhi<=Q(b['dose_budget_kj_m2'])and phi<=Q(b['peak_budget_kw_m2']);need(flag==b['proved'],'THERMAL_DECISION');proved.append(flag)
   unique_thermal+=1;all_records+=b['refinement']['records_processed'];capped+=bool(b['refinement']['cap'])
  need(g['verified_journey']==bool(g['centre_model']['feasible']and g['whole_road_contact']['status']=='CLEAR'and g['metric_agreement']['status']!='DISAGREE'and all(proved)),'JOURNEY_GRADE_DERIVATION')
for index,row in enumerate(m['jobs']):
 j=read(row['job_file']);folder=Path(row['output_path']);raw=read(folder/'RESULT.json');r=raw['result'];rc=read(folder/'COMPLETE_PROCESS_RECEIPT.json');boundary=read(folder/'PUBLICATION_BOUNDARY.json');grade=grades[context_map[index]]
 need(rc['execution_id']==row['execution_id']and rc['job_sha256']==sha(row['job_file']),'RECEIPT_IDENTITY')
 need(rc['result_sha256']==sha(folder/'RESULT.json')and rc['publication_boundary_sha256']==sha(folder/'PUBLICATION_BOUNDARY.json'),'PUBLICATION_FILE_BINDING')
 samples=rc['rss_samples'];sample_ok=bool(samples)and all(0<=s['rss_bytes']<=3072*1024*1024 and not s['detached']for s in samples)
 need(rc['complete_budget_s']==30 and rc['memory_guard_mib']==3072,'BUDGET_CHANGED')
 ontime=rc['status']=='COMPLETE'and rc['returncode']==0 and rc['stop_reason']is None and rc['elapsed_s']<=30 and rc['cleanup']['status']=='CLEAN'and not rc['cleanup']['remaining']and not rc['cleanup']['detached']and sample_ok and raw['authority_final']is True and boundary['result_published_before_deadline']is True and rc['origin_monotonic']<=boundary['monotonic_after_result_publication']<=rc['origin_monotonic']+30
 need(ontime==rc['on_time_complete_publication'],'DERIVED_PUBLICATION_GATE')
 for k,h in j['input_sha256'].items():need(raw['identities'][k]['sha256']==h,'RAW_INPUT_BINDING')
 for k,h in j['source_sha256'].items():need(raw['identities']['source:'+k]['sha256']==h,'RAW_PACKET_BINDING')
 actual=raw['engine_binding']['actual_imported_core_path'];need(Path(actual).resolve()==Path(j['source_root'])/'baseline/routing-package/routing/core.py'and sha(actual)==j['core_sha256'],'ACTUAL_CORE_IMPORT')
 cert=raw.get('refusal_certificate')or{};wr=raw.get('whole_road_check')or{};w=witness(raw)
 key=digest(dict(inputs=j['input_sha256'],sources=j['source_sha256'],witness=w));need(key==context_map[index],'EXACT_CONTEXT_BINDING')
 route_ok=ontime and w is not None and r['status']in ('CHECKED_ROUTE','CONDITIONAL_OPTIMUM')and wr.get('status')=='CERTIFIED_ADMISSIBLE'and grade.get('verified_journey')is True
 refusal_ok=ontime and w is None and r['status']=='PROVEN_INFEASIBLE'and cert.get('complete')is True and bool(cert.get('scope'))and cert.get('relaxation_kind')=='contact_only_lattice_relaxation'and grade.get('verified_no_route')is True
 state='CHECKED_ROUTE'if route_ok else'MODEL_NO_ROUTE'if refusal_ok else'UNRESOLVED'
 if route_ok:thermal+=len(grade['thermal_members'])
 # Compare complete original witness and scientific inputs, never just equal arrival times.
 original_kit=Path(m['original_queue_path']).parents[1];old=read(original_kit/'raw/LATEST_PRIMARY'/row['original_label']/'RESULT.json')
 same_witness=w==witness(old)
 entry=dict(index=index,execution_id=row['execution_id'],case_id=row['case_id'],cohort=row['cohort'],arm=row['arm'],rep=row['rep'],state=state,on_time=ontime,elapsed_s=rc['elapsed_s'],sampled_family_peak_mib=rc['sampled_family_peak_rss_bytes']/2**20,arrival=None if w is None else w['arrival'],destination=None if w is None else w['destination'],same_historical_witness=same_witness,raw_primary_status=r['status'],raw_reason=r.get('reason'),authority=raw['decision']['authoritative_status'],independent_context=key)
 rows.append(entry);mission[(row['arm'],row['cohort'],row['case_id'])].append(entry)
need(len(rows)==80 and len(mission)==40,'POPULATION')
by_arm={};by_region={}
for arm in ('RDA_BASE','RDA_CAND'):
 selected=[rr for (a,c,case),rr in mission.items()if a==arm];stable=Counter()
 for rr in selected:
  need(len(rr)==2 and {r['rep']for r in rr}=={1,2},'REPETITIONS')
  need(len({r['state']for r in rr})==1,'UNSTABLE_MISSION_CATEGORY')
  stable[rr[0]['state']]+=1
 rs=[r for r in rows if r['arm']==arm];by_arm[arm]=dict(missions=dict(stable),executions=dict(Counter(r['state']for r in rs)),resolved_missions=stable['CHECKED_ROUTE']+stable['MODEL_NO_ROUTE'],median_all_elapsed_s=S.median(r['elapsed_s']for r in rs),max_sampled_family_mib=max(r['sampled_family_peak_mib']for r in rs))
 for region in sorted({r['cohort']for r in rs}):
  rr=[v for (a,c,case),v in mission.items()if a==arm and c==region];by_region.setdefault(region,{})[arm]=dict(Counter(v[0]['state']for v in rr))
pairs=[]
for (a,c,case),rr in mission.items():
 if a!='RDA_BASE':continue
 for b in rr:
  d=next(r for r in mission[('RDA_CAND',c,case)]if r['rep']==b['rep'])
  if b['state']==d['state']=='CHECKED_ROUTE':
   need(b['arrival']==d['arrival'],'PAIRED_ARRIVAL_CHANGED');pairs.append(dict(case_id=case,rep=b['rep'],baseline_s=b['elapsed_s'],candidate_s=d['elapsed_s'],ratio=d['elapsed_s']/b['elapsed_s']))
out=dict(status='VERIFIED_BOUNDED_RESEARCH',missions=20,executions=80,by_arm=by_arm,by_region=by_region,matched_route_pairs=len(pairs),matched_arrivals_equal=True,matched_baseline_median_s=S.median(p['baseline_s']for p in pairs),matched_candidate_median_s=S.median(p['candidate_s']for p in pairs),median_paired_candidate_baseline_ratio=S.median(p['ratio']for p in pairs),candidate_faster_pairs=sum(p['ratio']<1 for p in pairs),historical_witness_presence_and_content_matches=sum(r['same_historical_witness']for r in rows),historical_route_witnesses_unchanged=sum(r['same_historical_witness']and r['arrival']is not None for r in rows),independent_contexts=len(grades),independent_route_contexts=sum(g['route_present']for g in grades.values()),unique_member_threshold_checks=unique_thermal,route_execution_member_assessments=thermal,member_partition_records_processed=all_records,member_partition_count_scope='Sum over member assessments; identical histories reuse the reference calculation, so this is not a count of unique arithmetic operations',capped_member_references=capped,manifest_sha256=sha(ROOT/'MANIFEST.json'),verification_input_sha256=sha(ROOT/'reference/VERIFICATION_INPUTS.json'),verification_batch_sha256=sha(ROOT/'reference/VERIFICATION_BATCH.json'),scope='Fresh 20-mission paired regression. Cumulative implementation changes, not single-factor attribution. Independent program verification, not physical validation or independent human review.')
(ROOT/'RESULTS.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
with(ROOT/'EXECUTIONS.csv').open('w',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with(ROOT/'PAIRED_ROUTES.csv').open('w',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
print(json.dumps(out,indent=2))
