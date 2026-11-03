"""Path A driver: per-origin records from the six cache files (planner rules), travel-only pairs and road redundancy.

Cache files are loaded one at a time; each road graph is loaded once, after its SHA-256 has been matched to the
``input_hashes.graph`` recorded in every cached route check of that region.
"""
from __future__ import annotations

import gc
from collections import Counter

from . import api_rules, planner_rules as pr, sources
from .maxflow import RedundancySolver, RoadGraph
from .trips import fastest_trips, walk_length_to_edge_end

HORIZON_S = 3600            # recorded scenario window (planner/src/domain/plan.ts RECORDED_HORIZON_S, line 44)


def deadline_category(best_verdict: str, latest_s) -> str:
    """Leave-by deadline class: the latest checked offset, or why there is none (never conflated)."""
    if latest_s is not None:
        return f'latest_{int(latest_s):04d}s'
    return 'none_model_no_route' if best_verdict == pr.NO_ROUTE else 'none_unresolved'


def cell_category(cell: dict) -> str:
    """A sweep cell as reported: the three verdicts, plus "시간창 밖" (window_unsatisfiable, no check) on its own."""
    return pr.WINDOW_UNSATISFIABLE if pr.is_window_skip(cell) else cell['verdict']


def _provenance(job: dict) -> dict:
    res = job.get('result') or {}
    return res.get('provenance') or job.get('provenance') or {}


def _route_props(job: dict) -> dict:
    return (((job.get('result') or {}).get('route') or {}).get('properties')) or {}


