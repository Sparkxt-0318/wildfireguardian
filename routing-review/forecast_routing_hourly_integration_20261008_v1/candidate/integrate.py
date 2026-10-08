"""Forecast integration CLI; the preserved routing package remains runnable."""
import argparse,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'routing-package'))
import numpy as np
from forecast_bridge import convert,inspect_mentor_export,IntegrationError


def read(path):
    return json.loads(pathlib.Path(path).read_text())


def emit(value):
    print(json.dumps(value,indent=2,allow_nan=False))


def load_bundle(path):
    path=pathlib.Path(path).resolve(); bundle=read(path); members=[]
    for member in bundle['members']:
        relative=pathlib.PurePath(member['arrays_file'])
        target=(path.parent/relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not target.is_relative_to(path.parent):
            raise IntegrationError('ARRAY_PATH','Member arrays must remain inside the bundle directory')
        with np.load(target,allow_pickle=False) as z:
            members.append({'id':member['id'],**{k:z[k].copy() for k in ('flux_w_m2','flame_contact','support')}})
    return bundle['metadata'],members


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('check',help='Verify preserved router and bridge regression gates')
    p=sub.add_parser('inspect',help='Inspect the mentor interval-mean export; no routing or imputation')
    p.add_argument('--summary',required=True);p.add_argument('--arrays',required=True)
    p=sub.add_parser('route',help='Admit an explicit physical native-interval bundle and route')
    p.add_argument('--graph',required=True);p.add_argument('--request',required=True);p.add_argument('--bundle',required=True)
    p.add_argument('--prepare-graph',action='store_true',help='Opt-in preparation, useful for repeated library work')
    args=parser.parse_args()
    if args.command=='check':
        subprocess.run([sys.executable,'-B',str(ROOT/'routing-package/run.py'),'check'],check=True)
        subprocess.run([sys.executable,'-B',str(ROOT/'test_forecast_bridge.py')],check=True)
        return 0
    if args.command=='inspect':
        with np.load(args.arrays,allow_pickle=False) as arrays:
            report=inspect_mentor_export(read(args.summary),{k:arrays[k] for k in arrays.files})
        emit(report);return 0 if report['ready_for_existing_router'] else 2
    from routing.core import solve
    from routing.prepared import prepare_graph
    from routing.independent import check_route
    try:
        graph=read(args.graph);graph=graph.get('graph',graph)
        request=read(args.request);request=request.get('request',request)
        metadata,members=load_bundle(args.bundle)
        hazard=convert(graph,metadata,members)
        result=solve(prepare_graph(graph) if args.prepare_graph else graph,hazard,request)
        if result.get('destination') is not None and result.get('status') in ('CHECKED_ROUTE','CONDITIONAL_OPTIMUM'):
            checked=check_route(graph,hazard,request,result['legs'],result['destination'])
            if not checked.get('ok'):
                emit({'status':'INTEGRATION_CHECK_FAILED','checker':checked});return 3
            result['integration_checker']=checked
        result['integration_evidence_class']=metadata['evidence_class']
        result['physical_safety_claim']=False
        emit(result)
        return 0 if result['status'] in ('CHECKED_ROUTE','CONDITIONAL_OPTIMUM','PROVEN_INFEASIBLE','DISCONNECTED') else 2
    except (IntegrationError,ValueError,KeyError,TypeError,OSError) as exc:
        emit({'status':'INVALID_NATIVE_FORECAST','code':getattr(exc,'code',type(exc).__name__),'reason':str(exc),
              'route_produced':False,'physical_safety_claim':False})
        return 2


if __name__=='__main__':raise SystemExit(main())
