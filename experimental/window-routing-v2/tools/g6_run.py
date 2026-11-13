"""G6a phase runner (G6A_RUN.md "Phases" and "Tracking and checkpointing"), checkpointed per job.
  WFG_F34=.../F-3.4 python -B g6_run.py --phase P1|P2|V|R --kit KIT --label PARENT|V2 --out RUN_DIR [--workers 3]
                                        [--only JOBS.json]
- Jobs: G6A_SAMPLE.json (all 705), or for phase R the list in --only (written by g6_compare.py).
- Each job runs tools/g6_job.py in a fresh interpreter; one row per finished job is appended to RUN_DIR/<phase>/ROWS.jsonl
  by this process only.
- Restart: jobs already in ROWS.jsonl are skipped; a job folder without a row is renamed _restartN and logged in
  RUN_DIR/<phase>/RESTARTS.log, then rerun from the start.
"""
import argparse, datetime, json, os, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', required=True, choices=['P1', 'P2', 'V', 'R']); ap.add_argument('--kit', type=Path, required=True)
    ap.add_argument('--label', required=True, choices=['PARENT', 'V2']); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=3); ap.add_argument('--only', type=Path)
    a = ap.parse_args()
    jobs = json.loads((a.only or V2 / 'G6A_SAMPLE.json').read_text())['jobs']
    ph = a.out / a.phase; ph.mkdir(parents=True, exist_ok=True)
    rows_p, log_p = ph / 'ROWS.jsonl', ph / 'RESTARTS.log'
    done = set()
    if rows_p.exists():
        done = {(r['cache'], r['job_id']) for r in map(json.loads, filter(str.strip, rows_p.read_text().splitlines()))}
    todo = [j for j in jobs if (j['cache'], j['job_id']) not in done]
    lock = threading.Lock()
    with log_p.open('a') as f:
        f.write('%s start phase %s kit %s: %d jobs, %d done, %d to run\n' % (now(), a.phase, a.kit, len(jobs), len(done), len(todo)))

    def one(j):
        d = ph / 'jobs' / ('%s__%s' % (Path(j['cache']).with_suffix('').as_posix().replace('/', '__'), j['job_id']))
        if d.exists():
            n = 1
            while Path('%s_restart%d' % (d, n)).exists():
                n += 1
            d.rename('%s_restart%d' % (d, n))
            with lock, log_p.open('a') as f:
                f.write('%s %s %s: folder without a row, renamed _restart%d, rerun\n' % (now(), j['cache'], j['job_id'], n))
        p = subprocess.run([sys.executable, '-B', str(HERE / 'g6_job.py'), a.label, str(a.kit), j['cache'], j['job_id'], str(d)],
                           capture_output=True, text=True, env=os.environ)
        if p.returncode != 0:
            row = {'kit_label': a.label, 'cache': j['cache'], 'job_id': j['job_id'], 'outcome': {'verdict': 'HARNESS_ERROR'},
                   'error': p.stderr[-2000:]}
        else:
            row = json.loads(p.stdout.strip().splitlines()[-1])
        row.update(stratum=j.get('stratum'), phase=a.phase, finished_utc=now())
        with lock, rows_p.open('a') as f:
            f.write(json.dumps(row, sort_keys=True, default=str) + '\n')
        return row['outcome'].get('verdict')

    with ThreadPoolExecutor(a.workers) as ex:
        for k, v in enumerate(ex.map(one, todo), 1):
            if k % 25 == 0 or k == len(todo):
                print('%s %s %d/%d last=%s' % (now(), a.phase, k, len(todo), v), flush=True)
    with log_p.open('a') as f:
        f.write('%s end phase %s\n' % (now(), a.phase))
    print('phase %s complete' % a.phase, flush=True)


if __name__ == '__main__':
    main()