def analyse_file(entry: dict, places: list[dict]) -> dict:
    doc = sources.load_cache(entry)
    pr.TieCounter.n = 0
    model = pr.cache_to_model(doc)
    origins = pr.scenario_origins(places, doc['scenario_set_id'])
    step_min = int(doc['generator']['step_min'])
    plans = pr.complete_plans(model, origins, HORIZON_S, step_min)

    # provenance of every API result in the file (route checks and travel-only checks)
    prov = Counter()
    hosts, hazards, graphs, graph_ids = Counter(), Counter(), Counter(), Counter()
    for job in list((doc.get('route_checks') or {}).values()) + list((doc.get('travel_only') or {}).values()):
        p = _provenance(job)
        graphs[(p.get('input_hashes') or {}).get('graph')] += 1
        graph_ids[p.get('graph_id')] += 1
        hazards[(p.get('input_hashes') or {}).get('hazard')] += 1
        h = p.get('host') or {}
        hosts[(h.get('platform'), h.get('machine'))] += 1
        prov[(p.get('scenario_set_id'), p.get('input_time'), p.get('region'))] += 1
    if len(graphs) != 1 or len(graph_ids) != 1 or len(hazards) != 1 or len(prov) != 1:
        raise sources.InputIdentityError(f'{entry["path"]}: results do not share one graph/hazard/scenario set')
    (sset, itime, region), = prov
    if (sset, itime, region) != (doc['scenario_set_id'], doc['input_time'], doc['region_id']):
        raise sources.InputIdentityError(f'{entry["path"]}: result provenance differs from the file header')
    window = sources.hazard_window(doc['region_id'], doc['input_time'], next(iter(hazards)))

    # API wire plans (recorded fields) and the request geometry of every dispatch origin
    wire = {}
    for job in doc.get('plans') or []:
        req = job['request']
        dest_ids = [d['id'] for d in req['destinations']]
        dest_nodes = [d['location']['node_id'] for d in req['destinations']]
        dest_dwell = [pr.js_number(d.get('dwell_s', req.get('dwell_s'))) for d in req['destinations']]
        dest_window = [[pr.js_number(x) for x in d['window']] for d in req['destinations']]
        origin_nodes = {o['id']: o['location']['node_id'] for o in req['origins']}
        req_offsets = sorted({pr.js_number(x) for x in req['depart_offsets_s']})   # adapter.ts 262
        for wp in (job.get('result') or {}).get('plans') or []:
            if wp['origin_id'] in wire:
                raise ValueError(f'{wp["origin_id"]} appears in two dispatch plans')
            wire[wp['origin_id']] = {'plan': wp, 'dest_ids': dest_ids, 'dest_nodes': dest_nodes,
                                     'dest_dwell': dest_dwell, 'dest_window': dest_window,
                                     'entry_node': origin_nodes[wp['origin_id']], 'offsets': req_offsets}
    jobs = doc.get('route_checks') or {}

    records = []
    for o in origins:
        plan = plans[o['id']]
        cells = {c['offset_s']: cell_category(c) for c in plan['sweep']}
        attempts = [a for c in plan['sweep'] for a in c['attempts']]
        rec = {
            'scope': entry['scope'], 'region': doc['region_id'], 'input_time': doc['input_time'],
            'input_kst': sources.kst_label(doc['input_time']), 'scenario_set_id': doc['scenario_set_id'],
            'origin_id': o['id'], 'name': o['name'], 'name_en': o['name_en'], 'role': o['role'], 'category': o['category'],
            'origin_type': pr.origin_type(o), 'vulnerable': o['vulnerable'], 'checkable': o['checkable'],
            'note': plan.get('note'), 'best_verdict': plan['best_verdict'],
            'latest_s': plan['latest_safe_departure_s'], 'contiguous_s': plan['contiguous_safe_departure_s'],
            'deadline_category': deadline_category(plan['best_verdict'], plan['latest_safe_departure_s']),
            'cells': cells, 'n_attempts': len(attempts),
            'n_rechecked_attempts': sum(1 for a in attempts if a.get('recheck_of')),
            'unresolved_reasons': dict(Counter(a['reason_code'] or 'NONE' for a in attempts if a['verdict'] == pr.UNRESOLVED)),
            'entry_node': None, 'dest_nodes': None,
        }
        best = plan.get('best')
        rec['best_destination_id'] = best['destination_id'] if best else None
        rec['best_arrival_s'] = best['arrival_s'] if best else None
        rec['best_job_id'] = best['job_id'] if best else None
        w = wire.get(o['id'])
        if w is not None:
            rec['entry_node'], rec['dest_nodes'] = w['entry_node'], list(w['dest_nodes'])
            rec['dest_ids'], rec['dest_dwell_s'], rec['dest_window'] = list(w['dest_ids']), w['dest_dwell'], w['dest_window']
            recorded = api_rules.recorded_fields(w['plan'])
            api_rule = api_rules.api_rule_fields(w['plan'], w['dest_ids'])
            original = pr.adapt_origin_plan(w['plan'], w['offsets'])  # planner rules, re-checks NOT applied
            rec['api'] = {
                'recorded': recorded, 'api_rule_on_original': api_rule,
                'planner_rule_on_original': {'best_verdict': original['best_verdict'],
                                             'latest_s': original['latest_safe_departure_s'],
                                             'contiguous_s': original['contiguous_safe_departure_s']},
                'planner_displayed': {'best_verdict': plan['best_verdict'], 'latest_s': plan['latest_safe_departure_s'],
                                      'contiguous_s': plan['contiguous_safe_departure_s']},
            }
        elif o['role'] == 'research_origin':
            rc_jobs = [jobs[a['job_id']] for a in attempts if a['job_id'] and a['job_id'] in jobs]
            if rc_jobs:
                rec['entry_node'] = rc_jobs[0]['request']['start']['node_id']
                rec['dest_nodes'] = [rc_jobs[0]['request']['destination']['node_id']]
        records.append(rec)

    # travel-time-only comparisons of OSM origins (cache.ts 250-258 already dropped stale ones)
    pairs = []
    for rec in records:
        if rec['origin_type'] not in ('village', 'care_facility') or rec['best_job_id'] is None:
            continue
        t = model['travel_only'].get(rec['origin_id'])
        pair = {'scope': rec['scope'], 'region': rec['region'], 'input_time': rec['input_time'],
                'origin_id': rec['origin_id'], 'origin_type': rec['origin_type'], 'name': rec['name'],
                'name_en': rec['name_en'],
                'depart_offset_s': rec['latest_s'], 'destination_id': rec['best_destination_id'],
                'destination_node': rec['dest_nodes'][rec['dest_ids'].index(rec['best_destination_id'])],
                'checked_arrival_s': rec['best_arrival_s'], 'has_comparison': t is not None}
        if t is not None:
            tj, cj = t['job'], jobs[rec['best_job_id']]
            tres = tj['result']
            fpa = tres.get('full_policy_assessment') or {}
            contact_members = sorted(e['scenario_id'] for e in tres.get('exposure') or [] if e.get('contact') is True)
            pair.update({
                'same_start_destination_offset': (tj['request']['start'] == cj['request']['start'] and
                                                  tj['request']['destination'] == cj['request']['destination'] and
                                                  tj['request']['depart_offset_s'] == rec['latest_s']),
                'fastest_verdict_own_policy': tres.get('verdict'), 'fastest_policy': tres.get('policy'),
                'fastest_arrival_s': pr.js_num(tres.get('arrival_s')),
                'fastest_contact_members': len(contact_members),
                'fastest_whole_road_contact': fpa.get('whole_road_contact'),
                'fastest_passes_full_policy': fpa.get('passes_full_centre_and_contact'),
                'fastest_violations': sorted({v.get('constraint') for v in fpa.get('violations') or []}),
                'checked_edge_ids': list(_route_props(cj).get('edge_ids') or []),
                'fastest_edge_ids': list(_route_props(tj).get('edge_ids') or []),
                'checked_waits': len(_route_props(cj).get('waits') or []),
            })
            pair['fastest_meets_flames'] = pair['fastest_contact_members'] > 0
            pair['extra_arrival_s'] = (pair['checked_arrival_s'] - pair['fastest_arrival_s']
                                       if pair['fastest_arrival_s'] is not None and pair['checked_arrival_s'] is not None else None)
        pairs.append(pair)

    meta = {
        'scope': entry['scope'], 'region': doc['region_id'], 'input_time': doc['input_time'],
        'input_kst': sources.kst_label(doc['input_time']), 'scenario_set_id': doc['scenario_set_id'],
        'cache_file': sources.rel(entry['abs_path']), 'cache_sha256': entry['sha256'],
        'created_at': doc.get('created_at'), 'api_version': (doc.get('api') or {}).get('health', {}).get('api_version'),
        'purpose': doc['generator'].get('purpose'), 'step_min': step_min,
        'shelters_per_origin': doc['generator'].get('shelters_per_origin'),
        'host': [{'platform': k[0], 'machine': k[1], 'results': v} for k, v in sorted(hosts.items())],
        'graph_sha256': next(iter(graphs)), 'graph_id': next(iter(graph_ids)), 'hazard_sha256': next(iter(hazards)),
        'hazard_file': window['path'], 'valid_from_s': window['valid_from'], 'valid_until_s': window['valid_until'],
        'dt_s': window['dt'],
        'route_check_records': len(jobs),
        'recheck_records': sum(1 for j in jobs.values() if j.get('recheck_of')),
        'dispatch_attempt_records': sum(1 for j in jobs.values() if j.get('parent_job_id') and not j.get('recheck_of')),
        'research_route_check_records': sum(1 for r in doc.get('research_checks') or [] if r.get('job_id') in jobs),
        'destination_ids': sorted({d['id'] for req in doc.get('requests') or [] for d in req['destinations']}),
        'travel_only_records': len(doc.get('travel_only') or {}),
        'dispatch_plans': len(doc.get('plans') or []), 'research_checks': len(doc.get('research_checks') or []),
        'rejected_requests': len(doc.get('rejected_requests') or []),
        'tie_breaks': pr.TieCounter.n,
    }
    if meta['dispatch_attempt_records'] + meta['recheck_records'] + meta['research_route_check_records'] != meta['route_check_records']:
        raise ValueError(f'{entry["path"]}: route checks are not dispatch attempts + re-checks + research checks')
    del doc, model, plans
    gc.collect()
    return {'records': records, 'pairs': pairs, 'meta': meta}


