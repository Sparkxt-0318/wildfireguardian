"""Path B: an independent recomputation of every number in NUMBERS.json (pandas + networkx).

Deliberately different from path A (``planner_rules`` / ``analysis`` / ``maxflow`` / ``numbers``), whose code this
module does not import:

* attempts are rebuilt from the cache's ``route_checks`` (each check's OWN request - start node, destination node,
  ``depart_offset_s`` - and its own result), not from the dispatch plans' ``attempts`` arrays; origin and destination
  ids come from the top-level ``requests`` list by node id; a re-check (``recheck_of``) replaces its original. Its
  request must equal the original's apart from ``client_ref`` and the incurred dose: in all 279 recorded re-checks the
  original omits ``incurred_dose_kj_m2`` and the re-check sends an explicit 0, the API's default for an omitted value,
  and the API's recorded ``provenance.input_hashes.request`` is identical for every original/re-check pair (checked
  below);
* research origins come from ``research_checks`` with verdicts looked up in ``route_checks``;
* cell verdicts, deadlines and contiguity are pandas group-by / cumulative operations;
* the fastest route's flame contact is read from ``full_policy_assessment.per_scenario[*].contact`` (path A reads
  ``exposure[*].contact``); failing the full policy from a non-empty ``violations`` list (path A:
  ``passes_full_centre_and_contact``); arrivals from the last ``times_s`` entry (path A: ``arrival_s``); route length
  from consecutive ``node_ids`` (path A: ``edge_ids``);
* road redundancy with networkx's Edmonds-Karp on graphs built here (path A: its own max-flow); the road segments
  shared by every route are grown on networkx's residual network (path A: its own residual arrays);
* fastest fire-free trips and shared-stretch lengths with networkx's Dijkstra on a turn-expanded graph built here
  (path A: its own heap Dijkstra); the scenario window is read from each HAZARD.json here (path A: ``sources``);
* origin types read directly from ``places.geojson`` properties.
Only file locations and SHA-256 checks are shared (``sources``).
"""
from __future__ import annotations

import gc
import json
import warnings
from collections import defaultdict

import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.flow import build_residual_network, edmonds_karp

from . import sources

CH, NR, UN, WIN = 'checked_route', 'model_no_route', 'unresolved', 'window_unsatisfiable'


# ------------------------------------------------------------------------------------------------ places

def places_frame(region: str) -> pd.DataFrame:
    fc = json.loads(sources.places_path(region).read_text(encoding='utf-8'))
    rows = []
    for f in fc['features']:
        p = f['properties']
        checkable = p.get('checkable', True) is not False
        if p['role'] not in ('origin', 'research_origin'):
            continue
        kind = ('not_checkable' if not checkable else 'research' if p['role'] == 'research_origin'
                else 'care_facility' if p.get('vulnerable') is True else 'village')
        rows.append({'region': region, 'origin_id': p['id'], 'role': p['role'], 'kind': kind,
                     'scenario_set_id': p.get('scenario_set_id')})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ one cache file

def _verdict(job: dict) -> str:
    if job.get('status') != 'done' or not isinstance(job.get('result'), dict):
        return UN
    v = job['result'].get('verdict')
    return v if v in (CH, NR, UN) else UN


def _times_end(job: dict):
    t = ((((job.get('result') or {}).get('route') or {}).get('properties') or {}).get('times_s')) or []
    return t[-1] if t else None


def _request_identity(req: dict) -> str:
    """A request without client_ref and with the API's documented default for an omitted incurred dose
    (api/README.md: omitted fields get the defaults ... incurred_dose_kj_m2 0)."""
    r = {k: v for k, v in req.items() if k != 'client_ref'}
    r.setdefault('incurred_dose_kj_m2', 0)
    return json.dumps(r, sort_keys=True)


def checks_frame(doc: dict) -> pd.DataFrame:
    rows = []
    for key, j in doc['route_checks'].items():
        req = j['request']
        rows.append({'key': key, 'job_id': j['job_id'], 'recheck_of': j.get('recheck_of') or None,
                     'start': req['start']['node_id'], 'dest': req['destination']['node_id'],
                     'offset': int(req['depart_offset_s']), 'verdict': _verdict(j),
                     'reason': (j.get('result') or {}).get('reason_code') if _verdict(j) == UN else None,
                     'arrival_end': _times_end(j) if _verdict(j) == CH else None,
                     'req_cmp': _request_identity(req),
                     'req_hash': (((j.get('result') or {}).get('provenance') or {}).get('input_hashes') or {}).get('request')})
    df = pd.DataFrame(rows)
    assert (df['key'] == df['job_id']).all()
    return df


def substitute_rechecks(checks: pd.DataFrame) -> pd.DataFrame:
    """Originals with each re-check's verdict/arrival/reason substituted (and a flag)."""
    orig = checks[checks['recheck_of'].isna()].copy()
    re = checks[checks['recheck_of'].notna()].set_index('recheck_of')
    assert re.index.is_unique, 'an attempt was re-checked twice'
    assert re.index.isin(orig['job_id']).all(), 're-check of an unknown attempt'
    m = orig['job_id'].isin(re.index)
    same_req = (orig.loc[m, 'req_cmp'].values == re.loc[orig.loc[m, 'job_id'], 'req_cmp'].values)
    assert same_req.all(), 'a re-check request differs from its original'
    same_hash = (orig.loc[m, 'req_hash'].values == re.loc[orig.loc[m, 'job_id'], 'req_hash'].values)
    assert same_hash.all() and orig.loc[m, 'req_hash'].notna().all(), 'a re-check request hash differs from its original'
    for col in ('verdict', 'reason', 'arrival_end'):
        orig.loc[m, col] = re.loc[orig.loc[m, 'job_id'], col].values
    orig.loc[m, 'eff_job'] = re.loc[orig.loc[m, 'job_id'], 'job_id'].values
    orig.loc[~m, 'eff_job'] = orig.loc[~m, 'job_id']
    orig['rechecked'] = m
    return orig


