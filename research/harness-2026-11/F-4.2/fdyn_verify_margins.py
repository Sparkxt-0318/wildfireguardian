"""Verify F-DYN margin witness routes (fdyn_clearance.py output) two ways, as verify_witnesses.py does on the panel:
1. the unchanged frozen whole-road checker (fixed_route_check.py, fresh interpreter): CERTIFIED_ADMISSIBLE required;
2. exact rational clearance > r_lo (verify_witnesses.exact_clearance_exceeds).
Margin routes are labelled KIT or TESTKIT exactly as their source route; never pooled.
  python fdyn_verify_margins.py --kit FROZEN_KIT --runs KIT=RUN TESTKIT=RUN --margins DIR/margin_routes --out OUT.jsonl
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clearance as C  # noqa: E402
import fdyn_clearance as FC  # noqa: E402
from verify_witnesses import exact_clearance_exceeds  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', type=Path, required=True); ap.add_argument('--runs', nargs='+', required=True)
    ap.add_argument('--margins', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    runs = dict(s.split('=', 1) for s in a.runs)
    for mf in sorted(a.margins.glob('*.json')):
        w = json.loads(mf.read_text()); d = Path(runs[w['label']]) / 'runs' / w['tag']
        job = json.loads((d / 'JOB.json').read_text())
        tmp, region, case, pk = FC.stage(job)
        I = C.Instance(*C.load(region, case, inputs=tmp, packet=pk))
        ok, dmin, pairs = exact_clearance_exceeds(I, w, w['r_lo_m'])
        p = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'fixed_route_check.py'), '--kit', str(a.kit), '--packet', str(pk),
                            '--graph', job['graph_path'], '--request', str(d / 'ORIGINAL_REQUEST.json'), '--route', str(mf)],
                           capture_output=True, text=True)
        chk = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {'status': 'ERROR', 'reason': p.stderr[-800:]}
        row = {'file': mf.name, 'label': w['label'], 'tag': w['tag'], 'deadline': w['deadline'], 'arrival': w['arrival'],
               'r_lo_m': w['r_lo_m'], 'exact_clearance_ok': ok, 'exact_min_distance_m': dmin, 'pairs': pairs,
               'checker_status': chk.get('status'), 'checker_reason': chk.get('reason'),
               'pass': ok and chk.get('status') == 'CERTIFIED_ADMISSIBLE'}
        with a.out.open('a') as f:
            f.write(json.dumps(row, default=str) + '\n')
        print('%-8s %-70s %-8s a=%5s r_lo=%7.1f exact=%s (%s) checker=%s' % (w['label'], w['tag'][-70:], w['deadline'], w['arrival'], w['r_lo_m'],
              ok, None if dmin is None else round(dmin, 1), chk.get('status')), flush=True)


if __name__ == '__main__':
    main()
