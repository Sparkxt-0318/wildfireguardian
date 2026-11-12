"""F-3.4 phase profile of the frozen 20-mission RDA_CAND workload.

Each execution goes through the kit's own lifecycle controller (``wfg_controller.run_attempt``: GNU time wrapper,
sampled family RSS, verified cleanup, outer complete deadline) exactly as ``wfg_latest.api.route_and_check`` builds it.
``--mode phase`` substitutes ``phase_worker.py`` as the launched file (it runs the unmodified worker in-process with
timers); ``--mode plain`` launches the unmodified worker directly (overhead control). The offline independent checker
is not run: it is excluded from complete-request time in the frozen protocol.

Example (one repetition, evaluated 30 s budget):
    .venv/bin/python research/harness-2026-11/F-3.4/run_profile.py --kit KIT --out OUT --reps 1 --budget 30
"""
import argparse, hashlib, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def missions(kit):
    q = json.loads((kit / 'queues/LATEST_PRIMARY.json').read_text())
    seen = []
    for j in q['jobs']:
        key = (j['cohort'], j['case_id'])
        if j['arm'] == 'RDA_CAND' and key not in seen:
            seen.append(key)
    return seen


def build_job(kit, inputs, region, case_id, out, budget, worker, label):
    cutoff = case_id.split('_')[0]
    graph = inputs / 'graphs' / region / 'graph.json'
    packet = inputs / 'latest_inputs_try02/packets' / region / cutoff
    request = inputs / 'latest_inputs_try02/requests' / region / (case_id + '.json')
    q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
    req = json.loads(request.read_text())
    job = {'label': label, 'case_id': label, 'cohort': 'f34', 'arm': 'RDA_CAND', 'arm_key': 'RDA_CAND', 'rep': 1,
           'source_root': q['source_root'], 'source_directory': str(packet), 'graph_path': str(graph),
           'hazard_path': str(packet / 'HAZARD.json'), 'request_path': str(request), 'complete_budget_s': float(budget),
           'original_limits': req['limits'], 'worker': str(worker), 'env': {},
           'input_sha256': {'graph_path': sha(graph), 'hazard_path': sha(packet / 'HAZARD.json'), 'request_path': sha(request)},
           'source_sha256': {n: sha(packet / n) for n in ('REPORT.json', 'NATIVE_METADATA.json', 'constructed_arrays.npz')},
           'core_sha256': q['core_sha256'], 'checker_module': q['checker_module'], 'checker_sha256': q['checker_sha256'],
           'root': None, 'decision_dir': None, 'output_path': str(out), 'campaign': 'F34', 'queue': 'F34',
           'preparation_mode': q['preparation_mode'], 'preparation_mode_sha256': q['preparation_mode_sha256'],
           'preparation_source_sha256': q['preparation_source_sha256'], 'memory_guard_mib': 3072,
           'phaseB_sha256': q['phaseB_sha256']}
    return job, graph, packet, request, req


def load(p):
    return json.loads(p.read_text()) if p.exists() else None


