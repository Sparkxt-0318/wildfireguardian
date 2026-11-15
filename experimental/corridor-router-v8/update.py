"""Fourth native arm: legal waiting, corridor contact and destination occupancy."""
import os
import signal
import sys
import time

if not __debug__:
    raise RuntimeError("This research worker requires Python assertions to be enabled")
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

HERE=Path(__file__).resolve().parent
from io_utils import dump,read,sha
from corridors import RoadIndex,SearchGraph,partition
from corridor_events import make_entry_sets,union
from legal import search,check_deadline
from drive_search import least_driving,road_cost
from loop_search import candidate_plans


def get_contact(graph,source,request):
    g=graph['grid'];w=g['width'];h=g['height']
    x0,y0,res=F(g['x0']),F(g['y0']),F(g['resolution'])
    if source.unsupported or source.horizon<request['horizon'] or len(source.rectangles)!=w*h:
        raise ValueError('UNSUPPORTED_SOURCE_OR_HORIZON')
    if set(source.ids)!=set(request['incurred']) or res<=0:
        raise ValueError('SCENARIO_OR_GRID_MISMATCH')
    cells=defaultdict(list)
    for member in source.phases:
        for i,b,e,_ in member:
            r,c=divmod(i,w);y=h-1-r
            rect=(x0+c*res,x0+(c+1)*res,y0+y*res,y0+(y+1)*res)
            if source.rectangles[i]!=rect:raise ValueError('GRID_ALIGNMENT')
            cells[y*w+c].append((b,e))
    merged={k:union(v) for k,v in cells.items()}
    points={};z=request['destinations'][0]['node']
    for n in graph['nodes']:
        if not n['waitable'] and n['id']!=z:continue
        x=(F(n['x'])-x0)/res;y=(F(n['y'])-y0)/res
        col=x.numerator//x.denominator;row=y.numerator//y.denominator
        cs=(col-1,col) if x.denominator==1 else (col,)
        rs=(row-1,row) if y.denominator==1 else (row,)
        periods=union(v for c in cs for r in rs if 0<=c<w and 0<=r<h for v in merged.get(r*w+c,()))
        if periods:points[n['id']]=periods
    return merged,points


