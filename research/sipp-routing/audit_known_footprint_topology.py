"""Read-only source-support/turn-topology census, never a timed contact planner.

Large graphs run one at a time under HEAVY. No source mask, source horizon,
trajectory, frozen graph/request, policy adapter or solver is changed here.
"""
from __future__ import annotations

import argparse
import collections
from datetime import datetime, timezone
import fcntl
from fractions import Fraction as F
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experimental/sipp-routing/src'))
from wfg_sipp.geometry import edge_occupancies, node_cell

PRIOR = ROOT / 'research/sipp-routing/full-member-support-census-20261030/RESULTS.json'
PRIOR_SHA = '87bf592ae3f3ed674fb21d6b4707083d9bcdd0f5cac429af8a3c9b30f16f756c'
CASES = ROOT / 'research/sipp-routing/native-panel-20261030/CASES.json'
DEADLINE_S = 90
RSS_MIB = 3072


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def pin(path, expected):
    actual = sha(path)
    if actual != expected:
        raise ValueError('Source identity changed: ' + str(path))
    return actual


def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def header(stream):
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        return np.lib.format.read_array_header_1_0(stream)
    if version == (2, 0):
        return np.lib.format.read_array_header_2_0(stream)
    raise ValueError('Unsupported saved NPY version')


def source_mask(domain, window):
    """Read original slot0 only; immutable full-N census proves mask equality."""
    path = Path(window['npz'])
    pin(path, window['npz_sha256'])
    record_path = next(path.parent.glob('FORECAST_RECORD_*.json'))
    pin(record_path, window['record_sha256'])
    record = load(record_path)
    with zipfile.ZipFile(path) as archive, archive.open('trajectory_first_burn_hour.npy') as stream:
        shape, fortran, dtype = header(stream)
        if fortran or dtype != np.dtype('int16') or tuple(shape) != tuple(window['shape']):
            raise ValueError('Saved source header changed')
        size = shape[1] * shape[2] * dtype.itemsize
        if size > 1 << 20:
            raise ValueError('One-member tiny-array guard')
        raw = stream.read(size)
        if len(raw) != size:
            raise ValueError('Incomplete original member')
        first = np.frombuffer(raw, dtype=dtype).reshape(shape[1:])
    with np.load(path, allow_pickle=False) as arrays:
        current_valid = arrays['source_burned_area_valid']
        affine = arrays['affine_transform'].ravel()[:6]
    if current_valid.dtype != np.bool_ or current_valid.shape != first.shape:
        raise ValueError('Cutoff validity shape/dtype')
    w = domain['existing_integer_window']
    sl = (slice(w['r0'], w['r1'] + 1), slice(w['c0'], w['c1'] + 1)) if w else (slice(None), slice(None))
    trajectory_unknown = first[sl] == -2
    if list(trajectory_unknown.shape) != domain['grid_shape']:
        raise ValueError('Existing declared-domain view differs')
    if not domain['all_saved_unknown_masks_byte_equal'] or domain['checked_members'] != 1024:
        raise ValueError('No complete shared-mask proof')
    if hashlib.sha256(trajectory_unknown.tobytes()).hexdigest() not in domain['distinct_unknown_mask_sha256']:
        raise ValueError('Original slot0 mask differs from complete saved-N census')
    effective = trajectory_unknown | ~current_valid[sl]
    horizon = F(record['trajectory_horizon_hours']) * 3600
    if horizon.denominator != 1 or horizon <= 0:
        raise ValueError('Positive whole-second saved horizon required')
    return effective[::-1].ravel(), dict(
        source_npz=str(path), source_npz_sha256=window['npz_sha256'],
        record=str(record_path), record_sha256=window['record_sha256'],
        cutoff_utc=record['cutoff_utc'], source_clock=record['clock'],
        source_horizon_s=int(horizon), valid_time_s=[0, int(horizon)],
        raw_source_affine=list(map(float, affine)), source_epsg=record['epsg'],
        trajectory_unknown_cells=int(trajectory_unknown.sum()),
        cutoff_invalid_cells=int((~current_valid[sl]).sum()),
        combined_unknown_cells=int(effective.sum()),
        combined_south_up_mask_sha256=hashlib.sha256(effective[::-1].tobytes()).hexdigest(),
        mask_scope='Original slot0 bytes plus unchanged full-N shared-mask proof, not a replicated member',
        never_semantics='-1 is no ignition through source horizon only; later time is unknown',
        base_seed=window['base_seed'], batch_size=window['trajectory_batch_size'])