def run_one(kit, inputs, region, case_id, out, budget, mode, python):
    sys.path[:0] = [str(kit / 'runner'), str(kit / 'decision')]
    import wfg_controller as CTL
    import journey_decision_v2_1 as JD
    target = kit / 'phaseB/rda_worker_v1_1.py'
    worker = HERE / 'phase_worker.py' if mode == 'phase' else target
    label = '%s__%s' % (region, case_id)
    job, graph, packet, request, req = build_job(kit, inputs, region, case_id, out, budget, worker, label)
    if mode == 'phase':
        job['env'] = {'WFG_PHASE_TARGET': str(target)}
    t0 = time.perf_counter()
    rc = CTL.run_attempt(kit, job, python, {'f34': True})
    harness_wall = time.perf_counter() - t0
    res = load(out / 'RESULT.json') or {}
    jobj = load(out / 'JOB.json')
    dec = JD.decision_from_worker_record(res, rc, jobj, graph=json.loads(graph.read_text()), request=req,
                                         hazard=json.loads((packet / 'HAZARD.json').read_text()),
                                         optimality_certificate=res.get('optimality_certificate'),
                                         refusal_certificate=res.get('refusal_certificate'))
    stages = {}
    for p in out.glob('STAGE_*.json'):
        d = json.loads(p.read_text()); stages[d['phase']] = d['elapsed_from_outer_s']
    wr = res.get('whole_road_check') or {}
    row = {'region': region, 'case_id': case_id, 'mode': mode, 'budget_s': budget,
           'complete_wall_s': rc.get('external_launch_to_completion_wall_s'), 'harness_wall_s': harness_wall,
           'on_time': rc.get('on_time_complete_publication'), 'cleanup': rc.get('cleanup_state'),
           'family_peak_rss_mib': (rc.get('sampled_family_peak_rss_bytes') or 0) / 2 ** 20,
           'rss_sampling_cost_s': rc.get('rss_sampling_cost_s'),
           'primary_status': res.get('primary_status'), 'authoritative_status': dec.get('authoritative_status'),
           'unresolved_reason': dec.get('unresolved_reason'), 'arrival_s': (dec.get('journey') or {}).get('arrival'),
           'published_stage': (res.get('result') or {}).get('published_stage'),
           'worker_import_start_from_outer_s': (res.get('worker_import_start_monotonic') or 0) - (res.get('outer_start_monotonic') or 0),
           'checkpoints_from_outer_s': stages, 'worker_stages_s': res.get('stages'),
           'preparation': {k: (res.get('preparation') or {}).get(k) for k in ('mode', 'prepare_s', 'total_s', 'identity_checks_s')},
           'rda_stages': [{k: s.get(k) for k in ('stage', 'elapsed_s', 'status', 'arrival', 'check_status', 'check_reason', 'check_elapsed_s', 'sweep_metrics')}
                          for s in res.get('rda_stages') or []],
           'earliest_arrival_bound': res.get('earliest_arrival_bound'),
           'whole_road': {'status': wr.get('status'), 'reason': wr.get('reason'), 'elapsed_s': wr.get('elapsed_s'),
                          'timing_s': wr.get('timing_s'), 'constructor_wall_s': wr.get('constructor_wall_s'),
                          'radiation': {k: (wr.get('radiation') or {}).get(k) for k in ('status', 'cap', 'elapsed_s', 'spatial_slabs', 'refinement_levels',
                                                                                       'analytic_source_bounds', 'analytic_corner_evaluations', 'window_active_source_count')},
                          'adaptive_fallback': {k: (wr.get('adaptive_fallback') or {}).get(k) for k in ('status', 'elapsed_s', 'reason')} if wr.get('adaptive_fallback') else None},
           'publication_boundary': load(out / 'PUBLICATION_BOUNDARY.json'),
           'phase_timers': load(out / 'PHASE_TIMERS.json')}
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--kit', type=Path, required=True)
    ap.add_argument('--inputs', type=Path, default=REPO / 'data/routing')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--budget', type=float, default=30.0)
    ap.add_argument('--mode', choices=['phase', 'plain'], default='phase')
    ap.add_argument('--only', default=None, help='comma-separated region__case_id filter')
    ap.add_argument('--python', default=sys.executable)
    a = ap.parse_args()
    kit = a.kit.resolve(); out = a.out.resolve()
    if out.exists():
        raise SystemExit('Output exists: %s' % out)
    out.mkdir(parents=True)
    todo = missions(kit)
    if a.only:
        keep = set(a.only.split(','))
        todo = [m for m in todo if '%s__%s' % m in keep]
    rows_path = out / 'ROWS.jsonl'
    for rep in range(1, a.reps + 1):
        order = todo if rep % 2 else list(reversed(todo))   # alternate order between repetitions
        for region, case_id in order:
            d = out / ('r%d' % rep) / ('%s__%s' % (region, case_id))
            d.parent.mkdir(parents=True, exist_ok=True)
            row = run_one(kit, a.inputs.resolve(), region, case_id, d, a.budget, a.mode, a.python)
            row['rep'] = rep
            with rows_path.open('a') as f:
                f.write(json.dumps(row, sort_keys=True) + '\n')
            print('%s r%d %-38s %-16s %-36s wall=%.2f' % (a.mode, rep, region + '/' + case_id, row['primary_status'],
                                                      row['authoritative_status'], row['complete_wall_s'] or -1), flush=True)


if __name__ == '__main__':
    main()
