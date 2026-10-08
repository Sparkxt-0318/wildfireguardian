"""Owned pipeline/cache development controls; all toy authority challenges explicit."""
from pathlib import Path
import copy,json,sys,time,tempfile,shutil
import numpy as np
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'candidate'))
from hybrid_checker import HybridChecker
from hybrid_shadow import HybridShadowWitnessAdapter,bind_witness_context
from mission_contract import graph_digest
import hybrid_checker as wrapper


def encode(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def fixture(path):
    path.mkdir();report=json.loads((D/'baseline/results/fresh_sources/20220304T030000Z/REPORT.json').read_text())
    report['native_metadata']['construction']['assumptions']['horizon_s']=30
    report['native_metadata']['affine_transform']=[10,0,0,0,-10,20]
    report['rows'][0]['request']['incurred']={'s':0}
    report['wrapper_fixture_scope']='GENERATED_AUTHORITY_CONTROL_NOT_INCIDENT_OR_PHYSICAL_EVIDENCE'
    encode(path/'REPORT.json',report)
    events=np.full((1,2,2),np.inf);events[0,0,1]=20
    np.savez_compressed(path/'constructed_arrays.npz',ignition_time_s=events,current_active=np.zeros((2,2),bool),support=np.ones((1,1,2,2),bool))
    graph={'revision':'wrapper-control-1','nodes':[{'id':'a','x':1,'y':5,'waitable':True},{'id':'b','x':5,'y':5,'waitable':True},{'id':'c','x':9,'y':5,'waitable':False}],
      'edges':[{'id':'ab','u':'a','v':'b','travel_ticks':3},{'id':'bc','u':'b','v':'c','travel_ticks':3}],'forbidden_turns':[]}
    request={'graph_revision':graph['revision'],'position':{'node':'a'},'incoming_edge':None,'departure':0,'horizon':30,'destinations':[{'node':'c','dwell':2,'open_intervals':[[0,30]]}],
      'exposure_scope':'including_dwell','incurred':{'s':0},'budgets':{'peak':10,'dose':{'s':100}},'hazard_version':1}
    legs=[{'kind':'EDGE','edge':'ab','start':0,'end':3,'from_fraction':0,'to_fraction':1},{'kind':'EDGE','edge':'bc','start':3,'end':6,'from_fraction':0,'to_fraction':1}]
    return graph,request,legs

def run():
    records=[]
    def record(name,result,expected):
        assert result['status']==expected,(name,result);records.append({'name':name,'expected':expected,'observed':result['status'],'reason':result.get('reason'),'elapsed_s':result.get('elapsed_s'),'pass':True})
    with tempfile.TemporaryDirectory(prefix='wrapper_controls_',dir=D/'development') as temp:
        p=Path(temp)/'source';g,r,legs=fixture(p)
        def check(c,g=g,r=r,legs=legs,**kw):return c.check(g,r,legs,'c',expected_graph_revision=g['revision'],expected_graph_sha256=graph_digest(g),**kw)
        c=HybridChecker(p);a=check(c);record('complete_cold_control',a,'CERTIFIED_ADMISSIBLE');b=check(c);record('complete_warm_control',b,'CERTIFIED_ADMISSIBLE')
        assert not a['cache_work']['source_snapshot_reused'] and b['cache_work']['source_snapshot_reused'];assert not a['cache_work']['radiation_object_reused'] and b['cache_work']['radiation_object_reused']
        assert b['cache_work']['request_result_cache_entries']==0 and b['cache_work']['contact_cache_entries']==0
        records.append({'name':'cold_warm_cost_and_cache_reporting','pass':True,'cold':a['timing_s'],'warm':b['timing_s']})
        original_report=(p/'REPORT.json').read_bytes();original_array=(p/'constructed_arrays.npz').read_bytes()
        report=json.loads(original_report);config=report['native_metadata']['construction']['assumptions']
        for key in config:
            changed=copy.deepcopy(report);v=config[key]
            changed['native_metadata']['construction']['assumptions'][key]=not v if isinstance(v,bool) else v+1 if isinstance(v,(int,float)) else str(v)+'_authority_change'
            encode(p/'REPORT.json',changed);record('source_assumption_epoch_'+key,check(c),'UNRESOLVED');(p/'REPORT.json').write_bytes(original_report)
        for name,mutate in [('source_affine',lambda x:x['native_metadata']['affine_transform'].__setitem__(0,11)),('member_ids',lambda x:x['rows'][0]['request'].update(incurred={'changed':0})),('report_metadata',lambda x:x.update(assumption_id='changed-provenance'))]:
            changed=copy.deepcopy(report);mutate(changed);encode(p/'REPORT.json',changed);record(name+'_invalidates_epoch',check(c),'UNRESOLVED');(p/'REPORT.json').write_bytes(original_report)
        with np.load(p/'constructed_arrays.npz',allow_pickle=False) as arrays:base={k:arrays[k].copy() for k in arrays.files}
        for name in ['ignition_time_s','current_active','support']:
            changed={k:v.copy() for k,v in base.items()}
            if name=='ignition_time_s':changed[name][0,0,1]=21
            elif name=='current_active':changed[name][0,0]=True
            else:changed[name][0,0,0,0]=False
            np.savez_compressed(p/'constructed_arrays.npz',**changed);record(name+'_invalidates_epoch',check(c),'UNRESOLVED');(p/'constructed_arrays.npz').write_bytes(original_array)
        record('restored_source_same_owned_epoch',check(c),'CERTIFIED_ADMISSIBLE')
        gg=copy.deepcopy(g);gg['nodes'][1]['x']=6;record('graph_geometry_epoch',check(c,g=gg),'UNRESOLVED')
        gg=copy.deepcopy(g);gg['edges'][0]['travel_ticks']=4;record('graph_duration_epoch',check(c,g=gg),'UNRESOLVED')
        gg=copy.deepcopy(g);gg['revision']='different';record('graph_revision_epoch',check(c,g=gg),'UNRESOLVED')
        gg=copy.deepcopy(g);gg['forbidden_turns']=[['ab','bc']];record('graph_turns_epoch',check(c,g=gg),'UNRESOLVED')
        gg=copy.deepcopy(g);gg['nodes'][0]['waitable']=False;record('graph_waitability_epoch',check(c,g=gg),'UNRESOLVED')
        rr=copy.deepcopy(r);rr['incurred']['s']=100;record('incurred_equality_recomputed_warm',check(c,r=rr),'CERTIFIED_ADMISSIBLE')
        rr['incurred']['s']=101;record('incurred_violation_recomputed_warm',check(c,r=rr),'DEFINITE_REJECT')
        rr=copy.deepcopy(r);rr['budgets']['dose']['s']=0;rr['incurred']['s']=1;record('dose_budget_change_recomputed',check(c,r=rr),'DEFINITE_REJECT')
        rr=copy.deepcopy(r);rr['budgets']['peak']=-1;record('peak_budget_change_validated',check(c,r=rr),'UNRESOLVED')
        rr=copy.deepcopy(r);rr['incurred'].clear();record('member_history_missing',check(c,r=rr),'UNRESOLVED')
        rr=copy.deepcopy(r);rr['incurred']['s']=True;record('boolean_history_rejected',check(c,r=rr),'UNRESOLVED')
        rr=copy.deepcopy(r);rr['destinations'][0]['dwell']=25;record('dwell_horizon_change',check(c,r=rr),'UNRESOLVED')
        ll=copy.deepcopy(legs);ll[1]['start']=4;record('leg_timing_recomputed',check(c,legs=ll),'UNRESOLVED')
        record('zero_wall_cap',check(c,wall_s=0),'UNRESOLVED');record('past_shared_deadline',check(c,deadline=time.perf_counter()-1),'UNRESOLVED')
        for key in c.settings:
            altered=HybridChecker(p);check(altered);changed=dict(altered.settings);v=changed[key];changed[key]=v+1 if isinstance(v,(int,float)) else str(v)+'_changed';altered.settings=changed
            record('settings_epoch_'+key,check(altered),'UNRESOLVED')
        altered=HybridChecker(p);check(altered);altered.directory=Path(temp)/'different';record('directory_epoch',check(altered),'UNRESOLVED')
        for kind in ['source','graph','request','legs','settings']:
            cc=HybridChecker(p);check(cc);gg=copy.deepcopy(g);rr=copy.deepcopy(r);ll=copy.deepcopy(legs);original=cc._radiation.trajectory_bound
            def mutate_during(*a,_kind=kind,**kw):
                result=original(*a,**kw)
                if _kind=='source':encode(p/'REPORT.json',{**report,'authority_mutation':True})
                elif _kind=='graph':gg['nodes'][0]['x']=2
                elif _kind=='request':rr['incurred']['s']=1
                elif _kind=='legs':ll[0]['end']=2
                else:cc.settings={**dict(cc.settings),'authority_mutation':True}
                return result
            cc._radiation.trajectory_bound=mutate_during;record(kind+'_mutation_during_check',check(cc,g=gg,r=rr,legs=ll),'UNRESOLVED');(p/'REPORT.json').write_bytes(original_report)
        cc=HybridChecker(p);check(cc);original=cc._radiation.trajectory_bound
        def late(*a,**kw):result=original(*a,**kw);time.sleep(.05);return result
        cc._radiation.trajectory_bound=late;record('deadline_crossed_after_radiation',check(cc,wall_s=.03),'UNRESOLVED')
        cc=HybridChecker(p);check(cc)
        def numerical_guard_failure(*a,**kw):raise ArithmeticError('INCOMPATIBLE_SAME_LAW_ENCLOSURES_FAULT_INJECTION')
        cc._radiation.trajectory_bound=numerical_guard_failure
        record('numerical_invariant_guard_unresolved',check(cc),'UNRESOLVED')
        saved=wrapper.rss_mb;wrapper.rss_mb=lambda:4096
        try:record('rss_gate_refuses_result',check(HybridChecker(p)),'UNRESOLVED')
        finally:wrapper.rss_mb=saved
        shadow=HybridShadowWitnessAdapter(p);primary={'escape':{'status':'TIMEOUT','checked_incumbent':{'status':'CHECKED_ROUTE','legs':copy.deepcopy(legs),'destination':'c'}}};binding=bind_witness_context(p,g,r)
        disabled=shadow.check(primary,g,r);assert disabled['primary_result']==primary and disabled['shadow_status']=='DISABLED';records.append({'name':'shadow_default_disabled','pass':True})
        out=shadow.check(primary,g,r,binding=binding,enabled=True);assert out['primary_result']==primary and out['primary_search_status']=='TIMEOUT' and out['shadow_status']=='CERTIFIED_ADMISSIBLE';records.append({'name':'timeout_checked_incumbent_secondary','pass':True})
        unsupported={'escape':{'status':'UNSUPPORTED'}};out=shadow.check(unsupported,g,r,binding=binding,enabled=True);assert out['primary_result']==unsupported and out['primary_search_status']=='UNSUPPORTED' and out['shadow_status']=='UNRESOLVED';records.append({'name':'unsupported_primary_unchanged','pass':True})
        out=shadow.check(primary,g,r,binding=binding,enabled=True,wall_s=0);assert out['shadow_status']=='UNRESOLVED';records.append({'name':'shadow_shared_zero_deadline','pass':True})
    output={'scope':'DEVELOPMENT_AUTHORITY_CONTROLS_ONLY','status':'PASS','checks':len(records),'records':records,'no_fresh_inputs_opened':True}
    encode(D/'development/wrapper_checks.json',output);return output
if __name__=='__main__':print(json.dumps({k:v for k,v in run().items() if k!='records'},indent=2))
