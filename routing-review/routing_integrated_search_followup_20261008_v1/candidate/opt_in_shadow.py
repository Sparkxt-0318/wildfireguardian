"""Explicit opt-in sidecar; never rewrites router outcomes or replaces defaults."""
from pathlib import Path
import copy,hashlib,json,time,math
from mission_contract import graph_digest,unmasked,q
from practical_checker import PracticalChecker,file_sha


def request_digest(request):
    unmasked(request)
    return hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def bind_witness_context(case_directory,graph,request):
    """Capture authoritative context before invoking a serialized router operation."""
    directory=Path(case_directory);unmasked((graph,request))
    return {'schema':'wfg.shadow.context/1','graph_revision':graph['revision'],'graph_sha256':graph_digest(graph),
      'request_sha256':request_digest(request),'source_identity':file_sha(directory/'constructed_arrays.npz')+':'+file_sha(directory/'REPORT.json')}


class ShadowWitnessAdapter:
    """One graph/source epoch, separately declared shadow budget, disabled by default."""
    def __init__(self,case_directory):
        self.directory=Path(case_directory);self._checker=None

    def check(self,primary_result,graph,request,*,binding=None,enabled=False,wall_s=30,deadline=None):
        # Caller must serialize ownership with the router; this is not a thread-safe scheduler.
        started=time.perf_counter();primary=copy.deepcopy(primary_result)
        output={'schema':'wfg.shadow.witness/1','primary_result':primary,'primary_search_status':None,'primary_search_outcome_unchanged':True,
          'shadow_check':None,'shadow_enabled':enabled is True,'default_replacement':False,'search_optimality_or_infeasibility_from_shadow':False,
          'physical_validation':False,'budget_scope':'Separate explicitly declared witness check; not included in or resolving primary search budget.'}
        escape=primary.get('escape',primary) if isinstance(primary,dict) else {}
        output['primary_search_status']=escape.get('status') if isinstance(escape,dict) else None
        if enabled is False:
            output.update(shadow_status='DISABLED',elapsed_s=time.perf_counter()-started);return output
        try:
            if enabled is not True:raise ValueError('EXPLICIT_BOOLEAN_OPT_IN_REQUIRED')
            limit=float(q(wall_s))
            if limit<0 or not math.isfinite(limit):raise ValueError('INVALID_SHADOW_WALL_CAP')
            stop=started+limit
            if deadline is not None:
                external=float(q(deadline))
                if not math.isfinite(external):raise ValueError('INVALID_SHADOW_DEADLINE')
                stop=min(stop,external)
            if time.perf_counter()>=stop:raise ValueError('SHADOW_WALL_CAP_BEFORE_BINDING')
            current=bind_witness_context(self.directory,graph,request)
            if binding!=current:raise ValueError('WITNESS_AUTHORITY_BINDING_MISMATCH_OR_MISSING')
            unmasked((primary_result,binding));snapshot=copy.deepcopy((graph,request,binding));g,r,b=snapshot
            if not isinstance(escape,dict):raise ValueError('PRIMARY_REPORT_SHAPE')
            if escape.get('hazard_version') is not None and escape.get('hazard_version')!=r.get('hazard_version'):raise ValueError('PRIMARY_REQUEST_VERSION_MISMATCH')
            if escape.get('status')=='TIMEOUT':
                witness=escape.get('checked_incumbent');origin='checked_incumbent_secondary_to_TIMEOUT'
                if not isinstance(witness,dict) or witness.get('status')!='CHECKED_ROUTE':raise ValueError('NO_CHECKED_INCUMBENT_WITNESS')
            elif escape.get('status') in ('CHECKED_ROUTE','CONDITIONAL_OPTIMUM'):
                witness=escape;origin='primary_supplied_witness'
            else:raise ValueError('NO_SUPPORTED_ROUTER_WITNESS')
            if not isinstance(witness.get('legs'),list) or not isinstance(witness.get('destination'),str):raise ValueError('INCOMPLETE_ROUTER_WITNESS')
            if self._checker is None:self._checker=PracticalChecker(self.directory)
            result=self._checker.check(g,r,witness['legs'],witness['destination'],wall_s=limit,deadline=stop,
              expected_graph_revision=b['graph_revision'],expected_graph_sha256=b['graph_sha256'])
            # Context preparation is charged to the same separately declared witness budget.
            elapsed=time.perf_counter()-started
            if time.perf_counter()>=stop:result={'status':'UNRESOLVED','reason':'SHADOW_CAP_AFTER_BINDING_AND_CHECK','checked_result':result,'checked_result_is_secondary':True}
            if primary_result!=primary or bind_witness_context(self.directory,graph,request)!=b:
                result={'status':'UNRESOLVED','reason':'SHADOW_AUTHORITY_CHANGED_DURING_CHECK','checked_result':result,'checked_result_is_secondary':True}
            output.update(shadow_check=result,shadow_status=result['status'],witness_origin=origin,witness_is_secondary_to_primary_search=True,
              context_binding=b,elapsed_s=time.perf_counter()-started)
        except (ValueError,TypeError,KeyError,OSError,OverflowError) as exc:
            output.update(shadow_check={'status':'UNRESOLVED','reason':str(exc)},shadow_status='UNRESOLVED',elapsed_s=time.perf_counter()-started)
        finished=time.perf_counter();output['elapsed_s']=finished-started
        if enabled is True and 'stop' in locals() and finished>=stop and output.get('shadow_status')!='UNRESOLVED':
            checked=output.get('shadow_check');output.update(shadow_check={'status':'UNRESOLVED','reason':'SHADOW_CAP_DURING_FINALIZATION','checked_result':checked,'checked_result_is_secondary':True},shadow_status='UNRESOLVED')
        return output
