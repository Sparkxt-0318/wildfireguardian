"""Independent four-mode/lifecycle/authority controls, before fresh opening."""
from pathlib import Path
import sys,json,copy,time,types
from unittest.mock import patch
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'review'),str(D/'tests'),str(D/'candidate'),str(D/'candidate/routing-package')]
from reference_fixtures import fixtures
from search_reference import exhaustive,witness
from search_followup import SearchFollowup,prepare_epoch,_heuristic_envelope
from routing import core_cached
from routing.search_geometry_cache import SearchGeometryCache
started=time.perf_counter();rows=[]
for c in fixtures():
 for mode in ['baseline','cache','heuristic','combined']:
  session=SearchFollowup()
  for phase in ['cold','warm']:
   r=session.run(c['graph'],c['hazard'],None,c['request'],mode=mode);p=r['primary_search'];assert p['status']==c['expected']['center_status'],(c['id'],mode,phase,r)
   assert r['whole_road_check']['status']=='UNRESOLVED' and r['whole_road_check']['reason']=='SOURCE_CONTRACT_UNAVAILABLE' and r['integrated_status']=='UNRESOLVED' and not r['road_optimality_claim'] and not r['physical_safety_claim'];assert r['limits_exactly_preserved'] and r['search_resource_limits']==c['request']['limits']
   if p['status']in ['CONDITIONAL_OPTIMUM','CHECKED_ROUTE']:
    own=witness(c['graph'],c['hazard'],c['request'],p['legs'],p['destination']);ref=exhaustive(c['graph'],c['hazard'],c['request']);assert own['ok'] and float(own['arrival'])==float(ref['arrival'])==p['arrival'];assert p['checker']['per_member']=={k:{'dose':float(v['dose_exact'] if '/'not in v['dose_exact'] else __import__('fractions').Fraction(v['dose_exact'])),'dose_exact':v['dose_exact'],'peak':float(v['peak_exact'])}for k,v in own['per_member'].items()}
   assert r['epoch_reused']==(phase=='warm');rows.append({'id':'four_mode_reference','case':c['id'],'mode':mode,'phase':phase,'status':p['status']})
# Explicit epoch refuses source/graph changes; request exposure/turn/incurred remain fresh.
c=fixtures()[0];s=SearchFollowup();r=s.run(c['graph'],c['hazard'],None,c['request']);assert r['primary_search_status']=='CONDITIONAL_OPTIMUM'
for kind in ['graph','hazard','settings','directory']:
 g,h,q=copy.deepcopy(c['graph']),copy.deepcopy(c['hazard']),copy.deepcopy(c['request']);directory=None
 if kind=='graph':g['nodes'][0]['waitable']=False
 if kind=='hazard':h['members'][0]['flux'][0][0]=1
 if kind=='settings':s._settings['receiver_span_m']=17
 if kind=='directory':directory=D/'development'
 r=s.run(g,h,directory,q);assert r['integrated_status']=='UNRESOLVED' and r.get('external_failure') and not r['center_optimality_claim'];rows.append({'id':'changed_epoch_dependency','dependency':kind,'reason':r['external_failure']['reason']})
 if kind=='settings':s._settings['receiver_span_m']=16
s=SearchFollowup();s.run(c['graph'],c['hazard'],None,c['request']);q=copy.deepcopy(c['request']);q['incurred']['m0']=101;r=s.run(c['graph'],c['hazard'],None,q);assert r['primary_search_status']=='AT_ISSUE_FAILURE';rows.append({'id':'fresh_incurred_on_warm_epoch','status':r['primary_search_status']})
# Final metadata mutation is detected after raw search authority was produced.
c=fixtures()[0];s=SearchFollowup();orig=SearchGeometryCache.cache_info;calls=[0]
def mutating_info(owner):
 out=orig(owner);calls[0]+=1
 if calls[0]==3:c['graph']['nodes'][0]['waitable']=False
 return out
with patch.object(SearchGeometryCache,'cache_info',mutating_info):r=s.run(c['graph'],c['hazard'],None,c['request'],mode='cache')
assert r['primary_search_status']=='CONDITIONAL_OPTIMUM' and r['integrated_status']=='UNRESOLVED' and not r['center_optimality_claim'] and r['whole_road_check']['reason']=='FINAL_AUTHORITY_FAILURE';rows.append({'id':'post_metadata_binding_mutation','status':r['integrated_status']})
# Last solver cache inspection crosses wall cap; retain checked incumbent, never optimum.
c=fixtures()[0];clock=[0.];calls=[0]
def late_info(owner):
 out=orig(owner);calls[0]+=1
 if calls[0]==2:clock[0]=31.
 return out
with patch.object(core_cached,'time',types.SimpleNamespace(perf_counter=lambda:clock[0])),patch.object(SearchGeometryCache,'cache_info',late_info):p=core_cached.solve_cached(c['graph'],c['hazard'],c['request'])
assert p['status']=='TIMEOUT' and p['checked_incumbent']['status']=='CHECKED_ROUTE' and not p['legs'];own=witness(c['graph'],c['hazard'],c['request'],p['checked_incumbent']['legs'],p['checked_incumbent']['destination']);assert own['ok'];rows.append({'id':'late_solver_metadata_checked_incumbent','status':p['status']})
# Exact integer-priority envelope refuses rounded large sum.
q=copy.deepcopy(c['request']);q['horizon']=float(2**53-1)
try:_heuristic_envelope(c['graph'],c['hazard'],q);raise AssertionError('unsafe heuristic envelope admitted')
except ValueError as exc:assert str(exc)=='HEURISTIC_EXACT_PRIORITY_ENVELOPE'
rows.append({'id':'exact_heuristic_priority_envelope','status':'REFUSED'})
report={'status':'PASS','checks':len(rows),'checks_detail':rows,'wall_s':time.perf_counter()-started,'scope':'Finite center-contract/API ownership/cap controls only; no compatible physical source constructed. All physical road outcomes unresolved.'};(D/'review/WRAPPER_DEVELOPMENT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='checks_detail'}))
