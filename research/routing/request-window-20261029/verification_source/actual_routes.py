"""Independent read-only whole-trajectory reference for the 15 bound contexts.

No project checker is imported. NPZ is decoded by NumPy; proof arithmetic and
geometry use the separately sealed rational-interval oracle.
"""
from pathlib import Path
from fractions import Fraction as Q
import argparse, hashlib, json, math, sys, time
import oracle as O

ROOT=Path(__file__).resolve().parent.parent
WS=ROOT.parents[1]
STUDY=WS/'outputs/routing_final_input_ablation_20261016_v1/study'
CARD=ROOT/'audit/CARDINALITY_SOURCE_SEAL.json'
SEAL=ROOT/'reference/ACTUAL_ROUTES_SOURCE_SEAL.json'

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):
    p=Path(p)
    if p.exists():raise RuntimeError('OUTPUT_EXISTS:'+str(p))
    p.write_text(json.dumps(O.encode(value),indent=2,sort_keys=True,allow_nan=False)+'\n')
def check(seal):
    for p,h in seal['source_sha256'].items():
        if sha(p)!=h:raise RuntimeError('SOURCE_CHANGED:'+p)

def witness(graph,request,result):
    """Build full road chords from raw graph nodes, not checker geometry."""
    nodes={n['id']:n for n in graph['nodes']};edges={e['id']:e for e in graph['edges']}
    if len(nodes)!=len(graph['nodes']) or len(edges)!=len(graph['edges']):raise ValueError('DUPLICATE_ID')
    if set(request['position'])!={'node'} or request['exposure_scope']!='including_dwell':raise ValueError('REQUEST_SCOPE')
    node=request['position']['node'];now=O.number(request['departure']);horizon=O.number(request['horizon'])
    incoming=request.get('incoming_edge');forbidden={tuple(x) for x in graph.get('forbidden_turns',[])}
    def point(n):return tuple(O.number(nodes[n][k]) for k in ('x','y'))
    legs=[O.Leg(now,now,point(node),point(node),'ISSUE')];arrived=True
    for raw in result['legs']:
        start,end=map(O.number,(raw['start'],raw['end']))
        if start!=now or not start<end<=horizon:raise ValueError('TIMELINE')
        if raw['kind']=='EDGE':
            edge=edges[raw['edge']]
            if edge['u']!=node or (incoming,edge['id']) in forbidden:raise ValueError('EDGE_CONTEXT')
            if O.number(raw.get('from_fraction',0))!=0 or O.number(raw.get('to_fraction',1))!=1:raise ValueError('PARTIAL_EDGE')
            if type(edge['travel_ticks']) is not int or end-start!=edge['travel_ticks'] or edge['travel_ticks']<=0:raise ValueError('EDGE_DURATION')
            legs.append(O.Leg(start,end,point(node),point(edge['v']),'EDGE'))
            node,incoming,arrived=edge['v'],edge['id'],True
        elif raw['kind']=='WAIT':
            if raw['node']!=node or nodes[node].get('waitable') is not True or end-start!=int(end-start):raise ValueError('WAIT_CONTEXT')
            legs.append(O.Leg(start,end,point(node),point(node),'WAIT'));arrived=False
        else:raise ValueError('LEG_KIND')
        now=end
    if node!=result['destination'] or not arrived or now!=O.number(result['arrival']):raise ValueError('DESTINATION')
    destinations=[d for d in request['destinations'] if d['node']==node]
    if len(destinations)!=1:raise ValueError('DESTINATION_COUNT')
    destination=destinations[0];dwell=O.number(destination['dwell']);finish=now+dwell
    if dwell<0 or dwell!=int(dwell) or finish>horizon:raise ValueError('DWELL')
    if not any(O.number(a)<=now and finish<=O.number(b) for a,b in destination['open_intervals']):raise ValueError('DESTINATION_OPENING')
    legs.append(O.Leg(now,finish,point(node),point(node),'DWELL'))
    if sum(l.end-l.start for l in legs)!=finish-legs[0].start:raise ValueError('COVERAGE')
    return legs

