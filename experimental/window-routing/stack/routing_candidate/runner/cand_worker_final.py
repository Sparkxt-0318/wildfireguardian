"""CANDIDATE worker: identical contract to the frozen cold worker except graph admission
runs once (PreparedGraph) and is reused by core.solve(prepared=...). Arms select a
candidate solver option. The fresh whole-road checker is unchanged and still mandatory."""
import time
START = time.perf_counter()
import argparse, copy, datetime, hashlib, json, os, pathlib, resource, signal, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = {}; FOLDER = None; WRITE = None
class DeadlineStop(Exception): pass
def stop(signum, frame): raise DeadlineStop('Parent complete deadline')
signal.signal(signal.SIGTERM, stop)
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def canonical(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def resolve(p):
 p=pathlib.Path(p);return p if p.is_absolute() else ROOT/p
def main():
 global STATE,FOLDER,WRITE
 p=argparse.ArgumentParser();p.add_argument('--job-file',required=True);a=p.parse_args()
 job=json.loads(pathlib.Path(a.job_file).read_text());FOLDER=resolve(job['output_path']);assert FOLDER.is_dir()
 src=resolve(job['source_root']);arm=job['arm'];ARM_SOLVER={'CAND_N_T':'astar','CAND_NO_T':'astar_opening','CAND_NOR_T':'astar_opening','CAND_N_A':'dijkstra'};assert arm in ARM_SOLVER
 origin=float(os.environ['WFG_OUTER_MONOTONIC_START']);deadline=origin+float(job['complete_budget_s'])
 sys.path[:0]=[str(src/'baseline/routing-package'),str(src/'baseline'),str(src/'search')]
 from exact_transport import preflight,atomic_create
 WRITE=lambda name,obj:atomic_create(FOLDER/(name+'.json'),preflight(obj))
 STATE={'schema':'wfg.audit.cand-worker/1','job_id':job['label'],'case_id':job['case_id'],'cohort':job['cohort'],'arm':arm,'repetition':job['rep'],'source_root':str(src),'source_directory':str(resolve(job['source_directory'])),'complete_budget_s':job['complete_budget_s'],'started_utc':utc(),'worker_import_start_monotonic':START,'outer_start_monotonic':origin,'deadline_monotonic':deadline,'result':None,'whole_road_check':{'status':'NOT_RUN','reason':'NO_SOLVER_WITNESS'},'stages':{},'identities':{},'physical_safety_claim':False,'original_limits':job['original_limits']}
 def checkpoint(phase):WRITE('STAGE_'+phase,{'phase':phase,'utc':utc(),'monotonic':time.perf_counter(),'elapsed_from_outer_s':time.perf_counter()-origin})
 checkpoint('IMPORTED');t=time.perf_counter()
 paths={k:resolve(job[k]) for k in ('graph_path','hazard_path','request_path')}
 objects={k:json.loads(v.read_text()) for k,v in paths.items()}
 for k,v in paths.items():
  actual=sha(v)
  if actual!=job['input_sha256'][k]:raise ValueError('INPUT_HASH_MISMATCH:'+k)
  STATE['identities'][k]={'path':str(v),'sha256':actual,'canonical_sha256':canonical(objects[k])}
 packet=resolve(job['source_directory'])
 for n,expected in job['source_sha256'].items():
  actual=sha(packet/n)
  if actual!=expected:raise ValueError('SOURCE_HASH_MISMATCH:'+n)
  STATE['identities']['source:'+n]={'path':str(packet/n),'sha256':actual}
 graph,hazard,original=(objects[k] for k in ('graph_path','hazard_path','request_path'))
 WRITE('ORIGINAL_REQUEST',original);STATE['stages']['load_hash_binding_s']=time.perf_counter()-t;checkpoint('INPUTS_BOUND')
 from routing import core,validation
 actual_core=pathlib.Path(core.__file__).resolve();expected_core=(src/'baseline/routing-package/routing/core.py').resolve()
 if actual_core!=expected_core:raise ValueError('ACTUAL_IMPORTED_CORE_PATH_MISMATCH')
 actual_core_sha256=sha(actual_core)
 if job.get('core_sha256',actual_core_sha256)!=actual_core_sha256:raise ValueError('ACTUAL_IMPORTED_CORE_HASH_MISMATCH')
 from clock_scope import check_clock_scope
 t=time.perf_counter();from routing.prepared import PreparedGraph;pg=PreparedGraph(graph);vg=pg.snapshot();vh=validation.validate_hazard(vg,hazard,original.get('as_of'),_graph_validated=True);vr=validation.validate_request(vg,vh,original,_validated_inputs=True);scope=check_clock_scope(vh,vr);STATE['clock_scope']=scope;STATE['stages']['normal_admission_clock_s']=time.perf_counter()-t;checkpoint('ADMITTED')
 request=copy.deepcopy(original);request['solver']=ARM_SOLVER[arm]
 request['limits']['wall_s']=max(0.,deadline-time.perf_counter())
 STATE['engine_binding']={'core_path':str(src/'baseline/routing-package/routing/core.py'),'core_sha256':actual_core_sha256,'actual_imported_core_path':str(actual_core),'actual_imported_core_sha256':actual_core_sha256,'actual_callable_module':core.solve.__module__,'solver':request['solver'],'actual_invocations':0,'original_request_sha256':STATE['identities']['request_path']['sha256'],'actual_search_request_canonical_sha256':canonical(request),'selected_core_unchanged':True}
 WRITE('ACTUAL_SEARCH_REQUEST',request);WRITE('ENGINE_BINDING',STATE['engine_binding'])
 if not scope['supported']:result={'status':'UNKNOWN','reason':'EXACT_CLOCK_SCOPE_UNSUPPORTED','solver_status':'UNSUPPORTED_CLOCK_SCOPE','legs':[],'destination':None,'arrival':None,'metrics':{}}
 elif time.perf_counter()>=deadline:result={'status':'TIMEOUT','reason':'NO_REMAINING_COMPLETE_BUDGET','solver_status':'INCOMPLETE_CAP','legs':[],'destination':None,'arrival':None,'metrics':{}}
 else:
  # The final provenance write is charged; the original remaining search cap
  # is conservatively smaller again. Logical caps and all science unchanged.
  request['limits']['wall_s']=max(0.,deadline-time.perf_counter());WRITE('FINAL_SEARCH_REQUEST',request)
  STATE['engine_binding']['actual_invocations']=1;STATE['engine_binding']['actual_search_wall_s']=request['limits']['wall_s'];STATE['engine_binding']['actual_search_request_canonical_sha256']=canonical(request)
  t=time.perf_counter();result=core.solve(graph,hazard,request,prepared=pg);STATE['stages']['search_including_internal_preparation_s']=time.perf_counter()-t
 STATE['result']=result;WRITE('SEARCH_RESULT',{'result':result,'engine_binding':STATE['engine_binding'],'authority':'Secondary raw primary evidence; outer complete gate determines on-time success.'});checkpoint('SEARCH_RETURNED')
 route=result if result.get('destination') is not None else result.get('checked_incumbent')
 if route is not None:
  STATE['whole_road_check']={'status':'UNRESOLVED','reason':'CHECK_INITIALIZATION_NOT_COMPLETED'}
  STATE['returned_witness_role']='PRIMARY' if result.get('destination') is not None else 'CHECKED_TIMEOUT_INCUMBENT'
  if time.perf_counter()>=deadline:STATE['whole_road_check']={'status':'UNRESOLVED','reason':'NO_REMAINING_COMPLETE_BUDGET'}
  else:
   from hybrid_checker import HybridChecker
   if job.get('checker_module'):
    import importlib;_m=importlib.import_module(job['checker_module']);HybridChecker=_m.HybridChecker
    _files={n:sha(pathlib.Path(_m.__file__).parent/n) for n in job.get('checker_sha256',{})}
    if _files!=job.get('checker_sha256',{}) or not _files:raise ValueError('CHECKER_MODULE_HASH_MISMATCH')
    STATE['checker_module']={'module':job['checker_module'],'path':_m.__file__,'sha256':_files}
   from mission_contract import graph_digest
   STATE['whole_road_check']={'status':'UNRESOLVED','reason':'CHECK_STARTED_NOT_COMPLETED'}  # REPAIR: honest label if stopped mid-check
   t=time.perf_counter();STATE['whole_road_check']=HybridChecker(packet).check(graph,original,route['legs'],route['destination'],deadline=deadline,wall_s=max(0.,deadline-time.perf_counter()),expected_graph_revision=graph['revision'],expected_graph_sha256=graph_digest(graph));STATE['stages']['fresh_whole_road_constructor_check_s']=time.perf_counter()-t
 WRITE('WHOLE_ROAD_CHECK',STATE['whole_road_check']);checkpoint('ROAD_CHECK_RETURNED')
 t=time.perf_counter()
 for k,v in paths.items():
  if sha(v)!=STATE['identities'][k]['sha256'] or canonical(objects[k])!=STATE['identities'][k]['canonical_sha256']:raise ValueError('FINAL_INPUT_AUTHORITY_CHANGED:'+k)
 for n,expected in job['source_sha256'].items():
  if sha(packet/n)!=expected:raise ValueError('FINAL_SOURCE_AUTHORITY_CHANGED:'+n)
 STATE['stages']['final_input_source_binding_s']=time.perf_counter()-t;STATE['authority_final']=True
 STATE.update(primary_status=result['status'],primary_reason=result.get('reason'),worker_elapsed_before_publication_s=time.perf_counter()-START,elapsed_from_outer_before_publication_s=time.perf_counter()-origin,publication_started_utc=utc(),self_lifetime_highwater_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 WRITE('RESULT',STATE);end=time.perf_counter();WRITE('PUBLICATION_BOUNDARY',{'utc':utc(),'monotonic_after_result_publication':end,'elapsed_from_outer_after_result_publication_s':end-origin,'result_published_before_deadline':end<=deadline,'scope':'RESULT completed; boundary receipt/normal process exit remain charged by outer process completion.'})
 print(json.dumps({'job':job['label'],'primary_status':result['status'],'whole_road_status':STATE['whole_road_check']['status'],'worker_elapsed_s':time.perf_counter()-START}))
if __name__=='__main__':
 try:main()
 except BaseException as exc:
  if WRITE is None:raise
  STATE.update(worker_failure={'type':type(exc).__name__,'reason':str(exc)},publication_complete=False,authority_final=False,worker_cleanup_elapsed_s=time.perf_counter()-START,primary_status=(STATE.get('result') or {}).get('status','TIMEOUT' if isinstance(exc,DeadlineStop) else 'NOT_RUN'))
  # Keep returned primary/checked incumbent unchanged if a later stage stops.
  if STATE.get('result') is None:STATE['result']={'status':'TIMEOUT' if isinstance(exc,DeadlineStop) else 'UNKNOWN','reason':str(exc),'solver_status':'INCOMPLETE_CAP' if isinstance(exc,DeadlineStop) else 'UNSUPPORTED','legs':[],'destination':None,'arrival':None,'metrics':{}}
  WRITE('FAILURE',STATE)
  if not (FOLDER/'RESULT.json').exists():WRITE('RESULT',STATE)
  print(json.dumps({'failure':type(exc).__name__,'reason':str(exc)}));sys.exit(2)
