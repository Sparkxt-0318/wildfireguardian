"""Diagnostic (Step 2 G5 memory): run one job via run_one_job.py and sample its whole process family every 10 ms,
summing per-process Rss (what the controller's family-RSS reading counts: shared pages count once per process) and
Pss (shared pages split between the processes sharing them). Prints one JSON line.
  python -B family_pss.py KIT REGION CASE_ID OUT_DIR [BUDGET_S]"""
import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
kit, region, case, out = sys.argv[1:5]; budget = sys.argv[5] if len(sys.argv) > 5 else '81'
p = subprocess.Popen([sys.executable, '-B', str(HERE / 'run_one_job.py'), kit, str(REPO / 'data/routing'), region, case, out, budget],
                     stdout=subprocess.PIPE, text=True)


def family(root):
    kids = {}
    for d in os.listdir('/proc'):
        if d.isdigit():
            try:
                ppid = int(open('/proc/%s/stat' % d).read().rsplit(')', 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(d))
            except (OSError, IndexError, ValueError):
                pass
    out, todo = [], [root]
    while todo:
        x = todo.pop(); out.append(x); todo.extend(kids.get(x, []))
    return out


def rollup(pid):
    r = {}
    try:
        for line in open('/proc/%d/smaps_rollup' % pid):
            k, *v = line.split()
            if k in ('Rss:', 'Pss:'):
                r[k[:-1]] = int(v[0]) / 1024
    except OSError:
        pass
    return r


mx = {'rss_sum': 0, 'pss_sum': 0, 'n_at_rss_max': 0}
while p.poll() is None:
    fam = family(p.pid)
    vals = [rollup(x) for x in fam]
    rs = sum(v.get('Rss', 0) for v in vals); ps = sum(v.get('Pss', 0) for v in vals)
    if rs > mx['rss_sum']:
        mx['rss_sum'] = rs; mx['n_at_rss_max'] = len([v for v in vals if v]); mx['pss_at_rss_max'] = ps
    mx['pss_sum'] = max(mx['pss_sum'], ps)
    time.sleep(0.01)
row = json.loads(p.stdout.read().strip().splitlines()[-1])
print(json.dumps({'kit': kit, 'mission': region + '/' + case, 'status': row['authoritative_status'],
                  'controller_family_peak_rss_mib': row['family_peak_rss_mib'], 'sampled': mx}))
