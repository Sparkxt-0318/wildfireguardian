"""Summarize F-3.4 ROWS.jsonl into an exclusive phase table (seconds) per execution plus medians across repetitions.

Phases are exclusive and add up to the controller's complete launch-to-completion wall time; whatever the timers do not
cover is reported as `unattributed`. Usage:
    python summarize.py ROWS.jsonl [--out PHASES.csv] [--json SUMMARY.json]
"""
import argparse, csv, json, statistics, sys
from pathlib import Path

PHASES = [
    ('launch_interpreter', 'process launch (GNU time + fork/exec) and interpreter start-up to first statement'),
    ('worker_imports', 'worker module imports (numpy, routing modules) before IMPORTED checkpoint'),
    ('input_load_hash', 'read graph/hazard/request JSON, SHA-256 and canonical-hash binding of inputs and packet files'),
    ('engine_imports_hash', 'routing/phaseB imports and module-hash checks before admission'),
    ('graph_preparation', 'graph validation + PreparedGraph construction (COLD_FAST) + snapshot'),
    ('hazard_validation', 'validate_hazard (edge-grid hazard admission)'),
    ('request_validation', 'validate_request + clock-scope check + admission remainder'),
    ('bound_model', 'RoadBoundModel construction (per-forecast road exposure bound model used by search)'),
    ('search', 'route search stages (Z contact sweep, EA bound, LO/LO2/HI solves); excludes whole-road checks'),
    ('check_contact_setup', 'whole-road checker: contact source preparation + mission validation + binding'),
    ('check_contact', 'whole-road checker: exact flame-contact check'),
    ('check_radiation_prep', 'whole-road checker: request-window radiation object construction'),
    ('check_radiation', 'whole-road checker: hybrid radiation (dose/peak) enclosure on the route'),
    ('check_adaptive_fallback', 'whole-road checker: adaptive radiation fallback after hybrid cap'),
    ('check_other', 'whole-road checker: remaining checker time (final authority checks, finalization)'),
    ('publication', 'publication contract (incl. unchanged centre re-check of the published route)'),
    ('finalize_write', 'final input/source re-binding, decision record, RESULT write'),
    ('exit_controller', 'worker teardown/exit and controller completion after RESULT publication'),
    ('unattributed', 'complete wall minus all of the above'),
]


def phases(row):
    pt = row.get('phase_timers') or {}
    tm = pt.get('timers') or {}
    T = lambda k: (tm.get(k) or {}).get('total_s', 0.0)
    cp = row.get('checkpoints_from_outer_s') or {}
    st = row.get('worker_stages_s') or {}
    prep = row.get('preparation') or {}
    wall = row.get('complete_wall_s') or 0.0
    out = {k: 0.0 for k, _ in PHASES}
    first = pt.get('interpreter_first_statement_from_outer_s')
    out['launch_interpreter'] = first if first is not None else row.get('worker_import_start_from_outer_s', 0.0)
    if 'IMPORTED' in cp:
        out['worker_imports'] = cp['IMPORTED'] - out['launch_interpreter']
    if 'INPUTS_BOUND' in cp:
        out['input_load_hash'] = cp['INPUTS_BOUND'] - cp.get('IMPORTED', 0.0)
    adm = st.get('normal_admission_clock_s')
    if 'ADMITTED' in cp and adm is not None:
        out['engine_imports_hash'] = cp['ADMITTED'] - cp['INPUTS_BOUND'] - adm
        # normal_admission_clock_s = preparation-module load + prepare_graph + snapshot + validate_hazard
        #                            + validate_request + clock scope; the last three are timed directly.
        out['hazard_validation'] = T('routing.validation.validate_hazard')
        out['request_validation'] = T('routing.validation.validate_request') + T('clock_scope.check_clock_scope')
        out['graph_preparation'] = adm - out['hazard_validation'] - out['request_validation']
    out['bound_model'] = st.get('bound_model_construction_s') or 0.0
    search = sum((s.get('elapsed_s') or 0.0) for s in row.get('rda_stages') or [] if s.get('stage') in ('Z', 'LO', 'LO2', 'HI'))
    search += st.get('earliest_arrival_bound_s') or 0.0
    out['search'] = search
    wr = row.get('whole_road') or {}
    ts = wr.get('timing_s') or {}
    total_check = sum(v for k, v in st.items() if k.startswith('whole_road_check_'))
    if total_check:
        out['check_contact_setup'] = ts.get('source_preparation_and_binding', 0.0) + ts.get('mission_validation', 0.0) + ts.get('dispatch_and_settings_binding', 0.0)
        out['check_contact'] = ts.get('contact_check', 0.0)
        out['check_radiation_prep'] = ts.get('radiation_preparation', 0.0)
        out['check_radiation'] = ts.get('radiation_check', 0.0)
        ad = T('adaptive_checker.adaptive_bound')
        out['check_adaptive_fallback'] = ad
        out['check_other'] = total_check - sum(out[k] for k in ('check_contact_setup', 'check_contact', 'check_radiation_prep', 'check_radiation', 'check_adaptive_fallback'))
    out['publication'] = st.get('publication_contract_s') or 0.0
    pb = (row.get('publication_boundary') or {}).get('elapsed_from_outer_after_result_publication_s')
    if pb is not None and 'ROAD_CHECK_RETURNED' in cp:
        out['finalize_write'] = pb - cp['ROAD_CHECK_RETURNED']
        out['exit_controller'] = wall - pb
    out['unattributed'] = wall - sum(v for k, v in out.items() if k != 'unattributed')
    return out