def context(c):
    import numpy as np
    job=read(c['job']);grade=read(c['grade']);result=read(c['result'])['result']
    if result.get('destination') is None:result=result['checked_incumbent']
    packet=Path(c['packet']);report=read(packet/'REPORT.json');md=report['native_metadata'];a=md['construction']['assumptions']
    request=read(STUDY/job['full_request_path']);graph=read(STUDY/job['graph_path'])
    ids=tuple(md['construction']['scenario_ids'])
    if ids!=tuple(report['rows'][0]['request']['incurred']) or ids!=tuple(request['incurred']) or set(ids)!=set(request['budgets']['dose']):raise ValueError('MEMBER_AXIS_BINDING')
    if a['version']!='wfg.hazard.construction/1' or md['evidence_class']!='RESEARCH_CONSTRUCTION':raise ValueError('SOURCE_LAW')
    affine=tuple(map(O.number,md['affine_transform']));dx,b,x0,d,dy,y0=affine
    if b or d or not dx or not dy:raise ValueError('AXIS_ALIGNED_AFFINE_REQUIRED')
    duration=O.number(a['burning_duration_s']);remaining=O.number(a['initial_remaining_s']);horizon=O.number(a['horizon_s'])
    if not 0<=remaining<=duration or duration<=0 or horizon<=0 or O.number(request['horizon'])>horizon:raise ValueError('SOURCE_TIME_DOMAIN')
    # Preserve each binary64 operation in the declared scalar resolution law.
    # This does not assert these physical parameters equal real-world values.
    fuel,consumed,heat,T,rad,tau=(float(a[k]) for k in ('fuel_load_kg_m2','consumed_fraction','heat_of_combustion_j_kg','burning_duration_s','radiative_fraction','atmospheric_transmissivity'))
    resolved=(((fuel*consumed)*heat)/T)*rad*tau
    separation=float(a['emission_height_m'])-float(a['receiver_height_m'])
    if not math.isfinite(resolved) or resolved<0 or not 0<=rad<=1 or not 0<=tau<=1 or not math.isfinite(separation) or separation<=0:raise ValueError('SCALAR_DOMAIN')
    density,height=O.number(resolved),O.number(separation)
    with np.load(packet/'constructed_arrays.npz',allow_pickle=False) as z:
        events=np.array(z['ignition_time_s'],copy=True);current=np.array(z['current_active'],copy=True);support=np.array(z['support'],copy=True)
    if events.ndim!=3 or current.dtype!=np.bool_ or current.shape!=events.shape[1:] or len(ids)!=events.shape[0]:raise ValueError('SOURCE_SHAPE')
    support_shape_ok=support.shape in (events.shape[1:],events.shape) or (support.ndim==4 and support.shape[0]==events.shape[0] and support.shape[1]>0 and support.shape[2:]==events.shape[1:])
    if support.dtype!=np.bool_ or not support.all() or not support_shape_ok:raise ValueError('COMPLETE_SUPPORT_REQUIRED')
    if np.isnan(events).any() or (events<0).any() or np.isfinite(events[:,current]).any():raise ValueError('SOURCE_EVENTS')
    rows,cols=events.shape[1:]
    if list(md['shape'])!=[rows,cols]:raise ValueError('METADATA_SHAPE')
    def rectangle(row,col):
        xa,xb=x0+col*dx,x0+(col+1)*dx;ya,yb=y0+row*dy,y0+(row+1)*dy
        return min(xa,xb),max(xa,xb),min(ya,yb),max(ya,yb)
    members=[]
    for axis,identity in enumerate(ids):
        sources=[]
        for row,col in zip(*np.nonzero(current)):
            if remaining>0:sources.append(O.Source(rectangle(int(row),int(col)),height,density,0,remaining))
        for row,col in zip(*np.nonzero(np.isfinite(events[axis]))):
            birth=O.number(float(events[axis,row,col]))
            if not 0<=birth<horizon:raise ValueError('IGNITION_OUTSIDE_HORIZON')
            sources.append(O.Source(rectangle(int(row),int(col)),height,density,birth,birth+duration))
        members.append((identity,tuple(sources)))
    legs=witness(graph,request,result)
    recorded=grade['full_whole']['trajectory']
    if len(recorded)!=len(legs):raise ValueError('RECORDED_TRAJECTORY_LENGTH')
    for raw,leg in zip(recorded,legs):
        if (raw['kind'],O.number(raw['start']),O.number(raw['end']),tuple(map(O.number,raw['p0'])),tuple(map(O.number,raw['p1'])))!=(leg.kind,leg.start,leg.end,leg.p0,leg.p1):raise ValueError('RECORDED_TRAJECTORY_MISMATCH')
    original={row['id']:row for row in grade['full_whole']['radiation']['per_member']}
    if set(original)!=set(ids):raise ValueError('ORIGINAL_BOUNDS_MEMBER_SET')
    return dict(case_id=job['case_id'],cohort=job['cohort'],legs=legs,members=members,request=request,original=original,
      binding=dict(job_path=c['job'],grade_path=c['grade'],result_path=c['result'],packet_path=str(packet),scenario_ids=ids,affine=affine,
       density_exact=density,height_exact=height,density_resolution='binary64 (((fuel*consumed)*heat)/duration)*radiative_fraction*transmissivity; resolved scalar then exact',height_resolution='binary64 emission_height-receiver_height; resolved scalar then exact',
       source_domain=md.get('regional',{}).get('source_domain'),source_shape=list(events.shape),support_complete=True,raw_witness_matches_recorded_trajectory=True,
       graph_file_sha256=sha(STUDY/job['graph_path']),request_sha256=sha(STUDY/job['full_request_path']),packet_sha256={name:sha(packet/name) for name in ('REPORT.json','NATIVE_METADATA.json','constructed_arrays.npz')}))

