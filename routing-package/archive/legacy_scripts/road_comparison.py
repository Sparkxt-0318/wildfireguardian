"""Read-only, cold exposed-road regression; run under the shared exclusive lane.

The original 60 s solver-stage/3072 MiB/95 s watchdog protocol is retained.
Independent lane-F checking is timed separately and included in end-to-end time.
No candidate outcomes select cases or alter caps. No old delivery is written.
"""
from pathlib import Path
import sys, os, json, time, subprocess, hashlib, resource
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
BASE = Path('/Users/jp/Documents/Codex/2026-09-24/fu/outputs')
OUT = ROOT/'evidence/road_comparison'
ARMS = ['established', 'astar', 'dijkstra', 'suffix_astar']

def frozen():
    rec=json.loads((ROOT/'evidence/ROAD_COMPARISON_FREEZE.json').read_text())
    for path,want in rec['hashes'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=want:
            raise RuntimeError('SOURCE_OR_INPUT_CHANGED: '+path)
    return rec

def imports():
    for path in [BASE/'korean_routing_comparison_20261002_v1/bench',
                 BASE/'korean_routing_comparison_20261002_v1/lane_F_evaluator',
                 BASE/'routing_controlled_validation_20261003_v1',
                 BASE/'routing_completion_20261003_v1']:
        sys.path.insert(0,str(path))
    import active_scenarios as AS
    return AS

def prune(cp, dests):
    """The SAME selected static legal-suffix pruning, applied to compiled turns.

    Every edge-state on a legal suffix to a destination is retained. Waiting
    leaves that state unchanged. No time or resource labels are merged.
    """
    reverse=[[] for _ in range(cp.pb.n_edges)]
    for e,ss in enumerate(cp.succ):
        for f in ss:reverse[int(f)].append(e)
    goals=set(int(x) for x in dests)
    keep={e for e,v in enumerate(cp.pb.ev) if int(v) in goals}
    todo=list(keep)
    while todo:
        for e in reverse[todo.pop()]:
            if e not in keep:keep.add(e);todo.append(e)
    removed=cp.pb.n_edges-len(keep)
    cp.succ=[[int(f) for f in ss if int(f) in keep] for ss in cp.succ]
    cp.out_by_node=[[int(f) for f in ss if int(f) in keep] for ss in cp.out_by_node]
    return {'removed_edge_states':removed,'retained_edge_states':len(keep)}

def child(qid, arm):
    frozen();begin=time.perf_counter();AS=imports();B=AS.B
    snapshots=[];pruning=[];seen=set()
    if arm!='established':
        from engine import solve
        from profile_exposure import member_tables
        def factory(g,occ,mems,delta,K,**kw):
            et=[];wt=[]
            for m in mems:
                e,w=member_tables(g,occ,m,delta,K);et.append(e);wt.append(w)
            return et,wt,{'n_pw_events_total':0}
        AS.member_exposure_tables=factory
        def engine(cp,et,wt,origin,dests,budget,**kw):
            started=time.perf_counter()
            if arm=='suffix_astar' and id(cp) not in seen:
                pruning.append(prune(cp,dests));seen.add(id(cp))
            remaining=kw['time_limit_s']-(time.perf_counter()-started)
            r=solve(cp,et,wt,origin,dests,budget,use_heuristic=arm!='dijkstra',
                    time_limit_s=max(0.,remaining),rss_limit_mb=kw['rss_limit_mb'],
                    frontier_width=kw.get('frontier_width',4096),max_pops=kw.get('max_pops',5000000))
            snapshots.append({'status':r['status'],'pops':r['pops'],'metrics':r['metrics'],
                              'edge_tables':[t.stats() for t in et],'wait_tables':[t.stats() for t in wt]})
            return r
        class Scalar:
            def __init__(self,cp):self.cp=cp
            def solve(self,origin,dests,**kw):
                cp=self.cp;r=engine(cp,[cp.edge_pw],[cp.wait_pw],origin,dests,cp.pb.E_max,**kw)
                if r['status']=='ROUTE':r.update(t_arr=r['t_arr_tick']*cp.pb.delta,dest_node=int(cp.pb.ev[r['dest_state']]))
                elif r['status']=='REFUSED':r['refusal_reason']='NO_ADMISSIBLE_LATTICE_ROUTE_WITHIN_HORIZON'
                else:r.update(status='TIMEOUT',refusal_reason=r.get('cap'))
                return r
        AS.TESolver=Scalar;AS.r3_bounded_exact=engine
    g,s,occ=B.window('W-MAIN');params,_=B.hz_params()
    q=next(q for q in B.queries('W-MAIN') if q['query_id']==qid)
    members=[B.planner_member(q['instance_id'],'plan',j) for j in range(B.n_plan_members(q['instance_id']))]
    active=AS.ActiveScenarioArm(g,occ,members,params);prep=time.perf_counter()-begin
    r=active.solve(g.node_index[q['origin_node']],[g.node_index[d] for d in q['dest_nodes']],
                   budget_s=60.,prep_charged_s=prep,rss_mb=3072.)
    r.update(query_id=qid,instance_id=q['instance_id'],arm=arm,cold_prep_s=prep,
             solver_profiles=snapshots,pruning=pruning,measured_stage_s=time.perf_counter()-begin,
             peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2),
             mode='cold',repetition=0,event_proxy_limit=None,independent_global_certificate=False)
    (OUT/(qid+'_'+arm+'.json')).write_text(json.dumps(r,indent=2));print(qid,arm,r['status'],flush=True)

