"""Explicit integrated search experiment; no installed/default solver replacement."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import copy
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

import numpy as np
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'routing-package'))
from routing import core, validation
from routing.prepared import PreparedGraph
from forecast_bridge import convert
from hybrid_checker import HybridChecker
from hybrid_radiation import DEFAULT_SETTINGS

SCHEMA = 'wfg.integrated-search-followup/1'
EPOCH_SCHEMA = 'wfg.integrated-search-epoch/1'
MODES = ('baseline', 'cache', 'heuristic', 'combined')
SOURCE_NAMES = ('REPORT.json', 'constructed_arrays.npz', 'NATIVE_METADATA.json')
IMPLEMENTATION_NAMES = ('search_followup.py', 'forecast_bridge.py', 'hourly.py', 'hybrid_checker.py',
 'hybrid_radiation.py', 'radiation_bounds.py', 'road_exposure.py', 'contact_first.py',
 'mission_contract.py', 'mentor_runtime/expected_heat_flux/model.py',
 'mentor_runtime/expected_heat_flux/__init__.py', 'routing-package/routing/__init__.py',
 'routing-package/routing/core.py',
 'routing-package/routing/prepared.py', 'routing-package/routing/validation.py',
 'routing-package/routing/independent.py', 'routing-package/routing/core_cached.py',
 'routing-package/routing/search_geometry_cache.py')

class EpochMismatch(ValueError):
    pass


def _json_type(value):
    # PreparedGraph's strict JSON rejection is replicated for source/request ownership.
    if type(value) is dict:
        if any(type(k) is not str for k in value):
            raise ValueError('NONSTRING_JSON_KEY')
        for v in value.values(): _json_type(v)
    elif type(value) is list:
        for v in value: _json_type(v)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError('NONJSON_OR_MASKED_INPUT')


def _json(value):
    _json_type(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _sha(payload): return hashlib.sha256(payload).hexdigest()


def _source_bytes(directory):
    if directory is None: return ()
    directory = Path(directory).resolve()
    result = []
    for name in SOURCE_NAMES:
        path = directory / name
        result.append((name, path.read_bytes()))
    return tuple(result)


def _implementation_bytes():
    return tuple((name, (ROOT / name).read_bytes() if (ROOT / name).exists() else None)
                 for name in IMPLEMENTATION_NAMES)


def _settings_bytes(settings):
    return _json({**DEFAULT_SETTINGS, **copy.deepcopy(settings or {})})


@dataclass(frozen=True, slots=True, init=False)
class PreparedSearchEpoch:
    """Immutable full-content snapshots; no request, cost, or result cache."""
    _graph: PreparedGraph
    _hazard: bytes
    _source: tuple
    _directory: str | None
    _implementation: tuple
    _settings: bytes
    preparation_wall_s: float
    preparation_timing_s: tuple

    def __init_subclass__(cls, **kwargs):
        raise TypeError('PreparedSearchEpoch cannot be subclassed')

    def graph_snapshot(self): return self._graph.snapshot()
    def hazard_snapshot(self): return json.loads(self._hazard)
    @property
    def fingerprint(self):
        return _sha(_json(self.identities()))
    def identities(self):
        return {'schema': EPOCH_SCHEMA, 'graph': self._graph.fingerprint,
                'hazard': _sha(self._hazard), 'directory': self._directory,
                'source': {k: _sha(v) if v is not None else None for k, v in self._source},
                'implementation': {k: _sha(v) if v is not None else None for k,v in self._implementation},
                'checker_settings': _sha(self._settings),
                'owned_payload_bytes': len(self._hazard) + sum(len(v) for _,v in self._source if v is not None)
                                      + sum(len(v) for _,v in self._implementation if v is not None)}

    def validate_binding(self, graph, hazard, directory, settings=None):
        if (str(Path(directory).resolve()) if directory is not None else None) != self._directory:
            raise EpochMismatch('SOURCE_DIRECTORY_CHANGED_NEW_EPOCH_REQUIRED')
        if not self._graph.matches(graph):
            raise EpochMismatch('GRAPH_CONTENT_CHANGED_NEW_EPOCH_REQUIRED')
        if _json(hazard) != self._hazard:
            raise EpochMismatch('HAZARD_CONTENT_CHANGED_NEW_EPOCH_REQUIRED')
        if _source_bytes(directory) != self._source:
            raise EpochMismatch('SOURCE_CONTENT_CHANGED_NEW_EPOCH_REQUIRED')
        if _implementation_bytes() != self._implementation:
            raise EpochMismatch('IMPLEMENTATION_CHANGED_NEW_EPOCH_REQUIRED')
        if _settings_bytes(settings) != self._settings:
            raise EpochMismatch('CHECKER_SETTINGS_CHANGED_NEW_EPOCH_REQUIRED')


def _packet_member_ids(metadata, report, admitted_hazard):
    """Original hourly routing namespace, by unchanged physical array index.

    Constructor event labels are not routing/exposure-history labels. Never
    rename an admitted hazard or transfer an incurred ledger here.
    """
    declared=metadata['construction']['scenario_ids']
    if type(declared) is not list or len(declared)!=4 or any(type(mid) is not str or not mid for mid in declared) or len(set(declared))!=4:
        raise EpochMismatch('INTEGRATED_CHECKER_FOUR_DISTINCT_MEMBERS_REQUIRED')
    if metadata.get('schema')=='wfg.forecast.native-intervals/2':
        identity=metadata.get('construction_id')
        if type(identity) is not str or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):
            raise EpochMismatch('SOURCE_ROUTING_CONSTRUCTION_ID_REQUIRED')
        issued_at=metadata.get('issued_at')
        if type(issued_at) is not str:
            raise EpochMismatch('SOURCE_HOURLY_CONSTRUCTION_TIME_REQUIRED')
        cutoff=datetime.fromisoformat(issued_at.replace('Z','+00:00'))
        if cutoff.tzinfo is None:
            raise EpochMismatch('SOURCE_HOURLY_CONSTRUCTION_TIME_REQUIRED')
        # Exact original hourly.build_hazard identity_input and jsonbytes rule.
        identity_input={'mode':metadata['mode'], 'version':metadata['version'],
                        'parent_sha256':metadata['parent_forecast_sha256'],
                        'cutoff':cutoff.astimezone(timezone.utc).isoformat(),
                        'construction':metadata['construction']}
        if identity!=_sha(_json(identity_input)):
            raise EpochMismatch('SOURCE_HOURLY_CONSTRUCTION_DIGEST_MISMATCH')
        # Exact original hourly.build_hazard lines 97-98, not a new remapping.
        expected=['construction:'+identity[:20]+':'+str(i) for i in range(4)]
    elif metadata.get('schema')=='wfg.forecast.native-intervals/1':
        expected=list(declared)  # Explicit legacy/synthetic declared identities.
    else:
        raise EpochMismatch('SOURCE_NATIVE_SCHEMA_UNSUPPORTED')
    if [m['id'] for m in admitted_hazard['members']]!=expected:
        raise EpochMismatch('ADMITTED_ROUTING_MEMBER_ORDER_OR_ID_MISMATCH')
    rows=report.get('rows')
    if not isinstance(rows,list) or not rows:
        raise EpochMismatch('SOURCE_REQUEST_MEMBER_AUTHORITY_REQUIRED')
    for row in rows:
        request=row.get('request')
        if not isinstance(request,dict) or list(request.get('incurred',{}))!=expected or list(request.get('budgets',{}).get('dose',{}))!=expected:
            raise EpochMismatch('SOURCE_REPORT_REQUEST_MEMBER_ORDER_OR_ID_MISMATCH')
    return expected


def prepare_epoch(graph, admitted_hazard, source_directory, *, checker_settings=None):
    """Re-admit source arrays through the unchanged bridge, then freeze owned data.

    External preparation is separately charged; the original solve cap is untouched.
    REPORT native_metadata is authoritative; the mandatory metadata sidecar must match exactly.
    """
    started=time.perf_counter(); timing={}
    ts=time.perf_counter(); g=PreparedGraph(graph); hazard_bytes=_json(admitted_hazard)
    h=validation.validate_hazard(g.snapshot(), json.loads(hazard_bytes), _graph_validated=True)
    timing['graph_and_hazard_admission']=time.perf_counter()-ts
    ts=time.perf_counter(); directory=str(Path(source_directory).resolve()) if source_directory is not None else None; source=_source_bytes(directory)
    implementation=_implementation_bytes(); settings=_settings_bytes(checker_settings)
    timing['source_and_implementation_snapshot']=time.perf_counter()-ts
    ts=time.perf_counter()
    if directory is not None:
        blobs=dict(source); report=json.loads(blobs['REPORT.json']); md=report['native_metadata']
        if blobs['NATIVE_METADATA.json'] is not None and _json(json.loads(blobs['NATIVE_METADATA.json'])) != _json(md):
            raise EpochMismatch('SOURCE_METADATA_SIDECAR_DISAGREEMENT')
        # Load the very same snapshotted bytes, never a second mutable path.
        import io
        with np.load(io.BytesIO(blobs['constructed_arrays.npz']), allow_pickle=False) as z:
            ids=_packet_member_ids(md,report,h)
            arrays={key:z[key].copy() for key in ('flux_w_m2','flame_contact','support')}
            if any(a.ndim!=4 or a.shape[0]!=len(ids) for a in arrays.values()):
                raise EpochMismatch('SOURCE_MEMBER_SHAPE')
            members=[{'id':mid, **{k:a[i] for k,a in arrays.items()}} for i,mid in enumerate(ids)]
        reconstructed=convert(g.snapshot(), md, members)
        if _json(reconstructed) != hazard_bytes:
            raise EpochMismatch('ADMITTED_HAZARD_NOT_EXACT_SOURCE_BRIDGE')
    timing['source_loading_and_original_bridge']=time.perf_counter()-ts
    ts=time.perf_counter()
    if _source_bytes(directory)!=source or _json(graph)!=_json(g.snapshot()) or _json(admitted_hazard)!=hazard_bytes:
        raise EpochMismatch('INPUT_CHANGED_DURING_PREPARATION')
    if _implementation_bytes()!=implementation or _settings_bytes(checker_settings)!=settings:
        raise EpochMismatch('IMPLEMENTATION_OR_SETTINGS_CHANGED_DURING_PREPARATION')
    timing['final_preparation_binding']=time.perf_counter()-ts
    epoch=object.__new__(PreparedSearchEpoch)
    for key,value in {'_graph':g,'_hazard':hazard_bytes,'_source':source,'_directory':directory,
                      '_implementation':implementation,'_settings':settings,
                      'preparation_wall_s':time.perf_counter()-started,
                      'preparation_timing_s':tuple(timing.items())}.items():
        object.__setattr__(epoch,key,value)
    return epoch


def _heuristic_envelope(graph,hazard,request):
    """Integer reverse Dijkstra and exactly represented priorities only."""
    dt=hazard.get('dt')
    if type(dt) is not int or dt<=0:
        raise ValueError('HEURISTIC_INTEGER_DT_REQUIRED')
    # With positive costs a shortest relaxed path is simple. Its length <= this sum.
    total=sum(e['travel_ticks']*dt for e in graph['edges'])
    horizon=request.get('horizon'); departure=request.get('departure')
    if type(horizon) not in (int,float) or type(departure) not in (int,float):
        raise ValueError('HEURISTIC_EXACT_PRIORITY_ENVELOPE')
    from fractions import Fraction
    if Fraction(horizon).denominator!=1 or Fraction(departure).denominator!=1 or abs(Fraction(horizon))+abs(Fraction(departure))+total>2**53:
        raise ValueError('HEURISTIC_EXACT_PRIORITY_ENVELOPE')


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform=='darwin' else 1024)


class SearchFollowup:
    """Explicit reusable session; content changes refuse until explicit replacement.

    Construction is cheap and timed. First run prepares an immutable source epoch.
    Replacement is prepare_epoch(...) then a NEW SearchFollowup(prepared_epoch=...).
    Request validation, exposure evaluation, and incumbent checking are per search.
    """
    def __init__(self, *, prepared_epoch=None, geometry_cache=None, checker_settings=None):
        started=time.perf_counter()
        if prepared_epoch is not None and type(prepared_epoch) is not PreparedSearchEpoch:
            raise TypeError('EXACT_PREPARED_SEARCH_EPOCH_REQUIRED')
        self._epoch=prepared_epoch
        self._geometry_cache=geometry_cache
        self._road_checker=None
        self._settings=json.loads(_settings_bytes(checker_settings))
        self._settings_binding=_json(self._settings)
        self.constructor_wall_s=time.perf_counter()-started
        self._has_run=False

    @property
    def prepared_epoch(self): return self._epoch

    def run(self,graph,admitted_hazard,source_directory,request,*,mode='baseline',check_witness=True,checker_wall_s=30):
        started=time.perf_counter();timing={};reused=self._epoch is not None;road_deadline=None
        constructor_charge=0 if self._has_run else self.constructor_wall_s
        self._has_run=True
        original_request=None;primary={'status':'NOT_RUN','reason':'EXTERNAL_ADMISSION_NOT_COMPLETE'}
        road={'status':'NOT_RUN','reason':'NO_CHECKED_SEARCH_WITNESS'};witness_origin=None
        report={'schema':SCHEMA,'mode':mode,'physical_safety_claim':False,'road_optimality_claim':False,
                'routing_defaults_changed':False,'epoch_reused':reused}
        try:
            if mode not in MODES: raise ValueError('UNKNOWN_EXPERIMENT_MODE')
            if type(check_witness) is not bool:raise ValueError('CHECK_WITNESS_BOOLEAN_REQUIRED')
            if type(checker_wall_s) not in (int,float) or not math.isfinite(checker_wall_s) or checker_wall_s<0:
                raise ValueError('CHECKER_CAP_FINITE_NONNEGATIVE_NONBOOLEAN_REQUIRED')
            if _json(self._settings)!=self._settings_binding:
                raise EpochMismatch('SESSION_SETTINGS_CHANGED_NEW_EPOCH_REQUIRED')
            ts=time.perf_counter();original_request=_json(request);graph_before=_json(graph);hazard_before=_json(admitted_hazard)
            r=json.loads(original_request);r['solver']='astar' if mode in ('heuristic','combined') else 'baseline'
            timing['request_snapshot_and_mode_dispatch']=time.perf_counter()-ts
            ts=time.perf_counter()
            if self._epoch is None:
                epoch=prepare_epoch(graph,admitted_hazard,source_directory,checker_settings=self._settings)
                self._epoch=epoch
                report['cold_epoch_preparation_timing_s']=dict(epoch.preparation_timing_s)
            else:
                self._epoch.validate_binding(graph,admitted_hazard,source_directory,self._settings)
            timing['external_epoch_preparation_or_validation']=time.perf_counter()-ts
            epoch=self._epoch
            ts=time.perf_counter();g=epoch.graph_snapshot();h=epoch.hazard_snapshot()
            timing['external_owned_snapshot_materialization']=time.perf_counter()-ts
            report['epoch_original_preparation_wall_s']=epoch.preparation_wall_s
            if mode in ('heuristic','combined'):
                ts=time.perf_counter()
                _heuristic_envelope(g,h,r)
                timing['external_heuristic_envelope_validation']=time.perf_counter()-ts
            cache_mode=mode in ('cache','combined')
            from routing.core_cached import solve_cached
            if cache_mode and self._geometry_cache is None:
                from routing.search_geometry_cache import SearchGeometryCache
                ts=time.perf_counter();self._geometry_cache=SearchGeometryCache(g)
                timing['external_geometry_cache_preparation']=time.perf_counter()-ts
            solver=solve_cached
            report['primary_implementation']='opt-in observer-derived exact core; cache_enabled controls eager versus lazy geometry'
            report['limits_exactly_preserved']=r.get('limits')==json.loads(original_request).get('limits')
            report['search_resource_limits']=copy.deepcopy(r.get('limits'))
            ts=time.perf_counter()
            # Cold raw baseline repeats graph validation, preserving original primary timing.
            # Only an explicitly warm epoch requests PreparedGraph admission reuse.
            kwargs={'prepared':epoch._graph} if reused else {}
            kwargs['cache_enabled']=cache_mode
            if cache_mode:kwargs['geometry_cache']=self._geometry_cache
            primary=solver(g,h,r,**kwargs)
            timing['primary_search_including_solver_preprocessing_and_center_check']=time.perf_counter()-ts
            witness=None
            if primary.get('status') in ('CONDITIONAL_OPTIMUM','CHECKED_ROUTE') and primary.get('checker',{}).get('ok') is True:
                witness=primary;witness_origin='COMPLETE_RETURNED_SEARCH_ROUTE'
            elif primary.get('status')=='TIMEOUT':
                incumbent=primary.get('checked_incumbent',{})
                if incumbent.get('status')=='CHECKED_ROUTE' and incumbent.get('checker',{}).get('ok') is True:
                    witness=incumbent;witness_origin='EXPLICIT_CHECKED_TIMEOUT_INCUMBENT'
            if source_directory is None:
                road={'status':'UNRESOLVED','reason':'SOURCE_CONTRACT_UNAVAILABLE','center_only_fixture':True}
            elif witness is not None and check_witness:
                ts=time.perf_counter()
                stop=ts+float(checker_wall_s);road_deadline=stop
                if self._road_checker is None:
                    self._road_checker=HybridChecker(source_directory,settings=self._settings)
                # Constructor is inside this separate road-check budget and total cost.
                road=self._road_checker.check(g,r,witness['legs'],witness['destination'],wall_s=checker_wall_s,deadline=stop,
                    expected_graph_revision=g['revision'],expected_graph_sha256=epoch._graph.fingerprint)
                timing['whole_road_check_including_constructor']=time.perf_counter()-ts
            elif witness is not None:
                road={'status':'NOT_RUN','reason':'CHECKING_EXPLICITLY_DISABLED'}
            ts=time.perf_counter()
            epoch.validate_binding(graph,admitted_hazard,source_directory,self._settings)
            if original_request!=_json(request) or graph_before!=_json(graph) or hazard_before!=_json(admitted_hazard):
                raise EpochMismatch('CALLER_INPUT_CHANGED_DURING_RUN')
            timing['final_full_content_validation']=time.perf_counter()-ts
            report['epoch']=epoch.identities()
        except (ValueError,TypeError,KeyError,OSError,ArithmeticError,ImportError) as exc:
            report['external_failure']={'reason':str(exc),'code':getattr(exc,'code',type(exc).__name__)}
            road={'status':'UNRESOLVED','reason':'INTEGRATION_BINDING_OR_ADMISSION_FAILURE','secondary_road_result':road}
        integrated='UNRESOLVED'
        if 'external_failure' not in report:
            if road['status']=='CERTIFIED_ADMISSIBLE':
                integrated='TIMEOUT_WITH_CHECKED_INTEGRATED_WITNESS' if primary['status']=='TIMEOUT' else 'CERTIFIED_INTEGRATED_WITNESS'
            elif road['status']=='DEFINITE_REJECT':integrated='SEARCH_WITNESS_DEFINITELY_REJECTED_ON_ROAD'
        report.update(primary_search=primary,whole_road_check=road,witness_origin=witness_origin,
                      integrated_status=integrated,primary_search_status=primary['status'],
                      center_optimality_claim='external_failure' not in report and primary.get('status')=='CONDITIONAL_OPTIMUM',
                      integrated_witness_available='external_failure' not in report and road['status']=='CERTIFIED_ADMISSIBLE',
                      global_road_optimum_or_refusal_certified=False,
                      timing_s=timing,combined_lifecycle_wall_s=time.perf_counter()-started,
                      external_constructor_wall_s=self.constructor_wall_s,
                      process_lifetime_rss_mb=_rss(),
                      budget_boundaries='Original solve limits unchanged; external epoch/admission/cache setup separately measured; whole-road check separately capped; all reported in combined lifecycle',
                      proof_scope='finite supplied members and constructed model only; centre optimum does not imply road optimum')
        try:
            if self._geometry_cache is not None:
                ts=time.perf_counter();report['geometry_cache']=self._geometry_cache.cache_info()
                timing['final_geometry_cache_inspection']=time.perf_counter()-ts
            # Binding is checked after metadata/cache access before authorization.
            if 'external_failure' not in report:
                ts=time.perf_counter()
                self._epoch.validate_binding(graph,admitted_hazard,source_directory,self._settings)
                if original_request!=_json(request):
                    raise EpochMismatch('CALLER_REQUEST_CHANGED_DURING_FINALIZATION')
                timing['post_metadata_full_content_validation']=time.perf_counter()-ts
        except (ValueError,TypeError,KeyError,OSError,ArithmeticError,ImportError) as exc:
            report['external_failure']={'reason':str(exc),'code':getattr(exc,'code',type(exc).__name__)}
            report['whole_road_check']={'status':'UNRESOLVED','reason':'FINAL_AUTHORITY_FAILURE',
                                      'secondary_road_result':report['whole_road_check']}
            report['integrated_status']='UNRESOLVED';report['center_optimality_claim']=False;report['integrated_witness_available']=False
        finished=time.perf_counter()
        if road_deadline is not None and finished>=road_deadline and report['whole_road_check']['status']!='UNRESOLVED':
            report['whole_road_check']={'status':'UNRESOLVED','reason':'ROAD_CAP_DURING_INTEGRATION_FINALIZATION',
                                      'secondary_road_result':report['whole_road_check']}
            report['integrated_status']='UNRESOLVED';report['integrated_witness_available']=False
        report['combined_lifecycle_wall_s']=finished-started
        report['constructor_cost_charged_to_this_run_wall_s']=constructor_charge
        report['combined_lifecycle_including_constructor_wall_s']=finished-started+constructor_charge
        return report


def run_search(graph,admitted_hazard,source_directory,request,*,mode='baseline',prepared_epoch=None,
               geometry_cache=None,checker_settings=None,check_witness=True,checker_wall_s=30):
    """Portable one-shot convenience; use SearchFollowup explicitly for warm reuse."""
    started=time.perf_counter()
    session=SearchFollowup(prepared_epoch=prepared_epoch,geometry_cache=geometry_cache,checker_settings=checker_settings)
    result=session.run(graph,admitted_hazard,source_directory,request,mode=mode,check_witness=check_witness,checker_wall_s=checker_wall_s)
    result['combined_lifecycle_including_constructor_wall_s']=time.perf_counter()-started
    return result
