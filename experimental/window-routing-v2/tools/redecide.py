"""Recompute each g1_panel row's authoritative decision with ITS OWN kit's decision module (loaded by file path under
a kit-unique module name), from the run folder's RESULT.json + COMPLETE_PROCESS_RECEIPT.json + JOB.json.

Why: run_profile.run_one imports `journey_decision_v2_1` by name from the kit's decision dir; in one process the first
kit's module is cached, so later rows of the other kit were decided by the first kit's module. Statuses are unaffected
whenever both modules give the same status (Step 0: identical code; Step 1: reason-only post-step), but reasons are not.
Writes ROWS_REDECIDED.jsonl with own-module status/reason and flags any status that differs from the recorded row.
  python -B redecide.py RUN_DIR
"""
import importlib.util, json, sys
from pathlib import Path


def load_mod(kit):
    p = Path(kit) / 'decision/journey_decision_v2_1.py'
    name = 'jd_v2_1_' + str(abs(hash(str(p))))
    spec = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def main():
    run = Path(sys.argv[1]); mods = {}; out = []; status_diff = 0
    for l in (run / 'ROWS.jsonl').read_text().splitlines():
        r = json.loads(l); kit = r['kit_path']; mods.setdefault(kit, load_mod(kit)); M = mods[kit]
        d = run / r['kit_label'] / ('r%d' % r['rep']) / ('%s__%s' % (r['region'], r['case_id']))
        L = lambda n: json.loads((d / n).read_text()) if (d / n).exists() else {}
        res, rc, job = L('RESULT.json'), L('COMPLETE_PROCESS_RECEIPT.json'), L('JOB.json')
        dec = M.decision_from_worker_record(res, rc, job, graph=json.loads(Path(job['graph_path']).read_text()),
                                            request=json.loads(Path(job['request_path']).read_text()),
                                            hazard=json.loads(Path(job['hazard_path']).read_text()),
                                            optimality_certificate=res.get('optimality_certificate'),
                                            refusal_certificate=res.get('refusal_certificate'))
        r2 = dict(r, recorded_status=r['authoritative_status'], recorded_reason=r['unresolved_reason'],
                  authoritative_status=dec['authoritative_status'], unresolved_reason=dec.get('unresolved_reason'),
                  arrival_s=(dec.get('journey') or {}).get('arrival'), decision_module_version=dec.get('module_version'))
        status_diff += r2['authoritative_status'] != r2['recorded_status']
        out.append(r2)
    (run / 'ROWS_REDECIDED.jsonl').write_text(''.join(json.dumps(x, sort_keys=True, default=str) + '\n' for x in out))
    print('rows %d, status differences vs recorded %d' % (len(out), status_diff))
    for x in out:
        if x['unresolved_reason'] != x['recorded_reason'] or x['authoritative_status'] != x['recorded_status']:
            print(x['kit_label'], x['rep'], x['case_id'], x['recorded_status'], x['recorded_reason'], '->', x['authoritative_status'], x['unresolved_reason'], x['decision_module_version'])


if __name__ == '__main__':
    main()
