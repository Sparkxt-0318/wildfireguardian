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
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists():
        raise SystemExit('Output exists: %s' % out)
    out.mkdir(parents=True)
    kits = {'FROZEN': a.frozen.resolve(), 'V2': a.v2.resolve()}
    todo = RP.missions(kits['FROZEN'])
    assert todo == RP.missions(kits['V2']), 'mission lists differ'
    if a.only:
        todo = [m for m in todo if '%s__%s' % m in set(a.only.split(','))]
    for rep in range(1, a.reps + 1):
        order = todo if rep % 2 else list(reversed(todo))
        for i, (region, case_id) in enumerate(order):
            labels = ['FROZEN', 'V2'] if (rep + i) % 2 else ['V2', 'FROZEN']
            for lab in labels:
                d = out / lab / ('r%d' % rep) / ('%s__%s' % (region, case_id)); d.parent.mkdir(parents=True, exist_ok=True)
                # Mira R14 N1: one fresh interpreter per job, so the controller and decision modules are the job's own kit's
                import subprocess
                pr = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('run_one_job.py')), str(kits[lab]),
                                     str(a.inputs.resolve()), region, case_id, str(d), str(a.budget)], capture_output=True, text=True)
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
