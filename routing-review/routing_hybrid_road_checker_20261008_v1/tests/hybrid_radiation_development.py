"""Known prior incident/control cases are development only, never fresh evidence."""
from pathlib import Path
from fractions import Fraction as F
import json,sys,time,hashlib,resource,argparse
H=Path(__file__).resolve().parents[1];sys.path.insert(0,str(H/'candidate'))
from hybrid_radiation import HybridRadiationBounds
p=argparse.ArgumentParser();p.add_argument('--output',default='hybrid_radiation_development_v1.json');p.add_argument('--all',action='store_true');a=p.parse_args()
rows=json.loads((H/'baseline/results/confirmation_v1/ROWS.json').read_text());out=[]
selected=('20220304T060000Z_confirmation-road-2_depart60','control_near_interior_peak','control_overlapping_source_heat','control_completed_threshold_straddle')
for row in rows:
 if not a.all and row['case']['id'] not in selected:continue
 if row['candidate']['cold']['raw'].get('contact',{}).get('status')=='DEFINITE_REJECT':continue
 trajectory=[]
 for leg in row['trajectory']:
  d=dict(leg);d['start']=F(d['start']);d['end']=F(d['end']);d['p0']=tuple(map(F,d['p0']));d['p1']=tuple(map(F,d['p1']));trajectory.append(d)
 request=row['case']['request'];start=time.perf_counter();deadline=start+30
 try:
  checker=HybridRadiationBounds.from_case(H/'baseline'/row['case']['source_directory'],row['case'].get('radiation_settings_override'))
  prepared=time.perf_counter()
  result=checker.trajectory_bound(trajectory,peak_budget_kw_m2=request['budgets']['peak'],dose_budget_kj_m2=request['budgets']['dose'],incurred=request['incurred'],deadline=deadline)
  item={'case':row['case']['id'],'scope':'KNOWN_DEVELOPMENT_ONLY','cold_preparation_s':prepared-start,'cold_total_s':time.perf_counter()-start,'result':result,'implementation_sha256':hashlib.sha256((H/'candidate/hybrid_radiation.py').read_bytes()).hexdigest(),'rss_mb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576}
  if result['complete']:
   t=time.perf_counter();item['warm_result']=checker.trajectory_bound(trajectory,peak_budget_kw_m2=request['budgets']['peak'],dose_budget_kj_m2=request['budgets']['dose'],incurred=request['incurred'],deadline=t+30);item['warm_total_s']=time.perf_counter()-t
 except Exception as e:item={'case':row['case']['id'],'error':repr(e),'cold_total_s':time.perf_counter()-start,'scope':'KNOWN_DEVELOPMENT_ONLY'}
 out.append(item);(H/'results'/a.output).write_text(json.dumps(out,indent=2));print(item['case'],item.get('cold_total_s'),item.get('result',{}).get('status'),item.get('result',{}).get('per_member'),item.get('error'),flush=True)