def spatial_flags(graph, masks):
    """Exact footprint support. Rectangle shortcut proves a sufficient subset;
    mixed rectangles use the original exact rational occupancy function.
    """
    grid = graph['grid']
    H, W = grid['height'], grid['width']
    if not isinstance(H, int) or not isinstance(W, int) or H <= 0 or W <= 0 or F(grid['resolution']) <= 0:
        raise ValueError('Invalid grid')
    nodes = {n['id']: n for n in graph['nodes']}
    edges = graph['edges']
    if len(nodes) != len(graph['nodes']) or len({e['id'] for e in edges}) != len(edges):
        raise ValueError('Duplicate graph identity')
    node_cells = []
    for node in nodes.values():
        x = math.floor((F(node['x']) - F(grid['x0'])) / F(grid['resolution']))
        y = math.floor((F(node['y']) - F(grid['y0'])) / F(grid['resolution']))
        if not 0 <= x < W or not 0 <= y < H:
            raise ValueError('Outside node cannot acquire support')
        node_cells.append(node_cell(graph, node))
    order = {n: i for i, n in enumerate(nodes)}
    masks = np.asarray(masks)
    if masks.dtype != np.bool_ or masks.ndim != 2 or masks.shape[1] != H * W:
        raise ValueError('Boolean south-up masks required')
    node_known = ~masks[:, node_cells]
    edge_known = np.zeros((len(masks), len(edges)), dtype=bool)
    methods = collections.Counter()
    for j, edge in enumerate(edges):
        D = edge['travel_ticks']
        if isinstance(D, bool) or not isinstance(D, int) or D <= 0:
            raise ValueError('Positive integer travel ticks required')
        a, b = node_cells[order[edge['u']]], node_cells[order[edge['v']]]
        ar, ac = divmod(a, W); br, bc = divmod(b, W)
        exact = None
        for k, mask in enumerate(masks):
            if mask[a] or mask[b]:
                methods['unknown_endpoint'] += 1
                continue
            rect = mask.reshape(H, W)[min(ar, br):max(ar, br) + 1, min(ac, bc):max(ac, bc) + 1]
            if not rect.any():
                edge_known[k, j] = True
                methods['known_closed_rectangle'] += 1
                continue
            if exact is None:
                exact = sorted({o['cell'] for o in edge_occupancies(edge, 0, 1, graph=graph, node_lookup=nodes)})
                if any(not 0 <= c < H * W for c in exact):
                    raise ValueError('Outside exact occupancy')
            edge_known[k, j] = not mask[exact].any()
            methods['exact_mixed_rectangle'] += 1
    return node_known, edge_known, dict(methods)


def topology(graph, request, node_known, edge_known):
    """Static turn-aware reachability, ignoring flame times and all path costs.

    A positive result is only a supported directed topology witness; it is
    neither a timed journey nor a contact-safe/optimal/operational route.
    """
    nodes = {n['id']: i for i, n in enumerate(graph['nodes'])}
    edges = graph['edges']; ids = {e['id']: i for i, e in enumerate(edges)}
    origin = request['position'].get('node')
    if origin not in nodes:
        raise ValueError('Only exact node-start topology scope')
    outgoing = collections.defaultdict(list)
    for j, e in enumerate(edges):
        if edge_known[j]:
            outgoing[e['u']].append(j)
    forbidden = {tuple(pair) for pair in graph['forbidden_turns']}
    incoming = request['incoming_edge']
    if incoming is not None and incoming not in ids:
        raise ValueError('Incoming turn history identity')
    goals = {d['node'] for d in request['destinations']}
    witnesses = {}
    predecessor = {}
    todo = collections.deque()
    if node_known[nodes[origin]]:
        if origin in goals:
            witnesses[origin] = []
        for j in outgoing[origin]:
            if incoming is None or (incoming, edges[j]['id']) not in forbidden:
                predecessor[j] = None; todo.append(j)
    while todo:
        j = todo.popleft(); e = edges[j]
        if e['v'] in goals and e['v'] not in witnesses:
            route = []; k = j
            while k is not None:
                route.append(edges[k]['id']); k = predecessor[k]
            witnesses[e['v']] = route[::-1]
        for k in outgoing[e['v']]:
            if k not in predecessor and (e['id'], edges[k]['id']) not in forbidden:
                predecessor[k] = j; todo.append(k)
    destinations = []
    for d in request['destinations']:
        route = witnesses.get(d['node'])
        # Recheck the static witness against original edge identities and turns.
        if route is not None:
            previous = incoming; node = origin
            for ident in route:
                e = edges[ids[ident]]
                if e['u'] != node or not edge_known[ids[ident]] or (previous, ident) in forbidden:
                    raise AssertionError('Invalid topology witness')
                previous, node = ident, e['v']
            if node != d['node'] or not node_known[nodes[node]]:
                raise AssertionError('Invalid endpoint support')
        destinations.append(dict(node=d['node'], known_node=bool(node_known[nodes[d['node']]]),
                                 supported_turn_topology_exists=route is not None,
                                 support_only_edge_witness=route))
    return dict(origin_known=bool(node_known[nodes[origin]]), destinations=destinations,
                any_supported_turn_topology=any(d['supported_turn_topology_exists'] for d in destinations),
                static_incoming_edge_states_reached=len(predecessor),
                interpretation='Static reachability only. No time-cost/flame/dose/peak/acceptance search.',
                temporal_contact_feasibility='NOT_EVALUATED')


