"""Host-speed figure per run (Iris 23:43 UTC, Step 3 known limit): Z sweep units per second of Z sweep wall, from each
v2 RESULT's own z_work record (sweep units / (Z wall - first sweep tick time)). Runs with fewer than 1e6 sweep units
are listed but excluded from the summary (too short to time). Prints a summary; --json writes per-run figures.
  python -B host_speed.py RUN_DIR [RUN_DIR ...] [--json OUT]"""
import argparse, json, statistics as st
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('runs', nargs='+'); ap.add_argument('--json')
    a = ap.parse_args()
    rows = []
    for root in a.runs:
        for p in sorted(Path(root).rglob('RESULT.json')):
            r = json.loads(p.read_text())
            z = next((s for s in r.get('rda_stages') or [] if s.get('stage') == 'Z' and s.get('z_work')), None)
            if not z:
                continue
            w = z['z_work']; sweep = (w.get('group_units') or {}).get('sweep', 0); t0 = (w.get('first_tick_s') or {}).get('sweep')
            sw = (z.get('elapsed_s') or 0) - t0 if t0 is not None else None
            rows.append({'run': str(p.parent), 'sweep_units': sweep, 'sweep_wall_s': sw,
                         'units_per_s': (sweep / sw) if sw and sweep >= 1e6 else None})
    rates = [x['units_per_s'] for x in rows if x['units_per_s']]
    summ = {'runs': len(rows), 'timed_runs': len(rates), 'median_units_per_s': st.median(rates) if rates else None,
            'min_units_per_s': min(rates) if rates else None, 'max_units_per_s': max(rates) if rates else None}
    print(json.dumps(summ))
    if a.json:
        Path(a.json).write_text(json.dumps({'summary': summ, 'rows': rows}, indent=1) + '\n')


if __name__ == '__main__':
    main()
