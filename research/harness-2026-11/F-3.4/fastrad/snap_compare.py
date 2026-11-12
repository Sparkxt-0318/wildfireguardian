"""Compare an option-B snap-kit run with the unchanged-kit control, both uninstrumented (run_profile --mode plain).

Per mission:
- identical authoritative status and arrival seconds in every repetition (the acceptance condition);
- median complete wall time;
- loosening of the certified radiation bounds, read from each run's RESULT.json whole_road_check per_member (largest
  dose and peak upper bound), as a share of the request's budgets: Iris's condition 2.

  python snap_compare.py --base CONTROL_DIR --snap SNAP_DIR [--json OUT]
"""
import argparse, json, statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def load(d):
    rows = [json.loads(l) for l in (Path(d) / 'ROWS.jsonl').read_text().splitlines() if l.strip()]
    for r in rows:
        res = Path(d) / ('r%d' % r['rep']) / ('%s__%s' % (r['region'], r['case_id'])) / 'RESULT.json'
        wr = (json.loads(res.read_text()).get('whole_road_check') or {}) if res.exists() else {}
        rad = wr.get('adaptive_fallback') or wr.get('radiation') or {}
        req = json.loads((REPO / 'data/routing/latest_inputs_try02/requests' / r['region'] / (r['case_id'] + '.json')).read_text())
        pm = rad.get('per_member') or []
        r['dose_upper_share'] = max((m['dose_upper_kj_m2'] / req['budgets']['dose'][m['id']] for m in pm), default=None)
        r['peak_upper_share'] = max((m['peak_upper_kw_m2'] / req['budgets']['peak'] for m in pm), default=None)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True); ap.add_argument('--snap', type=Path, required=True)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    B, Sn = load(a.base), load(a.snap)
    key = lambda r: '%s/%s' % (r['region'], r['case_id'])
    out = []; mism = 0
    for m in sorted({key(r) for r in B}):
        b = [r for r in B if key(r) == m]; s = [r for r in Sn if key(r) == m]
        bv = {(r['authoritative_status'], r['arrival_s']) for r in b}; sv = {(r['authoritative_status'], r['arrival_s']) for r in s}
        same = bv == sv
        mism += (not same)
        def med(rs, k):
            v = [r[k] for r in rs if r.get(k) is not None]
            return st.median(v) if v else None
        row = {'mission': m, 'identical_status_and_arrival': same, 'base': sorted(bv, key=str), 'snap': sorted(sv, key=str),
               'base_wall_s': med(b, 'complete_wall_s'), 'snap_wall_s': med(s, 'complete_wall_s'),
               'dose_upper_share_base': med(b, 'dose_upper_share'), 'dose_upper_share_snap': med(s, 'dose_upper_share'),
               'peak_upper_share_base': med(b, 'peak_upper_share'), 'peak_upper_share_snap': med(s, 'peak_upper_share')}
        out.append(row)
        f = lambda x: '   -  ' if x is None else '%6.4f' % x
        print('%-44s %-5s wall %7.2f -> %7.2f s | dose share %s -> %s | peak share %s -> %s'
              % (m, 'SAME' if same else 'DIFF', row['base_wall_s'] or -1, row['snap_wall_s'] or -1,
                 f(row['dose_upper_share_base']), f(row['dose_upper_share_snap']), f(row['peak_upper_share_base']), f(row['peak_upper_share_snap'])))
    tb = sum(r['base_wall_s'] or 0 for r in out); ts = sum(r['snap_wall_s'] or 0 for r in out)
    print('missions with different status/arrival: %d of %d; sum of median walls %.1f -> %.1f s (%.1f%%)' % (mism, len(out), tb, ts, 100 * (ts - tb) / tb))
    if a.json:
        a.json.write_text(json.dumps({'mismatches': mism, 'rows': out}, indent=1) + '\n')


if __name__ == '__main__':
    main()
