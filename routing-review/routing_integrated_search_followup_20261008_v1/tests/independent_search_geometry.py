"""Independent geometry translation and complete owner-binding stress controls."""
from pathlib import Path
from fractions import Fraction as F
import sys,json,copy,time,resource,types
from unittest.mock import patch
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'review'),str(D/'tests'),str(D/'candidate/routing-package')]
from reference_fixtures import fixtures
from search_reference import spans,exhaustive,witness
from routing.search_geometry_cache import SearchGeometryCache
from routing.core_cached import solve_cached
from routing.core import solve
start=time.perf_counter();rows=[];g=fixtures()[0]['graph'];owner=SearchGeometryCache(g)
for edge in g['edges']:
 for f,q in [(0,1),(.5,1),(.1,1),(.5,.5)]:
  for a,b in [(0,1),(7.5,11.5)]:
   actual=owner.occupancies(edge['id'],a,b,f,q);ref=spans(g,{'kind':'EDGE','edge':edge['id'],'start':a,'end':b,'from_fraction':f,'to_fraction':q});assert sorted((v['cell'],v['start'],v['end'])for v in actual)==sorted(ref),(edge,f,q,a,b,actual,ref)
   if actual:actual[0]['cell']=999
   again=owner.occupancies(edge['id'],a,b,f,q);assert all(x['cell']!=999 for x in again);rows.append({'id':'affine_geometry','edge':edge['id'],'fraction':[f,q],'time':[a,b]})
# Full canonical graph matching, including semantics unrelated to the static chord.
for name,change in [('revision',lambda x:x.update(revision='new')),('turns',lambda x:x['forbidden_turns'].append(['AB','BM'])),('waitable',lambda x:x['nodes'][0].update(waitable=False)),('coordinate',lambda x:x['nodes'][0].update(x=5.25)),('grid',lambda x:x['grid'].update(width=7)),('travel_ticks',lambda x:x['edges'][0].update(travel_ticks=2)),('reversal',lambda x:x.update(mid_edge_reversal=True)),('extra',lambda x:x.update(extra_metadata='changed'))]:
 mutated=copy.deepcopy(g);change(mutated);assert not owner.matches(mutated);rows.append({'id':'owner_content_changed','dependency':name})
assert owner.matches(g);snap=owner.snapshot();snap['nodes'][0]['x']=999;assert owner.matches(g)
for c in fixtures():
 for ordering in ['baseline','astar']:
  req=copy.deepcopy(c['request']);req['solver']=ordering;exact=exhaustive(c['graph'],c['hazard'],req)
  for enabled in [False,True]:
   r=solve_cached(c['graph'],c['hazard'],req,cache_enabled=enabled);assert r['status']==c['expected']['center_status'],(c['id'],ordering,enabled,r)
   if r['status']in ['CONDITIONAL_OPTIMUM','CHECKED_ROUTE']:
    check=witness(c['graph'],c['hazard'],req,r['legs'],r['destination']);assert check['ok'] and float(check['arrival'])==r['arrival']==float(exact['arrival'])
   rows.append({'id':'exact_four_modes','case':c['id'],'cache':enabled,'ordering':ordering,'status':r['status'],'arrival':r['arrival']})
# Reusable geometry never caches hazard/request/cost outcomes.
c=fixtures()[0];reuse=SearchGeometryCache(c['graph']);r=solve_cached(c['graph'],c['hazard'],c['request'],geometry_cache=reuse);assert r['status']=='CONDITIONAL_OPTIMUM'
h=copy.deepcopy(c['hazard'])
for m in h['members']:
 for row in m['flame']:row[8]=True
r=solve_cached(c['graph'],h,c['request'],geometry_cache=reuse);assert r['status']=='PROVEN_INFEASIBLE';rows.append({'id':'same_graph_changed_hazard','status':r['status']})
q=copy.deepcopy(c['request']);q['incurred']['m0']=101;r=solve_cached(c['graph'],c['hazard'],q,geometry_cache=reuse);assert r['status']=='AT_ISSUE_FAILURE';rows.append({'id':'same_graph_changed_incurred','status':r['status']})
for field,value in [('wall_s',0),('max_labels',1),('max_expansions',1)]:
 q=copy.deepcopy(c['request']);q['limits'][field]=value;r=solve_cached(c['graph'],c['hazard'],q);assert r['status']=='TIMEOUT';rows.append({'id':'bounded_cap','field':field,'status':r['status']})
q=copy.deepcopy(fixtures()[3]['request']);q['limits']['frontier_width']=1;c=fixtures()[3];r=solve_cached(c['graph'],c['hazard'],q);assert r['status']=='TIMEOUT' and r['reason']=='FRONTIER_WIDTH';rows.append({'id':'incomparable_member_frontier_cap','status':r['status']})
# Failed complete-template construction never commits partial data.
from routing import core as original_core,core_cached as measured_core
empty=SearchGeometryCache(g)
def partial_then_fail(*args,**kwargs):
 def gen():
  yield {'cell':0,'start':F(0),'end':F(1)}
  raise ArithmeticError('independent simulated incomplete geometry')
 return gen()
with patch.object(original_core,'edge_occupancies',partial_then_fail):
 try:empty.occupancies('AB',0,1);raise AssertionError('failed template falsely completed')
 except ArithmeticError:pass
assert empty.cache_info()['entries']==0
assert empty.occupancies('AB',0,1);rows.append({'id':'failed_template_atomicity','status':'NO_PARTIAL_ENTRY'})
# A final RSS breach with a checked route retains only secondary witness evidence.
c=fixtures()[0];rsscalls=[0]
def controlled_rss(_):
 rsscalls[0]+=1;mb=3073 if rsscalls[0]>=2 else 1
 return types.SimpleNamespace(ru_maxrss=mb*(1048576 if sys.platform=='darwin' else 1024))
with patch.object(measured_core,'resource',types.SimpleNamespace(getrusage=controlled_rss,RUSAGE_SELF=0)):
 r=measured_core.solve_cached(c['graph'],c['hazard'],c['request'])
assert r['status']=='TIMEOUT'and r['reason']=='RSS_LIMIT_DURING_FINALIZATION'and r['checked_incumbent']['checker']['ok']
rows.append({'id':'late_final_RSS_checked_incumbent','status':r['status']})
report={'status':'PASS','checks':len(rows),'checks_detail':rows,'cache_lifetime':owner.cache_info(),'wall_s':time.perf_counter()-start,'scope':'Finite exact geometry/center-contract controls; no road-source or network general-performance claim.'};(D/'review/GEOMETRY_DEVELOPMENT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='checks_detail'}))
