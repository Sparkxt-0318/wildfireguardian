from pathlib import Path
import importlib.util,json,tempfile,copy,hashlib
from types import SimpleNamespace
import numpy as np,pandas as pd,pytest
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');ROOT=TASK/'work/audit-1b';OUT=TASK/'work/farsite-subset-review-6ae52ab2/repair-d2512cbc'
def module(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
t=module('owner_repair_fixture',ROOT/'forecast/tests/test_farsite_matched_subset.py');checks=[]
def note(name,value,detail=None):checks.append(dict(name=name,passed=bool(value),detail=detail))
def fresh(folder):
 a=module('repair_farsite_'+str(len(checks)),ROOT/'research/forecast-v2/scripts/audit_farsite.py');m=t.fixture(a,folder);return a,m
def run(a,m):
 with pytest.MonkeyPatch.context() as mp:return t.run(a,m,mp)
def refuses(fn):
 try:fn()
 except ValueError as e:return str(e)
 return None
with tempfile.TemporaryDirectory(prefix='synthetic-',dir=OUT) as td:
 base=Path(td)
 a,m=fresh(base/'positive');r=run(a,m);note('full16_positive_common_coordinates',r['scores_available'] and set(r['scores']['models'])==a.EXPECTED_MODELS|{'farsite_scenario'} and r['cases'][0]['cells']==2 and r['superiority_criteria_pass'] is False)
 args=m.identity_calls[0];note('exact_identity_delegate_args_once',len(m.identity_calls)==1 and vars(args)==dict(data=m.data,run=m.assessment.parent,cohort='us2024',registry=m.repo/m.frozen['registry']['path']))
 for change in ['missing_d4','extra']:
  a,m=fresh(base/change)
  for p in [m.assessment/'cases/synthetic_case_00.npz',m.assessment/(m.event+'.npz')]:
   with np.load(p) as z:ar={n:z[n].copy() for n in z.files}
   if change=='missing_d4':del ar['p_d4_seed0']
   else:ar['p_extra']=ar['p_base_seed0'].copy()
   np.savez_compressed(p,**ar)
  t.resign_current(a,m);err=refuses(lambda:run(a,m));note('original_gap_'+change+'_refuses',err is not None and 'fixed 16 probability columns' in err,err)
 for hours in [48,49]:
  a,m=fresh(base/str(hours));t.rewrite_interval(a,m,hours);r=run(a,m)
  if hours==48:note('48h_endpoint_positive',r['scores_available'] and r['current_case_admission_pass'] and r['status']=='DESCRIPTIVE_MATCHED_SUBSET_COMPLETE')
  else:note('original49h_gap_retained_unavailable',r['status']=='HOLD' and r['scores_available'] is False and 'scores' not in r and len(r['cases'])==1 and r['cases'][0]['native_horizon']['status']=='AVAILABLE' and r['cases'][0]['status']=='UNAVAILABLE' and r['cases'][0]['reason']=='HISTORICAL_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY' and r['rejected_current_cases'][0]['reason']=='CURRENT_CASE_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY' and r['superiority_criteria_pass'] is False)
 a,m=fresh(base/'direct');start=pd.Timestamp('2024-01-01T00:00:00Z'); catalog={m.event:dict(country='US',year=2024)}
 def admission(end,hours,event=None,cat=None):return a.case_admission(dict(event=event or m.event,cutoff=start.isoformat(),endpoint=end.isoformat(),hours=hours),cat or catalog,{m.event})
 note('duration48h_plus1ns_refuses',admission(start+pd.Timedelta(hours=48)+pd.Timedelta(nanoseconds=1),48)=='CURRENT_CASE_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY')
 note('zero_duration_refuses',admission(start,0)=='CURRENT_CASE_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY')
 note('negative_duration_refuses',admission(start-pd.Timedelta(hours=1),-1)=='CURRENT_CASE_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY')
 note('duration_hours_disagreement_refuses',admission(start+pd.Timedelta(hours=1),2)=='CURRENT_CASE_DURATION_DIFFERS_FROM_ENDPOINTS')
 note('nonmember_event_refuses',admission(start+pd.Timedelta(hours=1),1,event='OTHER')=='CURRENT_CASE_OUTSIDE_FROZEN_US2024_POPULATION')
 for key,val in [('country','KR'),('year',2025)]:
  cat=copy.deepcopy(catalog);cat[m.event][key]=val;note('wrong_'+key+'_refuses',admission(start+pd.Timedelta(hours=1),1,cat=cat)=='CURRENT_CASE_OUTSIDE_FROZEN_US2024_POPULATION')
 for bad in ['identity_mismatch','verifier_refusal','model_contract_mismatch','split_bytes','registry_escape']:
  a,m=fresh(base/bad)
  if bad=='identity_mismatch':a.load_current_scorer=lambda:SimpleNamespace(EXPECTED_MODELS=set(a.EXPECTED_MODELS),identities=lambda args:dict(m.frozen,extra='changed'))
  if bad=='verifier_refusal':
   def denial(args):raise ValueError('synthetic identity refusal')
   a.load_current_scorer=lambda:SimpleNamespace(EXPECTED_MODELS=set(a.EXPECTED_MODELS),identities=denial)
  if bad=='model_contract_mismatch':a.load_current_scorer=lambda:SimpleNamespace(EXPECTED_MODELS={'wrong'},identities=lambda args:m.frozen)
  if bad=='split_bytes':m.split_path.write_text(m.split_path.read_text()+' ')
  if bad=='registry_escape':
   p=m.assessment/'FROZEN_ASSESSMENT.json';f=json.loads(p.read_text());f['registry']['path']='../../outside';t.write(p,f)
  with pytest.MonkeyPatch.context() as mp:
   mp.setattr(a.np,'load',lambda *args,**kw:(_ for _ in ()).throw(AssertionError('identity refusal reached arrays')))
   err=refuses(lambda:t.run(a,m,mp))
  note(bad+'_before_arrays',err is not None,err)
 a,m=fresh(base/'identity_only')
 a.load_current_scorer=lambda:(_ for _ in ()).throw(AssertionError('identity mode invoked current scorer'))
 with pytest.MonkeyPatch.context() as mp:r=t.run(a,m,mp,assessment=False)
 note('identity_only_no_current_verifier_or_scores',r['scores_available'] is False and r['status']=='AUTHENTICATED_IDENTITIES_ONLY' and 'scores' not in r)
 for events in [[],['X','X'],['X',3]]:
  a,m=fresh(base/('badlist'+str(len(checks))));t.write(m.split_path,dict(held_out=dict(us_2024=events)));m.frozen['split_sha256']=a.sha(m.split_path);t.write(m.assessment/'FROZEN_ASSESSMENT.json',m.frozen)
  err=refuses(lambda:a.frozen_current_identity(m.assessment,m.data));note('invalid_authenticated_event_list_'+str(len(checks))+'_refuses',err is not None,err)
result=dict(review_head='d2512cbcc2debc1b00074c99efb329089823549e',source_sha256=hashlib.sha256((ROOT/'research/forecast-v2/scripts/audit_farsite.py').read_bytes()).hexdigest(),scope='Exact two-gap repair plus source-verifier delegation/SPLIT/duration boundary. Synthetic source/arrays only; actual model/input verifier mocked at its unchanged identity boundary, never executed.',checks=checks,checks_passed=sum(x['passed'] for x in checks),checks_total=len(checks),failures=[x for x in checks if not x['passed']])
(OUT/'recheck.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(result['failures']))
