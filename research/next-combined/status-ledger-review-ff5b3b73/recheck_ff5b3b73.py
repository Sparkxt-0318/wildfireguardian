"""Tiny independent ledger boundary checks; synthetic metadata only."""
import hashlib,importlib.util,json,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'audit-1b/research/forecast-v2/scripts/status.py'
spec=importlib.util.spec_from_file_location('parent_ledger_ff5',source);S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
checks=[]
def check(name,value):
 checks.append({'id':name,'passed':bool(value)})
 assert value,name
with tempfile.TemporaryDirectory() as d:
 r=Path(d).resolve();p=r/'research/forecast-v2/BLIND_REGISTRY.json';p.parent.mkdir(parents=True)
 check('missing_registry_refuses',S.protocol_readiness(r,r/'run',p)['protocol_status']=='NOT_READY')
 for i,record in enumerate([{'protocol_status':'READY_FOR_OWNER_REGISTRATION'}, {'protocol_status':'READY_FOR_OWNER_REGISTRATION','producer_source_sha256':{}}, {'protocol_status':'READY_FOR_OWNER_REGISTRATION','producer_source_sha256':[]}]):
  p.write_text(json.dumps(record));check(f'original_vacuous_variant_{i}_refuses',S.protocol_readiness(r,r/'run',p)['protocol_status']=='NOT_READY')
 p.write_text('{');check('malformed_json_refuses',S.protocol_readiness(r,r/'run',p)['protocol_status']=='NOT_READY')
 record={'protocol_status':'READY_FOR_OWNER_REGISTRATION','execution_status':'NOT_READY_FOR_2026_EXECUTION','producer_source_sha256':{'source.py':'0'*64}}
 p.write_text(json.dumps(record));p.with_name('MODEL_SELECTION.json').write_text('{"selected_variant":"base"}')
 check('real_guard_refuses_incomplete_freeze',S.protocol_readiness(r,r/'run',p)['protocol_status']=='NOT_READY')
 calls=[]; original=S.F.saved_registry_admission
 def admitted(rr,run,sp,selection,rp):
  calls.append((rr,run,sp,selection,rp));return {'registry':S.F.identity(rr,rp)}
 S.F.saved_registry_admission=admitted
 v=S.protocol_readiness(r,r/'run',p)
 check('authenticated_delegation_positive',v['protocol_status']=='READY_FOR_OWNER_REGISTRATION' and v['execution_status']=='NOT_READY_FOR_2026_EXECUTION' and calls==[(r,r/'run',p.with_name('MODEL_SELECTION.json'),{'selected_variant':'base'},p)])
 record['execution_status']='READY';p.write_text(json.dumps(record));check('execution_ready_never_conferred',S.protocol_readiness(r,r/'run',p)['protocol_status']=='NOT_READY')
 record['execution_status']='NOT_READY_FOR_2026_EXECUTION';p.write_text(json.dumps(record))
 S.F.saved_registry_admission=lambda *a:{'registry':{'path':'different','sha256':'1'*64}}
 check('mismatched_proof_refuses',S.protocol_readiness(r,r/'run',p)['protocol_status']=='NOT_READY')
 S.F.saved_registry_admission=original
for i,v in enumerate([{'scores':{}},{'scores':{'models':{'base':{}}},'scores_available':True}]):
 check(f'scores_presence_not_measurement_{i}',S.farsite_readiness(v)['scores_available'] is False)
v={'status':'HOLD','execution_status':'NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY','superiority_criteria_pass':False,'scores_available':True,'measurement_status':'DESCRIPTIVE_COMMON_SUBSET_AVAILABLE','scored_cases':1,'total_historical_cases':2,'cases':[{'status':'SCORED_COMMON_SUBSET','cells':2},{'status':'UNAVAILABLE'}],'scores':{'models':{'base':{'pooled':{'entries':2}}}}}
check('partial_descriptive_preserves_hold',S.farsite_readiness(v)['status']=='HOLD' and S.farsite_readiness(v)['scores_available'] is True)
v['cases'][0]['cells']=0;check('zero_cells_not_measurement',S.farsite_readiness(v)['scores_available'] is False)
record={'head':'ff5b3b73345fe74cc3d5a6219b40b86b6b6a358e','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checks':checks,'passed':sum(x['passed'] for x in checks),'status':'PASS_LEDGER_REPAIR_SCOPED','scope':'Original empty-map boundary plus real refusal and synthetic positive delegation/measurement bookkeeping only; no actual registry/model/data and no replacement of prior saved-admission audit'}
Path(__file__).with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n');print(record['status'],record['passed'],len(checks))