def cell_rule(g: pd.DataFrame) -> str:
    if g.empty:
        return UN
    if (g['verdict'] == CH).any():
        return CH
    if (g['verdict'] == NR).all():
        return NR
    return UN


def origin_summary(att: pd.DataFrame, offsets: dict, window: dict) -> pd.DataFrame:
    """att: origin_id, offset, dest, verdict ... ; offsets: origin -> requested offsets; window: origin -> skipped."""
    out = []
    for oid, offs in offsets.items():
        a = att[att['origin_id'] == oid]
        cells = {}
        for t in sorted(set(offs) | set(a['offset']) | set(window.get(oid, ()))):
            here = a[a['offset'] == t]
            cells[t] = WIN if (t in window.get(oid, ()) and here.empty) else cell_rule(here)
        s = pd.Series(cells).sort_index()
        checked = s[s == CH]
        latest = int(checked.index.max()) if len(checked) else None
        run = s[s != WIN]
        ok = (run == CH).astype(int).cumprod()
        contiguous = int(run.index[ok.values.astype(bool)].max()) if ok.any() else None
        if a.empty:
            best = UN
        elif (a['verdict'] == CH).any():
            best = CH
        elif (a['verdict'] == NR).all():
            best = NR
        else:
            best = UN
        bj = None
        if latest is not None:
            cand = a[(a['offset'] == latest) & (a['verdict'] == CH)].sort_values(['arrival_end', 'dest_id'])
            bj = cand.iloc[0]
        out.append({'origin_id': oid, 'best_verdict': best, 'latest_s': latest, 'contiguous_s': contiguous,
                    'cells': cells, 'n_attempts': len(a), 'n_rechecked': int(a['rechecked'].sum()) if len(a) else 0,
                    'reasons': a.loc[a['verdict'] == UN, 'reason'].fillna('NONE').value_counts().to_dict(),
                    'best_job': None if bj is None else bj['eff_job'], 'best_dest_node': None if bj is None else bj['dest'],
                    'best_start_node': None if bj is None else bj['start'],
                    'best_arrival': None if bj is None else bj['arrival_end']})
    return pd.DataFrame(out)


