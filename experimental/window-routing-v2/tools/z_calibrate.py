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
    if z is None or not z.get('z_work'):
        return None
    w = z['z_work']; g = w.get('group_units') or {}; ft = w.get('first_tick_s') or {}
    zwall = z.get('elapsed_s')
    setup_wall = ft.get('sweep', zwall)            # Z start to the first sweep tick (whole setup)
    return {'setup_units': g.get('setup', 0), 'sweep_units': g.get('sweep', 0), 'z_wall_s': zwall, 'setup_wall_s': setup_wall,
            'sweep_wall_s': max(0.0, zwall - setup_wall), 'status': z.get('status'), 'reason': z.get('reason'),
            'z_capped_at_6s': z.get('reason') in ('WALL_CLOCK', 'WALL_CLOCK_AFTER_CHECK') or w.get('stopped') == 'WALL_CLOCK'}


def budget(rows, units_key, wall_key, label):
    rates = [r[units_key] / r[wall_key] * 6 for r in rows if r[wall_key] and r[wall_key] > 0 and r[units_key] > 0]
    long_ = [r for r in rows if r[wall_key] >= 6]
    if len(long_) >= 5:
        raw = st.median(r[units_key] for r in long_); how = 'median of %s over %d missions whose %s ran >= 6 s' % (units_key, len(long_), label)
    else:
        raw = st.median(rates); how = 'EXTRAPOLATED: median of %s / %s x 6 over %d missions (%d ran >= 6 s)' % (units_key, wall_key, len(rates), len(long_))
    return raw, 2 ** math.ceil(math.log2(raw)), how


def summarise(folders, out):
    by = {}
    for root in folders:
        for job in sorted(Path(root).glob('*__*')):
            r = z_row(job)
            if r:
                by.setdefault(job.name, []).append(dict(r, folder=str(job)))
    rows = []
    for m, rs in sorted(by.items()):
        med = lambda k: st.median(r[k] for r in rs)
        su = [r['setup_units'] for r in rs]; wu = [r['sweep_units'] for r in rs]
        rows.append({'mission': m, 'runs': len(rs), 'setup_units': med('setup_units'), 'sweep_units': med('sweep_units'),
                     'setup_wall_s': med('setup_wall_s'), 'sweep_wall_s': med('sweep_wall_s'), 'z_wall_s': med('z_wall_s'),
                     'setup_units_all': su, 'sweep_units_all': wu,
                     'spread_setup': max(su) / min(su) if min(su) else None, 'spread_sweep': max(wu) / min(wu) if min(wu) else None,
                     'spread_setup_wall': max(r['setup_wall_s'] for r in rs) / max(1e-9, min(r['setup_wall_s'] for r in rs)),
                     'spread_sweep_wall': max(r['sweep_wall_s'] for r in rs) / max(1e-9, min(r['sweep_wall_s'] for r in rs)),
                     'z_capped_at_6s': sum(r['z_capped_at_6s'] for r in rs) > len(rs) / 2,
                     'status': sorted({r['status'] for r in rs}), 'reason': sorted({str(r['reason']) for r in rs})})
    s_raw, s_b, s_how = budget(rows, 'setup_units', 'setup_wall_s', 'setup')
    w_raw, w_b, w_how = budget(rows, 'sweep_units', 'sweep_wall_s', 'sweep')
    s_need = max(r['setup_units'] for r in rows)                                          # every setup completes on 1 h
    w_need = max([r['sweep_units'] for r in rows if not r['z_capped_at_6s']] + [0])        # Z completing within 6 s
    s_f, w_f = s_b, w_b
    while s_f < s_need:
        s_f *= 2
    while w_f < w_need:
        w_f *= 2
    out_d = {'rule': 'STEP3_ACCEPTANCE correction to B2 (Iris 20:02)', 'missions': rows,
             'setup': {'raw': s_raw, 'power_of_two': s_b, 'how': s_how, 'largest_1h_setup_units': s_need, 'final': s_f,
                       'raised_by_safeguard': s_f != s_b, 'ratio_final_to_raw': s_f / s_raw},
             'sweep': {'raw': w_raw, 'power_of_two': w_b, 'how': w_how, 'largest_completing_sweep_units': w_need, 'final': w_f,
                       'raised_by_safeguard': w_f != w_b, 'ratio_final_to_raw': w_f / w_raw},
             'spread_over_1_25': [r['mission'] for r in rows if (r['spread_setup'] or 1) > 1.25 or (r['spread_sweep'] or 1) > 1.25]}
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