def groups():
    return {'startup_imports': ['launch_interpreter', 'worker_imports', 'engine_imports_hash'],
            'input_binding': ['input_load_hash'],
            'per_forecast_admission_and_models': ['graph_preparation', 'hazard_validation', 'bound_model', 'check_contact_setup', 'check_radiation_prep'],
            'request_validation': ['request_validation'],
            'search': ['search'],
            'route_check_contact': ['check_contact'],
            'route_check_radiation_exposure': ['check_radiation', 'check_adaptive_fallback'],
            'publication_and_exit': ['check_other', 'publication', 'finalize_write', 'exit_controller'],
            'unattributed': ['unattributed']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rows', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    rows = [json.loads(l) for l in a.rows.read_text().splitlines() if l.strip()]
    table = []
    for r in rows:
        p = phases(r)
        table.append(dict(region=r['region'], case_id=r['case_id'], rep=r.get('rep'), mode=r['mode'], budget_s=r['budget_s'],
                          status=r['authoritative_status'], on_time=r['on_time'], arrival_s=r.get('arrival_s'),
                          complete_wall_s=r['complete_wall_s'], **p))
    if a.out:
        with a.out.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]))
            w.writeheader(); w.writerows(table)
    G = groups(); summ = {'executions': len(table), 'groups': {}, 'phases': {}, 'per_mission': {}}
    walls = [t['complete_wall_s'] for t in table]
    total = sum(walls)
    for k, _ in PHASES:
        v = [t[k] for t in table]
        summ['phases'][k] = {'sum_s': sum(v), 'share_of_total': sum(v) / total, 'median_s': statistics.median(v), 'max_s': max(v)}
    for g, ks in G.items():
        v = [sum(t[k] for k in ks) for t in table]
        summ['groups'][g] = {'sum_s': sum(v), 'share_of_total': sum(v) / total, 'median_s': statistics.median(v), 'max_s': max(v)}
    by = {}
    for t in table:
        by.setdefault('%s/%s' % (t['region'], t['case_id']), []).append(t)
    for m, ts in by.items():
        w = [t['complete_wall_s'] for t in ts]
        summ['per_mission'][m] = {'status': sorted({t['status'] for t in ts}), 'reps': len(ts), 'wall_s': w,
                                  'wall_median_s': statistics.median(w), 'wall_range_s': max(w) - min(w),
                                  'wall_cv': (statistics.pstdev(w) / statistics.mean(w)) if len(w) > 1 else None,
                                  'groups_median_s': {g: statistics.median([sum(t[k] for k in ks) for t in ts]) for g, ks in G.items()}}
    summ['total_wall_s'] = total; summ['median_wall_s'] = statistics.median(walls)
    txt = json.dumps(summ, indent=1, sort_keys=True)
    if a.json:
        a.json.write_text(txt + '\n')
    print('%-34s %9s %7s %9s %8s' % ('group', 'sum_s', 'share', 'median', 'max'))
    for g, v in summ['groups'].items():
        print('%-34s %9.2f %6.1f%% %9.3f %8.2f' % (g, v['sum_s'], 100 * v['share_of_total'], v['median_s'], v['max_s']))
    print('%-34s %9.2f' % ('TOTAL complete wall', total))


if __name__ == '__main__':
    main()
