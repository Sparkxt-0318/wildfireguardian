"""PLAN.md G1/G5 run: the frozen 1-hour request-window panel (20 missions), frozen kit and v2 kit INTERLEAVED per
mission on the same host, uninstrumented (--mode plain), 81 s speed-equivalent budget, N reps (order of missions and
of the two kits alternates by rep). Uses research/harness-2026-11/F-3.4/run_profile.run_one (kit controller: GNU time,
sampled family RSS, outer deadline).
  python -B g1_panel.py --frozen FROZEN_KIT --v2 V2_KIT --out OUT [--reps 2] [--budget 81]
"""
import argparse, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'research/harness-2026-11/F-3.4'))
import run_profile as RP  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frozen', type=Path, required=True); ap.add_argument('--v2', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True); ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--budget', type=float, default=81.0); ap.add_argument('--inputs', type=Path, default=REPO / 'data/routing')
    ap.add_argument('--only', default=None)
    ap.add_argument('--noiso-arm', action='store_true', help='Step 2 amendment F: add the labelled V2_NOISO baseline comparison arm (same V2 kit, v2_check_isolation false)')
    ap.add_argument('--resume', action='store_true', help='continue an interrupted panel (Elena: checkpoint per job, '
                    'log restarts; a restarted panel is excluded from timing claims)')
    a = ap.parse_args()
    out = a.out.resolve()
    done = set()
    if out.exists() and not a.resume:
        raise SystemExit('Output exists: %s' % out)
    if a.resume:
        import time as _t
        rows_p = out / 'ROWS.jsonl'
        for line in (rows_p.read_text().splitlines() if rows_p.exists() else []):
            r = json.loads(line); done.add((r['rep'], r['kit_label'], r['region'], r['case_id']))
        aborted = []
        for d in sorted(out.glob('*/r*/*')):
            lab, rep, rc = d.parts[-3], int(d.parts[-2][1:]), d.parts[-1]
            region, case_id = rc.split('__', 1)
            if (rep, lab, region, case_id) not in done:
                dest = out / 'ABORTED' / ('%s_%s_%s_%d' % (lab, d.parts[-2], rc, int(_t.time())))
                dest.parent.mkdir(parents=True, exist_ok=True); d.rename(dest); aborted.append(str(dest))
        with (out / 'RESTARTS.jsonl').open('a') as f:
            f.write(json.dumps({'restart_utc': _t.strftime('%Y-%m-%dT%H:%M:%SZ', _t.gmtime()), 'rows_kept': len(done),
                                'aborted_job_folders_moved': aborted}) + '\n')
    out.mkdir(parents=True, exist_ok=True)
    kits = {'FROZEN': a.frozen.resolve(), 'V2': a.v2.resolve()}
    if a.noiso_arm:
        kits['V2_NOISO'] = a.v2.resolve()
    todo = RP.missions(kits['FROZEN'])
    assert todo == RP.missions(kits['V2']), 'mission lists differ'
    if a.only:
        todo = [m for m in todo if '%s__%s' % m in set(a.only.split(','))]
    for rep in range(1, a.reps + 1):
        order = todo if rep % 2 else list(reversed(todo))
        for i, (region, case_id) in enumerate(order):
            arms = list(kits)                       # rotate the arm order by mission and rep (2 or 3 arms)
            k = (rep + i) % len(arms)
            labels = arms[k:] + arms[:k]
            for lab in labels:
                if (rep, lab, region, case_id) in done:
                    continue
                d = out / lab / ('r%d' % rep) / ('%s__%s' % (region, case_id)); d.parent.mkdir(parents=True, exist_ok=True)
                # Mira R14 N1: one fresh interpreter per job, so the controller and decision modules are the job's own kit's
                import subprocess
                pr = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('run_one_job.py')), str(kits[lab]),
                                     str(a.inputs.resolve()), region, case_id, str(d), str(a.budget)] + (['V2_NOISO'] if lab == 'V2_NOISO' else []), capture_output=True, text=True)
                if pr.returncode != 0:
                    raise SystemExit(pr.stderr[-3000:])
                row = json.loads(pr.stdout.strip().splitlines()[-1])
                row.update(rep=rep, kit_label=lab, kit_path=str(kits[lab]))
                with (out / 'ROWS.jsonl').open('a') as f:
                    f.write(json.dumps(row, sort_keys=True, default=str) + '\n')
                print('r%d %-6s %-40s %-36s arr=%s wall=%.1f peak=%.0f' % (rep, lab, region + '/' + case_id, row['authoritative_status'],
                      row['arrival_s'], row['complete_wall_s'] or -1, row['family_peak_rss_mib']), flush=True)


if __name__ == '__main__':
    main()
    # own-module decisions per kit (see redecide.py: run_profile caches the first kit's decision module by name)
    import subprocess
    subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('redecide.py')), str(Path(sys.argv[sys.argv.index('--out') + 1]).resolve())], check=True)
