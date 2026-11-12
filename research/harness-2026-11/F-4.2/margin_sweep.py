"""Fixed-route admissibility of each published route under perturbed ignition timing (F-4.2 minimum experiment).

For every routed mission found in a run directory (worker RESULT.json with a destination), rebuild the packet under each
perturbation (perturbed_packet.py, own interpreter) and run the kit's whole-road checker on the unchanged route
(fixed_route_check.py, own interpreter). A delta grid (not a bisection) is used on purpose: it shows directly whether
admissibility is monotone in the perturbation on these inputs. Rows go to SWEEP.jsonl.

  python margin_sweep.py --kit KIT --runs RUN_DIR/r1 --out OUT [--advance 0,300,...] [--rate 1.5,2,4]
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return {'error': (p.stdout + p.stderr)[-800:]}
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', type=Path, required=True)
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--inputs', type=Path, default=REPO / 'data/routing')
    ap.add_argument('--advance', default='0,300,600,1200,1800,2400,3600')
    ap.add_argument('--rate', default='')
    ap.add_argument('--only', default=None)
    ap.add_argument('--wall', type=float, default=900)
    a = ap.parse_args()
    py = sys.executable; a.out.mkdir(parents=True, exist_ok=True)
    perts = [('advance', float(x)) for x in a.advance.split(',') if x] + [('rate', float(x)) for x in a.rate.split(',') if x]
    for d in sorted(a.runs.iterdir()):
        res = d / 'RESULT.json'
        if not res.exists():
            continue
        r = json.loads(res.read_text()).get('result') or {}
        if not r.get('destination'):
            continue
        region, case_id = d.name.split('__')
        if a.only and d.name not in a.only.split(','):
            continue
        cutoff = case_id.split('_')[0]
        graph = a.inputs / 'graphs' / region / 'graph.json'
        request = a.inputs / 'latest_inputs_try02/requests' / region / (case_id + '.json')
        for kind, val in perts:
            pk = a.out / 'packets' / ('%s__%s__%s%g' % (region, cutoff, kind, val))
            if not (pk / 'PERTURBATION.json').exists():
                b = run([py, '-I', '-B', str(HERE / 'perturbed_packet.py'), '--region', region, '--cutoff', cutoff,
                         '--' + kind, str(val), '--out', str(pk)])
                if 'error' in b:
                    print(json.dumps({'mission': d.name, kind: val, 'build_error': b['error']}), flush=True); continue
            c = run([py, '-I', '-B', str(HERE / 'fixed_route_check.py'), '--kit', str(a.kit), '--packet', str(pk), '--graph', str(graph),
                     '--request', str(request), '--route', str(res), '--wall', str(a.wall)])
            row = {'mission': d.name, 'kind': kind, 'value': val, 'arrival': r.get('arrival'), **c}
            row.pop('per_member', None)
            row['per_member_dose_upper_kj_m2'] = [m.get('dose_upper_kj_m2') for m in (c.get('per_member') or [])]
            row['per_member_peak_upper_kw_m2'] = [m.get('peak_upper_kw_m2') for m in (c.get('per_member') or [])]
            with (a.out / 'SWEEP.jsonl').open('a') as f:
                f.write(json.dumps(row, default=str) + '\n')
            print('%-46s %-7s %7g %-22s contact=%-14s rad=%-20s %.1fs' % (d.name, kind, val, row.get('status'), row.get('contact'),
                                                                    row.get('radiation'), row.get('elapsed_s') or -1), flush=True)


if __name__ == '__main__':
    main()
