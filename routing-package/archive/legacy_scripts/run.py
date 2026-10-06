#!/usr/bin/env python3
"""Fresh-process checks and JSON routing CLI. Standard library core only."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parent

def check():
    start=time.perf_counter();freeze=json.loads((ROOT/'evidence/CANDIDATE_FREEZE.json').read_text())
    for name,digest in freeze['hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('candidate hash mismatch '+name)
    subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests'],cwd=ROOT,check=True)
    from routing.replay import replay
    fixture=json.loads((ROOT/'evidence/CONTINUITY_REPLAY_FIXTURE.json').read_text());a=replay(fixture);b=replay(fixture)
    if a!=b:raise RuntimeError('replay not deterministic')
    pa=replay(fixture,prepare=True);pb=replay(fixture,prepare=True)
    if pa!=pb or a!=pa:raise RuntimeError('prepared replay disagreement')
    road=ROOT/'evidence/ROAD_INTEGRATION_SMOKE.json'
    if road.exists():
        from routing.independent import check_route
        x=json.loads((ROOT/'fixtures/nangok_full_graph_fixture.json').read_text());r=json.loads(road.read_text());v=check_route(x['graph'],x['hazard'],x['request'],r['legs'],r['destination'])
        if not v['ok']:raise RuntimeError('packaged full-road witness refused')
    return {'status':'PASS','candidate_hashes':len(freeze['hashes']),'deterministic_replay':True,'full_road_witness_checked':road.exists(),'elapsed_s':time.perf_counter()-start,'forecast_integration':'NOT_AVAILABLE','physical_safety_claim':False}

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('command',choices=['check','solve','replay']);a.add_argument('--input',type=Path);a.add_argument('--prepare-graph',action='store_true',help='opt-in owned graph admission for this process; initialization is charged');q=a.parse_args()
    if q.command=='check':r=check()
    else:
        lifecycle_start=time.perf_counter()
        x=json.loads((q.input or ROOT/'fixtures/example.json').read_text())
        if q.command=='replay':
            from routing.replay import replay
            r=replay(x,prepare=q.prepare_graph)
        else:
            from routing.service import plan_with_return
            from routing import prepare_graph
            graph=prepare_graph(x['graph']) if q.prepare_graph else x['graph']
            r=plan_with_return(graph,x['hazard'],x['request'],x.get('history'),x.get('return_endpoint'),return_budget_s=x.get('return_budget_s',5))
        if q.prepare_graph:
            if q.command=='solve':r['end_to_end_s']=time.perf_counter()-lifecycle_start
    print(json.dumps(r,indent=2,sort_keys=True,allow_nan=False))
if __name__=='__main__':main()