def main():
    p=Path(sys.argv[1]);j=read(p);out=Path(j['output_path'])
    t0=float(os.environ['WFG_OUTER_MONOTONIC_START']);deadline=t0+30
    src=Path(j['source_root']);phase=src.parent/'phaseB';packet=Path(j['source_directory'])
    full=phase/'rda_worker_v1_1.py';trace={'method':'corridor','steps':[]}
    def record(stage,**props):
        trace['steps'].append(dict(phase=stage,elapsed_s=time.perf_counter()-t0,**props))
    def traced():
        dump(out/'UPDATE_TRACE.json',trace)
    def fallback(reason):
        record('FALLBACK_TO_FULL',reason=reason);traced()
        os.execv(sys.executable,[sys.executable,'-B',str(full),'--job-file',str(p)])
    for name,digest in j['input_sha256'].items():
        if sha(j[name])!=digest:raise ValueError('INPUT_AUTHORITY')
    for name,digest in j['source_sha256'].items():
        if sha(packet/name)!=digest:raise ValueError('SOURCE_AUTHORITY')
    if sha(full)!=j['phaseB_sha256'][full.name]:raise ValueError('FALLBACK_AUTHORITY')
    for n,h in j['checker_sha256'].items():
        if sha(src/'baseline'/n)!=h:raise ValueError('CHECKER_AUTHORITY')
    if sha(src/'baseline/routing-package/routing/core.py')!=j['core_sha256']:
        raise ValueError('CORE_AUTHORITY')
    sys.path[:0]=[str(src/'baseline/routing-package'),str(src/'baseline'),str(src/'search'),
                  str(phase),str(j['decision_dir'])]
    from adaptive_checker import HybridChecker
    from clock_scope import check_clock_scope
    from contact_first import ContactSources
    from mission_contract import graph_digest
    from preparation_mode import prepare_graph
    from routing import validation
    graph=read(j['graph_path']);q=read(j['request_path']);haz=read(j['hazard_path'])
    if (j.get('update_arm')!='corridor' or len(q['destinations'])!=1 or
        set(q['position'])!={'node'} or haz['dt']!=1 or q['exposure_scope']!='including_dwell'):
        fallback('UNSUPPORTED_GRAMMAR')
    d=q['destinations'][0]
    if any(int(t)!=t for t in (q['departure'],q['horizon'],d['dwell'])) or q['horizon']>3600:
        fallback('UNSUPPORTED_CLOCK')
    vg=prepare_graph(graph,j,{}).snapshot()
    vh=validation.validate_hazard(vg,haz,q['as_of'],_graph_validated=True)
    vr=validation.validate_request(vg,vh,q,_validated_inputs=True)
    if not check_clock_scope(vh,vr)['supported']:fallback('CLOCK_ADMISSION')
    meta=read(packet/'NATIVE_METADATA.json')
    if meta['time_origin']!=haz['time_origin'] or meta['graph_revision']!=graph['revision'] or meta['crs']!=graph['crs']:
        fallback('PACKET_BINDING')
    del vg,vh,vr,haz
    # Reserve time for a native fallback if constructing the time-expanded relaxation is expensive.
    search_deadline=min(deadline-2,t0+15)
    try:
        check_deadline(search_deadline)
        source=ContactSources.from_case(packet,deadline=search_deadline)
        contact,points=get_contact(graph,source,q)
        index=RoadIndex(graph);parts,_=partition(index,{q['position']['node'],d['node']})
        compiled=SearchGraph(index,parts)
        forbidden,events=make_entry_sets(graph,compiled,contact,int(q['horizon']))
        record('corridor_compilation',native_edges=len(index.edges),corridors=len(parts),
               contact_entry_intervals=events,source_content_sha256=source.content_sha256)
        route,ev=search(compiled,forbidden,points,q,search_deadline)
        record('legal_wait_search',**ev)
        del compiled,index,parts,forbidden,source
    except (TimeoutError,ValueError) as e:
        fallback('CORRIDOR_STAGE_UNRESOLVED:'+str(e))
    if route is None:
        if not ev['exhausted']:raise ArithmeticError('Incomplete search cannot prove absence')
        record('REFUSAL_PROVEN',certificate=ev['reason']);traced()
        dump(out/'RESULT.json',{'result':{'status':'MODEL_INFEASIBLE','legs':[],'destination':None,'arrival':None},
             'optimality_certificate':{'complete':True,'exhausted':True,'reason':ev['reason'],
                                      'relaxation_kind':'legal_corridor_contact_lattice'},
             'decision':{'authoritative_status':'FULL_MODEL_REFUSAL_PROVEN','physical_safety_claim':False}})
        return
    rec=HybridChecker(packet).check(graph,q,route['legs'],route['destination'],deadline=deadline,
            wall_s=max(0,deadline-time.perf_counter()),expected_graph_revision=graph['revision'],
            expected_graph_sha256=graph_digest(graph))
    record('whole_journey_check',status=rec['status'],reason=rec.get('reason'))
    if rec['status']!='CERTIFIED_ADMISSIBLE':
        from heat import certify
        certificate=certify(graph,q,packet,step=30,contact=contact,points=points,tight=True)
        dump(out/'HEAT_TRACE.json',certificate)
        if certificate and certificate['proved']:
            record('REFUSAL_PROVEN',certificate='integer_lower_dose_on_time_expanded_roads');traced()
            dump(out/'RESULT.json',{'result':{'status':'MODEL_INFEASIBLE','legs':[],'destination':None,'arrival':None},
                 'optimality_certificate':{'complete':True,'exhausted':True,'reason':'MINIMUM_DOSE_EXCEEDS_BUDGET',
                                          'relaxation_kind':'integer_lower_dose_on_time_expanded_roads','heat_certificate':certificate},
                 'decision':{'authoritative_status':'FULL_MODEL_REFUSAL_PROVEN','physical_safety_claim':False}})
            return
        if certificate and time.perf_counter()<deadline-2:
            from discover import find
            # A sharper independently enclosed upper bound checks promising
            # candidates before falling back to the original checker.
            # A timeout or an inconclusive enclosure never publishes a route.
            checked = None
            candidate = None
            from world import make_world
            from fine_check import evaluate
            world = make_world(j['graph_path'],packet)
            def fine_timeout(_signum,_frame):
                raise TimeoutError('fine check deadline')
            previous_handler = signal.signal(signal.SIGALRM,fine_timeout)
            try:
                for slack in (.993,.99,.75):
                    if time.perf_counter()>=deadline-6:
                        break
                    candidate=find(graph,q,packet,slack=slack)
                    if candidate is None:
                        continue
                    remaining=deadline-.8-time.perf_counter()
                    if remaining<=0:
                        break
                    fine_budget=min(remaining,9.0)
                    try:
                        signal.setitimer(signal.ITIMER_REAL,fine_budget)
                        evidence=evaluate(world,q,candidate,span=6,grid=1)
                        signal.setitimer(signal.ITIMER_REAL,0)
                        accepted=evidence['verified_feasible']
                    except (TimeoutError,AssertionError,ValueError):
                        accepted=False
                        evidence={'verified_feasible':False,'reason':'inconclusive'}
                    finally:
                        signal.setitimer(signal.ITIMER_REAL,0)
                    record('fine_thermal_candidate',arrival=candidate['arrival'],
                           slack=slack,verified=accepted)
                    if accepted:
                        checked={'status':'CERTIFIED_ADMISSIBLE',
                                 'reason':'DIRECTED_SOLID_ANGLE_UPPER_ENCLOSURE',
                                 'evidence':evidence}
                        # Retain this witness while exploring a finer, faster
                        # arrival. Only a complete independent upper enclosure
                        # can replace it.
                        if slack == .993 and time.perf_counter()<deadline-6:
                            tighter=find(graph,q,packet,slack=.997)
                            if tighter is not None and tighter['arrival']<candidate['arrival']:
                                try:
                                    fine_budget=max(0,deadline-.8-time.perf_counter())
                                    if fine_budget>0:
                                        signal.setitimer(signal.ITIMER_REAL,fine_budget)
                                        tighter_evidence=evaluate(world,q,tighter,span=2,grid=1)
                                        signal.setitimer(signal.ITIMER_REAL,0)
                                        if tighter_evidence['verified_feasible']:
                                            candidate=tighter
                                            checked={'status':'CERTIFIED_ADMISSIBLE',
                                                     'reason':'DIRECTED_SOLID_ANGLE_UPPER_ENCLOSURE',
                                                     'evidence':tighter_evidence}
                                except (TimeoutError,AssertionError,ValueError):
                                    pass
                                finally:
                                    signal.setitimer(signal.ITIMER_REAL,0)
                        break
                if checked is None and time.perf_counter()<deadline-1:
                    # The original complete-journey checker remains the authority
                    # for candidates the faster enclosure does not establish.
                    candidate=find(graph,q,packet,slack=.75)
                    if candidate is not None:
                        checked=HybridChecker(packet).check(graph,q,candidate['legs'],candidate['destination'],
                            deadline=deadline-.5,wall_s=max(0,deadline-.5-time.perf_counter()),
                            expected_graph_revision=graph['revision'],expected_graph_sha256=graph_digest(graph))
                        if checked['status']!='CERTIFIED_ADMISSIBLE':
                            checked=None
            finally:
                signal.setitimer(signal.ITIMER_REAL,0)
                signal.signal(signal.SIGALRM,previous_handler)
            if checked is not None:
                bound=max(certificate['earliest_lower'],route['arrival'])
                if bound>candidate['arrival']:raise ArithmeticError('Contradictory thermal arrival lower bound')
                exact=bound==candidate['arrival']
                decision='CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN' if exact else 'CHECKED_JOURNEY_FEASIBLE'
                record('PUBLISHED',decision=decision,lower_bound_arrival=bound);traced()
                dump(out/'TIEBREAK_TRACE.json',{'minimum_drive_proved':False,'initial_drive_s':road_cost(candidate),
                    'final_drive_s':road_cost(candidate),'reason':'NEW_VERIFIED_HEAT_BOUNDED_WITNESS'})
                dump(out/'RESULT.json',{'result':{**candidate,'status':'CHECKED_ROUTE'},'whole_road_check':checked,
                    'optimality_certificate':{'complete':exact,'lower_bound_arrival':bound,'upper_bound_arrival':candidate['arrival'],
                                              'relaxation_kind':'integer_lower_dose_on_time_expanded_roads'},
                    'decision':{'authoritative_status':decision,'physical_safety_claim':False}})
                return
        fallback('CORRIDOR_WITNESS_'+str(rec.get('reason',rec['status'])))
    # Keep the already checked earliest-arrival witness available if refinement
    # cannot complete within its bounded share of the original request deadline.
    original=route
    outcome={'initial_drive_s':road_cost(route),'final_drive_s':road_cost(route),
             'minimum_drive_proved':False,'reason':'NOT_ATTEMPTED','stages':[]}
    refine_deadline=min(deadline-1.5,time.perf_counter()+4.0)
    def interrupted(_sig,_frame):
        raise TimeoutError('refinement deadline')
    previous=signal.signal(signal.SIGALRM,interrupted)
    try:
        if refine_deadline>time.perf_counter():
            signal.setitimer(signal.ITIMER_REAL,refine_deadline-time.perf_counter())
            from world import make_world
            world=make_world(j['graph_path'],packet)
            candidates=candidate_plans(q,route,world)
            for saved,candidate in candidates:
                if time.perf_counter()>=refine_deadline:break
                checked=HybridChecker(packet).check(graph,q,candidate['legs'],candidate['destination'],
                    deadline=refine_deadline,wall_s=max(0,refine_deadline-time.perf_counter()),
                    expected_graph_revision=graph['revision'],expected_graph_sha256=graph_digest(graph))
                outcome['stages'].append({'stage':'cycle_removal','saved_s':saved,'status':checked['status']})
                if checked['status']=='CERTIFIED_ADMISSIBLE':
                    route,rec=candidate,checked
                    break
            why,candidate,count=least_driving(world,q,route['arrival'],road_cost(route),
                                               refine_deadline,100000)
            outcome['reason']=why;outcome['states']=count
            if why in ('STATIC_BOUND','EXHAUSTED'):
                outcome['minimum_drive_proved']=True
            if candidate is not None and time.perf_counter()<refine_deadline:
                checked=HybridChecker(packet).check(graph,q,candidate['legs'],candidate['destination'],
                    deadline=refine_deadline,wall_s=max(0,refine_deadline-time.perf_counter()),
                    expected_graph_revision=graph['revision'],expected_graph_sha256=graph_digest(graph))
                outcome['stages'].append({'stage':'minimum_drive','status':checked['status']})
                if checked['status']=='CERTIFIED_ADMISSIBLE':
                    route,rec=candidate,checked
                    outcome['minimum_drive_proved']=True
        else:
            outcome['reason']='INSUFFICIENT_TIME'
    except TimeoutError:
        outcome['reason']='REFINEMENT_DEADLINE'
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
    assert route['arrival']==original['arrival'] and route['destination']==original['destination']
    outcome['final_drive_s']=road_cost(route)
    assert outcome['final_drive_s']<=outcome['initial_drive_s']
    dump(out/'TIEBREAK_TRACE.json',outcome)
    record('minimum_driving_tiebreak',**outcome)
    record('PUBLISHED',certificate='legal_corridor_contact_lattice');traced()
    dump(out/'RESULT.json',{'result':{**route,'status':'CHECKED_ROUTE'},'whole_road_check':rec,
         'optimality_certificate':{'complete':True,'lower_bound_arrival':route['arrival'],
                                  'relaxation_kind':'legal_corridor_contact_lattice'},
         'decision':{'authoritative_status':'CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN','physical_safety_claim':False}})


if __name__=='__main__':
    main()