def check(rows):
    AS=imports();B=AS.B
    from evalf.graph import RoadGraph
    from evalf.hazard import Scenario
    from evalf.core import prepare_route, score_prepared
    fg=RoadGraph.load_nangok(window=tuple(B.RB.windows_meta()['windows']['W-MAIN']['square']))
    _,s,_=B.window('W-MAIN');params,_=B.hz_params();qmap={q['query_id']:q for q in B.queries('W-MAIN')}
    checks=[]
    for r in rows:
        if r['status']!='ROUTE_JOINT_OPTIMAL':continue
        started=time.perf_counter();q=qmap[r['query_id']]
        prepared=prepare_route(dict(r,status='ROUTE'),fg,{'origin':q['origin_node'],'destinations':q['dest_nodes']},(s.x0,s.y0,s.h))
        for j in range(B.n_plan_members(r['instance_id'])):
            m=B.planner_member(r['instance_id'],'plan',j)
            sc=Scenario(s.x0,s.y0,s.h,m.A.T.copy(),m.tau,post_burn=m.post_burn,
                        **{k:params[k] for k in ['Q','r0','R','q_max','E_max','q_dest','T_dwell','H']},outside='UNREACHED')
            v=score_prepared(prepared,sc)
            checks.append({'query_id':r['query_id'],'arm':r['arm'],'member':j,'admissible':v['admissible'],
                           'codes':v['codes'],'dose':v['E_route'],'arrival':v['t_arr']})
        r['independent_check_s']=time.perf_counter()-started
        r['independent_route_passed']=all(x['admissible'] for x in checks if x['query_id']==r['query_id'] and x['arm']==r['arm'])
        r['end_to_end_s']=r['external_process_s']+r['independent_check_s']
    return checks

def run():
    rec=frozen();OUT.mkdir(parents=True,exist_ok=True);rows=[]
    for i,qid in enumerate(rec['query_ids']):
        for arm in ARMS[i%4:]+ARMS[:i%4]:
            started=time.perf_counter()
            try:
                p=subprocess.run([sys.executable,__file__,'--child',qid,arm],capture_output=True,text=True,
                                 timeout=95,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1'))
                path=OUT/(qid+'_'+arm+'.json')
                if p.returncode or not path.exists():r={'query_id':qid,'arm':arm,'status':'ERROR','stderr':p.stderr[-3000:]}
                else:r=json.loads(path.read_text())
            except subprocess.TimeoutExpired:
                r={'query_id':qid,'arm':arm,'status':'TIMEOUT','reason':'EXTERNAL_95S_WATCHDOG','legs':[]}
            r['external_process_s']=time.perf_counter()-started;r['end_to_end_s']=r['external_process_s']
            rows.append(r);(OUT/'rows.json').write_text(json.dumps(rows,indent=2))
            print(qid,arm,r['status'],round(r['external_process_s'],3),flush=True)
    checks=check(rows)
    (OUT/'checks.json').write_text(json.dumps(checks,indent=2));(OUT/'rows.json').write_text(json.dumps(rows,indent=2))
    (OUT/'summary.json').write_text(json.dumps({'rows':len(rows),'independent_route_member_checks':len(checks),
        'independent_failures':[x for x in checks if not x['admissible']],
        'global_optima_or_refusals_independently_recertified':False,'warm_and_repeats':'NOT_RUN_ON_HARD_ROADS; TINY_MATCHED_STUDY_HAS_BOTH'},indent=2))

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':child(*sys.argv[2:4])
    else:run()
