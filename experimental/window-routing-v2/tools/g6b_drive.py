"""G6b driver (G6B_RUN.md "Order, tracking and the stop rule"). One launch = one tracked task; resumable.
  WFG_F34=... WFG_WFT=... python -B g6b_drive.py --out RUN_DIR --frozen FROZEN_KIT --v2-kit V2_KIT [--workers 3]
For each cache in G6B_JOBS.json order: P1, P2, V (tools/g6_run.py --only <cache jobs>), then R for V2 time-capped
UNRESOLVED where PARENT resolved in a run, then tools/g6b_classify.py. A cache is done when RUN_DIR/<cache>/DONE exists.
If classification exits 3 (a failure or stop class), RUN_DIR/STOPPED is written and the driver exits 3. A later launch
refuses to continue while STOPPED exists (the author reports to the orchestrator first).
"""
import argparse, datetime, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2DIR = HERE.parent
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
TIME_CAPPED = {'LATE_RESULT', 'DEADLINE_STOP', 'SEARCH_TIMEOUT'}


def log(out, msg):
    with (out / 'RUNLOG.txt').open('a') as f:
        f.write('%s %s\n' % (now(), msg))
    print(now(), msg, flush=True)


def rows(p):
    return {(r['cache'], r['job_id']): r for r in map(json.loads, filter(str.strip, p.read_text().splitlines()))} if p.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True); ap.add_argument('--frozen', type=Path, required=True)
    ap.add_argument('--v2-kit', type=Path, required=True); ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if (a.out / 'STOPPED').exists():
        log(a.out, 'launch refused: STOPPED present (%s)' % (a.out / 'STOPPED').read_text().strip()); sys.exit(3)
    J = json.loads((V2DIR / 'G6B_JOBS.json').read_text())
    log(a.out, 'launch')
    for c in J['caches']:
        cd = a.out / Path(c).with_suffix('').as_posix().replace('/', '__')
        if (cd / 'DONE').exists():
            continue
        cd.mkdir(parents=True, exist_ok=True)
        jobs = [j for j in J['jobs'] if j['cache'] == c]
        (cd / 'JOBS.json').write_text(json.dumps({'jobs': jobs}) + '\n')
        for ph, kit, label in (('P1', a.frozen, 'PARENT'), ('P2', a.frozen, 'PARENT'), ('V', a.v2_kit, 'V2')):
            done = rows(cd / ph / 'ROWS.jsonl')
            if len(done) >= len(jobs):
                continue
            log(a.out, '%s %s start (%d/%d done)' % (c, ph, len(done), len(jobs)))
            subprocess.run([sys.executable, '-B', str(HERE / 'g6_run.py'), '--phase', ph, '--kit', str(kit), '--label', label,
                            '--out', str(cd), '--workers', str(a.workers), '--only', str(cd / 'JOBS.json')], check=True)
            log(a.out, '%s %s complete' % (c, ph))
        P1, P2, V = (rows(cd / ph / 'ROWS.jsonl') for ph in ('P1', 'P2', 'V'))
        rjobs = [j for j in jobs if (lambda i: V[i]['outcome'].get('verdict') == 'unresolved'
                 and V[i]['outcome'].get('reason_code') == 'TIMEOUT' and V[i]['outcome'].get('raw_reason') in TIME_CAPPED
                 and any(P[i]['outcome'].get('verdict') != 'unresolved' for P in (P1, P2)))((j['cache'], j['job_id']))]
        if rjobs and len(rows(cd / 'R' / 'ROWS.jsonl')) < len(rjobs):
            (cd / 'R_JOBS.json').write_text(json.dumps({'jobs': rjobs}) + '\n')
            log(a.out, '%s R start (%d jobs)' % (c, len(rjobs)))
            subprocess.run([sys.executable, '-B', str(HERE / 'g6_run.py'), '--phase', 'R', '--kit', str(a.v2_kit), '--label', 'V2',
                            '--out', str(cd), '--workers', str(a.workers), '--only', str(cd / 'R_JOBS.json')], check=True)
        p = subprocess.run([sys.executable, '-B', str(HERE / 'g6b_classify.py'), str(cd), '--cache', c, '--frozen', str(a.frozen),
                            '--v2-kit', str(a.v2_kit)], capture_output=True, text=True)
        (cd / 'CLASSIFY.log').write_text(p.stdout + p.stderr)
        if p.returncode == 3:
            (a.out / 'STOPPED').write_text('%s: failure or stop class in %s (see CLASSIFY.json)\n' % (now(), c))
            log(a.out, '%s classified: STOP RULE (%s)' % (c, p.stdout.strip()[-400:])); sys.exit(3)
        if p.returncode != 0:
            log(a.out, '%s classification error rc=%d' % (c, p.returncode)); sys.exit(p.returncode)
        (cd / 'DONE').write_text(now() + '\n')
        log(a.out, '%s classified: %s' % (c, p.stdout.strip()[-400:]))
    log(a.out, 'all caches done')


if __name__ == '__main__':
    main()
