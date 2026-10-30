from pathlib import Path
import importlib.util,json,copy,hashlib
import numpy as np,pandas as pd
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');ROOT=TASK/'work/audit-1b';OUT=TASK/'work/farsite-subset-review-6ae52ab2'
s=importlib.util.spec_from_file_location('farsite',ROOT/'research/forecast-v2/scripts/audit_farsite.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
start=pd.Timestamp('2024-06-01T00:00:00Z');end=start+pd.Timedelta(hours=1)
clock=dict(duration_minutes=60); report=dict(native_clock_verification=clock,farsite_execution=dict(elapsed_minutes=60,native_clock_verification=clock,header=dict(nodata_value=-9999),timings_sha256='a'*64,arrival_sha256='b'*64,arrival_units='minutes since simulation cutoff',endpoint_selection='0 <= arrival <= 60'))
metadata=dict(exact_duration_minutes=60,no_burn_value=-9999,arrival_units='minutes',arrival_origin_time_utc=start.timestamp(),arrival_endpoint='inclusive_at_exact_cutoff_plus_hours',initial_ignition_policy='observed_initial_burn_union_simulated_arrivals_including_zero',method='farsite_deterministic',scenario_count=1)
arrival=np.array([[0,60],[-9999,61]],float);initial=np.array([[1,0],[0,0]],bool);valid=np.ones((2,2),bool);probability=np.array([[0,1],[0,0]],float)
checks=[]
def note(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
positive=a.native_horizon(report,metadata,arrival,initial,probability,valid,start,end);note('inclusive_endpoint_and_finite_censor_positive',positive['status']=='AVAILABLE')
for name in ['missing_elapsed','nan_elapsed','bool_elapsed','short_elapsed','duration_mismatch','selection_mismatch','missing_timings_hash','missing_arrival_hash','origin_mismatch','nodata_mismatch','sentinel_mismatch','unit_mismatch','endpoint_convention','negative_arrival','false_negative','false_positive','initial_cell_probability','missing_arrivals']:
 r=copy.deepcopy(report);m=copy.deepcopy(metadata);ar=arrival.copy();p=probability.copy()
 if name=='missing_elapsed':del r['farsite_execution']['elapsed_minutes']
 if name=='nan_elapsed':r['farsite_execution']['elapsed_minutes']=float('nan')
 if name=='bool_elapsed':r['farsite_execution']['elapsed_minutes']=True
 if name=='short_elapsed':r['farsite_execution']['elapsed_minutes']=59
 if name=='duration_mismatch':r['native_clock_verification']['duration_minutes']=61
 if name=='selection_mismatch':r['farsite_execution']['endpoint_selection']='0 <= arrival <= 61'
 if name=='missing_timings_hash':del r['farsite_execution']['timings_sha256']
 if name=='missing_arrival_hash':del r['farsite_execution']['arrival_sha256']
 if name=='origin_mismatch':m['arrival_origin_time_utc']+=1
 if name=='nodata_mismatch':r['farsite_execution']['header']['nodata_value']=-1
 if name=='sentinel_mismatch':m['no_burn_value']=-1
 if name=='unit_mismatch':m['arrival_units']='hours'
 if name=='endpoint_convention':m['arrival_endpoint']='exclusive'
 if name=='negative_arrival':ar[1,0]=-2
 if name=='false_negative':p[0,1]=0
 if name=='false_positive':p[1,0]=1
 if name=='initial_cell_probability':p[0,0]=1
 if name=='missing_arrivals':ar=None
 res=a.native_horizon(r,m,ar,initial,p,valid,start,end);note(name,res['status']=='UNAVAILABLE',res['reason'])
# Manual fire-weight distinction, independent of the owner fixture's array recipe.
reporting=a.load_reporting();entries=dict(fire=np.array(['A','A','B']),y=np.array([0,1,1]),predictions=dict(candidate=np.array([.2,.8,.5]),persistence=np.array([0.,0.,0.]),dilation_best=np.array([.1,.9,.9])))
scores=reporting.detailed_scores(entries,draws=32,seed=7);q=scores['models']['candidate'];note('manual_pooled_and_perfire_arithmetic',np.isclose(q['pooled']['brier'],.11) and np.isclose(q['per_fire']['A']['brier'],.04) and np.isclose(q['per_fire']['B']['brier'],.25),dict(pooled=q['pooled']['brier'],per_fire=q['per_fire']))
ident=json.loads((ROOT/'research/forecast-v2/FARSITE_IDENTITIES_V2.json').read_text());h=[r['native_horizon']['native_horizon_minutes'] for r in ident['cases']];note('actual_identity_metadata_only_30_finite_horizons',len(h)==30 and min(h)==263 and max(h)==4489 and all(r['native_horizon']['status']=='AVAILABLE' for r in ident['cases']) and ident['scores_available'] is False and ident['superiority_criteria_pass'] is False,dict(cases=30,min_minutes=min(h),max_minutes=max(h),over48h=sum(x>2880 for x in h)))
res=dict(scope='Tiny synthetic horizon/arithmetic controls plus existing identity-JSON metadata only. No actual prediction array/data/model/quality assessment loaded.',checks=checks,checks_passed=sum(c['passed'] for c in checks),checks_total=len(checks),failures=[c for c in checks if not c['passed']],audit_source_sha256=hashlib.sha256((ROOT/'research/forecast-v2/scripts/audit_farsite.py').read_bytes()).hexdigest())
(OUT/'independent_controls.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(res,indent=2));raise SystemExit(bool(res['failures']))
