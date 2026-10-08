"""Finite self-checks, no candidate import; all known labelled controls."""
from pathlib import Path
import sys,json,time,resource
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'review'),str(D/'tests')]
from reference_fixtures import fixtures
from search_reference import exhaustive,witness,spans
start=time.perf_counter();cpu=time.process_time();rows=[]
for c in fixtures():
 r=exhaustive(c['graph'],c['hazard'],c['request']);expected=c['expected'].get('reference_status',c['expected']['center_status']);assert r['status']==expected,(c['id'],r)
 if c['expected']['arrival']is not None:assert float(r['arrival'])==c['expected']['arrival'] and r['checker']['ok']
 if c['id']=='mandatory_wait_opening':assert sum(l['end']-l['start'] for l in r['legs']if l['kind']=='WAIT')==3
 if c['id']=='member_tradeoff_dwell':assert r['checker']['per_member']=={'m0':{'dose_exact':'4','peak_exact':'4'},'m1':{'dose_exact':'15/2','peak_exact':'3'}}
 rows.append({'id':c['id'],'expected':c['expected'],'reference':r})
report={'status':'PASS','checks':len(rows),'cases':rows,'wall_s':time.perf_counter()-start,'cpu_s':time.process_time()-cpu,'process_lifetime_rss_raw':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'Independent finite center-contract timed-walk enumeration. Source physics unavailable; cannot establish whole-road feasibility.'}
(D/'review/REFERENCE_DEVELOPMENT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='cases'}))
