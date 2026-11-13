"""One G6 job in its own interpreter (G6A_RUN.md "Running a job" and "Outcome of a job"). Prints one JSON row.
  WFG_F34=.../F-3.4 python -B g6_job.py KIT_LABEL KIT CACHE_REL JOB_ID OUT_DIR
- inputs re-verified (HAZARD.json and graph sha256 prefixes from G6_RULE.md; scenario_set_id in the packet members);
- request rebuilt with api.requests_build.build_request exactly as api/runner.py does;
- run through F-3.4 run_profile.run_one with explicit paths, 81 s, guard 3,072 MiB, plain;
- outcome: api.verdict.classify (verdict, reason_code), authoritative_status, arrival_s, and the route triple
  (edge_ids, times_s, waits) from api.runner.route_feature.
"""
import hashlib, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
F34 = Path(os.environ['WFG_F34']).resolve()
sys.path[:0] = [str(REPO), str(F34)]
from api.requests_build import build_request, effective_limits   # noqa: E402
from api.verdict import classify                                  # noqa: E402
from api.runner import route_feature                              # noqa: E402

PREFIX = {('uiseong_andong_2025', '20250323T010000Z'): '21a8a087', ('uiseong_andong_2025', '20250324T090000Z'): 'cde0707d',
          ('uiseong_andong_2025', '20250325T170000Z'): '87c2ee0c', ('yeongdeok_2025', '20250325T190000Z'): 'fe33db21',
          ('yeongdeok_2025', '20250325T230000Z'): 'fa347cf3', ('yeongdeok_2025', '20250326T080000Z'): '0f468b69'}
GRAPH_PREFIX = {'uiseong_andong_2025': '8c37e5b6', 'yeongdeok_2025': 'f097e6c8'}
BUDGET_S, GUARD_MIB = 81.0, 3072
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

label, kit, cache_rel, job_id, out = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4], Path(sys.argv[5])
cache = json.loads((REPO / 'planner/cache' / cache_rel).read_text())
rec = cache['route_checks'][job_id]
region = cache['region_id']; tag = cache['input_time'].replace('-', '').replace(':', '')
inputs = REPO / 'data/routing'
packet = inputs / 'latest_inputs_try02/packets' / region / tag
graph = inputs / 'graphs' / region / 'graph.json'
row = {'kit_label': label, 'cache': cache_rel, 'job_id': job_id, 'region': region, 'input': tag,
       'recorded': {k: (rec.get('result') or {}).get(k) for k in ('verdict', 'raw_status', 'reason_code', 'arrival_s')},
       'recheck_of': rec.get('recheck_of')}
hz_sha, g_sha = sha(packet / 'HAZARD.json'), sha(graph)
hazard = json.loads((packet / 'HAZARD.json').read_text())
sids = [m['id'] for m in hazard['members']]
row['input_check'] = {'hazard_sha256': hz_sha, 'graph_sha256': g_sha,
                      'hazard_prefix_ok': hz_sha.startswith(PREFIX[(region, tag)]),
                      'graph_prefix_ok': g_sha.startswith(GRAPH_PREFIX[region]),
                      'scenario_set_ok': all(s.startswith(cache['scenario_set_id'] + ':') for s in sids)}
if not all(v for k, v in row['input_check'].items() if k.endswith('_ok')):
    row['outcome'] = {'verdict': 'INPUT_MISMATCH'}
    print(json.dumps(row, sort_keys=True)); sys.exit(0)

q = rec['request']
try:
    request = build_request(start_node=q['start']['node_id'], dest_node=q['destination']['node_id'],
                            depart_offset_s=q.get('depart_offset_s', 0), dwell_s=q.get('dwell_s'),
                            window=q.get('destination_window'), limits=effective_limits(q), scenario_ids=sids,
                            horizon_s=hazard['valid_until'], valid_from=hazard['valid_from'],
                            hazard_version=hazard['version'], as_of_iso=hazard['time_origin'], dt=int(hazard['dt']))
except Exception as exc:   # the API would answer 422; reported for both kits, never compared
    row['outcome'] = {'verdict': 'INPUT_REJECTED', 'error': '%s: %s' % (type(exc).__name__, exc)}
    print(json.dumps(row, sort_keys=True)); sys.exit(0)
out.mkdir(parents=True, exist_ok=False)
rp = out / 'REQUEST.json'; rp.write_text(json.dumps(request))
row['request_sha256'] = sha(rp)

import run_profile as RP   # noqa: E402  (F-3.4, imports the job's own kit modules in this fresh interpreter)
t0 = time.perf_counter()
prow = RP.run_one(kit, None, region, '%s__%s' % (Path(cache_rel).stem, job_id), out / 'run', BUDGET_S, 'plain',
                  sys.executable, paths=(graph, packet, rp), memory_guard_mib=GUARD_MIB)
row['wall_s'] = time.perf_counter() - t0
run = out / 'run'
load = lambda n: json.loads((run / n).read_text()) if (run / n).exists() else {}
result, receipt, jobj = load('RESULT.json'), load('COMPLETE_PROCESS_RECEIPT.json'), load('JOB.json')
# the decision exactly as run_one computed it: this interpreter's (= this kit's) journey_decision_v2_1, same inputs
JD = sys.modules['journey_decision_v2_1']
assert Path(JD.__file__).resolve().is_relative_to(kit), JD.__file__
decision = JD.decision_from_worker_record(result, receipt, jobj, graph=json.loads(graph.read_text()), request=request,
                                          hazard=hazard, optimality_certificate=result.get('optimality_certificate'),
                                          refusal_certificate=result.get('refusal_certificate'))
assert decision.get('authoritative_status') == prow.get('authoritative_status'), (decision.get('authoritative_status'), prow.get('authoritative_status'))
verdict, reason, raw_reason = classify(decision, receipt, result, None, GUARD_MIB)
o = {'verdict': verdict, 'reason_code': reason, 'raw_reason': raw_reason, 'raw_status': decision.get('authoritative_status'),
     'arrival_s': None, 'route': None,
     'wall_cap': bool(receipt.get('deadline_termination_requested')) and reason == 'TIMEOUT',
     'memory_guard_triggered': receipt.get('memory_guard_triggered'),
     'family_peak_rss_mib': (receipt.get('sampled_family_peak_rss_bytes') or 0) / 2 ** 20,
     'complete_wall_s': receipt.get('external_launch_to_completion_wall_s'),
     # Step 2: status and arrival before the memory map (as tools/redecide.py), reported beside the verdict
     'pre_memory_status': decision.get('certified_status_within_kit') or decision.get('authoritative_status'),
     'pre_memory_arrival_s': ((decision.get('journey') or decision.get('journey_outside_memory_budget') or {}).get('arrival')),
     'memory_mapped': decision.get('certified_status_within_kit') is not None,
     'decision_module': JD.__file__}
journey = decision.get('journey') or {}
if verdict == 'checked_route' and journey.get('legs'):
    g = json.loads(graph.read_text())
    edges = {e['id']: (e['u'], e['v'], e['travel_ticks']) for e in g['edges']}
    feat = route_feature(journey, request, edges, lambda n: (0.0, 0.0))
    o['arrival_s'] = journey.get('arrival')
    o['route'] = {k: feat['properties'][k] for k in ('edge_ids', 'times_s', 'waits')}
row['outcome'] = o
row['kit_identity'] = result.get('kit_identity')
print(json.dumps(row, sort_keys=True, default=str))