def radial_trajectory(sources,legs,*,density,max_records=8192,wall_s=45):
    """Positive area-integral boxes, exact events; capped tails stay enclosed.

    The common-density disjoint native source rectangles are a subset of one
    infinite plane, whose coefficient integral is 1/2. This independent cap
    encloses every uncomputed slab and endpoint. No uncomputed work is zero.
    """
    began=time.monotonic();global_upper=density/2;records=[]
    for leg in legs:
        cuts=sorted({leg.start,leg.end,*[t for s in sources for t in (s.birth,s.expiry) if leg.start<t<leg.end]})
        for t in cuts:records.append((leg,t,t))
        records.extend((leg,a,b) for a,b in zip(cuts,cuts[1:]))
    duration=sum(l.end-l.start for l in legs);dose=O.Interval(0,global_upper*duration);peak=O.Interval(0,global_upper)
    dose_low=Q(0);dose_high=global_upper*duration;peak_low=Q(0);peak_high=Q(0);processed=0;cap=None
    for leg,a,b in records:
        if processed>=max_records:cap='RECORD_CAP';break
        if time.monotonic()-began>=wall_s:cap='WALL_CAP';break
        pa,pb=leg.point(a),leg.point(b);box=(min(pa[0],pb[0]),max(pa[0],pb[0]),min(pa[1],pb[1]),max(pa[1],pb[1]))
        time_point=(a+b)/2;active=[s for s in sources if s.active(time_point)]
        flux=O.Interval.point(0)
        for source in active:flux=flux+O.radial_integral_coefficient(source.rect,box,source.height)*source.density
        flux=O.Interval(max(Q(0),flux.lo),min(global_upper,flux.hi))
        dose_low+=flux.lo*(b-a);dose_high+=(flux.hi-global_upper)*(b-a)
        # Every point flux within a nonempty slab is >= its box lower bound;
        # the essential supremum shares that lower bound even at expiry.
        peak_low=max(peak_low,flux.lo);peak_high=max(peak_high,flux.hi);processed+=1
    dose=O.Interval(dose_low,dose_high);peak=O.Interval(peak_low,global_upper if cap else peak_high)
    return dict(dose=dose,peak=peak,cap=cap,complete_partition=cap is None,records_total=len(records),records_processed=processed,elapsed_s=time.monotonic()-began,
      method='independent positive area-integral source/receiver distance enclosure; unprocessed tail uses proved common-density plane cap')