def worker(bundle_path, result_path):
    bundle = load(bundle_path)
    graph_path = Path(bundle['graph'])
    pin(graph_path, bundle['graph_sha256'])
    if graph_path.stat().st_size > 64 << 20:
        raise ValueError('Graph JSON input-size guard')
    prior = load(PRIOR); pin(PRIOR, PRIOR_SHA)
    graph = load(graph_path)
    windows = {(w['event'], w['cutoff']): w for w in prior['export_windows']}
    domains = {d['domain_id']: d for d in prior['domains']}
    mask_list = []; bindings = []
    for ident in bundle['domain_ids']:
        d = domains[ident]
        mask, binding = source_mask(d, windows[d['event'], d['cutoff']])
        H, W = d['grid_shape']; a = d['affine']; g = graph['grid']
        if (graph['crs'] != d['crs'] or [g['height'], g['width']] != [H, W]
                or F(g['resolution']) != F(a[0]) or F(a[4]) != -F(a[0])
                or F(g['x0']) != F(a[2]) or F(g['y0']) != F(a[5]) + H * F(a[4])):
            raise ValueError('Exact original graph/native domain binding')
        mask_list.append(mask); bindings.append(binding)
    known_nodes, known_edges, methods = spatial_flags(graph, mask_list)
    rows = []
    for case in bundle['cases']:
        d = next(domains[x] for x in bundle['domain_ids'] if case['mission'] in domains[x]['missions'])
        k = bundle['domain_ids'].index(d['domain_id']); binding = bindings[k]
        request_path = Path(case['request']); pin(request_path, case['input_sha256']['request'])
        md_path = Path(case['packet']) / 'NATIVE_METADATA.json'
        pin(md_path, case['input_sha256']['NATIVE_METADATA.json'])
        request = load(request_path); metadata = load(md_path)
        if not utc(request['as_of']) == utc(metadata['time_origin']) == utc(binding['cutoff_utc']):
            raise ValueError('Original exact source/mission clock')
        dep, horizon = F(request['departure']), F(request['horizon'])
        if dep.denominator != 1 or horizon.denominator != 1 or dep < 0:
            raise ValueError('Original integer mission time scope')
        bound = min(horizon, binding['source_horizon_s'])
        time_windows = [dict(node=d['node'], dwell_s=d['dwell'], original_open_intervals=d['open_intervals'],
                             possible_arrival_intervals_s=[[float(max(dep, F(a))), float(min(bound - F(d['dwell']), F(b) - F(d['dwell'])))]
                                 for a, b in d['open_intervals'] if max(dep, F(a)) <= min(bound - F(d['dwell']), F(b) - F(d['dwell']))])
                        for d in request['destinations']]
        rows.append(dict(mission=case['mission'], region=case['region'], domain_id=d['domain_id'],
                         graph_sha256=bundle['graph_sha256'], request_sha256=case['input_sha256']['request'],
                         metadata_sha256=case['input_sha256']['NATIVE_METADATA.json'], source=binding,
                         node_count=len(graph['nodes']), known_nodes=int(known_nodes[k].sum()),
                         waitable_nodes=sum(bool(n['waitable']) for n in graph['nodes']),
                         known_waitable_nodes=sum(bool(n['waitable']) and bool(v) for n, v in zip(graph['nodes'], known_nodes[k])),
                         directed_edge_count=len(graph['edges']), known_directed_edges=int(known_edges[k].sum()),
                         node_known_flags_sha256=hashlib.sha256(known_nodes[k].tobytes()).hexdigest(),
                         edge_known_flags_sha256=hashlib.sha256(known_edges[k].tobytes()).hexdigest(),
                         original_departure_s=int(dep), original_horizon_s=int(horizon),
                         restricted_source_horizon_s=int(bound), dwell_clock_preconditions=time_windows,
                         topology=topology(graph, request, known_nodes[k], known_edges[k])))
    flags_path = Path(result_path).with_suffix('.npz')
    np.savez_compressed(flags_path, node_known=known_nodes, edge_known=known_edges,
                        domain_ids=np.asarray(bundle['domain_ids'], dtype='U16'))
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 2 if sys.platform == 'darwin' else 1024)
    dump(result_path, dict(rows=rows, support_methods=methods, domain_order=bundle['domain_ids'],
                           graph_sha256=pin(graph_path, bundle['graph_sha256']), flags_npz_sha256=sha(flags_path),
                           node_and_edge_order='Original pinned graph JSON list order', peak_rss_mib=peak,
                           no_timed_search=True, no_source_or_default_change=True))


