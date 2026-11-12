"""Step 2 amendment F evaluation of a 3-arm g1_panel run (FROZEN, V2, V2_NOISO), as written in STEP2_ACCEPTANCE
"Amendment F" and "changes from Mira's review" (R1-R7), before the panel:

M1  every V2 rep's harness family-PSS peak <= 3,072 MiB (max over reps)
M2  per-mission table: V2, V2_NOISO, FROZEN PSS peaks (median over reps), MiB and ratios
    post-hoc tripwire (labelled; passing it is not evidence of an acceptable cost): V2 - V2_NOISO > 50% AND > 300 MiB
    M2-model (fixed before the panel): median V2 PSS - median V2_NOISO PSS <= largest per-check cgroup peak in the
    mission's V2 reps + 64 MiB
M4  V2_NOISO pre-memory-map (status, arrival) set == FROZEN's (G1 rule incl. FL2)
R6  V2 pre-memory-map set == V2_NOISO's, per mission
R7  V2 / V2_NOISO summed-median wall (the isolation cost); harness sampler CPU per arm
G5w V2 / FROZEN summed-median wall <= 1.10
  python -B step2f_compare.py RUN_DIR --json OUT
"""
import argparse, json, statistics as st
from pathlib import Path

FL2 = 'yeongdeok_2025/20250325T230000Z_FL2'
FL2_OK = {('UNRESOLVED', None), ('CHECKED_JOURNEY_FEASIBLE', 1922), ('CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN', 1922)}
SEEN = {'uljin_2022/20220304T120000Z_FW2', 'yeongdeok_2025/20250326T080000Z_FW1'}   # R1: seen before the tripwire


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run', type=Path); ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    src = a.run / 'ROWS_REDECIDED.jsonl'
    rows = [json.loads(l) for l in (src if src.exists() else a.run / 'ROWS.jsonl').read_text().splitlines() if l.strip()]
    key = lambda r: '%s/%s' % (r['region'], r['case_id'])
    pre = lambda r: (r.get('pre_memory_status', r['authoritative_status']), r.get('pre_memory_arrival_s', r['arrival_s']))
    med = lambda v: st.median(v) if v else None
    out = {'missions': [], 'M1_fail': [], 'M2_posthoc_tripwire_fail': [], 'M2_model_fail': [], 'M4_fail': [], 'R6_fail': [],
           'labels': {'M2_posthoc': 'post-hoc tripwire (set after 2 diagnostics on panel missions); passing it is not evidence of an acceptable cost',
                      'V2_NOISO': 'baseline comparison: same kit without check isolation'}}
    wall = {'FROZEN': 0.0, 'V2': 0.0, 'V2_NOISO': 0.0}; cpu = {'FROZEN': [], 'V2': [], 'V2_NOISO': []}
    for m in sorted({key(r) for r in rows}):
        by = {lab: [r for r in rows if key(r) == m and r['kit_label'] == lab] for lab in ('FROZEN', 'V2', 'V2_NOISO')}
        pss = {lab: [((r.get('harness_mem') or {}).get('family_pss_peak_mib')) for r in by[lab]] for lab in by}
        pmed = {lab: med([x for x in v if x is not None]) for lab, v in pss.items()}
        sets = {lab: {pre(r) for r in by[lab]} for lab in by}
        g1 = lambda s_ref, s: (s <= FL2_OK) if m == FL2 else (s == s_ref)
        m4 = g1(sets['FROZEN'], sets['V2_NOISO']) and (m != FL2 or sets['FROZEN'] <= FL2_OK)
        r6 = (sets['V2'] <= FL2_OK and sets['V2_NOISO'] <= FL2_OK) if m == FL2 else (sets['V2'] == sets['V2_NOISO'])
        if m == FL2:
            r6_exact = sets['V2'] == sets['V2_NOISO']
        m1 = all(x is not None and x <= 3072 for x in pss['V2'])
        # largest per-check cgroup peak in the mission's V2 reps (STATE.check_budgets in RESULT)
        cpk = 0.0
        for r in by['V2']:
            res = a.run / 'V2' / ('r%d' % r['rep']) / ('%s__%s' % (r['region'], r['case_id'])) / 'RESULT.json'
            if res.exists():
                for b in json.loads(res.read_text()).get('check_budgets') or []:
                    cpk = max(cpk, b.get('peak_mb') or 0.0)
        inc = (pmed['V2'] - pmed['V2_NOISO']) if pmed['V2'] is not None and pmed['V2_NOISO'] is not None else None
        trip = inc is not None and inc > 300 and pmed['V2_NOISO'] and inc / pmed['V2_NOISO'] > 0.5
        model_ok = inc is None or inc <= cpk + 64
        for lab in wall:
            w = med([r['complete_wall_s'] for r in by[lab] if r.get('complete_wall_s') is not None]); wall[lab] += w or 0
            cpu[lab] += [((r.get('harness_mem') or {}).get('sampler_cpu_s') or 0) for r in by[lab]]
        rec = {'mission': m, 'seen_before_tripwire': m in SEEN, 'pss_peaks_mib': pss, 'pss_median_mib': pmed,
               'v2_minus_noiso_mib': inc, 'v2_over_noiso': (pmed['V2'] / pmed['V2_NOISO']) if pmed['V2'] and pmed['V2_NOISO'] else None,
               'v2_over_frozen': (pmed['V2'] / pmed['FROZEN']) if pmed['V2'] and pmed['FROZEN'] else None,
               'largest_check_cgroup_peak_mib': cpk, 'M1': m1, 'M2_posthoc_tripwire_ok': not trip, 'M2_model_ok': model_ok,
               'M4': m4, 'R6': r6, 'sets': {k: sorted(v, key=str) for k, v in sets.items()}}
        if m == FL2:
            rec['R6_exact_sets_equal'] = r6_exact
        out['missions'].append(rec)
        for k, ok in (('M1_fail', m1), ('M2_posthoc_tripwire_fail', not trip), ('M2_model_fail', model_ok), ('M4_fail', m4), ('R6_fail', r6)):
            if not ok:
                out[k].append(m)
        print('%-42s M1 %-5s trip %-5s model %-5s M4 %-5s R6 %-5s | PSS F %6.0f V2 %6.0f NOISO %6.0f (+%s MiB) chk %4.0f'
              % (m, m1, not trip, model_ok, m4, r6, pmed['FROZEN'] or -1, pmed['V2'] or -1, pmed['V2_NOISO'] or -1,
                 None if inc is None else round(inc), cpk))
    out['wall_sum_median_s'] = wall
    out['G5_wall_v2_over_frozen'] = wall['V2'] / wall['FROZEN'] if wall['FROZEN'] else None
    out['G5_wall_ok'] = out['G5_wall_v2_over_frozen'] is not None and out['G5_wall_v2_over_frozen'] <= 1.10
    out['R7_isolation_wall_cost_v2_over_noiso'] = wall['V2'] / wall['V2_NOISO'] if wall['V2_NOISO'] else None
    out['R7_sampler_cpu_s_median'] = {k: med(v) for k, v in cpu.items()}
    print(json.dumps({k: out[k] for k in ('M1_fail', 'M2_posthoc_tripwire_fail', 'M2_model_fail', 'M4_fail', 'R6_fail',
                                          'G5_wall_v2_over_frozen', 'G5_wall_ok', 'R7_isolation_wall_cost_v2_over_noiso',
                                          'R7_sampler_cpu_s_median')}, default=str))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