def graph_metrics_for_region(region: str, metas: list[dict], records: list[dict], pairs: list[dict]) -> tuple[list, dict]:
    """On the exact graph the API used: road redundancy (+ the common-edge chain of single-path places), fire-free
    fastest trip times to every candidate destination, and the route lengths of the travel-only pairs."""
    shas = {m['graph_sha256'] for m in metas}
    ids = {m['graph_id'] for m in metas}
    dts = {m['dt_s'] for m in metas}
    if len(shas) != 1 or len(ids) != 1 or len(dts) != 1:
        raise sources.InputIdentityError(f'{region}: cache files used different graphs / time steps {shas} {dts}')
    dt = dts.pop()
    dt = int(dt) if float(dt).is_integer() else dt    # whole-second ticks stay integers
    path = sources.verify_graph(region, shas.pop(), ids.pop())
    graph = RoadGraph(path)
    solver = RedundancySolver(graph)
    places: dict[str, dict] = {}
    for r in records:
        if r['entry_node'] is None:
            continue
        key = r['origin_id']
        geo = (r['entry_node'], tuple(r['dest_nodes']))
        if key in places:
            if places[key]['geo'] != geo:
                raise ValueError(f'{key}: different entry/destinations across input times')
            continue
        places[key] = {'geo': geo, 'rec': r}
    rows, trips = [], {}
    for key, p in sorted(places.items()):
        entry, dests = p['geo']
        o = graph.node_index[entry]
        dn = [graph.node_index[d] for d in dests]
        ta, cut, common = solver.turn_aware(o, dn, chain=True)
        pl = solver.plain(o, dn)
        t = fastest_trips(graph, o, dn)
        trips[key] = {dests[i]: (None if t[dn[i]] is None else t[dn[i]] * dt) for i in range(len(dn))}
        r = p['rec']
        row = {'region': region, 'origin_id': key, 'name': r['name'], 'name_en': r['name_en'],
               'origin_type': r['origin_type'],
               'entry_node': entry, 'dest_nodes': list(dests), 'entry_out_degree': len(graph.out_edges[o]),
               'turn_aware_paths': ta, 'plain_paths': pl, 'cut_edges': cut,
               'cut_source_ways': sorted({graph.source_way[graph.edge_index[e]] for e in cut}),
               'cut_at_entry_node': all(graph.eu[graph.edge_index[e]] == o for e in cut),
               'trip_by_dest_s': trips[key], 'common_edges': None, 'shared_stretch_m': None}
        if common is not None:
            if graph.edge_ids[common[0]] not in cut:
                raise AssertionError(f'{key}: first common edge is not the source-side minimum cut')
            row['common_edges'] = [graph.edge_ids[e] for e in common]
            row['shared_stretch_m'] = walk_length_to_edge_end(graph, o, common[-1])
        rows.append(row)
    for pair in pairs:
        if pair['region'] != region or not pair.get('has_comparison'):
            continue
        for k in ('checked', 'fastest'):
            eids = pair.pop(f'{k}_edge_ids')
            pair[f'{k}_length_m'] = sum(graph.edge_length_m(graph.edge_index[e]) for e in eids)
            pair[f'{k}_edges'] = len(eids)
        pair['extra_length_m'] = pair['checked_length_m'] - pair['fastest_length_m']
        node = pair['destination_node']
        pair['trip_model_s'] = trips[pair['origin_id']][node]
    graph_info = {'region': region, 'graph_file': sources.rel(path), 'graph_sha256': sources.sha256_file(path),
                  'graph_id': graph.revision, 'nodes': len(graph.node_ids), 'edges': len(graph.edge_ids),
                  'forbidden_turns': len(graph.forbidden), 'allowed_turns': solver.allowed_turns}
    del solver, graph
    gc.collect()
    return rows, graph_info


