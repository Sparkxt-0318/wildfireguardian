"""One fresh forecast-to-route chain with explicit external environment inputs."""
import argparse,json,sys
from pathlib import Path
from wfg_latest import api

def main():
 root=Path(__file__).resolve().parents[2]
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--data-root',type=Path,required=True,help='Aligned environmental tree with events.json')
 ap.add_argument('--inputs',type=Path,default=root/'data/routing')
 ap.add_argument('--forecast-root',type=Path,default=root/'forecast')
 ap.add_argument('--kit',type=Path,default=root/'integration/kit')
 ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--python',default=sys.executable)
 a=ap.parse_args();out=a.out.resolve()
 if out.exists():raise SystemExit('Output exists: '+str(out))
 if not (a.data_root/'events.json').is_file():raise SystemExit('Environmental data root must contain events.json')
 ck=a.forecast_root/'runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt'
 graph=a.inputs/'graphs/uljin_2022/graph.json';template=a.inputs/'latest_inputs_try02/requests/uljin_2022/20220304T030000Z_FX1.json'
 cut='2022-03-04T03:00:00Z';out.mkdir(parents=True)
 api.export_forecast(source_root=a.forecast_root.resolve(),data_root=a.data_root.resolve(),checkpoint=ck.resolve(),event='KFS_02',cutoff=cut,out_dir=out/'export',python=a.python)
 api.build_packet(graph=graph.resolve(),export_dir=out/'export',event='KFS_02',cutoff=cut,region='uljin_2022',out_dir=out/'packet',python=a.python)
 api.rekey_request(template.resolve(),out/'packet',cut,out_path=out/'request.json')
 res=api.route_and_check(kit_root=a.kit.resolve(),packet_dir=out/'packet',graph=graph.resolve(),request=out/'request.json',out_dir=out/'route',arm='RDA_CAND',python=a.python)
 (out/'PIPELINE_RESULT.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(res,indent=2))
if __name__=='__main__':main()