def assess(route,mode):
    memo={};rows=[];started=time.monotonic()
    for identity,sources in route['members']:
        key=tuple((s.rect,s.height,s.density,s.birth,s.expiry) for s in sources)
        if key not in memo:
            if mode=='triangle':
                memo[key]=O.bound_trajectory(sources,route['legs'],0,max_slabs=4096,dose_tolerance=Q(1,10**4),peak_tolerance=Q(1,10**6),wall_s=60)
            else:memo[key]=radial_trajectory(sources,route['legs'],density=route['binding']['density_exact'],max_records=8192,wall_s=45)
        raw=memo[key];prior=O.number(route['request']['incurred'][identity])*1000
        dose=(raw['dose']+prior)/1000;peak=raw['peak']/1000
        dose_budget=O.number(route['request']['budgets']['dose'][identity]);peak_budget=O.number(route['request']['budgets']['peak'])
        acceptance='PROVED_WITHIN_THERMAL_THRESHOLDS' if dose.hi<=dose_budget and peak.hi<=peak_budget else ('PROVED_THERMAL_VIOLATION' if dose.lo>dose_budget or peak.lo>peak_budget else 'INCONCLUSIVE_THRESHOLDS')
        old=route['original'][identity]
        rows.append(dict(id=identity,source_count=len(sources),incurred_kj_m2=prior/1000,dose_kj_m2=dose,peak_kw_m2=peak,
          dose_budget_kj_m2=dose_budget,peak_budget_kw_m2=peak_budget,thermal_threshold_result=acceptance,
          candidate_dose_relation=O.compare((old['dose_lower_kj_m2'],old['dose_upper_kj_m2']),dose),
          candidate_peak_relation=O.compare((old['peak_lower_kw_m2'],old['peak_upper_kw_m2']),peak),
          refinement={k:v for k,v in raw.items() if k not in ('dose','peak')},original_bounds=old))
    return dict(case_id=route['case_id'],cohort=route['cohort'],mode=mode,binding=route['binding'],trajectory_legs=len(route['legs']),unique_member_histories=len(memo),
      per_member=rows,all_members_within_thermal_thresholds=all(r['thermal_threshold_result']=='PROVED_WITHIN_THERMAL_THRESHOLDS' for r in rows),elapsed_s=time.monotonic()-started,
      scope='Fixed recorded journey thermal bounds only. No contact/optimality/refusal reproof, real-fire physical validation, or new routing run.')

def freeze():
    original=read(CARD);check(original)
    files={Path(p) for p in original['source_sha256']}
    files|={CARD,Path(__file__).resolve(),ROOT/'reference/oracle.py',ROOT/'reference/PROTOCOL.md',ROOT/'reference/ACTUAL_ROUTES_PROTOCOL.md',ROOT/'reference/test_actual_adapter.py'}
    write(SEAL,dict(status='FROZEN_BEFORE_ACTUAL_ROUTE_REFERENCE',contexts=original['contexts'],source_sha256={str(p):sha(p) for p in sorted(files)}))
    print('SEALED',len(files),'files',len(original['contexts']),'contexts')

def run(case,mode):
    seal=read(SEAL);check(seal)
    selected=[]
    for c in seal['contexts']:
        if read(c['job'])['case_id']==case:selected.append(c)
    if len(selected)!=1:raise ValueError('EXPLICIT_UNIQUE_CASE_REQUIRED')
    result=assess(context(selected[0]),mode);check(seal)
    write(ROOT/'reference'/('ACTUAL_'+case+'_'+mode.upper()+'.json'),dict(status='COMPLETE_SCOPED',source_seal_sha256=sha(SEAL),result=result))
    print(json.dumps(dict(case=case,mode=mode,thermal_pass=result['all_members_within_thermal_thresholds'],elapsed_s=result['elapsed_s'],outcomes=[{k:r[k] for k in ('id','thermal_threshold_result','candidate_dose_relation','candidate_peak_relation')} for r in result['per_member']])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','run']);p.add_argument('--case');p.add_argument('--mode',choices=['triangle','radial'],default='radial');args=p.parse_args()
    if args.action=='seal':freeze()
    elif not args.case:p.error('--case required')
    else:run(args.case,args.mode)
