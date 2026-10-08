"""Exact closed-footprint contact check. CLEAR is only an intermediate result."""
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
import hashlib,json,math,time
import numpy as np
from mission_contract import q,unmasked,guard,MissionInvalid

@dataclass(frozen=True)
class ContactSources:
    ids:tuple
    rectangles:tuple
    phases:tuple
    horizon:F
    domain:tuple
    unsupported:tuple=()
    content_sha256:str=''

    @classmethod
    def from_case(cls,directory,*,deadline):
        guard(deadline);directory=Path(directory)
        report=json.loads((directory/'REPORT.json').read_text())
        with np.load(directory/'constructed_arrays.npz',allow_pickle=False) as a:
            support=a['support']; support=support.all(axis=1) if support.ndim==4 else support
            source=cls.from_arrays(a['ignition_time_s'],a['current_active'],report['native_metadata']['construction']['assumptions'],report['native_metadata']['affine_transform'],list(report['rows'][0]['request']['incurred']),support,deadline=deadline)
        guard(deadline);return source

    @classmethod
    def from_arrays(cls,events,current,config,affine,ids,support,*,deadline,evidence_class='RESEARCH_CONSTRUCTION'):
        guard(deadline);unmasked((events,current,config,affine,ids,support))
        events=np.asarray(events);current=np.asarray(current);support=np.asarray(support)
        if events.ndim!=3 or min(events.shape)<1 or current.shape!=events.shape[1:] or current.dtype!=np.bool_: raise MissionInvalid('SOURCE_SHAPE_OR_CURRENT_TYPE')
        if np.any(np.isnan(events)) or np.any(events<0) or np.isfinite(events[:,current]).any(): raise MissionInvalid('INVALID_OR_OVERLAPPING_SOURCE_EVENTS')
        S,H,W=events.shape;ids=tuple(ids)
        if len(ids)!=S or len(set(ids))!=S: raise MissionInvalid('MEMBER_IDS')
        duration=q(config['burning_duration_s']);remaining=q(config['initial_remaining_s']);horizon=q(config['horizon_s'])
        if not 0<=remaining<=duration or duration<=0 or horizon<=0: raise MissionInvalid('PHASE_PARAMETERS')
        a,b,c,d,e,f=map(q,affine)
        unsupported=[]
        if b or d or not a or not e: unsupported.append('AXIS_ALIGNED_AFFINE_REQUIRED')
        if evidence_class!='RESEARCH_CONSTRUCTION' or config.get('version')!='wfg.hazard.construction/1': unsupported.append('DECLARED_SOURCE_LAW_REQUIRED')
        if support.dtype!=np.bool_ or support.shape not in {(H,W),(S,H,W)} or not support.all():unsupported.append('UNKNOWN_SOURCE_SUPPORT')
        rectangles=tuple((min(c+col*a,c+(col+1)*a),max(c+col*a,c+(col+1)*a),min(f+row*e,f+(row+1)*e),max(f+row*e,f+(row+1)*e)) for row in range(H) for col in range(W))
        phases=[]
        for s in range(S):
            guard(deadline);row=[]
            for i in range(H*W):
                if current.ravel()[i] and remaining>0:row.append((i,F(0),remaining,'CURRENT'))
                elif math.isfinite(float(events[s].ravel()[i])):
                    birth=q(events[s].ravel()[i])
                    if birth>=horizon:raise MissionInvalid('IGNITION_OUTSIDE_HORIZON')
                    row.append((i,birth,birth+duration,'FUTURE'))
            phases.append(tuple(row))
        domain=(min(c,c+W*a),max(c,c+W*a),min(f,f+H*e),max(f,f+H*e))
        content=repr((ids,rectangles,tuple(phases),horizon,domain,tuple(unsupported))).encode()
        guard(deadline)
        return cls(ids,rectangles,tuple(phases),horizon,domain,tuple(unsupported),hashlib.sha256(content).hexdigest())

    @classmethod
    def from_road(cls,road):
        """Copy exact contact-only state. No reused mutable spatial/thermal cache."""
        phases=tuple(tuple([(i,F(0),road.remaining,'CURRENT') for i in sorted(road.current) if road.remaining>0]+[(i,t,t+road.duration,'FUTURE') for i,t in sorted(events.items())]) for events in road.events)
        state=(tuple(road.ids),tuple(road.rectangles),phases,q(road.horizon),tuple(road.domain),tuple(road.unsupported))
        return cls(*state,hashlib.sha256(repr(state).encode()).hexdigest())

def clip_closed_rectangle(p0,p1,rectangle):
    """Exact line parameter interval inside closed axis-aligned rectangle."""
    low,high=F(0),F(1)
    for x,y,left,right in ((p0[0],p1[0],rectangle[0],rectangle[1]),(p0[1],p1[1],rectangle[2],rectangle[3])):
        delta=y-x
        if delta==0:
            if x<left or x>right:return None
        else:
            a,b=(left-x)/delta,(right-x)/delta
            low=max(low,min(a,b));high=min(high,max(a,b))
            if low>high:return None
    return low,high