def self_test():
    graph = dict(grid=dict(width=3, height=3, x0=0, y0=0, resolution=1),
                 nodes=[dict(id='a', x=.5, y=.5), dict(id='b', x=2.5, y=2.5),
                        dict(id='c', x=2.5, y=.5), dict(id='d', x=1., y=1.)],
                 edges=[dict(id='ab', u='a', v='b', travel_ticks=2),
                        dict(id='ac', u='a', v='c', travel_ticks=2),
                        dict(id='cd', u='c', v='d', travel_ticks=2)], forbidden_turns=[])
    for bits in range(1 << 9):
        mask = np.array([bool(bits & (1 << c)) for c in range(9)], dtype=bool)
        nk, ek, _ = spatial_flags(graph, [mask])
        for j, edge in enumerate(graph['edges']):
            cells = {o['cell'] for o in edge_occupancies(edge, 0, 1, graph=graph)}
            assert bool(ek[0, j]) == (not mask[list(cells)].any())
    mask = np.zeros(9, dtype=bool); nk, ek, _ = spatial_flags(graph, [mask])
    request = dict(position=dict(node='a'), incoming_edge=None, destinations=[dict(node='d')])
    assert topology(graph, request, nk[0], ek[0])['any_supported_turn_topology']
    graph['forbidden_turns'] = [['ac', 'cd']]
    assert not topology(graph, request, nk[0], ek[0])['any_supported_turn_topology']
    graph['forbidden_turns'] = []; request['incoming_edge'] = 'cd'
    graph['forbidden_turns'] = [['cd', 'ac']]
    assert not topology(graph, request, nk[0], ek[0])['any_supported_turn_topology']
    graph['nodes'][0]['x'] = -1
    try:
        spatial_flags(graph, [mask])
    except ValueError:
        pass
    else:
        raise AssertionError('Outside graph coordinate admitted')
    print(json.dumps(dict(status='PASS', exhaustive_masks=512, exact_edge_comparisons=1536,
                          boundary_point_cell=True, forbidden_turns=True, incoming_history=True,
                          outside_refusal=True, actual_graphs_read=0, planner_runs=0)))


