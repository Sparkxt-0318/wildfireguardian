"""Recompute public evidence with stdlib only; no routing/checker imports."""
from pathlib import Path
from fractions import Fraction as Q
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,statistics as S
R=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
def need(ok,why):
 if not ok:raise ValueError(why)
def close(a,b):return abs(float(a)-float(b))<1e-12
for name,expected in read(R/'EVIDENCE_SHA256.json').items():
 need(hashlib.sha256((R/name).read_bytes()).hexdigest()==expected,'PUBLIC_EVIDENCE_CHANGED:'+name)
summary=read(R/'RESULTS.json');m=read(R/'MANIFEST.json');proof=read(R/'INDEPENDENT_GRADES.json')
with(R/'EXECUTIONS.csv').open()as f:rows=list(csv.DictReader(f))
with gzip.open(R/'RAW_EXECUTIONS.jsonl.gz','rt')as f:raw=[json.loads(line)for line in f]
need(len(rows)==len(raw)==len(m['jobs'])==80,'80_EXECUTIONS')
need(summary['missions']==20,'20_MISSIONS')
contexts={r['index']:r['context']for r in proof['rows']};missions=defaultdict(list);pairs=defaultdict(dict);inputs={};route_members=0;unique_members=0
for k,g in proof['grades'].items():
 if g['route_present']:
  flags=[]
  for b in g['thermal_members']:
   d,p=b['dose_kj_m2'],b['peak_kw_m2'];dlo,dhi,plo,phi=Q(d['lower']),Q(d['upper']),Q(p['lower']),Q(p['upper'])
   need(0<=dlo<=dhi and Q(d['width'])==dhi-dlo and 0<=plo<=phi and Q(p['width'])==phi-plo,'INTERVAL_ORDER')
   flag=dhi<=Q(b['dose_budget_kj_m2'])and phi<=Q(b['peak_budget_kw_m2']);need(flag==b['proved'],'THERMAL_DECISION');flags.append(flag)
   need(b['refinement']['cap']is None and b['refinement']['complete_partition'],'REFERENCE_CAP');unique_members+=1
  need(all(flags)and g['verified_journey']and g['grammar']['ok']and g['centre_model']['feasible']and g['whole_road_contact']['status']=='CLEAR'and g['metric_agreement']['status']!='DISAGREE','INDEPENDENT_JOURNEY')
for index,(row,entry)in enumerate(zip(rows,raw)):
 j,res,rc,boundary=(entry[k]for k in ('job','result','receipt','publication'));q=entry['queue_entry'];g=proof['grades'][contexts[index]]
 need(row['execution_id']==q['execution_id']==m['jobs'][index]['execution_id']==rc['execution_id'],'EXECUTION_ORDER')
 need(j['complete_budget_s']==rc['complete_budget_s']==30 and j['memory_guard_mib']==rc['memory_guard_mib']==3072 and j['preparation_mode']=='COLD_FAST','UNCHANGED_LIMITS')
 samples=rc['rss_samples'];ontime=bool(rc['status']=='COMPLETE'and rc['returncode']==0 and rc['stop_reason']is None and rc['elapsed_s']<=30 and rc['cleanup']['status']=='CLEAN'and not rc['cleanup']['remaining']and not rc['cleanup']['detached']and samples and all(0<=s['rss_bytes']<=3072*2**20 and not s['detached']for s in samples)and res['authority_final']and boundary['result_published_before_deadline']and rc['origin_monotonic']<=boundary['monotonic_after_result_publication']<=rc['origin_monotonic']+30)
 need(ontime==rc['on_time_complete_publication']==(row['on_time']=='True'),'ON_TIME_GATE')
 need(entry['native_result_sha256']==rc['result_sha256'],'NATIVE_RESULT_BINDING')
 for key,h in j['input_sha256'].items():need(res['identities'][key]['sha256']==h,'INPUT_BINDING')
 for key,h in j['source_sha256'].items():need(res['identities']['source:'+key]['sha256']==h,'SOURCE_BINDING')
 identity=(j['input_sha256'],j['source_sha256'],j['original_limits']);case=row['case_id'];need(case not in inputs or inputs[case]==identity,'INPUTS_CHANGED_BETWEEN_ARMS');inputs[case]=identity
 result=res['result'];has_route=result.get('destination')is not None;cert=res.get('refusal_certificate')or{}
 route_ok=ontime and has_route and (res.get('whole_road_check')or{}).get('status')=='CERTIFIED_ADMISSIBLE'and g.get('verified_journey')is True
 refusal_ok=ontime and not has_route and result['status']=='PROVEN_INFEASIBLE'and cert.get('complete')is True and cert.get('relaxation_kind')=='contact_only_lattice_relaxation'and bool(cert.get('scope'))and g.get('verified_no_route')is True
 state='CHECKED_ROUTE'if route_ok else'MODEL_NO_ROUTE'if refusal_ok else'UNRESOLVED';need(row['state']==state,'STATE')
 if route_ok:route_members+=len(g['thermal_members'])
 need(close(row['elapsed_s'],rc['elapsed_s']),'ELAPSED')
 missions[(row['arm'],case)].append(row);pairs[(case,row['rep'])][row['arm']]=row
for arm in ('RDA_BASE','RDA_CAND'):
 counts=Counter()
 for (a,c),rs in missions.items():
  if a!=arm:continue
  need(len(rs)==2 and {r['rep']for r in rs}=={'1','2'}and len({r['state']for r in rs})==1,'STABLE_REPETITIONS');counts[rs[0]['state']]+=1
 need(dict(counts)==summary['by_arm'][arm]['missions'],'MISSION_TOTALS')
matched=[(v['RDA_BASE'],v['RDA_CAND'])for v in pairs.values()if all(r['state']=='CHECKED_ROUTE'for r in v.values())]
need(len(matched)==summary['matched_route_pairs']==26,'PAIRED_COUNT')
need(all(b['arrival']==c['arrival']for b,c in matched),'PAIRED_ARRIVALS')
need(close(S.median(float(b['elapsed_s'])for b,c in matched),summary['matched_baseline_median_s']),'REFERENCE_MEDIAN')
need(close(S.median(float(c['elapsed_s'])for b,c in matched),summary['matched_candidate_median_s']),'CANDIDATE_MEDIAN')
need(close(S.median(float(c['elapsed_s'])/float(b['elapsed_s'])for b,c in matched),summary['median_paired_candidate_baseline_ratio']),'RATIO_MEDIAN')
need(unique_members==summary['unique_member_threshold_checks']==72 and route_members==224,'THERMAL_POPULATION')
need(len(proof['grades'])==25,'CONTEXT_COUNT')
caldor=read(R/'CALDOR_RIM_INDEPENDENT_REVIEW.json');need(caldor['metrics']['BASELINE']['resolved_missions']==3 and caldor['metrics']['CANDIDATE']['resolved_missions']==6 and caldor['proved_member_thresholds']==caldor['member_threshold_assessments']==24,'CALDOR_SCOPE')
with(R/'CALDOR_RIM_EXECUTIONS.csv').open()as f:caldor_rows=list(csv.DictReader(f))
need(len(caldor_rows)==24,'CALDOR_EXECUTIONS')
smoke=read(R/'API_SMOKE_RESULT.json');need(smoke['on_time']and smoke['cleanup_state']=='CLEAN'and smoke['successful_journey']and smoke['arrival_s']==3119 and not smoke['independent']['contradictions'],'API_SMOKE')
print('PASS: 80 executions, unchanged inputs/limits, stable mission counts, 26 paired times, 72 exact thermal assessments and separately scoped Caldor/API evidence')