def analyse_file(entry: dict, places: pd.DataFrame) -> dict:
    doc = json.loads(entry['abs_path'].read_text(encoding='utf-8'))
    scope = entry['scope']
    checks = checks_frame(doc)
    # dispatch geometry from the top-level requests list (not from the plan jobs)
    o_node, dests, offs, detail = {}, {}, {}, {}
    for req in doc['requests']:
        for o in req['origins']:
            assert o['location']['node_id'] not in o_node
            o_node[o['location']['node_id']] = o['id']
            dests[o['id']] = {d['location']['node_id']: d['id'] for d in req['destinations']}
            offs[o['id']] = sorted({int(x) for x in req['depart_offsets_s']})
            # the fit rule below needs no wait for an opening: every destination window opens at 0
            assert all(float(d['window'][0]) == 0 for d in req['destinations']), 'a destination window opens late'
            detail[o['id']] = tuple((d['location']['node_id'], d.get('dwell_s', req['dwell_s']), d['window'][1])
                                    for d in req['destinations'])
    hz_sha = {((j.get('result') or {}).get('provenance') or {}).get('input_hashes', {}).get('hazard')
              for j in doc['route_checks'].values()}
    assert len(hz_sha) == 1
    hz_path = (sources.routing_data_root() / 'latest_inputs_try02' / 'packets' / entry['region_id'] /
               entry['path'].split('/')[-1][:-len('.json')] / 'HAZARD.json')
    assert sources.sha256_file(hz_path) == hz_sha.pop(), 'hazard packet differs from the API provenance'
    hz = json.loads(hz_path.read_text(encoding='utf-8'))
    research_jobs = {r['job_id'] for r in doc['research_checks'] if r.get('job_id')}
    results = {}
    for substitute in (True, False):
        if substitute:
            eff = substitute_rechecks(checks)
        else:
            eff = checks[checks['recheck_of'].isna()].copy()
            eff['eff_job'] = eff['job_id']
            eff['rechecked'] = False
        disp = eff[~eff['job_id'].isin(research_jobs)].copy()
        disp['origin_id'] = disp['start'].map(o_node)
        assert disp['origin_id'].notna().all(), 'a dispatch check whose start node is no requested origin'
        disp['dest_id'] = [dests[o][n] for o, n in zip(disp['origin_id'], disp['dest'])]
        # every origin x destination x offset exactly once
        assert not disp.duplicated(['origin_id', 'dest_id', 'offset']).any()
        assert len(disp) == sum(len(dests[o]) * len(offs[o]) for o in dests)
        summ = origin_summary(disp, offs, {})
        # research origins
        rrows, roffs, rwin = [], defaultdict(list), defaultdict(set)
        refused = {(r.get('origin_id'), r.get('depart_offset_s')) for r in doc['rejected_requests'] if r.get('kind') == 'route_check'}
        assert not refused, 'refused research requests are not expected in these files'
        byjob = eff.set_index('job_id')
        for r in doc['research_checks']:
            roffs[r['origin_id']].append(int(r['depart_offset_s']))
            if r.get('job_id'):
                x = byjob.loc[r['job_id']]
                rrows.append({'origin_id': r['origin_id'], 'offset': int(r['depart_offset_s']), 'dest_id': r['destination_id'],
                              'dest': x['dest'], 'start': x['start'], 'verdict': x['verdict'], 'reason': x['reason'],
                              'arrival_end': x['arrival_end'], 'eff_job': x['eff_job'], 'rechecked': x['rechecked']})
            elif r.get('skipped') in ('WINDOW_UNSATISFIABLE', 'window_unsatisfiable'):
                rwin[r['origin_id']].add(int(r['depart_offset_s']))
            else:
                raise AssertionError('research check without a job is not expected in these files')
        ratt = pd.DataFrame(rrows, columns=['origin_id', 'offset', 'dest_id', 'dest', 'start', 'verdict', 'reason',
                                            'arrival_end', 'eff_job', 'rechecked'])
        rsum = origin_summary(ratt, dict(roffs), dict(rwin))
        with warnings.catch_warnings():   # all-None columns in one frame; dtype behaviour fixed by pandas==2.2.3
            warnings.simplefilter('ignore', FutureWarning)
            both = pd.concat([summ, rsum], ignore_index=True)
        both['scope'] = scope
        both['region'] = entry['region_id']
        results[substitute] = both
        if substitute:
            disp_attempts = disp
    cases = results[True]
    orig = results[False].set_index('origin_id')
    kinds = places.set_index('origin_id')['kind']
    cases['kind'] = cases['origin_id'].map(kinds)
    assert cases['kind'].notna().all()
    cases['orig_best'] = cases['origin_id'].map(orig['best_verdict'])
    cases['orig_latest'] = cases['origin_id'].map(orig['latest_s'])
    cases['orig_contiguous'] = cases['origin_id'].map(orig['contiguous_s'])
    # recorded API fields (only use of the plan jobs in path B)
    rec = {}
    for job in doc['plans']:
        for p in job['result']['plans']:
            rec[p['origin_id']] = (p['best_verdict'], p['latest_checked_depart_offset_s'],
                                   p['latest_contiguous_checked_depart_offset_s'])
    cases['api_best'] = cases['origin_id'].map(lambda o: rec.get(o, (None,))[0])
    cases['api_latest'] = cases['origin_id'].map(lambda o: rec.get(o, (None, None))[1])
    cases['api_contiguous'] = cases['origin_id'].map(lambda o: rec.get(o, (None, None, None))[2])
    cases['entry_node'] = cases['origin_id'].map({v: k for k, v in o_node.items()})
    cases['dest_nodes'] = cases['origin_id'].map(lambda o: tuple(dests[o]) if o in dests else None)
    cases['dest_detail'] = cases['origin_id'].map(lambda o: detail.get(o))
    cases['valid_from'], cases['valid_until'] = float(hz['valid_from']), float(hz['valid_until'])
    # travel-only comparisons
    tos = []
    for _, c in cases[cases['kind'].isin(['village', 'care_facility']) & cases['latest_s'].notna()].iterrows():
        t = doc['travel_only'].get(c['origin_id'])
        row = {'scope': scope, 'region': entry['region_id'], 'origin_id': c['origin_id'], 'has': False,
               'latest': int(c['latest_s'])}
        if t is not None and int(t['request']['depart_offset_s']) == int(c['latest_s']) and \
                t['request']['start']['node_id'] == c['best_start_node'] and t['request']['destination']['node_id'] == c['best_dest_node']:
            fpa = t['result']['full_policy_assessment']
            bj = doc['route_checks'][c['best_job']]
            row.update({'has': True, 'members': sum(1 for v in fpa['per_scenario'].values() if v['contact'] is True),
                        'fails_full': len(fpa['violations']) > 0, 'fast_end': _times_end(t), 'checked_end': _times_end(bj),
                        'dest_node': t['request']['destination']['node_id'], 'depart': int(t['request']['depart_offset_s']),
                        'fast_nodes': t['result']['route']['properties']['node_ids'],
                        'checked_nodes': bj['result']['route']['properties']['node_ids']})
        tos.append(row)
    research_in_checks = checks['job_id'].isin(research_jobs)
    meta = {'scope': scope, 'region': entry['region_id'], 'route_checks': len(doc['route_checks']),
            'rechecks': int(checks['recheck_of'].notna().sum()), 'travel_only': len(doc['travel_only']),
            'dispatch_attempts': int((checks['recheck_of'].isna() & ~research_in_checks).sum()),
            'research_checks': int(research_in_checks.sum()),
            'graph_sha': {((j.get('result') or {}).get('provenance') or {}).get('input_hashes', {}).get('graph')
                          for j in doc['route_checks'].values()},
            'research_ids': set(roffs), 'dt': float(hz['dt']),
            'destinations': {d['id'] for req in doc['requests'] for d in req['destinations']}}
    del doc
    gc.collect()
    return {'cases': cases, 'travel': tos, 'meta': meta,
            'attempts': disp_attempts.assign(scope=scope, region=entry['region_id'])}


