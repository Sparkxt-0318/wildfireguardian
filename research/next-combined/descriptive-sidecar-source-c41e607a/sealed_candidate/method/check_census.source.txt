"""Additive frozen current-cohort case census, without loading scientific arrays.

Run only during authorized final saved-result review after both assessments finish.
The existing independent metric checker remains separate and unchanged.
"""
from pathlib import Path
import argparse,collections,hashlib,json,subprocess
COMMIT='6887dc618253e6568c6cbbfd3c9a96f1d0d86b70'
INVENTORIES={
 'us2024':('research/forecast-v2/PREASSESSMENT_US2024_TIMESTAMPS.json','51d910392b5f47f20b57ba56a4b2d25bc9096d33ac1dd09361f32a925884028d',273,6),
 'korea2025':('research/forecast-v2/PREASSESSMENT_KOREA2025_WINDOWS.json','6286e0541a95b5f4806943bb809aa9314d55c2a637171002027c05e6292fc42d',33,4)}
COMPANION_CHECKER_SHA256='b3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8'
class CensusError(ValueError):pass
def need(value,message):
 if not value:raise CensusError(message)
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def unique(pairs):
 out={}
 for key,val in pairs:
  need(key not in out,'DUPLICATE_JSON_OBJECT_KEY:'+key);out[key]=val
 return out
def parse(data):
 return json.loads(data,object_pairs_hook=unique,parse_constant=lambda s:(_ for _ in ()).throw(CensusError('NONFINITE_JSON:'+s)))
def canonical(case):return json.dumps(case,sort_keys=True,allow_nan=False)
def case_id(case):return hashlib.sha256(canonical(case).encode()).hexdigest()[:24]
def frozen_payloads(repo):
 # Exact committed objects plus independent byte pins; never a caller-provided expected map.
 return {cohort:subprocess.check_output(['git','--no-replace-objects','-C',str(Path(repo).resolve()),'show',COMMIT+':'+spec[0]]) for cohort,spec in INVENTORIES.items()}
def expected(payload,cohort):
 path,pin,total,fires=INVENTORIES[cohort]
 need(type(payload) is bytes and sha_bytes(payload)==pin,'FROZEN_INVENTORY_BYTES_CHANGED:'+cohort)
 inventory=parse(payload);records=inventory['cases'];cases=records if cohort=='us2024' else [r['case'] for r in records]
 need(inventory['case_count']==total and len(cases)==total,'FROZEN_INVENTORY_COUNT:'+cohort)
 mapping={case_id(c):c for c in cases};events=list(dict.fromkeys(c['event'] for c in cases));counts=dict(collections.Counter(c['event'] for c in cases))
 need(len(mapping)==total and len(events)==fires,'FROZEN_INVENTORY_DUPLICATE_OR_EVENT_COUNT:'+cohort)
 need(all(set(c)=={'event','cutoff','endpoint','hours'} for c in cases),'FROZEN_CASE_SCHEMA:'+cohort)
 if cohort=='korea2025':need([r['case_id'] for r in records]==[case_id(c) for c in cases] and inventory['case_ids']==[case_id(c) for c in cases],'FROZEN_KOREAN_CASE_IDS')
 return mapping,[case_id(c) for c in cases],events,counts

