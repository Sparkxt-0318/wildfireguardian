"""Fail-closed graph/witness grammar; no exposure or route search."""
from fractions import Fraction as F
import hashlib,json,math,time
import numpy as np

class MissionInvalid(ValueError): pass

def q(value):
    if isinstance(value,(bool,np.bool_)): raise MissionInvalid('BOOLEAN_NUMERIC')
    if isinstance(value,F): return value
    if isinstance(value,(int,np.integer)): return F(int(value))
    if isinstance(value,(float,np.floating)) and math.isfinite(float(value)): return F.from_float(float(value))
    if isinstance(value,str):
        try:return F(value)
        except Exception:pass
    raise MissionInvalid('NONFINITE_OR_INVALID_NUMBER')

def unmasked(value):
    if np.ma.isMaskedArray(value): raise MissionInvalid('MASKED_INPUT')
    if isinstance(value,dict):
        for v in value.values():unmasked(v)
    elif isinstance(value,(list,tuple)):
        for v in value:unmasked(v)

def guard(deadline):
    if deadline is None or not math.isfinite(deadline): raise MissionInvalid('SHARED_DEADLINE_REQUIRED')
    if time.perf_counter()>=deadline: raise MissionInvalid('WALL_CAP')

def graph_digest(graph):
    return hashlib.sha256(json.dumps(graph,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def prepare_mission(graph,request,legs,destination,*,scenario_ids,source_horizon,deadline,
                    expected_graph_revision=None,expected_graph_sha256=None,dt=1):
    """Validate complete issue->walk/waits->arrival+dwell; return no certificate."""
    started=time.perf_counter()
    try:
        guard(deadline);unmasked((graph,request,legs))
        revision=graph.get('revision')
        if not isinstance(revision,str) or not revision: raise MissionInvalid('GRAPH_REVISION_REQUIRED')
        expected=expected_graph_revision if expected_graph_revision is not None else request.get('graph_revision')
        if expected is None or revision!=expected: raise MissionInvalid('GRAPH_REVISION_MISMATCH_OR_UNBOUND')
        digest=graph_digest(graph)
        if expected_graph_sha256 is not None and digest!=expected_graph_sha256: raise MissionInvalid('GRAPH_CONTENT_MISMATCH')
        if request.get('exposure_scope')!='including_dwell': raise MissionInvalid('FULL_MISSION_SCOPE_REQUIRED')
        ids=tuple(scenario_ids)
        if not ids or len(set(ids))!=len(ids) or set(request['incurred'])!=set(ids) or set(request['budgets']['dose'])!=set(ids): raise MissionInvalid('MEMBER_HISTORY_OR_BUDGET_MISMATCH')
        if q(request['budgets']['peak'])<0 or any(q(request['incurred'][i])<0 or q(request['budgets']['dose'][i])<0 for i in ids): raise MissionInvalid('NEGATIVE_BUDGET_OR_HISTORY')
        nodes={n['id']:n for n in graph['nodes']};edges={e['id']:e for e in graph['edges']}
        if len(nodes)!=len(graph['nodes']) or len(edges)!=len(graph['edges']): raise MissionInvalid('DUPLICATE_GRAPH_ID')
        for node in nodes.values():q(node['x']);q(node['y'])
        forbidden=set()
        for pair in graph.get('forbidden_turns',[]):
            if len(pair)!=2 or pair[0] not in edges or pair[1] not in edges: raise MissionInvalid('INVALID_TURN_TABLE')
            forbidden.add(tuple(pair))
        for edge in edges.values():
            if edge['u'] not in nodes or edge['v'] not in nodes or type(edge['travel_ticks']) is not int or edge['travel_ticks']<=0: raise MissionInvalid('INVALID_GRAPH_EDGE')
        if set(request['position'])!={'node'}: raise MissionInvalid('PARTIAL_EDGE_POSITION_UNSUPPORTED')
        node=request['position']['node'];incoming=request.get('incoming_edge');t=q(request['departure']);departure=t;horizon=q(request['horizon']);tick=q(dt)
        if node not in nodes or tick<=0 or t<0 or t>horizon or horizon>q(source_horizon) or t/tick!=int(t/tick) or horizon/tick!=int(horizon/tick): raise MissionInvalid('POSITION_OR_TIME_COVERAGE')
        if incoming is not None and (incoming not in edges or edges[incoming]['v']!=node): raise MissionInvalid('INCOMING_CONTEXT')
        def point(n): return [q(nodes[n]['x']),q(nodes[n]['y'])]
        trajectory=[{'kind':'ISSUE','start':t,'end':t,'p0':point(node),'p1':point(node)}];arrived=True
        for index,leg in enumerate(legs):
            guard(deadline);start,end=q(leg['start']),q(leg['end'])
            if start!=t or end<=start or end>horizon: raise MissionInvalid('LEG_TIME_OR_GAP')
            if leg['kind']=='EDGE':
                edge=edges[leg['edge']]
                if edge['u']!=node or (incoming,edge['id']) in forbidden or q(leg.get('from_fraction',0))!=0 or q(leg.get('to_fraction',1))!=1: raise MissionInvalid('EDGE_OR_TURN_CONTEXT')
                if end-start!=edge['travel_ticks']*tick: raise MissionInvalid('TRAVEL_DURATION')
                trajectory.append({'kind':'EDGE','edge':edge['id'],'leg_index':index,'start':start,'end':end,'p0':point(node),'p1':point(edge['v'])})
                node,incoming,arrived=edge['v'],edge['id'],True
            elif leg['kind']=='WAIT':
                if leg.get('node')!=node or nodes[node].get('waitable') is not True or (end-start)/tick!=int((end-start)/tick): raise MissionInvalid('WAIT_CONTEXT')
                trajectory.append({'kind':'WAIT','leg_index':index,'start':start,'end':end,'p0':point(node),'p1':point(node)});arrived=False
            else: raise MissionInvalid('LEG_KIND')
            t=end
        if node!=destination or not arrived: raise MissionInvalid('DESTINATION_ARRIVAL_CONTEXT')
        choices=[d for d in request['destinations'] if d['node']==destination]
        if len(choices)!=1: raise MissionInvalid('EXPLICIT_SINGLE_DESTINATION_CONTRACT_REQUIRED')
        d=choices[0];dwell=q(d['dwell']);end=t+dwell
        if dwell<0 or dwell/tick!=int(dwell/tick) or end>horizon: raise MissionInvalid('DWELL_OR_HORIZON')
        opening=False
        for interval in d['open_intervals']:
            if len(interval)!=2: raise MissionInvalid('OPENING_GRAMMAR')
            a,b=map(q,interval)
            if a>b: raise MissionInvalid('OPENING_ORDER')
            opening|=a<=t and end<=b
        if not opening: raise MissionInvalid('DESTINATION_CLOSED')
        trajectory.append({'kind':'DWELL','start':t,'end':end,'p0':point(node),'p1':point(node)})
        if sum(x['end']-x['start'] for x in trajectory)!=end-departure: raise MissionInvalid('INCOMPLETE_COVERAGE')
        guard(deadline)
        return {'status':'VALID','complete':True,'trajectory':trajectory,'arrival':t,'mission_end':end,'graph_revision':revision,'graph_sha256':digest,'scenario_ids':ids,'wall_s':time.perf_counter()-started}
    except (MissionInvalid,KeyError,TypeError,ValueError,OverflowError) as exc:
        return {'status':'UNRESOLVED','complete':False,'reason':str(exc),'wall_s':time.perf_counter()-started}
