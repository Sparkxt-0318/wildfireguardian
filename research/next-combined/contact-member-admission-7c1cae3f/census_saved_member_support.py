"""Source-bound all-saved-member support census, streamed without any search.

The exact current contact adapter requires no -2 cell in any selected member
on its declared domain. This validates that predicate, not physical tenability.
"""
import argparse
import ast
import collections
import csv
from datetime import datetime, timezone
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


def load(path): return json.loads(Path(path).read_text())
def utc(text): return datetime.fromisoformat(text.replace('Z','+00:00')).astimezone(timezone.utc)


def header(stream):
    version = np.lib.format.read_magic(stream)
    if version == (1,0): return np.lib.format.read_array_header_1_0(stream)
    if version == (2,0): return np.lib.format.read_array_header_2_0(stream)
    raise ValueError('Unsupported NPY version')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prior', type=Path, default=Path('research/sipp-routing/member-scaling-closure-20261030-v2'))
    p.add_argument('--cases', type=Path, default=Path('research/sipp-routing/native-panel-20261030/CASES.json'))
    p.add_argument('--exports', type=Path, default=Path('../data/trajectory-exports-20261030-v2'))
    p.add_argument('--out', type=Path, default=Path('research/sipp-routing/full-member-support-census-20261030'))
    a = p.parse_args()
    prior = load(a.prior/'RESULTS.json')
    if sha('research/sipp-routing/audit_member_scaling.py') != prior['producer_sha256']:
        raise ValueError('Prior grid/window proof producer identity changed')
    for name, expected in prior['outputs'].items():
        if sha(a.prior/name) != expected: raise ValueError('Prior proof output identity changed')
    if sha(a.cases) != prior['inputs'][str(a.cases)]: raise ValueError('Native case manifest changed')
    with (a.prior/'KOREAN_PRESEARCH_ADMISSION.csv').open() as stream:
        proofs = {r['mission']:r for r in csv.DictReader(stream) if r['K']=='4'}
    records = {}
    for path in sorted(a.exports.glob('*/*/FORECAST_RECORD_*.json')):
        rec = load(path); records[rec['event'],rec['cutoff_utc']] = (path,rec)
    prior_exports = {(w['event'],w['cutoff']):w for w in prior['actual_export_windows']}
    groups = collections.defaultdict(list); verified = {}; reuse = []
    def pin(path, expected):
        path = Path(path); actual = verified.get(str(path))
        if actual is None: actual = verified[str(path)] = sha(path)
        if actual != expected: raise ValueError('Existing evidence/input identity changed: '+str(path))
        return actual
    cases = [c for c in load(a.cases) if c['panel']=='Korean']
    for case in cases:
        proof = proofs[case['mission']]
        if proof['grid_clock_aligned'] != 'True': raise ValueError('Prior grid/clock proof not admitted')
        for path in [Path(case['graph']),Path(case['request']),Path(case['packet'])/'NATIVE_METADATA.json']:
            pin(path, prior['sealed_input_pins'][str(path)])
        md = load(Path(case['packet'])/'NATIVE_METADATA.json'); request = load(case['request'])
        parent = md['construction']['parent_forecast']; key = parent['event_id'],parent['cutoff_utc']
        rp,rec = records[key]; previous = prior_exports[key]
        pin(rp, previous['source_record_sha256']); npz = rp.parent/rec['npz']; pin(npz,previous['npz_sha256'])
        if rec['npz_sha256'] != previous['npz_sha256']: raise ValueError('Export producer binding differs')
        if not utc(key[1]) == utc(rec['cutoff_utc']) == utc(md['time_origin']) == utc(request['as_of']):
            raise ValueError('Exact source/mission clock mismatch')
        region = md.get('regional'); window = region['window_rows_cols_north_up'] if region else None
        old_window = ast.literal_eval(proof['existing_regional_integer_window']) if proof['existing_regional_integer_window'] else None
        if old_window != window: raise ValueError('Existing regional window proof changed')
        groups[key].append(dict(mission=case['mission'],region=case['region'],shape=list(md['shape']),
                                affine=list(md['affine_transform']),crs=md['crs'],window=window,
                                full_shape=region['full_event_shape'] if window else md['shape'],
                                full_affine=region['full_event_affine_transform'] if window else md['affine_transform']))
        reuse.append(dict(mission=case['mission'],source_event=key[0],source_cutoff=key[1],grid_clock_proof='Prior exact proof and all current graph/request/metadata/export bytes unchanged'))
    a.out.mkdir(parents=True,exist_ok=False)
    rows = []; windows = []; maximum_member_bytes = 0; unique_domains = 0
    with (a.out/'MEMBER_SUPPORT.csv').open('w',newline='') as out:
        fields = ['domain_id','event','cutoff','trajectory_index','unknown_cells','current_contract_supported','unknown_mask_sha256']
        writer = csv.DictWriter(out,fieldnames=fields); writer.writeheader()
        for key, bindings in sorted(groups.items()):
            rp,rec = records[key]; npz = rp.parent/rec['npz']; previous = prior_exports[key]
            # Small affine field only. No complete trajectory array is loaded.
            with np.load(npz,allow_pickle=False) as z: affine = tuple(z['affine_transform'].ravel()[:6])
            domains = {}
            for b in bindings:
                signature = json.dumps({k:b[k] for k in ['shape','affine','crs','window','full_shape','full_affine']},sort_keys=True)
                if signature not in domains:
                    domains[signature] = dict(binding=b,missions=[],supported=[],unknown_histogram=collections.Counter(),
                                              mask_reference=None,all_masks_byte_equal=True,mask_hashes=set())
                domains[signature]['missions'].append(b['mission'])
            with zipfile.ZipFile(npz) as archive, archive.open('trajectory_first_burn_hour.npy') as stream:
                shape,fortran,dtype = header(stream)
                if fortran or dtype != np.dtype('int16') or len(shape)!=3:
                    raise ValueError('Expected C-order int16 saved trajectory array')
                N,H,W = shape
                if N != rec['trajectory_count'] or N != previous['shape'][0] or N != 1024:
                    raise ValueError('Not exactly the saved N1024 cohort')
                member_bytes = H*W*dtype.itemsize; maximum_member_bytes = max(maximum_member_bytes,member_bytes)
                if member_bytes > (1 << 20): raise ValueError('Stream member exceeds tiny-validation bound; queue HEAVY instead')
                for d in domains.values():
                    b = d['binding']
                    if tuple(b['full_shape']) != (H,W) or tuple(b['full_affine']) != affine or b['crs'] != 'EPSG:%d'%rec['epsg']:
                        raise ValueError('Full source grid binding differs')
                    window = b['window']
                    if window:
                        r0,r1,c0,c1 = [window[k] for k in ['r0','r1','c0','c1']]
                    else: r0,r1,c0,c1 = 0,H-1,0,W-1
                    if not (0 <= r0 <= r1 < H and 0 <= c0 <= c1 < W): raise ValueError('Existing window outside grid')
                    mapped = (affine[0],0,affine[2]+c0*affine[0],0,affine[4],affine[5]+r0*affine[4])
                    if tuple(b['shape']) != (r1-r0+1,c1-c0+1) or tuple(b['affine']) != mapped:
                        raise ValueError('Exact inclusive integer window shape/affine mismatch')
                    d['slice'] = (slice(r0,r1+1),slice(c0,c1+1)); d['domain_id'] = 'd%03d'%unique_domains
                    unique_domains += 1
                payload = hashlib.sha256(); prefix = hashlib.sha256()
                for index in range(N):
                    raw = stream.read(member_bytes)
                    if len(raw) != member_bytes: raise ValueError('Incomplete saved member')
                    payload.update(raw)
                    if index < 32: prefix.update(raw)
                    member = np.frombuffer(raw,dtype=dtype).reshape((H,W))
                    if member.min() < -2 or member.max() > rec['trajectory_horizon_hours']:
                        raise ValueError('Invalid first-burn encoding in saved member')
                    unknown = member == -2
                    for d in domains.values():
                        mask = unknown[d['slice']]; count = int(np.count_nonzero(mask)); mask_bytes = mask.tobytes(order='C')
                        digest = hashlib.sha256(mask_bytes).hexdigest(); d['mask_hashes'].add(digest)
                        if d['mask_reference'] is None: d['mask_reference'] = mask_bytes
                        else: d['all_masks_byte_equal'] &= mask_bytes == d['mask_reference']
                        supported = count == 0
                        if supported: d['supported'].append(index)
                        d['unknown_histogram'][count] += 1
                        writer.writerow(dict(domain_id=d['domain_id'],event=key[0],cutoff=key[1],trajectory_index=index,
                                             unknown_cells=count,current_contract_supported=supported,unknown_mask_sha256=digest))
                if stream.read(1) != b'': raise ValueError('Unexpected trailing NPY payload')
                if prefix.hexdigest() != previous['prefix_sha256']:
                    raise ValueError('First32 prefix differs from immutable prior audit')
                for d in domains.values():
                    counts = d['unknown_histogram']
                    if sum(counts.values()) != N: raise ValueError('Incomplete member census')
                    b = d['binding']; support = len(d['supported'])
                    rows.append(dict(domain_id=d['domain_id'],event=key[0],cutoff=key[1],missions=d['missions'],
                                     grid_shape=b['shape'],affine=b['affine'],crs=b['crs'],existing_integer_window=b['window'],
                                     saved_members=N,checked_members=sum(counts.values()),strictly_supported_members=support,
                                     supported_member_indices=d['supported'],unsupported_members=N-support,
                                     unknown_cell_count_histogram=dict(sorted(counts.items())),
                                     all_saved_unknown_masks_byte_equal=d['all_masks_byte_equal'],
                                     distinct_unknown_mask_sha256=sorted(d['mask_hashes']),
                                     K_admission={str(k):support>=k for k in [4,8,16,32]},
                                     current_contract_reason='Every member has at least one unknown domain cell' if support==0 else 'Some saved members have complete declared-domain support'))
                windows.append(dict(event=key[0],cutoff=key[1],npz=str(npz.resolve()),npz_sha256=rec['npz_sha256'],
                                    record_sha256=sha(rp),shape=list(shape),dtype=dtype.str,N=N,
                                    first_burn_payload_sha256=payload.hexdigest(),first32_prefix_sha256=prefix.hexdigest(),
                                    base_seed=rec['trajectory_base_seed'],trajectory_batch_size=rec['trajectory_batch_size'],
                                    no_regeneration='Read original saved slots0..1023, no draws, fill or replication'))
    no_supported = all(r['strictly_supported_members']==0 for r in rows)
    support_csv=a.out/'MEMBER_SUPPORT.csv'
    report=dict(schema='wfg.next.full-member-contact-support-census/1',source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                host=platform.platform(),python=sys.version,numpy=np.__version__,producer_sha256=sha(Path(__file__)),
                command='python research/sipp-routing/census_saved_member_support.py --out FRESH_CENSUS_DIRECTORY',
                scope='All savedN1024 members of each of15existing export windows, on every distinct declared contact domain used by20missions. Streamed read-only source admission, no solver/simulation/selector/benchmark.',
                status='NO_NONEMPTY_SAVED_MEMBER_SELECTION_ADMITTED_BY_CURRENT_CONTACT_CONTRACT' if no_supported else 'SUPPORTED_MEMBERS_EXIST_REDUCTION_MISSING_MASS_ADMISSION_UNRESOLVED',
                prior_first32_report_sha256=sha(a.prior/'RESULTS.json'),prior_first32_csv_sha256=sha(a.prior/'KOREAN_PRESEARCH_ADMISSION.csv'),
                input_pins=verified,grid_clock_proof_reuse=reuse,export_windows=windows,domains=rows,
                totals=dict(missions=len(cases),distinct_export_windows=len(windows),distinct_contact_domains=len(rows),
                            saved_export_slots=sum(w['N'] for w in windows),domain_member_checks=sum(r['checked_members'] for r in rows),
                            domain_member_supports=sum(r['strictly_supported_members'] for r in rows),
                            domains_with_any_supported_member=sum(r['strictly_supported_members']>0 for r in rows)),
                selection_implication='Every saved member on every audited domain is unsupported. Any nonempty selected set therefore contains an unknown cell. Current bridge support admission rejects before search regardless of first-K, forward selection, medoid choice, weights or k_of_m; it does not discard unknown mass.' if no_supported else 'Report counts only. Choosing only supported members could discard empirical unknown mass, and the full-N distance/coverage contracts require a separate missingness analysis; no selection run.',
                distance_contract='Current full-grid L1 and road-symmetric-difference constructors reject -2 fields; positive-weight unknown road features also reject. No distance computation or redistribution is executed here.',
                resource_scope=dict(one_export_at_a_time=True,one_original_member_at_a_time=True,maximum_member_raw_bytes=maximum_member_bytes,
                                    member_allocation_guard_bytes=1<<20,working_data_bound_description='One int16 member view, one full Boolean mask, at most the existing domain mask references, hash/read buffers. No fullN array or graph JSON is loaded; graph hashes bind the prior exact proof. This is a construction bound, not measured RSS or timing.',
                                    measured_performance=False,heavy_lease_required=False),
                source_identity={path:sha(path) for path in ['experimental/scenario-members/bridge_v2.py','experimental/sipp-routing/src/wfg_sipp/frontend.py','experimental/scenario-members/src/wfg_scenario_members/reduction.py']},
                output_sha256={'MEMBER_SUPPORT.csv':sha(support_csv)},
                limits='Exact only for current strict whole-declared-domain support predicate and saved inputs. No physical impossibility, local pessimistic support theorem, radiation-law validation, routing-risk rate or new policy is inferred. Prior first32 artifacts unchanged.')
    (a.out/'RESULTS.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=report['status'],totals=report['totals'],maximum_member_raw_bytes=maximum_member_bytes,
                         all_domain_masks_shared=all(r['all_saved_unknown_masks_byte_equal'] for r in rows),new_searches=0)))


if __name__=='__main__': main()
