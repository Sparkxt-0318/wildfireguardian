#!/usr/bin/env python3
"""Independent integration review. Only standard library; preserves every run."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def semantic(value):
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items()
                if k not in ('wall_s', 'peak_rss_mb', 'end_to_end_s') or k == 'wall_s' and 'max_labels' in value}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


def record_test(records, name, fn):
    try:
        evidence = fn()
        records.append({'name': name, 'status': 'PASS', 'evidence': evidence})
    except Exception:
        records.append({'name': name, 'status': 'FAIL', 'traceback': traceback.format_exc()})


def equal(a, b):
    if a != b:
        raise AssertionError(json.dumps({'expected': a, 'actual': b}, sort_keys=True, default=str))


def worker(package, mode):
    sys.path.insert(0, str(package))
    from routing.fixture import example
    from routing.session import RoutingSession
    from routing.fallback import checked_return
    from routing.service import plan_with_return
    from routing.replay import replay
    from routing.independent import exhaustive, check_route
    from routing.validation import validate_graph, validate_hazard, validate_request
    if mode != 'baseline':
        from routing import prepare_graph
    prepared = mode == 'prepared'
    records, outputs = [], {}
    def new_session(g):
        return RoutingSession(g, prepare=True) if prepared else RoutingSession(g)
    def fallback(g, h, q, hist, endpoint='O', dwell=0):
        return checked_return(prepare_graph(g) if prepared else g, h, q, hist, endpoint, dwell)
    def service(g, h, q, hist):
        return plan_with_return(prepare_graph(g) if prepared else g, h, q, hist, 'O', return_budget_s=1)
    def capture(name, fn):
        value=fn(); outputs[name]=semantic(value); return outputs[name]

    def continuity():
        x=example(); g,h,q=(x[k] for k in ('graph','hazard','request')); s=new_session(g); events=[]
        events.append(s.accept_update(h,q['as_of']))
        first=s.plan(q); second=s.plan(q); events.extend([first,second,s.commit(first),s.commit(second),s.retained_plan()])
        events.append(s.accept_update(h,q['as_of'])); events.append(s.commit(second)); events.append(s.retained_plan())
        bad=copy.deepcopy(h);bad['schema']='bad';events.append(s.accept_update(bad,q['as_of']));events.append(s.retained_plan())
        newer=copy.deepcopy(h);newer['version']=2;newer['members'][1]['flux'][0]=[3.]*8
        events.append(s.accept_update(newer,q['as_of']));events.extend([s.commit(second),s.retained_plan()])
        hist=[{'edge':'OA','from_fraction':0,'to_fraction':1}]
        events.append(s.set_progress({'node':'A'},'OA',2,{'m0':2,'m1':4},hist))
        current=s.plan(q);events.extend([current,s.commit(current),s.retained_plan()]);equal(current['request']['incurred'],{'m0':2,'m1':4})
        events.append(s.set_progress({'node':'A'},'OA',1,{'m0':2,'m1':4},hist))
        events.append(s.set_progress({'node':'A'},'OA',3,{'m0':0,'m1':0},hist))
        events.append(s.set_progress({'node':'D'},'AD',4,{'m0':4,'m1':10},hist+[{'edge':'AD','from_fraction':0,'to_fraction':1}]))
        events.append(s.retained_plan())
        member=copy.deepcopy(newer);member['version']=3;member['members'][1]['id']='new'
        events.append(s.accept_update(member,q['as_of']));events.append(s.accept_update(member,q['as_of'],{'m0':4,'new':10}))
        events.append(s.accept_update(member,q['as_of'],{'m0':10,'new':10}))
        rejected=s.plan(q);events.append(rejected);equal(rejected['status'],'INVALID_INPUT')
        q=copy.deepcopy(q);q['budgets']['dose']={'m0':25,'new':25};mapped=s.plan(q);events.append(mapped);equal(mapped['request']['incurred'],{'m0':10,'new':10})
        events.append(s.reset());events.extend([s.commit(mapped),s.retained_plan()]);events.append(s.accept_update(h,q['as_of']));events.append(s.plan(x['request']))
        return events
    record_test(records,'actual_session_continuity_and_identity',lambda:capture('continuity',continuity))

    def fresh_hazard():
        variants=[]
        for kind in ('wrong_revision','bad_grid','wrong_members','wrong_version','nan_flux','future_available','old_issue','flame','missing_support','time_origin'):
            x=example();s=new_session(x['graph']);s.accept_update(x['hazard'],x['request']['as_of']);s.commit(s.plan(x['request']));h=copy.deepcopy(x['hazard']);h['version']=2
            if kind=='wrong_revision':h['graph_revision']='different'
            if kind=='bad_grid':h['grid']['width']=1
            if kind=='wrong_members':h['members'][1]['id']=h['members'][0]['id']
            if kind=='wrong_version':h['version']=True
            if kind=='nan_flux':h['members'][0]['flux'][0][1]=float('nan')
            if kind=='future_available':h['available_at']='2026-10-04T00:00:09+08:00'
            if kind=='old_issue':h['issued_at']='2026-10-03T23:59:59+08:00'
            if kind=='flame':h['members'][0]['flame'][0][1]=True
            if kind=='missing_support':h['members'][0]['support'][0][1]=False
            if kind=='time_origin':h['time_origin']='2026-10-04T01:00:00+08:00'
            admission=s.accept_update(h,x['request']['as_of']);r=s.plan(x['request']);variants.append([kind,admission,r,s.retained_plan()])
        return variants
    record_test(records,'hazards_always_readmitted',lambda:capture('hazards',fresh_hazard))

    def returns():
        results=[]
        for kind in ('success','dwell_dose','forbidden','support','flame','opening','missing_reverse','partial_allowed','partial_forbidden','partial_history_mismatch','nonrepresentable_partial','timeout'):
            x=example();g,h,q=(x[k] for k in ('graph','hazard','request'));hist=[{'edge':'OA','from_fraction':0,'to_fraction':1}]
            q.update(position={'node':'A'},incoming_edge='OA',departure=2,incurred={'m0':2,'m1':4},return_endpoint={'node':'O','dwell':2,'open_intervals':[[0,30]]})
            if kind=='dwell_dose':q['exposure_scope']='including_dwell'
            if kind=='forbidden':g['forbidden_turns']=[['OA','AO']]
            if kind=='support':h['members'][0]['support'][0][0]=False
            if kind=='flame':h['members'][0]['flame'][0][0]=True
            if kind=='opening':q['return_endpoint']['open_intervals']=[[0,4]]
            if kind=='missing_reverse':
                g['edges'][0].pop('reverse_edge');g['edges'][1].pop('reverse_edge')
            if kind.startswith('partial') or kind=='nonrepresentable_partial':
                fraction=.1 if kind=='nonrepresentable_partial' else .5
                q.update(position={'edge':'OA','fraction':fraction},incoming_edge='OA',departure=1,incurred={'m0':1,'m1':2});hist[0]['to_fraction']=fraction
                g['mid_edge_reversal']=kind!='partial_forbidden'
                if kind=='partial_history_mismatch':hist[0]['to_fraction']=.25
            if kind=='timeout':q['limits']['wall_s']=0
            r=fallback(g,h,q,hist);results.append([kind,r])
            if kind=='success':equal(r['status'],'CHECKED_ROUTE');equal(r['per_member']['m1']['dose_exact'],'8')
            if kind=='dwell_dose':equal(r['per_member']['m1']['dose_exact'],'12')
            if kind=='timeout':equal(r['status'],'TIMEOUT')
        x=example();q=x['request'];q.update(position={'node':'A'},incoming_edge='OA',departure=2,incurred={'m0':2,'m1':4});q['limits']['wall_s']=0
        timeout=service(x['graph'],x['hazard'],q,[{'edge':'OA','from_fraction':0,'to_fraction':1}]);equal(timeout['escape']['status'],'TIMEOUT');equal(timeout['primary_problem_resolved'],False);equal(timeout['return_alternative']['status'],'CHECKED_ROUTE');results.append(['primary_timeout_return',timeout])
        return results
    record_test(records,'actual_return_direction_support_dwell_timeout',lambda:capture('returns',returns))

    def replays():
        x=example();h2=copy.deepcopy(x['hazard']);h2['version']=2
        x['events']=[{'kind':'PLAN','request':copy.deepcopy(x['request'])},{'kind':'UPDATE','hazard':h2,'as_of':x['request']['as_of']}, {'kind':'RETAINED'}, {'kind':'PROGRESS','position':{'node':'A'},'incoming_edge':'OA','departure':2,'incurred':{'m0':2,'m1':4},'history':[{'edge':'OA','from_fraction':0,'to_fraction':1}]},{'kind':'PLAN','request':copy.deepcopy(x['request'])},{'kind':'RETURN','endpoint':'O'},{'kind':'RESET'}]
        a=replay(x,prepare=True) if prepared else replay(x);b=replay(x,prepare=True) if prepared else replay(x);equal(a,b);equal(a['status'],'RESET');return a
    record_test(records,'real_replay_updates_progress_return_reset',lambda:capture('replay',replays))

    def oracle_checks():
        cases=json.loads((package/'fixtures/evaluation_cases.json').read_text())['cases'];results=[]
        for case in cases:
            g,h,q=(copy.deepcopy(case[k]) for k in ('graph','hazard','request'));q['limits']['wall_s']=5
            validate_graph(g);h=validate_hazard(g,h,q['as_of']);q=validate_request(g,h,q)
            ref=exhaustive(g,h,q,max_walks=200000);assert ref['status']!='UNRESOLVED',case['id']
            for solver in ('baseline','dijkstra','astar'):
                q['solver']=solver;s=new_session(g);equal(s.accept_update(h,q['as_of'])['status'],'ACCEPTED_UPDATE');r=s.plan(q)
                expected=ref['status'];
                # Static reachability may provide the stricter graph-only refusal.
                if r['status']=='DISCONNECTED':equal(expected,'PROVEN_INFEASIBLE')
                else:equal(r['status'],expected)
                if expected in ('CONDITIONAL_OPTIMUM','CHECKED_ROUTE'):
                    equal(r['arrival'],ref['arrival']);checked=check_route(g,h,r['request'],r['legs'],r['destination']);equal(checked['ok'],True);equal(r['per_member'],checked['per_member'])
                results.append({'case':case['id'],'solver':solver,'result':r,'reference':ref})
        return results
    record_test(records,'all_finite_cases_complete_exhaustive_reference',lambda:capture('oracle',oracle_checks))

    if mode!='baseline':
        def ownership():
            items=[]
            for policy in ('snapshot','checked'):
                x=example();g=x['graph'];s=RoutingSession(g,prepare=True,graph_ownership=policy);s.accept_update(x['hazard'],x['request']['as_of']);r=s.plan(x['request']);equal(s.commit(r),True)
                export=s.graph;export['nodes'].clear();equal(s.graph['nodes'][0]['id'],'O')
                if policy=='snapshot':
                    g['edges'][0]['travel_ticks']=9;equal(semantic(s.plan(x['request']))['arrival'],4)
                else:
                    g['edges'][0]['travel_ticks']=9
                    # Each operation must reject authority mismatch rather than read
                    # a mixture of admitted old geometry and new caller geometry.
                    for name,fn in [('plan',lambda:s.plan(x['request'])),('update',lambda:s.accept_update(x['hazard'],x['request']['as_of'])),('progress',lambda:s.set_progress({'node':'O'},None,0,{'m0':0,'m1':0},[])),('retained',lambda:s.retained_plan()),('return',lambda:s.check_return(x['request'],'O')),('commit',lambda:s.commit(r))]:
                        out=fn()
                        if name=='commit':equal(out,False)
                        else:assert out['status'] not in ('CONDITIONAL_OPTIMUM','CHECKED_ROUTE','ACCEPTED_UPDATE','PROGRESS_ACCEPTED'),out
                        items.append([name,out])
                    old_handle=s.prepared_graph;s.reset();equal(s.hazard,None);equal(s.progress,None);equal(s.prepared_graph,old_handle)
                    equal(s.accept_update(x['hazard'],x['request']['as_of'])['reason'],'PREPARED_GRAPH_MISMATCH')
                    equal(s.replace_graph(g)['status'],'GRAPH_REPLACED');equal(s.accept_update(x['hazard'],x['request']['as_of'])['status'],'ACCEPTED_UPDATE');equal(s.plan(x['request'])['arrival'],6)
                items.append([policy,'export_and_caller_mutation_pass'])
            return items
        record_test(records,'snapshot_and_checked_all_operation_guards',ownership)

        def replacements():
            x=example();s=RoutingSession(x['graph'],prepare=True);s.accept_update(x['hazard'],x['request']['as_of']);r=s.plan(x['request']);s.commit(r);g=copy.deepcopy(x['graph']);g['edges'][0]['travel_ticks']=3
            try:
                out=s.replace_graph(g)
                assert out['status'] not in ('GRAPH_REPLACED','REPLACED','RESET'),out
            except (ValueError,TypeError):pass
            equal(s.graph,x['graph']);equal(s.retained_plan()['status'],'CHECKED_ROUTE')
            bad=copy.deepcopy(g);bad['edges'][0]['travel_ticks']=0
            try:s.replace_graph(bad,reset=True)
            except (ValueError,TypeError):pass
            equal(s.graph,x['graph']);equal(s.retained_plan()['status'],'CHECKED_ROUTE')
            out=s.replace_graph(g,reset=True);equal(out['status'],'GRAPH_REPLACED');equal(s.hazard,None);equal(s.progress,None);equal(s.commit(r),False);equal(s.retained_plan()['status'],'UNSUPPORTED')
            s.accept_update(x['hazard'],x['request']['as_of']);equal(s.plan(x['request'])['arrival'],5)
            export=s.graph;export['edges'][0]['travel_ticks']=1;equal(s.plan(x['request'])['arrival'],5)
            s.reset();equal(s.graph,g);return out
        record_test(records,'explicit_atomic_replacement_and_reset',replacements)

        def mismatch_facades():
            x=example();p=prepare_graph(x['graph']);x['graph']['edges'][0]['travel_ticks']=9
            r=checked_return(x['graph'],x['hazard'],x['request'],[],'O',prepared=p);equal(r['status'],'INVALID_INPUT')
            v=plan_with_return(x['graph'],x['hazard'],x['request'],prepared=p);equal(v['escape']['status'],'INVALID_INPUT');return [r,v]
        record_test(records,'external_mutable_fallback_service_full_content_binding',mismatch_facades)

        def checked_facade_positive_and_types():
            x=example();g,h,q=(x[k] for k in ('graph','hazard','request'));q.update(position={'node':'A'},incoming_edge='OA',departure=2,incurred={'m0':2,'m1':4})
            hist=[{'edge':'OA','from_fraction':0,'to_fraction':1}];p=prepare_graph(g)
            equal(semantic(checked_return(g,h,q,hist,'O')),semantic(checked_return(g,h,q,hist,'O',prepared=p)))
            q['limits']['wall_s']=0
            equal(semantic(plan_with_return(g,h,q,hist,'O',return_budget_s=1)),semantic(plan_with_return(g,h,q,hist,'O',return_budget_s=1,prepared=p)))
            bad=checked_return(g,h,q,hist,'O',prepared=g);equal(bad['reason'],'PREPARED_GRAPH_TYPE')
            bad2=plan_with_return(g,h,q,prepared=g);equal(bad2['escape']['reason'],'PREPARED_GRAPH_TYPE')
            return [bad,bad2]
        record_test(records,'checked_facade_positive_and_type_rejections',checked_facade_positive_and_types)

        def same_revision_other_contents():
            checked=[]
            edits=[('turns',lambda g:g['forbidden_turns'].append(['OA','AD'])),('geometry',lambda g:g['edges'][0]['segments'][0].update(cell=7)),('node_wait',lambda g:g['nodes'][0].update(waitable=True)),('provenance',lambda g:g.update(provenance={'source':'changed'})),('array_order',lambda g:g['nodes'].reverse())]
            for name,edit in edits:
                x=example();g=x['graph'];s=RoutingSession(g,prepare=True,graph_ownership='checked');s.accept_update(x['hazard'],x['request']['as_of']);r=s.plan(x['request']);s.commit(r);revision=g['revision'];edit(g);equal(g['revision'],revision)
                equal(s.plan(x['request'])['reason'],'PREPARED_GRAPH_MISMATCH');equal(s.commit(r),False);checked.append(name)
            return checked
        record_test(records,'same_revision_all_contents_bind_session_authority',same_revision_other_contents)

        def replacement_reset_requires_boolean():
            evidence=[]
            for value in ('false', [], [1], 0, 1, None):
                x=example();g,h,q=(x[k] for k in ('graph','hazard','request'));s=new_session(g);s.accept_update(h,q['as_of']);s.commit(s.plan(q))
                state=copy.deepcopy([s.graph,s.hazard,s.progress,s.retained,s._pending_request,s._last_request,s.last_update,s._as_of,s.generation])
                replacement=copy.deepcopy(g);replacement['edges'][0]['travel_ticks']=3
                out=s.replace_graph(replacement,reset=value)
                equal(out['status'],'INVALID_INPUT');equal(out['reason'],'GRAPH_REPLACEMENT_RESET_FLAG')
                equal([s.graph,s.hazard,s.progress,s.retained,s._pending_request,s._last_request,s.last_update,s._as_of,s.generation],state)
                x['events']=[{'kind':'GRAPH_REPLACE','graph':replacement,'reset':value},{'kind':'RETAINED'}]
                replayed=replay(x,prepare=True) if prepared else replay(x)
                equal(replayed['events'][2]['status'],'INVALID_INPUT');equal(replayed['events'][2]['reason'],'GRAPH_REPLACEMENT_RESET_FLAG')
                equal(replayed['events'][3]['status'],'CHECKED_ROUTE');equal(replayed['result']['arrival'],4)
                evidence.append({'reset':value,'direct_replacement':out,'replay_replacement':replayed['events'][2]})
            return evidence
        record_test(records,'replacement_reset_boolean_admission_and_replay',replacement_reset_requires_boolean)
    return {'records':records,'outputs':outputs}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',type=Path);parser.add_argument('--mode',default='raw');args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker,args.mode),sort_keys=True,allow_nan=False));return
    timestamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());run_dir=HERE/'runs'/timestamp;run_dir.mkdir(parents=True,exist_ok=False)
    manifest={'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'candidate':{},'baseline':{}}
    for name in ('candidate','baseline'):
        for path in sorted((ROOT/name/'routing').glob('*.py')):
            manifest[name][str(path.relative_to(ROOT/name))]=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest[name]['run.py']=hashlib.sha256((ROOT/name/'run.py').read_bytes()).hexdigest()
        manifest[name]['fixtures/evaluation_cases.json']=hashlib.sha256((ROOT/name/'fixtures/evaluation_cases.json').read_bytes()).hexdigest()
    (run_dir/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    findings=[];runs={}
    for label,package,mode in [('baseline',ROOT/'baseline','baseline'),('raw',ROOT/'candidate','raw'),('prepared',ROOT/'candidate','prepared')]:
        child=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--worker',str(package),'--mode',mode],capture_output=True,text=True,timeout=60)
        (run_dir/(label+'.stdout')).write_text(child.stdout);(run_dir/(label+'.stderr')).write_text(child.stderr)
        if child.returncode:findings.append({'name':label,'status':'FAIL','exit':child.returncode});continue
        runs[label]=json.loads(child.stdout);findings.extend([dict(item,mode=label) for item in runs[label]['records']])
    if 'baseline' in runs:
        for label in ('raw','prepared'):
            if label in runs:
                for name,value in runs['baseline']['outputs'].items():
                    record_test(findings,label+'_vs_preserved_baseline_'+name,lambda label=label,name=name,value=value:equal(value,runs[label]['outputs'].get(name)))
    # Actual CLIs: raw and explicit preparation, solve and replay, candidate and
    # preserved baseline. CLI output can differ only in measured wall/RSS fields.
    for command in ('solve','replay'):
        ref=subprocess.run([sys.executable,'-B',str(ROOT/'baseline/run.py'),command],capture_output=True,text=True,timeout=30)
        (run_dir/('cli_baseline_'+command+'.stdout')).write_text(ref.stdout);(run_dir/('cli_baseline_'+command+'.stderr')).write_text(ref.stderr)
        for flag in ([],['--prepare-graph']):
            label=command+('_prepared' if flag else '_raw');out=subprocess.run([sys.executable,'-B',str(ROOT/'candidate/run.py'),command]+flag,capture_output=True,text=True,timeout=30)
            (run_dir/('cli_'+label+'.stdout')).write_text(out.stdout);(run_dir/('cli_'+label+'.stderr')).write_text(out.stderr)
            def check(out=out,ref=ref):
                equal(ref.returncode,0);equal(out.returncode,0);equal(semantic(json.loads(ref.stdout)),semantic(json.loads(out.stdout)))
            record_test(findings,'actual_cli_'+label,check)
    result={'status':'PASS' if all(i['status']=='PASS' for i in findings) else 'FAIL','records':findings,'run_directory':str(run_dir),'script_sha256':manifest['script_sha256'],'limits':'Bounded fixtures; no concurrency/thread-safety, physical, exhaustive-road, or universal performance claim.'}
    (run_dir/'RESULTS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');(HERE/'LATEST_RESULTS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'checks':len(findings),'failures':[i['name'] for i in findings if i['status']=='FAIL'],'run_directory':str(run_dir)},indent=2));raise SystemExit(result['status']!='PASS')

if __name__=='__main__':main()