# ------------------------------------------------------------------------------------------------ redundancy

class NxRedundancy:
    def __init__(self, path):
        g = json.loads(path.read_text(encoding='utf-8'))
        self.coords = {n['id']: (float(n['x']), float(n['y'])) for n in g['nodes']}
        forb = {tuple(p) for p in g['forbidden_turns']}
        self.outs, self.ins, self.tail = defaultdict(list), defaultdict(list), {}
        for e in g['edges']:
            self.outs[e['u']].append(e['id'])
            self.ins[e['v']].append(e['id'])
            self.tail[e['id']] = e['u']
        L = nx.DiGraph()
        for e in g['edges']:
            (x0, y0), (x1, y1) = self.coords[e['u']], self.coords[e['v']]
            L.add_edge(('in', e['id']), ('out', e['id']), capacity=1, ticks=int(e['travel_ticks']),
                       chord=float(np.hypot(x1 - x0, y1 - y0)))
        for node in set(self.outs) | set(self.ins):
            for a in self.ins[node]:
                for b in self.outs[node]:
                    if (a, b) not in forb:
                        L.add_edge(('out', a), ('in', b))          # no capacity attribute = unbounded
        L.add_nodes_from(['S', 'T'])
        P = nx.DiGraph()
        for e in g['edges']:
            P.add_edge(e['u'], e['v'], capacity=1)
        P.add_node('T')
        del g
        self.L, self.P = L, P
        self.RL = build_residual_network(L, 'capacity')
        self.RP = build_residual_network(P, 'capacity')

    @staticmethod
    def _flow(G, R, s, t, arcs):
        inf = R.graph['inf']
        for u, v in arcs:
            R.add_edge(u, v, capacity=inf)
            R.add_edge(v, u, capacity=0)
        value = edmonds_karp(G, s, t, residual=R).graph['flow_value']
        for u, v in arcs:
            R.remove_edge(u, v)
            R.remove_edge(v, u)
        return value

    def turn_aware(self, entry, dests, chain=False):
        """(max-flow value, road edges every legal walk drives in walking order - value 1 only - or None)."""
        arcs = [('S', ('in', b)) for b in self.outs[entry]] + [(('out', a), 'T') for d in dests for a in self.ins[d]]
        R = self.RL
        for u, v in arcs:
            R.add_edge(u, v, capacity=R.graph['inf'])
            R.add_edge(v, u, capacity=0)
        value = edmonds_karp(self.L, 'S', 'T', residual=R).graph['flow_value']
        common = self._common_edges(R, 'S', 'T') if (chain and value == 1) else None
        for u, v in arcs:
            R.remove_edge(u, v)
            R.remove_edge(v, u)
        return value, common

    @staticmethod
    def _common_edges(R, s, t):
        """Grow the residual closure of s in networkx's residual network (flow attributes still set); each time it
        stops short of t, the single saturated arc leaving it is a road edge on every s-t walk."""
        seen, stack, blocked, chain = {s}, [s], [], []
        while True:
            while stack:
                u = stack.pop()
                for v, attr in R[u].items():
                    if v in seen:
                        continue
                    if attr['capacity'] - attr['flow'] > 0:
                        seen.add(v)
                        stack.append(v)
                    elif attr['capacity'] > 0:
                        blocked.append((u, v))
            if t in seen:
                return chain
            live = {(u, v) for u, v in blocked if v not in seen}
            assert len(live) == 1, live
            u, v = live.pop()
            assert u[0] == 'in' and v[0] == 'out' and u[1] == v[1], (u, v)
            chain.append(u[1])
            seen.add(v)
            stack.append(v)
            blocked = [x for x in blocked if x[1] not in seen]

    def _from_entry(self, entry, fn):
        arcs = [('S', ('in', b)) for b in self.outs[entry]]
        self.L.add_edges_from(arcs)
        try:
            return fn()
        finally:
            self.L.remove_edges_from(arcs)

    def trips(self, entry, dests):
        """Fastest fire-free legal travel time (ticks) to each destination node: networkx Dijkstra on the line graph."""
        dist = self._from_entry(entry, lambda: nx.single_source_dijkstra_path_length(
            self.L, 'S', weight=lambda u, v, d: d.get('ticks', 0)))
        return {x: min((dist[('out', a)] for a in self.ins[x] if ('out', a) in dist), default=None) for x in dests}

    def stretch(self, entry, last_edge):
        """Shortest legal-walk length (m) from the entry node to the end of last_edge."""
        return self._from_entry(entry, lambda: nx.dijkstra_path_length(
            self.L, 'S', ('out', last_edge), weight=lambda u, v, d: d.get('chord', 0.0)))

    def plain(self, entry, dests):
        return self._flow(self.P, self.RP, entry, 'T', [(d, 'T') for d in dests])

    def length(self, nodes):
        xy = np.array([self.coords[n] for n in nodes])
        return float(np.sqrt((np.diff(xy, axis=0) ** 2).sum(axis=1)).sum()) if len(xy) > 1 else 0.0


# ------------------------------------------------------------------------------------------------ numbers

