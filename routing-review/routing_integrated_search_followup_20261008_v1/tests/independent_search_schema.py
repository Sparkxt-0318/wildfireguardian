"""Pre-opening raw-verifier/schema controls; known tiny records only."""
from pathlib import Path
import sys,json,types,copy,importlib.util,time
from unittest.mock import patch
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'tests'),str(D/'candidate'),str(D/'candidate/routing-package')]
from reference_fixtures import fixtures
from search_followup import SearchFollowup
spec=importlib.util.spec_from_file_location('independent_search_confirmation_schema',D/'tests/independent_search_confirmation.py');verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)
root=D/'review/SCHEMA_KNOWN_CASES';root.mkdir(exist_ok=True);rows=[];roster=[];launches=[];start=time.perf_counter()
for c in fixtures():
 path=root/(c['id']+'.json');path.write_text(json.dumps(c,indent=2)+'\n');meta={'id':c['id'],'kind':'reference','case_path':str(path.relative_to(D)),'source_directory':None,'source_contract_unavailable':True};roster.append(meta)
 for mode in ['baseline','cache','heuristic','combined']:
  session=SearchFollowup();recs={}
  for phase in ['cold','warm']:
   result=session.run(c['graph'],c['hazard'],None,c['request'],mode=mode);recs[phase]={'result':result,'search_limits_input':c['request']['limits'],'center_hazard_sha256':verify.hashlib.sha256(verify.canonical(c['hazard'])).hexdigest(),'complete_call_wall_s':None,'complete_call_CPU_s':None,'RSS_process_lifetime_MiB':None}
  launch={'case':c['id'],'mode':mode,'returncode':0,'watchdog':False,'complete_process_wall_s':None};launches.append(launch);rows.append({'case':meta,'mode':mode,'records':recs,'launcher':launch})
# Explicit missing phases cannot become invented zero-cost successful results.
rows[0]['records'].pop('warm');rows[1]['records']={};rows[1]['worker_failure']=True;assert verify.decision_record(None)['status']=='UNRESOLVED'and verify.decision_record(None)['wall_s']is None
# Retain null incomplete unsupported data; no Fraction(None) on unused bounds.
r=verify.verify_road({}, {}, {}, None,{'status':'UNRESOLVED','reason':'SOURCE_CONTRACT_UNAVAILABLE','radiation':{'status':'UNSUPPORTED','complete':False,'per_member':[{'dose_lower_kj_m2':None}]}},None,{})
assert r['road_decision']=='UNRESOLVED'
# Malformed present records fail loudly; omitted records remain separately unresolved.
malformed_rejected=False
try:verify.decision_record({'result':{'primary_search':None}})
except AssertionError:malformed_rejected=True
assert malformed_rejected,'malformed positive record accepted'
# Recorded work may be UNKNOWN; negative/nonfinite values cannot become evidence.
negative_cost_rejected=False
try:verify.decision_record({'result':rows[0]['records']['cold']['result'],'complete_call_wall_s':-1})
except AssertionError:negative_cost_rejected=True
assert negative_cost_rejected
nonfinite_cost_rejected=False
try:verify.decision_record({'result':rows[0]['records']['cold']['result'],'complete_call_CPU_s':float('nan')})
except AssertionError:nonfinite_cost_rejected=True
assert nonfinite_cost_rejected
out=root/'panel';out.mkdir(exist_ok=True);(out/'ROWS.json').write_text(json.dumps(rows)+'\n');(out/'LAUNCHES.json').write_text(json.dumps(launches)+'\n');rp=root/'ROSTER.json';rp.write_text(json.dumps(roster)+'\n')
with patch.object(sys,'argv',['independent_search_confirmation.py','--development','--roster',str(rp.relative_to(D)),'--panel',str(out.relative_to(D))]):verify.main()
assert verify.report['verified_workers']==68 and verify.report['failed']==0 and verify.report['missing_phases']==3
report={'status':'PASS','checks':6,'known_reference_workers':68,'known_reference_cases':17,'verified_missing_phases_as_unresolved':3,'wall_s':time.perf_counter()-start,'scope':'Known tiny pre-opening complete raw-verifier run, missing/null/malformed schema negative controls. No fresh incident source or outcomes opened.'};(D/'review/SCHEMA_DEVELOPMENT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
