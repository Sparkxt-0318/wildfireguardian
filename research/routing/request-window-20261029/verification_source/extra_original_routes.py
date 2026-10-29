"""Three original-reference witnesses that cannot inherit current-route checks.

Read-only adapter over the sealed actual_routes implementation. Sources, graph,
request and numerical law must match; each distinct original witness is checked
directly and is not replaced by another route with the same arrival time.
"""
from pathlib import Path
from fractions import Fraction as Q
import argparse,json
import actual_routes as A
import oracle as O

ROOT=A.ROOT
INDEX=ROOT/'audit/UNMAPPED_CONTEXT_REVIEW.json'
SEAL=ROOT/'reference/EXTRA_ORIGINAL_SOURCE_SEAL.json'

def decode(value):
    if isinstance(value,dict):
        if set(value)=={'__wfg_fraction__'}:
            f=value['__wfg_fraction__']
            if set(f)!={'numerator','denominator'}:raise ValueError('FRACTION_ENCODING')
            def integer(x):
                if type(x) is int:return x
                if isinstance(x,str):
                    try:n=int(x)
                    except ValueError:raise ValueError('FRACTION_INTEGER_ENCODING')
                    if str(n)==x:return n
                raise ValueError('FRACTION_INTEGER_ENCODING')
            numerator,denominator=integer(f['numerator']),integer(f['denominator'])
            if not denominator:raise ValueError('FRACTION_ZERO_DENOMINATOR')
            return Q(numerator,denominator)
        return {k:decode(v) for k,v in value.items()}
    if isinstance(value,list):return [decode(v) for v in value]
    return value

def extra_context(row,current):
    route=A.context(current);job=A.read(row['job_path']);raw=decode(A.read(row['result_path']));result=raw['result']
    if result.get('destination') is None:result=result['checked_incumbent']
    binding=route['binding']
    if job['arm']!='RDA_BASE' or job['case_id']!=route['case_id'] or job['cohort']!=route['cohort']:raise ValueError('ORIGINAL_CONTEXT')
    if job['input_sha256']['graph_path']!=binding['graph_file_sha256'] or job['input_sha256']['request_path']!=binding['request_sha256']:raise ValueError('ORIGINAL_GRAPH_OR_REQUEST_DIFFERENT')
    if job['source_sha256']!=binding['packet_sha256']:raise ValueError('ORIGINAL_PACKET_DIFFERENT')
    if raw['whole_road_check']['status']!='CERTIFIED_ADMISSIBLE':raise ValueError('ORIGINAL_NOT_CHECKED')
    cj=A.read(current['job']);graph=A.read(A.STUDY/cj['graph_path']);request=A.read(A.STUDY/cj['full_request_path'])
    legs=A.witness(graph,request,result);recorded=raw['whole_road_check']['trajectory']
    if len(legs)!=len(recorded):raise ValueError('ORIGINAL_TRAJECTORY_LENGTH')
    for r,l in zip(recorded,legs):
        if (r['kind'],O.number(r['start']),O.number(r['end']),tuple(map(O.number,r['p0'])),tuple(map(O.number,r['p1'])))!=(l.kind,l.start,l.end,l.p0,l.p1):raise ValueError('ORIGINAL_TRAJECTORY_MISMATCH')
    if len(result['legs'])!=row['original_route_leg_count'] or O.number(result['arrival'])!=O.number(row['arrival']):raise ValueError('INDEX_WITNESS_MISMATCH')
    original={m['id']:m for m in raw['whole_road_check']['radiation']['per_member']}
    if set(original)!=set(binding['scenario_ids']):raise ValueError('ORIGINAL_MEMBER_SET')
    route['legs']=legs;route['original']=original
    route['binding']={**binding,'original_job_path':row['job_path'],'original_result_path':row['result_path'],
       'comparison_bounds_origin':'original RESULT.whole_road_check.radiation; recorded project report, not a new independent grade',
       'original_whole_model_context_digest_from_audit':row['whole_model_context_digest'],
       'original_witness_directly_reconstructed_and_compared':True,'source_graph_request_hashes_match_current':True}
    return route

def freeze():
    inherited=A.read(A.SEAL);A.check(inherited);index=A.read(INDEX)
    if index['unmapped_original_executions']!=6 or index['unique_unmapped_contexts']!=3:raise ValueError('FIXED_POPULATION')
    files=set(inherited['source_sha256'])|{str(A.SEAL),str(INDEX),str(Path(__file__).resolve()),str(ROOT/'reference/EXTRA_ORIGINAL_PROTOCOL.md'),str(ROOT/'reference/test_extra_original.py')}
    for row in index['rows']:files|={row['job_path'],row['result_path']}
    A.write(SEAL,dict(status='FROZEN_BEFORE_THREE_EXTRA_ORIGINAL_REFERENCES',source_sha256={p:A.sha(p) for p in sorted(files)},contexts=inherited['contexts'],extra=index['rows']))
    print('SEALED',len(files),'files')

def run(case):
    s=A.read(SEAL);A.check(s);rows=[r for r in s['extra'] if r['case_id']==case]
    current=[c for c in s['contexts'] if A.read(c['job'])['case_id']==case]
    if len(rows)!=1 or len(current)!=1:raise ValueError('UNIQUE_ORIGINAL_CASE_REQUIRED')
    result=A.assess(extra_context(rows[0],current[0]),'radial');A.check(s)
    A.write(ROOT/'reference'/('ORIGINAL_EXTRA_'+case+'_RADIAL.json'),dict(status='COMPLETE_SCOPED',source_seal_sha256=A.sha(SEAL),result=result))
    print(json.dumps(dict(case=case,thermal_pass=result['all_members_within_thermal_thresholds'],elapsed_s=result['elapsed_s'],scope='Direct check of one original-reference witness, two duplicate executions require separate exact context identity map')))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','run']);p.add_argument('--case');args=p.parse_args()
    if args.action=='seal':freeze()
    elif not args.case:p.error('--case required')
    else:run(args.case)