def _put(out, key, value, num=None, den=None):
    assert key not in out, key
    out[key] = {'value': value, 'numerator': num, 'denominator': den}


def compute() -> dict:
    """Every number, keyed exactly as in NUMBERS.json: {key: {value, numerator, denominator}}."""
    entries = sources.load_index()
    places = pd.concat([places_frame(r) for r in sources.REGIONS], ignore_index=True)
    frames, travel, metas, attempts = [], [], [], []
    for e in entries:
        res = analyse_file(e, places[places['region'] == e['region_id']])
        frames.append(res['cases'])
        travel += res['travel']
        metas.append(res['meta'])
        attempts.append(res['attempts'])
    cases_all = pd.concat(frames, ignore_index=True)
    att_all = pd.concat(attempts, ignore_index=True)
    tr = pd.DataFrame(travel)
    out: dict[str, dict] = {}

    # redundancy (networkx) and route lengths
    red_rows = []
    for region in sources.REGIONS:
        shas = set().union(*[m['graph_sha'] for m in metas if m['region'] == region])
        assert len(shas) == 1
        path = sources.verify_graph(region, shas.pop())
        nr = NxRedundancy(path)
        geo = cases_all[(cases_all['region'] == region) & cases_all['entry_node'].notna()]
        geo = geo.drop_duplicates(['origin_id', 'entry_node', 'dest_nodes'])
        assert geo['origin_id'].is_unique
        dts = {m['dt'] for m in metas if m['region'] == region}
        assert len(dts) == 1
        dt = dts.pop()
        dt = int(dt) if dt.is_integer() else dt
        for _, g in geo.iterrows():
            dn = list(g['dest_nodes'])
            ta, common = nr.turn_aware(g['entry_node'], dn, chain=True)
            trip = nr.trips(g['entry_node'], dn)
            red_rows.append({'region': region, 'origin_id': g['origin_id'], 'kind': g['kind'], 'ta': ta,
                             'pl': nr.plain(g['entry_node'], dn), 'out_deg': len(nr.outs[g['entry_node']]),
                             'cut_at_entry': (nr.tail[common[0]] == g['entry_node']) if common else None,
                             'stretch': nr.stretch(g['entry_node'], common[-1]) if common else None,
                             'trip': {x: (None if v is None else v * dt) for x, v in trip.items()}})
        m = (tr['region'] == region) & tr['has']
        tr.loc[m, 'extra_len'] = [nr.length(c) - nr.length(f) for c, f in zip(tr.loc[m, 'checked_nodes'], tr.loc[m, 'fast_nodes'])]
        del nr
        gc.collect()
    red = pd.DataFrame(red_rows)

    osm = cases_all[cases_all['kind'].isin(['village', 'care_facility'])].copy()
    for t in sources.GRID_OFFSETS_S:
        osm[f'c{t}'] = osm['cells'].map(lambda c, t=t: c.get(t))
    file_scopes = [e['scope'] for e in entries]
    scopes = file_scopes + [f'{r}/pooled' for r in sources.REGIONS] + ['all/pooled']

    def pick(df, scope, col='scope', regcol='region'):
        reg, _, part = scope.partition('/')
        if part in ('pooled', 'places'):
            return df if reg == 'all' else df[df[regcol] == reg]
        return df[df[col] == scope]

    # records
    for mt in metas:
        _put(out, 'records.route_checks@' + mt['scope'], mt['route_checks'])
        _put(out, 'records.rechecks@' + mt['scope'], mt['rechecks'])
        _put(out, 'records.travel_only@' + mt['scope'], mt['travel_only'])
        _put(out, 'records.dispatch_attempts@' + mt['scope'], mt['dispatch_attempts'])
        _put(out, 'records.research_route_checks@' + mt['scope'], mt['research_checks'])
    _put(out, 'records.dispatch_attempts@all/pooled', sum(m['dispatch_attempts'] for m in metas))
    _put(out, 'records.research_route_checks@all/pooled', sum(m['research_checks'] for m in metas))
    _put(out, 'records.route_checks@all/pooled', sum(m['route_checks'] for m in metas))
    _put(out, 'records.rechecks@all/pooled', sum(m['rechecks'] for m in metas))
    _put(out, 'records.travel_only@all/pooled', sum(m['travel_only'] for m in metas))
    dcat = {}
    for region in sources.REGIONS:
        for f in json.loads(sources.places_path(region).read_text(encoding='utf-8'))['features']:
            dcat[(region, f['properties']['id'])] = f['properties']['category']
    for reg in list(sources.REGIONS) + ['all']:
        used = set().union(*[{(m['region'], x) for x in m['destinations']} for m in metas if reg == 'all' or m['region'] == reg])
        _put(out, f'destinations_used@{reg}/places', len(used))
        for c in ('school', 'community_hall', 'shelter'):
            _put(out, f'destinations_used.{c}@{reg}/places', sum(1 for u in used if dcat[u] == c))
    for reg in list(sources.REGIONS) + ['all']:
        p = places if reg == 'all' else places[places['region'] == reg]
        _put(out, f'osm_origins_listed@{reg}/places', int((p['role'] == 'origin').sum()))
        _put(out, f'osm_origins_not_checkable@{reg}/places', int(((p['role'] == 'origin') & (p['kind'] == 'not_checkable')).sum()))
        ids = set().union(*[m['research_ids'] for m in metas if reg == 'all' or m['region'] == reg])
        _put(out, f'research_origins@{reg}/places', len(ids))

    last = sources.GRID_OFFSETS_S[-1]
    for sc in scopes:
        for sub in ('', 'village', 'care_facility'):
            d = pick(osm, sc)
            if sub:
                d = d[d['kind'] == sub]
            if d.empty:
                continue
            tag = f'@{sc}' + (f'#{sub}' if sub else '')
            n = len(d)
            _put(out, 'cases' + tag, n)
            for v in (CH, NR, UN):
                k = int((d['best_verdict'] == v).sum())
                _put(out, f'best_verdict.{v}' + tag, k, k, n)
            lat = d['latest_s']
            for t in sources.GRID_OFFSETS_S:
                k = int((lat == t).sum())
                _put(out, f'deadline.latest_{t:04d}s' + tag, k, k, n)
            for v in (NR, UN):
                k = int((lat.isna() & (d['best_verdict'] == v)).sum())
                _put(out, f'deadline.none_{v}' + tag, k, k, n)
            k = int((d['c0'] != CH).sum())
            _put(out, 'no_checked_route_at_offset_0000s' + tag, k, k, n)
            k = int((lat.notna() & (lat < last)).sum())
            _put(out, 'window_closes_within_hour' + tag, k, k, n)
            k = int(lat.isna().sum())
            _put(out, 'no_checked_route_any_offset' + tag, k, k, n)
            k = int((d[f'c{last}'] != CH).sum())
            _put(out, f'not_checked_at_offset_{last:04d}s' + tag, k, k, n)
            if sub:
                continue
            for t in sources.GRID_OFFSETS_S:
                vc = d[f'c{t}'].value_counts()
                for v in (CH, NR, UN, WIN):
                    k = int(vc.get(v, 0))
                    _put(out, f'cell.{v}.offset_{t:04d}s' + tag, k, k, n)
            withroute = d[lat.notna()]
            k = int((withroute['contiguous_s'] != withroute['latest_s']).sum())
            _put(out, 'contiguous_differs_from_latest' + tag, k, k, len(withroute))
            a = pick(att_all, sc)
            a = a[a['origin_id'].isin(set(d['origin_id']))]
            na = len(a)
            _put(out, 'attempts' + tag, na)
            un = a[a['verdict'] == UN]['reason'].fillna('NONE')
            for code in ('AT_ISSUE_FAILURE', 'TIMEOUT'):
                k = int((un == code).sum())
                _put(out, f'attempts.unresolved.{code}' + tag, k, k, na)
            k = int((~un.isin(['AT_ISSUE_FAILURE', 'TIMEOUT'])).sum())
            _put(out, 'attempts.unresolved.other' + tag, k, k, na)

    # distinct places
    for reg in list(sources.REGIONS) + ['all']:
        for sub in ('', 'village', 'care_facility'):
            d = pick(osm, f'{reg}/places')
            if sub:
                d = d[d['kind'] == sub]
            if d.empty:
                continue
            tag = f'@{reg}/places' + (f'#{sub}' if sub else '')
            g = d.assign(no0=d['c0'] != CH, nolast=d[f'c{last}'] != CH,
                         closes=d['latest_s'].notna() & (d['latest_s'] < last), none=d['latest_s'].isna()
                         ).groupby(['region', 'origin_id'])[['no0', 'nolast', 'closes', 'none']].any()
            n = len(g)
            _put(out, 'places' + tag, n)
            for col, name in (('no0', 'places.no_checked_route_at_offset_0000s_any_input'),
                              ('nolast', f'places.not_checked_at_offset_{last:04d}s_any_input'),
                              ('closes', 'places.window_closes_within_hour_any_input'),
                              ('none', 'places.no_checked_route_any_offset_any_input')):
                k = int(g[col].sum())
                _put(out, name + tag, k, k, n)

    # API cross-check
    for sc in file_scopes + ['all/pooled']:
        d = pick(osm, sc)
        n = len(d)
        tag = '@' + sc

        def same(a, b):
            return (a == b) | (a.isna() & b.isna())
        rec_eq_orig = same(d['api_best'], d['orig_best']) & same(d['api_latest'], d['orig_latest']) & \
            same(d['api_contiguous'], d['orig_contiguous'])
        k = int(rec_eq_orig.sum())
        _put(out, 'api_check.recorded_equals_api_rule_on_original' + tag, k, k, n)
        _put(out, 'api_check.recorded_equals_planner_rule_on_original' + tag, k, k, n)
        eqs = {'latest_checked_depart_offset_s': same(d['api_latest'], d['latest_s']),
               'latest_contiguous_checked_depart_offset_s': same(d['api_contiguous'], d['contiguous_s']),
               'best_verdict': same(d['api_best'], d['best_verdict'])}
        for name, s in eqs.items():
            k = int(s.sum())
            _put(out, f'api_check.displayed_equals_recorded.{name}' + tag, k, k, n)
        _put(out, 'api_check.origins_with_rechecked_attempts' + tag, int((d['n_rechecked'] > 0).sum()))
        differs = ~(eqs['latest_checked_depart_offset_s'] & eqs['latest_contiguous_checked_depart_offset_s'] & eqs['best_verdict'])
        k = int((differs & (d['n_rechecked'] > 0) & rec_eq_orig).sum())
        _put(out, 'api_check.displayed_differs_explained_by_recheck' + tag, k, k, int(differs.sum()))

    # travel-only
    tr['meets'] = tr['has'] & (tr['members'].fillna(0) > 0)
    tr['extra_s'] = tr['checked_end'] - tr['fast_end']
    for sc in scopes:
        d = pick(tr, sc)
        tag = '@' + sc
        comp = d[d['has']]
        _put(out, 'travel_only.pairs' + tag, len(comp), len(comp), len(d))
        fl = comp[comp['meets']]
        _put(out, 'travel_only.fastest_meets_flames' + tag, len(fl), len(fl), len(comp))
        cl = comp[~comp['meets']]
        k = int((cl['extra_s'] == 0).sum())
        _put(out, 'travel_only.clear_pairs_equal_arrival' + tag, k, k, len(cl))
        if sc == 'all/pooled':
            for m in (1, 2, 3, 4):
                k = int((fl['members'] == m).sum())
                _put(out, f'travel_only.fastest_contact_members_{m}' + tag, k, k, len(fl))
            k = int(comp['fails_full'].sum())
            _put(out, 'travel_only.fastest_fails_full_policy' + tag, k, k, len(comp))
        if len(fl) and sc in ('all/pooled', 'uiseong_andong_2025/pooled'):
            for stat in ('min', 'median', 'max'):
                v = getattr(fl['extra_s'], stat)()
                _put(out, f'travel_only.extra_arrival_s.{stat}' + tag, int(v) if float(v).is_integer() else float(v))
                _put(out, f'travel_only.extra_length_m.{stat}' + tag, round(float(getattr(fl['extra_len'], stat)()), 1))
    hp = tr[tr['has']].drop_duplicates(['region', 'origin_id'])
    fp = tr[tr['meets']].drop_duplicates(['region', 'origin_id'])
    _put(out, 'travel_only.places_fastest_meets_flames_any_input@all/places', len(fp), len(fp), len(hp))

    # redundancy
    ro = red[red['kind'].isin(['village', 'care_facility'])]
    for reg in list(sources.REGIONS) + ['all']:
        for sub in ('', 'village', 'care_facility'):
            d = ro if reg == 'all' else ro[ro['region'] == reg]
            if sub:
                d = d[d['kind'] == sub]
            if d.empty:
                continue
            tag = f'@{reg}/places' + (f'#{sub}' if sub else '')
            n = len(d)
            _put(out, 'redundancy.places' + tag, n)
            for k in (1, 2, 3, '4plus'):
                for col, name in (('ta', 'turn_aware'), ('pl', 'plain')):
                    c = int((d[col] >= 4).sum()) if k == '4plus' else int((d[col] == k).sum())
                    _put(out, f'redundancy.{name}_paths_{k}' + tag, c, c, n)
            c = int((d['ta'] == 0).sum())
            _put(out, 'redundancy.zero_paths' + tag, c, c, n)
            c = int((d['ta'] == d['pl']).sum())
            _put(out, 'redundancy.turn_aware_equals_plain' + tag, c, c, n)
            single = d[d['ta'] == 1]
            c = int(single['cut_at_entry'].astype(bool).sum())
            _put(out, 'redundancy.single_cut_at_entry_node' + tag, c, c, len(single))
            _put(out, 'redundancy.entry_out_degree_1' + tag, int((d['out_deg'] == 1).sum()), int((d['out_deg'] == 1).sum()), n)
    cls = {(r['region'], r['origin_id']): r['ta'] for _, r in red.iterrows()}
    for name, f in (('rc1', lambda v: v == 1), ('rc2plus', lambda v: v >= 2)):
        d = osm[[f(cls[(r, o)]) for r, o in zip(osm['region'], osm['origin_id'])]]
        tag = f'@all/pooled#{name}'
        _put(out, 'redundancy_x.cases' + tag, len(d))
        k = int((d['c0'] != CH).sum())
        _put(out, 'redundancy_x.no_checked_route_at_offset_0000s' + tag, k, k, len(d))
        k = int((d[f'c{last}'] != CH).sum())
        _put(out, f'redundancy_x.not_checked_at_offset_{last:04d}s' + tag, k, k, len(d))
    # ---- scenario window: could the departure be checked at all if there were no fire?
    trip_of = {(r['region'], r['origin_id']): r['trip'] for _, r in red.iterrows()}

    def fits_at(case, t):
        trip = trip_of[(case['region'], case['origin_id'])]
        return any(trip[node] is not None and t >= case['valid_from'] and
                   t + trip[node] + dwell <= min(close, case['valid_until']) for node, dwell, close in case['dest_detail'])
    for t in sources.GRID_OFFSETS_S:
        osm[f'f{t}'] = [fits_at(c, t) for _, c in osm.iterrows()]
        assert not ((osm[f'c{t}'] == CH) & ~osm[f'f{t}']).any(), 'checked although no fire-free trip fits'
    osm['trip_min'] = [min(v for v in trip_of[(r, o)].values() if v is not None) for r, o in zip(osm['region'], osm['origin_id'])]

    def set_by(case):
        if pd.isna(case['latest_s']) or case['latest_s'] >= last:
            return None
        nxt = min(t for t in sources.GRID_OFFSETS_S if t > case['latest_s'])
        return 'fire_or_limits' if case[f'f{nxt}'] else 'window'
    osm['set_by'] = [set_by(c) for _, c in osm.iterrows()]
    for sc in scopes:
        for sub in ('', 'village', 'care_facility'):
            d = pick(osm, sc)
            if sub:
                d = d[d['kind'] == sub]
            if d.empty:
                continue
            tag = f'@{sc}' + (f'#{sub}' if sub else '')
            n = len(d)
            closes = d[d['latest_s'].notna() & (d['latest_s'] < last)]
            for by in ('window', 'fire_or_limits'):
                k = int((closes['set_by'] == by).sum())
                _put(out, f'deadline_set_by.{by}' + tag, k, k, len(closes))
                for t in sources.GRID_OFFSETS_S[:-1]:
                    k = int(((d['latest_s'] == t) & (d['set_by'] == by)).sum())
                    _put(out, f'deadline.latest_{t:04d}s.set_by_{by}' + tag, k, k, n)
            none = d[d['latest_s'].isna()]
            k = int(none['f0'].sum())
            _put(out, 'no_checked_route_any_offset.trip_fits_at_offset_0000s' + tag, k, k, len(none))
            if sub:
                continue
            for t in sources.GRID_OFFSETS_S:
                lim, fit = d[~d[f'f{t}']], d[d[f'f{t}']]
                _put(out, f'window_limited.offset_{t:04d}s' + tag, len(lim), len(lim), n)
                notc = d[d[f'c{t}'] != CH]
                k = int((~notc[f'f{t}']).sum())
                _put(out, f'window_limited_among_not_checked.offset_{t:04d}s' + tag, k, k, len(notc))
                k = int((fit[f'c{t}'] != CH).sum())
                _put(out, f'not_checked_although_fits.offset_{t:04d}s' + tag, k, k, len(fit))
                for v in (NR, UN):
                    for cls, grp in (('fits', fit), ('limited', lim)):
                        k = int((grp[f'c{t}'] == v).sum())
                        _put(out, f'cell_window.{v}.{cls}.offset_{t:04d}s' + tag, k, k, n)
    for reg in list(sources.REGIONS) + ['all']:
        for sub in ('', 'village', 'care_facility'):
            d = pick(osm, f'{reg}/places')
            if sub:
                d = d[d['kind'] == sub]
            if d.empty:
                continue
            tag = f'@{reg}/places' + (f'#{sub}' if sub else '')
            g = d.assign(nl=d[f'c{last}'] != CH, nlf=(d[f'c{last}'] != CH) & d[f'f{last}'],
                         anyf=pd.concat([(d[f'c{t}'] != CH) & d[f'f{t}'] for t in sources.GRID_OFFSETS_S], axis=1).any(axis=1),
                         lim_last=~d[f'f{last}']).groupby(['region', 'origin_id']).agg(
                nl=('nl', 'any'), nlf=('nlf', 'any'), anyf=('anyf', 'any'), lim_last=('lim_last', 'all'),
                lim_last_any=('lim_last', 'any'), tmin=('trip_min', 'min'), tmax=('trip_min', 'max'))
            assert (g['lim_last'] == g['lim_last_any']).all() and (g['tmin'] == g['tmax']).all()
            k = int(g['nlf'].sum())
            _put(out, f'places.not_checked_although_fits_at_offset_{last:04d}s_any_input' + tag, k, k, int(g['nl'].sum()))
            k = int(g['anyf'].sum())
            _put(out, 'places.not_checked_although_fits_any_offset_any_input' + tag, k, k, len(g))
            k = int(g['lim_last'].sum())
            _put(out, f'places.window_limited_at_offset_{last:04d}s' + tag, k, k, len(g))
            for stat in ('min', 'median', 'max'):
                v = float(getattr(g['tmin'], stat)())
                _put(out, f'fastest_trip_s.{stat}' + tag, int(v) if v.is_integer() else v)
    comp = tr[tr['has']]
    trip_ok = [trip_of[(r, o)][dn] == fe - dep for r, o, dn, fe, dep in
               zip(comp['region'], comp['origin_id'], comp['dest_node'], comp['fast_end'], comp['depart'])]
    _put(out, 'trip_model.equals_travel_only@all/pooled', int(sum(trip_ok)), int(sum(trip_ok)), len(comp))
    for sc in ('all/pooled', 'uiseong_andong_2025/pooled'):
        d = pick(tr[tr['has']], sc)
        for name, sel in (('leave_by_3000s', d['latest'] == last), ('leave_by_before_3000s', d['latest'] < last)):
            grp = d[sel]
            k = int(grp['meets'].sum())
            _put(out, f'travel_only.fastest_meets_flames@{sc}#{name}', k, k, len(grp))
    one = red[red['kind'].isin(['village', 'care_facility']) & (red['ta'] == 1)]
    for reg in list(sources.REGIONS) + ['all']:
        d = one if reg == 'all' else one[one['region'] == reg]
        tag = f'@{reg}/places'
        for stat in ('min', 'median', 'max'):
            _put(out, f'redundancy.shared_stretch_m.{stat}' + tag, round(float(getattr(d['stretch'].astype(float), stat)()), 1))
        k = int((d['stretch'] <= 100.0).sum())
        _put(out, 'redundancy.shared_stretch_within_100m' + tag, k, k, len(d))
    return out, {'cases': osm, 'red': red, 'travel': tr}