def run(out):
    pin(PRIOR, PRIOR_SHA); prior = load(PRIOR)
    cases = [c for c in load(CASES) if c['panel'] == 'Korean']
    first32_path = ROOT / 'research/sipp-routing/member-scaling-closure-20261030-v2/RESULTS.json'
    pin(first32_path, prior['prior_first32_report_sha256'])
    pin(CASES, load(first32_path)['inputs'][str(CASES.relative_to(ROOT))])
    groups = collections.defaultdict(list)
    for case in cases:
        groups[case['graph']].append(case)
    out.mkdir(parents=True, exist_ok=False)
    source_paths = [Path(__file__), ROOT / 'experimental/sipp-routing/src/wfg_sipp/geometry.py',
                    ROOT / 'experimental/scenario-members/src/wfg_scenario_members/features.py',
                    ROOT / 'experimental/scenario-members/bridge_v2.py',
                    ROOT / 'experimental/sipp-routing/src/wfg_sipp/frontend.py']
    source_pins = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    completed = []; execution = []
    for index, (graph, group) in enumerate(sorted(groups.items())):
        bundle = dict(graph=graph, graph_sha256=group[0]['input_sha256']['graph'], cases=group,
                      domain_ids=[d['domain_id'] for d in prior['domains'] if any(c['mission'] in d['missions'] for c in group)])
        bp, rp = out / ('graph-%02d-input.json' % index), out / ('graph-%02d-result.json' % index)
        dump(bp, bundle)
        lease_path = Path('/tmp/wfg/HEAVY.lock'); lease_path.parent.mkdir(parents=True, exist_ok=True)
        with lease_path.open('a') as lease:
            print(json.dumps(dict(status='WAITING_HEAVY', graph_index=index)), flush=True)
            fcntl.flock(lease, fcntl.LOCK_EX)
            start = time.monotonic(); acquired = datetime.now(timezone.utc).isoformat()
            cmd = [sys.executable, str(Path(__file__).resolve()), '--worker', str(bp.resolve()), '--result', str(rp.resolve())]
            proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, start_new_session=True)
            print(json.dumps(dict(status='ACQUIRED_HEAVY', graph_index=index, child_pid=proc.pid)), flush=True)
            maximum = 0.; stop = None
            while proc.poll() is None:
                if time.monotonic() - start >= DEADLINE_S:
                    stop = 'DEADLINE'
                ps = subprocess.run(['ps', '-o', 'rss=', '-p', str(proc.pid)], text=True, capture_output=True)
                if ps.stdout.strip():
                    maximum = max(maximum, float(ps.stdout.strip()) / 1024)
                if maximum > RSS_MIB:
                    stop = 'RSS_LIMIT'
                if stop:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    break
                time.sleep(.1)
            stdout, stderr = proc.communicate()
            elapsed = time.monotonic() - start
            result = load(rp) if proc.returncode == 0 and rp.exists() else None
            if stop is None and elapsed >= DEADLINE_S:
                stop = 'DEADLINE_AFTER_EXIT'
            if stop is None and result and result['peak_rss_mib'] > RSS_MIB:
                stop = 'RSS_LIMIT_AFTER_EXIT'
            cleanup = subprocess.run(['ps', '-o', 'pid=', '-g', str(proc.pid)], text=True, capture_output=True)
            if cleanup.stdout.strip():
                os.killpg(proc.pid, signal.SIGKILL)
                stop = stop or 'OWNED_GROUP_CLEANUP_REQUIRED'
            row = dict(graph_index=index, command=cmd, bundle_sha256=sha(bp), lease_acquired_utc=acquired,
                       lease_released_utc=datetime.now(timezone.utc).isoformat(), child_pid=proc.pid,
                       exit_code=proc.returncode, stop=stop, stdout=stdout.decode(errors='replace'),
                       stderr=stderr.decode(errors='replace'), sampled_rss_mib=maximum,
                       reported_peak_rss_mib=result.get('peak_rss_mib') if result else None,
                       control_elapsed_s=elapsed, owned_group_absent=not cleanup.stdout.strip(),
                       admission='ACCEPTED_CENSUS' if result and stop is None else 'UNRESOLVED_CONTROL_FAILURE')
            execution.append(row); dump(out / 'CONTROL_RECEIPT.json', execution)
            if result and stop is None:
                completed.extend(result['rows'])
        print(json.dumps(dict(graph_index=index, admission=row['admission'], source_missions=len(group))), flush=True)
    for path, expected in source_pins.items():
        pin(ROOT / path, expected)
    dump(out / 'RESULTS.json', dict(schema='wfg.next.known-footprint-topology-census/1',
         source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
         producer_sha256=sha(__file__), host=platform.platform(), python=sys.version, numpy=np.__version__,
         source_pins=source_pins, prior_full_N_sha256=PRIOR_SHA, rows=completed,
         status='COMPLETE_STATIC_SUPPORT_CENSUS' if len(completed) == 20 else 'PARTIAL_UNRESOLVED_CONTROL_FAILURE',
         totals=dict(expected_missions=20, admitted_census_missions=len(completed),
                     supported_turn_topologies=sum(r['topology']['any_supported_turn_topology'] for r in completed)),
         controls=dict(timeout_s=DEADLINE_S, rss_mib=RSS_MIB, exclusive_heavy_per_graph=True,
                       enforcement='Sampled child RSS with final self-reported ru_maxrss and post-exit elapsed admission; polling is not an instantaneous OS memory limit.'),
         limits='No timed contact search, policy change, simulator/retraining, risk/radiation claim, or source fill. Static support topology does not establish temporal contact feasibility.',
         output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--result', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.worker:
        worker(args.worker, args.result)
    elif args.out:
        run(args.out)
    else:
        parser.error('Choose --self-test, --worker/--result, or separately authorized --out census')