def check_contact(source,trajectory,*,deadline,max_clip_tests=200000):
    started=time.perf_counter();clips=0;candidates=0
    try:
        guard(deadline);unmasked(trajectory)
        if not isinstance(source,ContactSources):source=ContactSources.from_road(source)
        if source.unsupported:raise MissionInvalid(';'.join(source.unsupported))
        if type(max_clip_tests) is not int or max_clip_tests<1:raise MissionInvalid('CLIP_LIMIT')
        if not trajectory or trajectory[0]['kind']!='ISSUE' or trajectory[-1]['kind']!='DWELL':raise MissionInvalid('FULL_TRAJECTORY_GRAMMAR')
        last_t=last_p=None
        for index,raw in enumerate(trajectory):
            guard(deadline);kind=raw['kind'];start,end=q(raw['start']),q(raw['end']);p0=tuple(map(q,raw['p0']));p1=tuple(map(q,raw['p1']))
            if len(p0)!=2 or len(p1)!=2 or start<0 or end<start or end>source.horizon:raise MissionInvalid('TRAJECTORY_TIME_OR_POINT')
            if index==0 and (start!=end or p0!=p1):raise MissionInvalid('ISSUE_GRAMMAR')
            if index>0 and (start!=last_t or p0!=last_p):raise MissionInvalid('TRAJECTORY_GAP_OR_POSITION_JUMP')
            if kind not in {'ISSUE','EDGE','WAIT','DWELL'} or (kind=='ISSUE' and index!=0) or (kind=='DWELL' and index!=len(trajectory)-1):raise MissionInvalid('TRAJECTORY_KIND')
            if kind in {'WAIT','DWELL'} and p0!=p1:raise MissionInvalid('STATIONARY_POSITION')
            if kind in {'EDGE','WAIT'} and end<=start:raise MissionInvalid('EMPTY_MOVING_OR_WAIT_SEGMENT')
            x0,x1,y0,y1=source.domain
            if any(not(x0<=p[0]<=x1 and y0<=p[1]<=y1) for p in (p0,p1)):raise MissionInvalid('OUTSIDE_SOURCE_DOMAIN')
            last_t,last_p=end,p1
        # Grammar/support are complete before an early supported rejection is used.
        phase_maps=tuple(dict((i,(birth,expiry,phase)) for i,birth,expiry,phase in row) for row in source.phases)
        for index,raw in enumerate(trajectory):
            guard(deadline);start,end=q(raw['start']),q(raw['end']);p0=tuple(map(q,raw['p0']));p1=tuple(map(q,raw['p1']))
            box=(min(p0[0],p1[0]),max(p0[0],p1[0]),min(p0[1],p1[1]),max(p0[1],p1[1]))
            for cell,rectangle in enumerate(source.rectangles):
                if cell%128==0:guard(deadline)
                if rectangle[1]<box[0] or rectangle[0]>box[1] or rectangle[3]<box[2] or rectangle[2]>box[3]:continue
                candidates+=1
                if clips>=max_clip_tests:raise MissionInvalid('CLIP_CAP')
                clips+=1;intersection=clip_closed_rectangle(p0,p1,rectangle)
                if intersection is None:continue
                enter=start+(end-start)*intersection[0];leave=start+(end-start)*intersection[1]
                for s,phases in enumerate(phase_maps):
                    if cell not in phases:continue
                    birth,expiry,phase=phases[cell];witness_time=max(enter,birth)
                    if witness_time<=leave and witness_time<expiry:
                        u=F(0) if end==start else (witness_time-start)/(end-start)
                        point=tuple(x+(y-x)*u for x,y in zip(p0,p1))
                        guard(deadline)
                        return {'status':'DEFINITE_REJECT','complete':False,'contact_clear':False,'reason':'FLAME_CONTACT','witness':{'member':source.ids[s],'source_cell':cell,'segment_index':index,'segment_kind':raw['kind'],'edge':raw.get('edge'),'time_exact':str(witness_time),'point_exact':list(map(str,point)),'rectangle_exact':list(map(str,rectangle)),'line_parameter_interval_exact':list(map(str,intersection)),'occupancy_interval_exact':[str(enter),str(leave)],'source_phase_interval_exact':[str(birth),str(expiry)],'source_phase':phase,'source_right_endpoint_included':False},'source_content_sha256':source.content_sha256,'clip_tests':clips,'bbox_candidates':candidates,'wall_s':time.perf_counter()-started}
        guard(deadline)
        return {'status':'CLEAR','complete':True,'contact_clear':True,'source_content_sha256':source.content_sha256,'clip_tests':clips,'bbox_candidates':candidates,'cache_hits':0,'retained_cache_bytes':0,'wall_s':time.perf_counter()-started}
    except (MissionInvalid,KeyError,ValueError,TypeError,OverflowError) as exc:
        return {'status':'UNRESOLVED','complete':False,'contact_clear':False,'reason':str(exc),'clip_tests':clips,'bbox_candidates':candidates,'wall_s':time.perf_counter()-started}
