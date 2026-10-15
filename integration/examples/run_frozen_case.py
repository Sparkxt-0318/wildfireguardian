"""One unscored Uljin route replay using the published, already constructed hazards.
No forecast inference or external environmental rasters are needed.
"""
import argparse,json,sys
from pathlib import Path
from wfg_latest import api

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--inputs',type=Path,default=Path(__file__).resolve().parents[2]/'data/routing')
 ap.add_argument('--kit',type=Path,default=Path(__file__).resolve().parents[1]/'kit')
 ap.add_argument('--out',type=Path,required=True,help='Fresh directory; existing outputs are never overwritten')
 ap.add_argument('--arm',choices=['RDA_CAND','RDA_BASE'],default='RDA_CAND')
 ap.add_argument('--python',default=sys.executable)
 a=ap.parse_args();a.out=a.out.resolve()
 if a.out.exists():raise SystemExit('Output exists: '+str(a.out))
 a.out.parent.mkdir(parents=True,exist_ok=True)
 inputs=a.inputs.resolve();cut='20220304T030000Z';region='uljin_2022'
 graph=inputs/'graphs'/region/'graph.json'
 packet=inputs/'latest_inputs_try02/packets'/region/cut
 request=inputs/'latest_inputs_try02/requests'/region/(cut+'_FX1.json')
 for p in [graph,packet/'HAZARD.json',request,a.kit/'CANDIDATE_MANIFEST.json']:
  if not p.is_file():raise SystemExit('Missing '+str(p)+'; first run tools/fetch_routing_inputs.py')
 result=api.route_and_check(kit_root=a.kit,packet_dir=packet,graph=graph,request=request,out_dir=a.out,arm=a.arm,python=a.python)
 (a.out/'API_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
 if not result.get('on_time') or result.get('cleanup_state')!='CLEAN':raise SystemExit(2)
 # Publication status is authoritative; a raw solver witness is not sufficient.
 if not result.get('successful_journey'):raise SystemExit(3)
if __name__=='__main__':main()
