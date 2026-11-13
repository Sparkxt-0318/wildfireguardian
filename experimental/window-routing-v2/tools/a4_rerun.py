"""A4 rerun on a v2 kit (STEP3_ACCEPTANCE "A4 rerun on kit-v2-step23"), checkpointed per rep.
  WFG_F34=.../F-3.4 python -B a4_rerun.py KIT LEO OUT_PREFIX [REPS=10]
Each rep runs fdyn_profile.py --only <both firms_early tags> at 900 s, guard 3,072 MiB, no rss_limit_mb, --mode plain,
into OUT_PREFIX_rNN. A rep with both rows in ROWS.jsonl is complete and skipped; a partial rep is renamed _restartN,
logged in OUT_PREFIX_RESTARTS.log, and rerun from the start.
"""
import datetime, json, os, subprocess, sys
from pathlib import Path

TAGS = ['yeongdeok_2025__20250325T230000Z_firms_early__osm_node_11753630207',
        'yeongdeok_2025__20250325T230000Z_firms_early__osm_node_415158168']
F34 = Path(os.environ['WFG_F34']).resolve()
kit, leo, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
reps = int(sys.argv[4]) if len(sys.argv) > 4 else 10
log = Path(prefix + '_RESTARTS.log')
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
for i in range(1, reps + 1):
    out = Path('%s_r%02d' % (prefix, i))
    rows = out / 'ROWS.jsonl'
    if rows.exists() and len([l for l in rows.read_text().splitlines() if l.strip()]) == len(TAGS):
        print('rep %02d complete, skipped' % i, flush=True); continue
    if out.exists():
        n = 1
        while Path('%s_restart%d' % (out, n)).exists():
            n += 1
        out.rename('%s_restart%d' % (out, n))
        with log.open('a') as f:
            f.write('%s rep %02d partial (%s) renamed _restart%d and rerun from the start\n' % (now(), i, rows.exists(), n))
    t0 = now()
    rc = subprocess.call([sys.executable, '-B', str(F34 / 'fdyn_profile.py'), '--kit', kit, '--leo', leo, '--out', str(out),
                          '--budget', '900', '--mode', 'plain', '--memory-guard-mib', '3072', '--only', ','.join(TAGS)],
                         cwd=str(F34))
    print('rep %02d rc=%d %s..%s' % (i, rc, t0, now()), flush=True)
    if rc != 0:
        raise SystemExit('rep %02d failed rc=%d' % (i, rc))
print('A4 done', flush=True)