def cohort_census(assessment,cohort,payload):
 mapping,order,events,counts=expected(payload,cohort);total=INVENTORIES[cohort][2]
 need(isinstance(assessment,dict) and assessment.get('receipt_version')=='wfg.forecast-assessment/2','ASSESSMENT_SCHEMA:'+cohort)
 need(assessment.get('status') in ['COMPLETE','HOLD'],'ASSESSMENT_STATUS:'+cohort)
 declared=assessment.get('events');need(isinstance(declared,list) and len(declared)==len(set(declared))==len(events) and set(declared)==set(events),'DECLARED_EVENT_POPULATION:'+cohort)
 records=assessment.get('cases');need(isinstance(records,list),'ASSESSMENT_CASE_LIST:'+cohort)
 need(len(records)==total,f'EXACT_CASE_COUNT:{cohort}:expected={total}:actual={len(records)}')
 actual_ids=[];actual_counts=collections.Counter();statuses=collections.Counter();actual_cases={}
 for record in records:
  need(isinstance(record,dict) and isinstance(record.get('case'),dict),'CASE_RECORD_SCHEMA:'+cohort)
  case=record['case'];need(set(case)=={'event','cutoff','endpoint','hours'},'EXACT_FOUR_FIELD_CASE_SCHEMA:'+cohort)
  try:computed=case_id(case)
  except (ValueError,TypeError) as exc:raise CensusError('CASE_SERIALIZATION:'+cohort) from exc
  cid=record.get('case_id');need(type(cid) is str and cid==computed,'CASE_ID_FORMULA:'+cohort)
  need(cid in mapping,'UNEXPECTED_REPLACED_OR_RELABELLED_CASE:'+cohort+':'+cid)
  need(canonical(case)==canonical(mapping[cid]),'EXACT_CASE_IDENTITY:'+cohort+':'+cid)
  need(record.get('status') in ['SCORED','UNAVAILABLE','FAILED'],'CASE_OUTCOME_STATUS:'+cohort)
  actual_ids.append(cid);actual_cases[cid]=case;actual_counts[case['event']]+=1;statuses[record['status']]+=1
 need(len(set(actual_ids))==total,'DUPLICATE_CASE_ID:'+cohort)
 need(set(actual_ids)==set(mapping),'MISSING_OR_EXTRA_EXPECTED_CASE:'+cohort)
 need(dict(actual_counts)==counts,'EXACT_PER_FIRE_CASE_COUNTS:'+cohort)
 need(assessment['status']!='COMPLETE' or statuses['SCORED']==total,'FALSE_COMPLETE_WITH_UNSCORED_CASES:'+cohort)
 # Ordering is reported, not a scientific membership condition. The companion
 # checker verifies declared event ordering and interval-to-array alignment.
 return dict(status='COMPLETE_FROZEN_CASE_CENSUS',cohort=cohort,expected_cases=total,represented_cases=len(records),unique_cases=len(set(actual_ids)),expected_fires=len(events),per_fire_counts=counts,outcome_counts=dict(statuses),assessment_status=assessment['status'],case_order_matches_inventory=actual_ids==order,declared_event_order_matches_inventory=declared==events,case_population_sha256=sha_bytes(json.dumps(sorted(actual_ids),separators=(',',':')).encode()),inventory_path=INVENTORIES[cohort][0],inventory_sha256=INVENTORIES[cohort][1])
def validate(us,kr,payloads):
 need(set(payloads)==set(INVENTORIES),'BOTH_FROZEN_INVENTORIES_REQUIRED')
 results={key:cohort_census(assessment,key,payloads[key]) for key,assessment in [('us2024',us),('korea2025',kr)]}
 return dict(status='COMPLETE_FROZEN_306_CASE_CENSUS',scope='Saved case membership/identity/status census only. Honest unavailable and failed cases remain represented. No arrays, metrics, masks, field values, model identity, inference or scientific criterion checked.',frozen_commit=COMMIT,total_expected_cases=306,total_represented_cases=sum(x['represented_cases'] for x in results.values()),cohorts=results,scientific_clearance=False,companion_metric_checker_sha256=COMPANION_CHECKER_SHA256)
def reconcile(repo,us_path,kr_path):
 payloads=frozen_payloads(repo)
 # Authenticate fixed inventories before reading saved assessment metadata.
 for key,data in payloads.items():expected(data,key)
 us_data=Path(us_path).read_bytes();kr_data=Path(kr_path).read_bytes();result=validate(parse(us_data),parse(kr_data),payloads)
 result.update(assessment_sha256={'us2024':sha_bytes(us_data),'korea2025':sha_bytes(kr_data)},checker_sha256=sha_bytes(Path(__file__).read_bytes()))
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True,type=Path);p.add_argument('--us-assessment',required=True,type=Path);p.add_argument('--korean-assessment',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 result=reconcile(a.repo,a.us_assessment,a.korean_assessment);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':result['status'],'represented':result['total_represented_cases'],'statuses':{k:v['outcome_counts'] for k,v in result['cohorts'].items()}}))
if __name__=='__main__':main()
