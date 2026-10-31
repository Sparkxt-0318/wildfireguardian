"""Only fabricated assessment records over immutable timestamp inventories."""
from pathlib import Path
import copy,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parent;TASK=ROOT.parent.parent
s=importlib.util.spec_from_file_location('census',ROOT/'check_census.py');C=importlib.util.module_from_spec(s);s.loader.exec_module(C)
payloads=C.frozen_payloads(TASK/'work/audit-1b')
for cohort,data in payloads.items():(ROOT/(cohort+'_FROZEN_INVENTORY.json')).write_bytes(data)
def base(*,outcomes=('SCORED',)):
 out={}
 for cohort,data in payloads.items():
  mapping,order,events,_=C.expected(data,cohort);records=[dict(case=copy.deepcopy(mapping[cid]),case_id=cid,status=outcomes[i%len(outcomes)]) for i,cid in enumerate(order)]
  out[cohort]=dict(receipt_version='wfg.forecast-assessment/2',status='HOLD' if any(r['status']!='SCORED' for r in records) else 'COMPLETE',events=events,cases=records)
 return out
results=[]
def note(name,ok,reason=None):results.append(dict(name=name,passed=bool(ok),detail=reason))
def run(d,pins=None):return C.validate(d['us2024'],d['korea2025'],payloads if pins is None else pins)
for label,statuses in [('all_scored',('SCORED',)),('honest_mixed',('SCORED','UNAVAILABLE','FAILED')),('all_unavailable',('UNAVAILABLE',)),('all_failed',('FAILED',))]:
 r=run(base(outcomes=statuses));note(label+'_full306_census',r['total_represented_cases']==306 and r['scientific_clearance'] is False)
d=base();d['us2024']['cases'].reverse();r=run(d);note('case_order_diagnostic_not_membership_failure',r['cohorts']['us2024']['case_order_matches_inventory'] is False)
for cohort in ['us2024','korea2025']:
 for change in ['missing','duplicate','relabel_event','replace_cutoff','wrong_hours','wrong_id','unlisted_event','extra_case_field','false_complete_unavailable','false_complete_failed','invalid_outcome','empty_cases']:
  d=base();a=d[cohort]
  if change=='missing':a['cases'].pop()
  if change=='duplicate':a['cases'][-1]=copy.deepcopy(a['cases'][0])
  if change=='relabel_event':a['cases'][0]['case']['event']='SYNTHETIC_WRONG_EVENT';a['cases'][0]['case_id']=C.case_id(a['cases'][0]['case'])
  if change=='replace_cutoff':a['cases'][0]['case']['cutoff']='2099-01-01T00:00:00+00:00';a['cases'][0]['case_id']=C.case_id(a['cases'][0]['case'])
  if change=='wrong_hours':a['cases'][0]['case']['hours']+=.5;a['cases'][0]['case_id']=C.case_id(a['cases'][0]['case'])
  if change=='wrong_id':a['cases'][0]['case_id']='0'*24
  if change=='unlisted_event':a['events'][0]='SYNTHETIC_WRONG_EVENT'
  if change=='extra_case_field':a['cases'][0]['case']['extra']='ignored?';a['cases'][0]['case_id']=C.case_id(a['cases'][0]['case'])
  if change=='false_complete_unavailable':a['cases'][0]['status']='UNAVAILABLE'
  if change=='false_complete_failed':a['cases'][0]['status']='FAILED'
  if change=='invalid_outcome':a['cases'][0]['status']='FAKE_ZERO_SUCCESS'
  if change=='empty_cases':a['cases']=[]
  try:run(d);note(cohort+'_'+change,False,'INCORRECT_ACCEPTANCE')
  except C.CensusError as e:note(cohort+'_'+change,True,str(e))
for cohort in ['us2024','korea2025']:
 p=dict(payloads);p[cohort]=p[cohort]+b' '
 try:run(base(),p);note(cohort+'_changed_inventory_pin',False)
 except C.CensusError as e:note(cohort+'_changed_inventory_pin',True,str(e))
try:run(base(),{});note('empty_caller_inventory_map_refused',False)
except C.CensusError as e:note('empty_caller_inventory_map_refused',True,str(e))
# The paired inventory carries the producer's exact default-JSON SHA formula.
mapping,_,_,_=C.expected(payloads['us2024'],'us2024');case=next(iter(mapping.values()));need=hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()[:24];note('case_ID_default_JSON_formula',C.case_id(case)==need)
metric=TASK/'work/final-forecast-result-review/check_results.py';note('existing_metric_checker_unchanged',hashlib.sha256(metric.read_bytes()).hexdigest()==C.COMPANION_CHECKER_SHA256)
result=dict(scope='Synthetic assessment dictionaries only; immutable timestamp JSON objects read. No actual current assessment output, arrays, models, scorer, metrics or plot opened.',actual_reconciliation_run=False,checks=results,passed=sum(x['passed'] for x in results),total=len(results),failures=[x for x in results if not x['passed']]);(ROOT/'SYNTHETIC_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(result['failures']))
