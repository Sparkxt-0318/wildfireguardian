"""Coordinator-only entry: run through existing exclusive measurement wrapper."""
from pathlib import Path
import json,subprocess,sys,os
ROOT=Path(__file__).resolve().parent
x=json.loads((ROOT/'fixtures/nangok_full_graph_fixture.json').read_text())
from routing.core import solve
from routing.independent import check_route
r=solve(x['graph'],x['hazard'],x['request'])
(ROOT/'evidence/ROAD_INTEGRATION_SMOKE.json').write_text(json.dumps(r,indent=2))
print('full-road fixture smoke',r['status'],r.get('arrival'),flush=True)
if r['status'] not in ['CONDITIONAL_OPTIMUM','CHECKED_ROUTE']:raise SystemExit('road integration smoke did not produce checked route; retain raw failure')
subprocess.run([sys.executable,str(ROOT/'benchmark.py'),'--run','--out',str(ROOT/'evidence/benchmark')],check=True,cwd=ROOT)
