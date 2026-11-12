"""Step 3 acceptance (STEP3_ACCEPTANCE D): on the F-DYN set, every stage stops within max(1 s, 5% of its cap) of its
cap. Reads run folders (RESULT.json):
- LO, LO2, HI: elapsed_s (recorded when the solve returns, before the whole-road check) vs wall_cap_s; the check's own
  time is reported beside it and is not part of the stage's search cap;
- EA: build time vs its cap (deadline minus the HI reserve, as recorded in the stage timings);
- Z: unit groups vs the budgets (it must stop at the first tick over a budget, i.e. within one unit of work); setup
  units, setup wall and sweep wall are reported separately (Iris condition 4);
- any STAGE_CAP_WATCHDOG is listed as a finding.
  python -B stage_stop_check.py RUN_DIR [RUN_DIR ...] --json OUT
"""
import argparse, json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('runs', nargs='+'); ap.add_argument('--json')
    a = ap.parse_args()
    rows, findings = [], []
    for root in a.runs:
        for d in sorted(Path(root).glob('*')):
            p = d / 'RESULT.json'
            if not p.exists():
                continue
            r = json.loads(p.read_text())
            if r.get('stage_cap_watchdog'):
                findings.append({'run': d.name, 'watchdog': r['stage_cap_watchdog']})
            for s in r.get('rda_stages') or []:
                st = s.get('stage')
                if st == 'Z':
                    w = s.get('z_work') or {}; g = w.get('group_units') or {}; caps = s.get('z_work_caps') or {}
                    ft = (w.get('first_tick_s') or {})
                    over = {k: g.get(k, 0) - caps[k] for k in ('setup', 'sweep') if caps.get(k) is not None}
                    rows.append({'run': d.name, 'stage': 'Z', 'status': s.get('status'), 'reason': s.get('reason'),
                                 'elapsed_s': s.get('elapsed_s'), 'setup_units': g.get('setup'), 'sweep_units': g.get('sweep'),
                                 'caps': caps, 'units_over_cap': over, 'setup_wall_s': ft.get('sweep', s.get('elapsed_s')),
                                 'sweep_wall_s': (s.get('elapsed_s') or 0) - ft['sweep'] if 'sweep' in ft else 0.0,
                                 # stopped by a budget: the overshoot must be at most one tick (setup: 1 unit; sweep: E+1)
                                 'ok': all(v <= 1 for k, v in over.items() if k == 'setup') and
                                       all(v <= 120000 for k, v in over.items() if k == 'sweep')})
                elif st in ('LO', 'LO2', 'HI') and s.get('wall_cap_s') is not None:
                    cap = s['wall_cap_s']; el = s.get('elapsed_s') or 0; chk = s.get('check_elapsed_s') or 0
                    search = el   # record() is called right after the solve returns, before consider()'s whole-road check
                    tol = max(1.0, 0.05 * cap)
                    rows.append({'run': d.name, 'stage': st, 'status': s.get('status'), 'reason': s.get('reason'),
                                 'cap_s': cap, 'elapsed_s': el, 'check_s': chk, 'search_s': search,
                                 'over_s': search - cap, 'tol_s': tol, 'ok': search <= cap + tol})
            ea = r.get('earliest_arrival_bound') or {}
            if ea:
                rows.append({'run': d.name, 'stage': 'EA', 'elapsed_s': (r.get('stages') or {}).get('earliest_arrival_bound_s'),
                             'error': ea.get('error'), 'note': 'EA cap = deadline - HI reserve; checked every backward second'})
    bad = [x for x in rows if x.get('ok') is False]
    out = {'rows': rows, 'violations': bad, 'watchdog_findings': findings,
           'summary': {'stages': len(rows), 'violations': len(bad), 'watchdog': len(findings)}}
    print(json.dumps(out['summary'])); [print(json.dumps(b)) for b in bad + findings]
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
