"""Step 3 calibration (STEP3_ACCEPTANCE C + Iris 19:16): V2 calibration-kit jobs on the 1-hour panel, Z counting work
units under the parent 6 s wall cap. Runs REPS more repetitions (each job in its own interpreter via run_one_job.py)
into OUT/rN/, then (--summarise) reads every run folder given (g1_panel V2 folders and these) and writes the per-mission
Z unit counts, Z wall, stop reason, setup units, and the budget by the pre-stated rule.
  python -B z_calibrate.py --kit KIT --inputs DATA --out OUT --reps 2 [--start 2]
  python -B z_calibrate.py --summarise --folders DIR [DIR ...] --json OUT.json
"""
import argparse, json, math, statistics as st, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'research/harness-2026-11/F-3.4'))


def z_row(job):
    res = json.loads((job / 'RESULT.json').read_text())
    z = next((s for s in res.get('rda_stages') or [] if s.get('stage') == 'Z'), None)
    if z is None:
        return None
    w = z.get('z_work') or {}
    bk = w.get('by_kind') or {}
    return {'units': w.get('units'), 'setup_units': bk.get('setup_contact', 0) + bk.get('setup_wait', 0),
            'sweep_units': bk.get('sweep', 0), 'z_wall_s': z.get('elapsed_s'), 'status': z.get('status'),
            'reason': z.get('reason'), 'stopped_by_6s_cap': z.get('reason') in ('WALL_CLOCK', 'WALL_CLOCK_AFTER_CHECK')
            or w.get('stopped') == 'WALL_CLOCK'}


def summarise(folders, out):
    by = {}
    for root in folders:
        for job in sorted(Path(root).glob('*__*')):
            r = z_row(job)
            if r:
                by.setdefault(job.name, []).append(dict(r, folder=str(job)))
    rows = []
    for m, rs in sorted(by.items()):
        u = [r['units'] for r in rs]
        capped = [r for r in rs if r['stopped_by_6s_cap']]
        rows.append({'mission': m, 'runs': len(rs), 'units': u, 'median_units': st.median(u),
                     'spread_max_over_min': (max(u) / min(u)) if min(u) else None,
                     'still_running_at_6s': len(capped) > len(rs) / 2, 'median_z_wall_s': st.median(r['z_wall_s'] for r in rs),
                     'median_setup_units': st.median(r['setup_units'] for r in rs), 'status': sorted({r['status'] for r in rs}),
                     'reason': sorted({str(r['reason']) for r in rs})})
    hard = [r for r in rows if r['still_running_at_6s']]
    if len(hard) >= 5:
        raw = st.median(r['median_units'] for r in hard); how = 'median over %d missions still running at 6 s' % len(hard)
    else:
        raw = st.median(r['median_units'] / r['median_z_wall_s'] * 6 for r in rows); how = 'EXTRAPOLATED: median rate x 6 s over all %d missions (only %d still running at 6 s)' % (len(rows), len(hard))
    budget = 2 ** math.ceil(math.log2(raw))
    # Iris safeguard: every mission that completed within 6 s must complete within the budget; setup alone never cut
    need = max([r['median_units'] for r in rows if not r['still_running_at_6s']] + [0])
    setup_max = max(r['median_setup_units'] for r in rows)
    final = budget
    while final < need or final < setup_max:
        final *= 2
    out_d = {'rule': 'STEP3_ACCEPTANCE C + Iris 19:16', 'missions': rows, 'raw_median_units': raw, 'how': how,
             'budget_power_of_two': budget, 'largest_completing_mission_units': need, 'largest_setup_units': setup_max,
             'final_budget': final, 'raised_by_safeguard': final != budget,
             'spread_over_1_25': [r['mission'] for r in rows if r['spread_max_over_min'] and r['spread_max_over_min'] > 1.25]}
    Path(out).write_text(json.dumps(out_d, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out_d.items() if k != 'missions'}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', type=Path); ap.add_argument('--inputs', type=Path); ap.add_argument('--out', type=Path)
    ap.add_argument('--reps', type=int, default=2); ap.add_argument('--start', type=int, default=2)
    ap.add_argument('--summarise', action='store_true'); ap.add_argument('--folders', nargs='*'); ap.add_argument('--json')
    a = ap.parse_args()
    if a.summarise:
        return summarise(a.folders, a.json)
    import run_profile as RP
    todo = RP.missions(a.kit)
    for rep in range(a.start, a.start + a.reps):
        order = todo if rep % 2 else list(reversed(todo))
        for region, case in order:
            d = a.out / ('r%d' % rep) / ('%s__%s' % (region, case))
            if (d / 'RESULT.json').exists():
                continue
            d.parent.mkdir(parents=True, exist_ok=True)
            p = subprocess.run([sys.executable, '-B', str(HERE / 'run_one_job.py'), str(a.kit), str(a.inputs), region, case, str(d), '81'],
                               capture_output=True, text=True)
            if p.returncode != 0:
                raise SystemExit(p.stderr[-2000:])
            print('r%d %s/%s' % (rep, region, case), json.dumps(z_row(d)), flush=True)


if __name__ == '__main__':
    main()
