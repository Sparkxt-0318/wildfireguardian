"""Read-only deliverable/admission audit; no planner, simulation or benchmark call."""
import argparse
import collections
import csv
from datetime import datetime, timezone
from fractions import Fraction as F
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile
import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def prefix(path, key, count):
    """Read original trajectory prefix bytes, without simulating or loading all N."""
    with zipfile.ZipFile(path) as z, z.open(key+'.npy') as stream:
        version = np.lib.format.read_magic(stream)
        if version == (1, 0): shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
        elif version == (2, 0): shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream)
        else: raise ValueError('Unsupported NPY header version')
        if fortran or len(shape) != 3 or dtype != np.dtype('int16') or shape[0] < count:
            raise ValueError('Expected C-order int16 trajectory prefix')
        n = count*shape[1]*shape[2]
        raw = stream.read(n*dtype.itemsize)
        if len(raw) != n*dtype.itemsize: raise ValueError('Incomplete source trajectory prefix')
        return np.frombuffer(raw, dtype=dtype).reshape((count,*shape[1:])).copy(), shape


def utc(value): return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def native_index(graph, node, shape):
    g = graph['grid']
    col = (F(node['x'])-F(g['x0'])) // F(g['resolution'])
    row = (F(node['y'])-F(g['y0'])) // F(g['resolution'])
    if not 0 <= row < shape[0] or not 0 <= col < shape[1]: raise ValueError('Node outside native grid')
    return int(shape[0]-1-row), int(col)


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--native-panel', type=Path, default=Path('research/sipp-routing/native-panel-20261030'))
    p.add_argument('--exports', type=Path, default=Path('../data/trajectory-exports-20261030-v2'))
    p.add_argument('--admission', type=Path, default=Path('research/synthetic-truth/strict-support-20261030'))
    p.add_argument('--out', type=Path, default=Path('research/sipp-routing/member-scaling-closure-20261030-v2'))
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=False)
    cases = json.loads((a.native_panel/'CASES.json').read_text())
    executions = [json.loads(s) for s in (a.native_panel/'EXECUTIONS.jsonl').read_text().splitlines()]
    measured = json.loads((a.native_panel/'MEASURED_SOURCE_SHA256.json').read_text())
    sizes = {}; pins = {}; pairs = collections.defaultdict(dict)
    for i, case in enumerate(cases):
        request = json.loads(Path(case['request']).read_text()); sizes[i] = len(request['incurred'])
        for label, path in [('graph',Path(case['graph'])),('request',Path(case['request'])),('NATIVE_METADATA.json',Path(case['packet'])/'NATIVE_METADATA.json'),('constructed_arrays.npz',Path(case['packet'])/'constructed_arrays.npz')]:
            digest = sha(path)
            if digest != case['input_sha256'][label]: raise ValueError('Sealed native input identity changed')
            pins[str(path)] = digest
    for row in executions:
        if row['mission'] != cases[row['case_index']]['mission']: raise ValueError('Mission/case binding mismatch')
        pair = pairs[(row['case_index'],row['repetition'])]
        if row['method'] in pair: raise ValueError('Duplicate execution method')
        pair[row['method']] = row
    fixed = []
    for (index, rep), pair in sorted(pairs.items()):
        if set(pair) != {'sipp','sweep'}: raise ValueError('Incomplete stored pair')
        si, sw = pair['sipp'], pair['sweep']; sm, wm = si['metrics'], sw['metrics']
        fixed.append(dict(case_index=index,mission=cases[index]['mission'],panel=cases[index]['panel'],repetition=rep,K=sizes[index],
                          sipp_interval_pieces=sm['pieces'],sipp_piece_expansions=sm['expansions'],sipp_successor_runs=sm['successor_runs'],
                          sweep_states_reached=wm['states_reached'],sipp_outcome=si['status'],sweep_outcome=sw['status']))
    write_csv(a.out/'NATIVE_FIXED_K_COUNTERS.csv', fixed)
    prior = []
    for name in ['C1','C2','C3','C4']:
        path = a.admission/(name+'.jsonl.gz'); n = 0; ks = collections.Counter(); reasons = collections.Counter(); counters = 0
        with gzip.open(path,'rt') as stream:
            for line in stream:
                r = json.loads(line); n += 1; ks[r['acceptance']['m']] += 1; reasons[r['reason']] += 1
                counters += any(k in r for k in ['metrics','pieces','expansions','states_reached'])
        prior.append(dict(campaign=name, records=n,K_counts=dict(ks),reasons=dict(reasons),search_counter_records=counters,path=str(path),sha256=sha(path)))
    records = {}
    for path in sorted(a.exports.glob('*/*/FORECAST_RECORD_*.json')):
        r = json.loads(path.read_text()); records[r['event'],r['cutoff_utc']] = (path,r)
    cache = {}; feasible = []
    for case in cases:
        if case['panel'] != 'Korean': continue
        md = json.loads((Path(case['packet'])/'NATIVE_METADATA.json').read_text()); parent = md['construction']['parent_forecast']
        key = parent['event_id'],parent['cutoff_utc']; rp, rec = records[key]; npz = rp.parent/rec['npz']
        if key not in cache:
            if sha(npz) != rec['npz_sha256']: raise ValueError('Actual v3 export identity changed')
            first, shape = prefix(npz,'trajectory_first_burn_hour',32)
            with np.load(npz,allow_pickle=False) as z:
                transform = tuple(z['affine_transform'].ravel()[:6]); source_valid = z['source_burned_area_valid'].copy()
            cache[key] = dict(first=first,shape=shape,transform=transform,source_valid=source_valid,
                              source_record_sha256=sha(rp),npz_sha256=rec['npz_sha256'],
                              base_seed=rec['trajectory_base_seed'],batch_size=rec['trajectory_batch_size'],
                              prefix_sha256=hashlib.sha256(first.tobytes()).hexdigest())
        data = cache[key]; first = data['first']; H,W = first.shape[1:]
        g = json.loads(Path(case['graph']).read_text()); q = json.loads(Path(case['request']).read_text()); grid = g['grid']
        expected = (grid['resolution'],0,grid['x0'],0,-grid['resolution'],grid['y0']+grid['height']*grid['resolution'])
        aligned = expected == data['transform'] and (H,W) == (grid['height'],grid['width']) and g['crs'] == 'EPSG:%d'%rec['epsg']
        clock_match = utc(parent['cutoff_utc']) == utc(rec['cutoff_utc']) == utc(md['time_origin']) == utc(q['as_of'])
        view = first; valid_view = data['source_valid']; view_shape = (H,W); window = None
        if not aligned and md.get('regional'):
            region = md['regional']; window = region['window_rows_cols_north_up']
            if tuple(region['full_event_affine_transform']) != data['transform'] or tuple(region['full_event_shape']) != (H,W):
                raise ValueError('Regional source grid provenance mismatch')
            r0,r1,c0,c1 = [window[k] for k in ['r0','r1','c0','c1']]
            # Existing regional metadata uses inclusive native bounds. This is
            # a read-only integer view, not interpolation or a new grid binding.
            view = first[:,r0:r1+1,c0:c1+1]; valid_view = valid_view[r0:r1+1,c0:c1+1]
            cropped = (data['transform'][0],0,data['transform'][2]+c0*data['transform'][0],0,data['transform'][4],data['transform'][5]+r0*data['transform'][4])
            view_shape = view.shape[1:]
            aligned = cropped == expected and view_shape == (grid['height'],grid['width']) and g['crs'] == 'EPSG:%d'%rec['epsg']
        if not aligned or not clock_match: raise ValueError('No existing exact grid/window and clock binding')
        nodes = {n['id']:n for n in g['nodes']}; origin = native_index(g,nodes[q['position']['node']],view_shape)
        for k in [4,8,16,32]:
            unknown = view[:k] == -2
            # This is exactly the current bridge's whole-model support predicate,
            # observed from input bytes. No constructor or planner is called.
            global_support = not bool(unknown.any())
            point_values = view[:k,origin[0],origin[1]]
            feasible.append(dict(mission=case['mission'],event=key[0],cutoff=key[1],K=k,selection='actual first K original trajectory identities, no replication',
                                 grid_clock_aligned=aligned and clock_match,existing_regional_integer_window=window,global_bridge_contact_admitted=global_support,
                                 trajectory_unknown_cells_any_member=int(unknown.any(axis=0).sum()),
                                 issue_cell_trajectory_unknown_members=int((point_values == -2).sum()),
                                 cutoff_source_state_valid=bool(valid_view[origin]),
                                 departure_s=q['departure'],horizon_s=q['horizon'],
                                 admission='ADMITTED' if global_support else 'UNSUPPORTED_CURRENT_GLOBAL_CONTACT_CONTRACT'))
    write_csv(a.out/'KOREAN_PRESEARCH_ADMISSION.csv', feasible)
    window_rows = []
    for key,data in sorted(cache.items()):
        first = data['first']; d = {k:v for k,v in data.items() if k not in ['first','transform','source_valid']}
        d.update(event=key[0],cutoff=key[1],affine=list(data['transform']),shape=list(data['shape']),
                 unique_actual_prefix_fields={str(k):len({hashlib.sha256(m.tobytes()).hexdigest() for m in first[:k]}) for k in [4,8,16,32]})
        window_rows.append(d)
    inputs = {str(a.native_panel/name):sha(a.native_panel/name) for name in ['CASES.json','EXECUTIONS.jsonl','MEASURED_SOURCE_SHA256.json','RESULTS.json']}
    sources = ['experimental/sipp-routing/src/wfg_sipp/frontend.py','experimental/sipp-routing/src/wfg_sipp/sipp.py','experimental/scenario-members/bridge_v2.py','research/synthetic-truth/run_strict_support_campaigns.py']
    result = dict(initial_audit_disclosure='Initial exact full-grid comparison stopped at documented KFS_01 regional windows. Initial source and fixed-K extraction retained in member-scaling-closure-20261030. Final audit verifies and applies only existing inclusive integer regional views, preserving values and masks; no resampling or new grid.',status='FIG02_NOT_PRODUCED_NO_ADMITTED_MEMBER_COUNT_SEARCH_SERIES',source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  host=platform.platform(),python=sys.version,numpy=np.__version__,producer_sha256=sha(Path(__file__)),inputs=inputs,sealed_input_pins=pins,
                  measured_counter_source=measured,analysis_scope='Existing counter extraction and read-only presearch admission. No algorithm, simulation, rerun, resource benchmark or new panel executed.',
                  fixed_native=dict(missions=len(cases),pairs=len(pairs),executions=len(executions),distinct_K=sorted(set(sizes.values())),
                                    table='NATIVE_FIXED_K_COUNTERS.csv',counter_units='SIPP pieces and expansions count interval pieces; sweep states_reached is a distinct internal reachability counter. No ratio or common-work-unit claim.',
                                    original_seed='Frozen constructed packet members; no new draws in this audit',repetitions='two per mission, not independent missions'),
                  existing_admission_records=prior,actual_export_windows=window_rows,
                  presearch=dict(cases=len(feasible),missions=len({r['mission'] for r in feasible}),K=[4,8,16,32],admitted=sum(r['global_bridge_contact_admitted'] for r in feasible),
                                 table='KOREAN_PRESEARCH_ADMISSION.csv',obstacle='Every selected actual prefix contains unknown trajectory cells, including after its existing exact regional window when applicable. bridge_v2.to_contact_model sets supported=False for any such cell, and frontend.sipp_plan returns unresolved before graph preparation/search.',
                                 point_scope='Issue-cell trajectory unknown is a spatial future-arrival-support diagnostic, not proof that current contact occurs. Known cutoff state is retained separately. No route-local feasibility claim is made.'),
                  selector_scope='Only first-K controls0..K-1 are audited. Exactly32actual trajectory fields per window were read. Full-N unknown-mask sharing and other selectors were not assessed; no rejection claim for uninspected selectors.',
                  classification='The missing figure is separately unexecuted, and the audited first-K K4/8/16/32 study on the existing exports is blocked by current input admission. The1A physics gate is not a prerequisite for a pure contact solver study.',
                  proposed_campaign='NOT_SCHEDULED_NO_ADMITTED_SEARCHES under current contract. No empty benchmark or global-support override is proposed.',
                  conditional_future_protocol='Only after admissible actual contact inputs or a separately justified spatial/temporal support contract: fixed20Korean missions, exact grids/clocks, first-K original identities K4/8/16/32, paired sweep/SIPP, two ABBA repetitions,30s/3072MiB limits, serialized HEAVY lease after B. No replicated members, threshold changes, unknown fill or thermal/risk interpretation.',
                  remaining_boundary='A future local/pessimistically bounded contact checker might admit some routes; this audit neither implements it nor proves it impossible. Unknown global emitting support is a separate thermal issue. Fixed-K counters cannot identify a slope versus K.',
                  current_source_sha256={p:sha(p) for p in sources},outputs={name:sha(a.out/name) for name in ['NATIVE_FIXED_K_COUNTERS.csv','KOREAN_PRESEARCH_ADMISSION.csv']})
    (a.out/'RESULTS.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(native_K=result['fixed_native']['distinct_K'],native_pairs=len(pairs),existing_admission_search_counter_records=sum(r['search_counter_records'] for r in prior),new_searches=0,presearch_candidates=len(feasible),presearch_admitted=result['presearch']['admitted'],figure='NOT_PRODUCED')))


if __name__ == '__main__': main()