def classify_window(records: list[dict], metas: list[dict], redundancy: list[dict]) -> None:
    """Per village/care-facility cell: could ANY checked route exist at this departure inside the scenario window if
    there were no fire at all? fits(t) = some candidate destination d with
    t + fastest fire-free trip(d) + required stay(d) <= min(window close(d), hazard valid_until).
    Planner verdicts are unchanged; this is an extra classification ("window-limited" when nothing fits)."""
    window = {m['scope']: m for m in metas}
    trips = {(x['region'], x['origin_id']): x['trip_by_dest_s'] for x in redundancy}
    for r in records:
        if r['origin_type'] not in ('village', 'care_facility'):
            continue
        m = window[r['scope']]
        t_by_dest = trips[(r['region'], r['origin_id'])]
        r['trip_by_dest_s'] = t_by_dest
        r['trip_min_s'] = min(v for v in t_by_dest.values() if v is not None)
        offsets = sorted(r['cells'])
        if any(win[0] != 0 for win in r['dest_window']):   # kit: also a <= arrival; with a = 0 it always holds
            raise AssertionError(f'{r["scope"]} {r["origin_id"]}: a destination window opens after 0 s')
        fits = {}
        for t in offsets:
            fits[t] = any(t_by_dest[node] is not None and
                          t + t_by_dest[node] + dwell <= min(win[1], m['valid_until_s']) and t >= m['valid_from_s']
                          for node, dwell, win in zip(r['dest_nodes'], r['dest_dwell_s'], r['dest_window']))
            if r['cells'][t] == pr.CHECKED and not fits[t]:
                raise AssertionError(f'{r["scope"]} {r["origin_id"]} +{t}s: checked although no fire-free trip fits')
        r['fits'] = fits
        later = [t for t in offsets if r['latest_s'] is not None and t > r['latest_s']]
        if r['latest_s'] is None:
            r['deadline_set_by'] = None
        elif not later:
            r['deadline_set_by'] = 'grid_end'           # still checked at the last checked departure
        else:
            r['deadline_set_by'] = 'fire_or_limits' if fits[later[0]] else 'window'


def run(with_graphs: bool = True) -> dict:
    entries = sources.load_index()
    places = {r: [pr.place_from_properties(p) for p in sources.load_places(r)] for r in sources.REGIONS}
    records, pairs, metas = [], [], []
    for e in entries:
        out = analyse_file(e, places[e['region_id']])
        records += out['records']
        pairs += out['pairs']
        metas.append(out['meta'])
    redundancy, graphs = [], []
    if with_graphs:
        for region in sources.REGIONS:
            rows, info = graph_metrics_for_region(region, [m for m in metas if m['region'] == region],
                                                  [r for r in records if r['region'] == region], pairs)
            redundancy += rows
            graphs.append(info)
        classify_window(records, metas, redundancy)
    return {'entries': entries, 'records': records, 'pairs': pairs, 'metas': metas, 'redundancy': redundancy,
            'graphs': graphs}
