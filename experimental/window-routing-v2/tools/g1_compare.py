"""PLAN.md G1, G3, G5 evaluation of a g1_panel.py run, plus the list of published routes for G2/G2b.
G1: per mission, the set of (authoritative status, arrival) over V2 reps equals that over FROZEN reps, on all missions
except Yeongdeok 0325T23 FL2; FL2 passes iff every V2 outcome is in {UNRESOLVED, FEASIBLE@1922, OPTIMUM_PROVEN@1922}.
Any V2 change is classified; the mechanical exception (PLAN G1) is NOT applied automatically: it is listed for review.
G3: median largest dose / peak upper-bound share of budget equal within 1e-4 where both kits completed the check.
G5: summed median plain wall (V2 vs FROZEN) rises <= 10%; per-mission median family peak RSS <= +10% and <= 3072 MiB.
  python -B g1_compare.py RUN_DIR [--json OUT]
"""
import argparse, json, os, statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FL2 = 'yeongdeok_2025/20250325T230000Z_FL2'
FL2_OK = {('UNRESOLVED', None), ('CHECKED_JOURNEY_FEASIBLE', 1922), ('CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN', 1922)}


def shares(run, r):
    res = run / r['kit_label'] / ('r%d' % r['rep']) / ('%s__%s' % (r['region'], r['case_id'])) / 'RESULT.json'
    wr = (json.loads(res.read_text()).get('whole_road_check') or {}) if res.exists() else {}
    rad = wr.get('adaptive_fallback') or wr.get('radiation') or {}
    pm = rad.get('per_member') or []
    if isinstance(pm, dict):
        pm = [dict(v, id=k) for k, v in pm.items()]
    req = json.loads((Path(os.environ.get('WFG_DATA_ROUTING', str(REPO / 'data/routing'))) / 'latest_inputs_try02/requests' / r['region'] / (r['case_id'] + '.json')).read_text())
    d = max((m['dose_upper_kj_m2'] / req['budgets']['dose'][m['id']] for m in pm), default=None)
    p = max((m['peak_upper_kw_m2'] / req['budgets']['peak'] for m in pm), default=None)
    return d, p, (json.loads(res.read_text()).get('kit_identity') if res.exists() else None)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run', type=Path); ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    src = a.run / 'ROWS_REDECIDED.jsonl'   # own-module decisions (redecide.py) when present; else the recorded rows
    rows = [json.loads(l) for l in (src if src.exists() else a.run / 'ROWS.jsonl').read_text().splitlines() if l.strip()]
    print('rows from', src.name if src.exists() else 'ROWS.jsonl')
    for r in rows:
        r['dose_share'], r['peak_share'], r['kit_identity'] = shares(a.run, r)
    key = lambda r: '%s/%s' % (r['region'], r['case_id'])
    med = lambda v: st.median(v) if v else None
    out = {'missions': [], 'g1_failures': [], 'g3_failures': [], 'review_changes': []}
    tw = {'FROZEN': 0.0, 'V2': 0.0}
    for m in sorted({key(r) for r in rows}):
        F = [r for r in rows if key(r) == m and r['kit_label'] == 'FROZEN']; V = [r for r in rows if key(r) == m and r['kit_label'] == 'V2']
        fs = {(r['authoritative_status'], r['arrival_s']) for r in F}; vs = {(r['authoritative_status'], r['arrival_s']) for r in V}
        g1 = (vs <= FL2_OK) if m == FL2 else (fs == vs)
        if not g1:
            out['g1_failures'].append(m)
            if any(s == 'UNRESOLVED' for s, _ in fs) and not any(s == 'UNRESOLVED' for s, _ in vs):
                out['review_changes'].append(m)
        g3 = True; dd = {}
        for k in ('dose_share', 'peak_share'):
            fv = med([r[k] for r in F if r[k] is not None]); vv = med([r[k] for r in V if r[k] is not None])
            dd[k] = (fv, vv)
            if fv is not None and vv is not None and abs(fv - vv) > 1e-4:
                g3 = False
        if not g3:
            out['g3_failures'].append(m)
        fw = med([r['complete_wall_s'] for r in F]); vw = med([r['complete_wall_s'] for r in V])
        fp = med([r['family_peak_rss_mib'] for r in F]); vp = med([r['family_peak_rss_mib'] for r in V])
        tw['FROZEN'] += fw or 0; tw['V2'] += vw or 0
        g5m = vp is not None and vp <= 3072 and (fp is None or vp <= 1.10 * fp)
        fr = sorted({str(r.get('unresolved_reason')) for r in F}); vr = sorted({str(r.get('unresolved_reason')) for r in V})
        if fr != vr:
            out.setdefault('reason_changes', []).append({'mission': m, 'frozen_reasons': fr, 'v2_reasons': vr})
        out['missions'].append({'mission': m, 'frozen': sorted(fs, key=str), 'v2': sorted(vs, key=str), 'g1': g1, 'g3': g3, 'shares': dd,
                                'wall_frozen': fw, 'wall_v2': vw, 'peak_frozen': fp, 'peak_v2': vp, 'g5_memory': g5m})
        print('%-40s G1 %-4s G3 %-4s G5mem %-4s | F %s | V %s | wall %.1f/%.1f peak %.0f/%.0f' % (m, g1, g3, g5m, sorted(fs, key=str), sorted(vs, key=str),
              fw or -1, vw or -1, fp or -1, vp or -1))
    out['sum_median_wall'] = tw; out['g5_wall_ratio'] = tw['V2'] / tw['FROZEN'] if tw['FROZEN'] else None
    out['g5_wall'] = out['g5_wall_ratio'] is not None and out['g5_wall_ratio'] <= 1.10
    out['g5_memory'] = all(x['g5_memory'] for x in out['missions'])
    out['v2_rows_with_kit_identity'] = sum(1 for r in rows if r['kit_label'] == 'V2' and r['kit_identity'])
    out['v2_rows'] = sum(1 for r in rows if r['kit_label'] == 'V2')
    out['frozen_rows_with_kit_identity'] = sum(1 for r in rows if r['kit_label'] == 'FROZEN' and r['kit_identity'])
    out['published_v2_routes'] = [str(a.run / 'V2' / ('r%d' % r['rep']) / ('%s__%s' % (r['region'], r['case_id'])))
                                  for r in rows if r['kit_label'] == 'V2' and str(r['authoritative_status']).startswith('CHECKED_JOURNEY')]
    print('G1 failures %s | G3 failures %s | review %s | G5 wall ratio %.3f (%s) | G5 memory %s | kit_identity V2 %d/%d, FROZEN %d'
          % (out['g1_failures'], out['g3_failures'], out['review_changes'], out['g5_wall_ratio'] or -1, out['g5_wall'], out['g5_memory'],
             out['v2_rows_with_kit_identity'], out['v2_rows'], out['frozen_rows_with_kit_identity']))
    print('reason changes:', out.get('reason_changes', []))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
