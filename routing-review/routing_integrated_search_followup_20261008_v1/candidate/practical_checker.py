"""Opt-in standalone fixed-mission checking; no routing search/default replacement."""
from pathlib import Path
from types import MappingProxyType
import copy,hashlib,json,math,resource,sys,time
from contact_first import ContactSources,check_contact
from mission_contract import prepare_mission,graph_digest,q,unmasked,MissionInvalid
from radiation_bounds import RadiationBounds,DEFAULT_SETTINGS

RSS_LIMIT_MB=3072

def rss_mb():return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if sys.platform=='darwin' else 1024)
def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

class PracticalChecker:
    """Owned source/cache epoch. New graph/source contents require a new instance."""
    schema='wfg.practical.fixed-mission/1'
    def __init__(self,case_directory,settings=None):
        unmasked(settings)
        self.directory=Path(case_directory).resolve()
        self.settings=MappingProxyType({**DEFAULT_SETTINGS,**copy.deepcopy(settings or {})})
        self._source_identity=None;self._graph_identity=None;self._source=None;self._radiation=None

    def _finish(self,result,started,deadline,times):
        measured=rss_mb();checked=dict(result)
        if time.perf_counter()>=deadline or measured>RSS_LIMIT_MB:
            result={'status':'UNRESOLVED','reason':'WALL_CAP_AFTER_CHECK' if measured<=RSS_LIMIT_MB else 'RSS_LIMIT',
                    'checked_result':checked,'checked_result_is_secondary':True}
        result.update({'schema':self.schema,'elapsed_s':time.perf_counter()-started,'timing_s':times,
          'process_lifetime_rss_mb':measured,'rss_gate_mb':RSS_LIMIT_MB,'rss_gate_scope':'Fail-closed measured lifetime RSS, not OS allocation ceiling',
          'source_identity':self._source_identity,'graph_identity':self._graph_identity,'cache_epoch':'owned immutable source/geometry/settings; content changes refused; instantiate explicitly for new epoch',
          'fixed_path_only':True,'global_optimality_or_infeasibility_claim':False,'physical_validation':False})
        # Metadata finalization is charged before the final primary cap gate.
        finished=time.perf_counter();result['elapsed_s']=finished-started
        if finished>=deadline and result['status']!='UNRESOLVED':
            result={'schema':self.schema,'status':'UNRESOLVED','reason':'WALL_CAP_DURING_FINALIZATION',
              'checked_result':result,'checked_result_is_secondary':True,'elapsed_s':finished-started,
              'timing_s':times,'process_lifetime_rss_mb':measured,'rss_gate_mb':RSS_LIMIT_MB,
              'fixed_path_only':True,'global_optimality_or_infeasibility_claim':False,'physical_validation':False}
        return result

    def check(self,graph,request,legs,destination,*,wall_s=30,deadline=None,expected_graph_revision=None,expected_graph_sha256=None):
        started=time.perf_counter();times={};limit=float(q(wall_s))
        if not math.isfinite(limit) or limit<0:raise ValueError('nonnegative finite wall cap')
        stop=started+limit
        if deadline is not None:
            if not math.isfinite(float(deadline)):raise ValueError('finite shared deadline')
            stop=min(stop,float(deadline))
        result={'status':'UNRESOLVED','reason':'INCOMPLETE'}
        try:
            if time.perf_counter()>=stop:raise MissionInvalid('WALL_CAP_BEFORE_PREPARATION')
            ts=time.perf_counter();identity=file_sha(self.directory/'constructed_arrays.npz')+':'+file_sha(self.directory/'REPORT.json')
            if self._source_identity is not None and identity!=self._source_identity:raise MissionInvalid('SOURCE_CONTENT_CHANGED_NEW_EPOCH_REQUIRED')
            if self._source is None:self._source=ContactSources.from_case(self.directory,deadline=stop);self._source_identity=identity
            times['source_preparation_and_binding']=time.perf_counter()-ts
            ts=time.perf_counter();g=copy.deepcopy(graph);r=copy.deepcopy(request);walk=copy.deepcopy(legs)
            unmasked((graph,request,legs));digest=graph_digest(g)
            if self._graph_identity is not None and digest!=self._graph_identity:raise MissionInvalid('GRAPH_CONTENT_CHANGED_NEW_EPOCH_REQUIRED')
            authority=expected_graph_sha256 if expected_graph_sha256 is not None else self._graph_identity
            mission=prepare_mission(g,r,walk,destination,scenario_ids=self._source.ids,source_horizon=self._source.horizon,deadline=stop,
                expected_graph_revision=expected_graph_revision,expected_graph_sha256=authority)
            times['mission_validation']=time.perf_counter()-ts
            if mission['status']!='VALID':
                result={'status':'UNRESOLVED','reason':'MISSION_VALIDATION','mission':mission};return self._finish(result,started,stop,times)
            if self._graph_identity is None:self._graph_identity=digest
            ts=time.perf_counter();contact=check_contact(self._source,mission['trajectory'],deadline=stop)
            times['contact_check']=time.perf_counter()-ts
            public_mission={k:v for k,v in mission.items() if k!='trajectory'}
            result={'status':'UNRESOLVED','reason':'CONTACT_NOT_COMPLETE','contact':contact,'mission':public_mission,'trajectory':mission['trajectory']}
            if contact['status']=='DEFINITE_REJECT':
                result.update(status='DEFINITE_REJECT',reason='FLAME_CONTACT_WITNESS',radiation={'status':'NOT_RUN_CONTACT_REJECT'})
            elif contact['status']=='CLEAR':
                ts=time.perf_counter()
                if self._radiation is None:self._radiation=RadiationBounds.from_case(self.directory,settings=dict(self.settings))
                times['radiation_preparation']=time.perf_counter()-ts
                if time.perf_counter()>=stop:raise MissionInvalid('WALL_CAP_AFTER_RADIATION_PREPARATION')
                ts=time.perf_counter();radiation=self._radiation.trajectory_bound(mission['trajectory'],peak_budget_kw_m2=r['budgets']['peak'],
                   dose_budget_kj_m2=r['budgets']['dose'],incurred=r['incurred'],deadline=stop)
                times['radiation_check']=time.perf_counter()-ts;result['radiation']=radiation
                if radiation['status']=='CERTIFIED_RADIATION':result.update(status='CERTIFIED_ADMISSIBLE',reason='COMPLETE_CONTACT_AND_RADIATION')
                elif radiation['status']=='DEFINITE_REJECT':result.update(status='DEFINITE_REJECT',reason='RADIATION_LOWER_BOUND_VIOLATION')
                else:result.update(status='UNRESOLVED',reason='RADIATION_UNRESOLVED_OR_UNSUPPORTED')
            # Recheck source/graph/request authority after computation before any certificate.
            ts=time.perf_counter()
            if identity!=file_sha(self.directory/'constructed_arrays.npz')+':'+file_sha(self.directory/'REPORT.json'):raise MissionInvalid('SOURCE_CHANGED_DURING_CHECK')
            if digest!=graph_digest(graph) or r!=request or walk!=legs:raise MissionInvalid('MISSION_AUTHORITY_CHANGED_DURING_CHECK')
            times['final_content_check']=time.perf_counter()-ts
        except (MissionInvalid,ValueError,TypeError,KeyError,OverflowError,OSError) as exc:
            result={'status':'UNRESOLVED','reason':str(exc),'partial_check':result}
        return self._finish(result,started,stop,times)
