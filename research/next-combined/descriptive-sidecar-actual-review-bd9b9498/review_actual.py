"""Prepared independent actual sidecar review. DO NOT RUN before root release.

No producer imports or model execution. Actual arrays are exclusively US per-fire
saved predictions and the completed US draw matrix. KR NPZ is never decoded.
"""
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
import argparse
import ast
import fcntl
import gzip
import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
import numpy as np
import review_math as M

METHOD='5fd4314d7bfa7523fe3a19432c61198a93f8484abb83bc20a4ae7d11937088a0'
SPEC='0dffd934920b72b0eac36d83dc1b7950b818e039c25264874e59d161a08b04fb'
SOURCE='c41e607a167edae4058da2d5945c30b3d6e021f79461b17cdabf07c442bca799'
SOURCE_REVIEW='2bb880ce72b27a13c2290f6eec639bc17038de522329a55493ee5ad85ce8cb31'
CANONICAL='083d06c50d44258a771793410eea513f297fbc587432df872b9ea8cc46b8b755'
HEAD='691cc162bf2c0295cecc257a558ae0d583f9018e'
MODEL_ORDER=['base_seed0','burnout_seed0','burnout_spotting_seed0','c651_mc','c651_meanfield',
 'd4_seed0','d4_wind_seed0','dilation_1h','dilation_2h','dilation_4h','dilation_8h','dilation_best',
 'ellipse_seed0','logistic','mixed_base_seed0','persistence']
EVENTS=['ID-BOF-000683_Wapiti_Wapiti','ID-BOF-000904_Goat','ID-BOF-001080_Lava',
 'ID-SCF-240202_RedRock','WA-SES-000173_Pioneer','WY-BTF-002416_FishCreek']
KR_EVENTS=['KFS_01','KFS_04','KFS_06','KFS_13']
INVENTORIES={
 'us2024':('research/forecast-v2/PREASSESSMENT_US2024_TIMESTAMPS.json','51d910392b5f47f20b57ba56a4b2d25bc9096d33ac1dd09361f32a925884028d'),
 'korea2025':('research/forecast-v2/PREASSESSMENT_KOREA2025_WINDOWS.json','6286e0541a95b5f4806943bb809aa9314d55c2a637171002027c05e6292fc42d')}
LITERAL_MODELS=('c651_mc','d4_wind_seed0','logistic')
LITERAL_VECTORS=((1,1,1,1,1,1),(3,0,1,0,1,1))


def need(value,message):
    if not value:raise AssertionError(message)


def digest(blob):return hashlib.sha256(blob).hexdigest()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(8*1024*1024):h.update(block)
    return h.hexdigest()


def strict(blob):
    def pairs(values):
        out={}
        for k,v in values:
            need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def finite(token):
        value=float(token);need(math.isfinite(value),'nonfinite JSON number');return value
    def forbidden(token):raise AssertionError('nonfinite JSON token '+token)
    return json.loads(blob,object_pairs_hook=pairs,parse_float=finite,parse_constant=forbidden)


def inside(root,name):
    p=Path(name)
    need(type(name) is str and not p.is_absolute() and str(p)==name and '..' not in p.parts,'normalized relative path')
    q=root/p
    need(not any(x.is_symlink() for x in (q,*q.parents)) and q.resolve().is_relative_to(root),'nonsymlink contained path')
    return q


def compare_values(actual,expected,label,exact=False):
    if expected is None:need(actual is None,label+' must be null');return
    if isinstance(expected,list):
        need(isinstance(actual,list) and len(actual)==len(expected),label+' interval shape')
        for i,(a,b) in enumerate(zip(actual,expected)):compare_values(a,b,f'{label}[{i}]',exact)
        return
    need(type(actual) in (int,float) and type(expected) in (int,float) and math.isfinite(actual),label+' finite scalar')
    need(actual==expected if exact else np.isclose(actual,expected,rtol=1e-12,atol=1e-14),label+' differs')


def compare_descriptor(actual,expected,label):
    compare_values(actual.get('point'),expected['point'],label+' point',exact=True)
    for key in ('percentile_95_interval','conditional_on_defined_draws_interval'):
        compare_values(actual.get(key),expected[key],label+' '+key)
    for key in ('status','defined_draws','undefined_no_positive_draws','undefined_no_negative_draws','undefined_union_draws','conditional_scope'):
        need(type(actual.get(key)) is type(expected[key]) and actual[key]==expected[key],label+' '+key)
    need(actual['draws']==10000 and actual['seed']==20261030 and actual['quantile_method']=='linear',label+' fixed policy')
    need(actual['interval_unit']=='whole fire, pooled canonical cell-interval entries',label+' pooled unit')


def map858(value):
    candidates=[]
    def walk(x):
        if isinstance(x,dict):
            if len(x)==858 and all(type(k) is str and type(v) is str and len(v)==64
                                   and all(c in '0123456789abcdef' for c in v) for k,v in x.items()):candidates.append(x)
            for item in x.values():walk(item)
        elif isinstance(x,list):
            for item in x:walk(item)
    walk(value);need(len(candidates)==1,'one root-bound858-file canonical map');return candidates[0]


@contextmanager
def heavy():
    with Path('/tmp/wfg/HEAVY.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def review(args):
    versions={k:importlib.metadata.version(k) for k in ('numpy','scipy','scikit-learn')}
    need(versions=={'numpy':'1.26.4','scipy':'1.13.1','scikit-learn':'1.5.2'},'pinned versions')
    auth_path=args.authorization.resolve();need(sha(auth_path)==args.authorization_sha256,'exogenous authorization hash')
    auth=strict(auth_path.read_bytes());root=Path(auth['model_root']).resolve()
    need(auth['method_protocol_sha256']==METHOD and auth['prerequisite_spec_sha256']==SPEC,'method/spec')
    need(auth['receipt_version']=='wfg.current-descriptive-interval-authorization/2' and auth['status']=='AUTHORIZED_SAVED_OUTPUT_ONLY','root authorization role')
    need(auth['canonical_review_source_head']==HEAD and auth['model_order']==MODEL_ORDER,'canonical head/model order')
    need(auth['supplement_source']['sha256']==SOURCE and auth['independent_source_review']['sha256']==SOURCE_REVIEW,'source/review pins')
    need(sha(args.canonical_map)==args.canonical_map_sha256,'exogenous858-map hash')
    protected_receipt=strict(args.canonical_map.read_bytes())
    need(protected_receipt['source_head']==HEAD and protected_receipt['status']=='MATCH_ROOT_CANONICAL_858_PROTECTION'
         and protected_receipt['changed_current_files']==[],'canonical858 immutable head/claim')
    canonical_map=map858(protected_receipt)
    output=inside(root,auth['output_relative_directory']);completion=output/'COMPLETION.json'
    need(completion.is_file(),'producer completion required before any output/array review')
    need({p.name for p in output.iterdir()}=={'COMPLETION.json','DESCRIPTIVE_INTERVALS.json','README.md','supplement_source.py.gz','us2024_draws.npy'},'exclusive completed output set; no KR draw')
    completion_before=sha(completion);done=strict(completion.read_bytes());result_path=output/'DESCRIPTIVE_INTERVALS.json'
    need(done['status']=='COMPLETED_SAVED_OUTPUT_COMPUTATION' and done['result_sha256']==sha(result_path),'completion result hash')
    need(done['readme_sha256']==sha(output/'README.md'),'completion README hash')
    result=strict(result_path.read_bytes())
    source_gzip_before=sha(output/'supplement_source.py.gz')
    need(result['executed_source_sha256']==SOURCE==done['executed_source_sha256']==digest(gzip.decompress((output/'supplement_source.py.gz').read_bytes())),'executed source/snapshot')
    need(result['dependencies']['numpy']=='1.26.4' and result['dependencies']['scipy']=='1.13.1'
         and result['dependencies']['sklearn']=='1.5.2','producer pinned dependencies')
    baseline_sha='325abbe79ba7c22ed3eb60391a68d2becdbfd0aa4c6659debb94db6a34afbb1f'
    tool=inside(root,auth['supplement_source']['path']).parent
    raw_point_source=gzip.decompress((tool/'frozen_source'/baseline_sha/'baselines.py.gz').read_bytes())
    need(digest(raw_point_source)==baseline_sha and result['point_estimator_source_sha256']==baseline_sha,'point source identity')
    tree=ast.parse(raw_point_source)
    imports=[n for n in tree.body if isinstance(n,ast.Import) and any(a.name=='numpy' and a.asname=='np' for a in n.names)]
    constants=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'BINS','LOG_FLOOR'} for t in n.targets)]
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'score','_average_precision','_auc','calibration_table'}]
    ast_pins={str(i):digest(ast.dump(n,include_attributes=False).encode()) for i,n in enumerate(imports+constants+functions)}
    need(result['point_estimator_ast_sha256']==ast_pins,'exact point AST metadata')
    need(result['root_authorization_sha256']==args.authorization_sha256 and result['method_protocol_sha256']==METHOD
         and result['prerequisite_spec_sha256']==SPEC,'result identity chain')
    need(result['canonical_bindings']==auth['canonical_bindings'] and result['frozen_files_sha256']==auth['frozen_files_sha256'],'canonical/frozen binding maps')
    need(result['frozen_primary_unchanged'] is True and result['promotion_criteria_pass'] is False and result['model_inference'] is False,'no promotion/inference claim')
    pins=dict(auth['input_artifacts_sha256']);need(len(auth['frozen_files_sha256'])==223,'exact frozen223 count')
    for name,h in auth['frozen_files_sha256'].items():
        need(name not in pins or pins[name]==h,'consistent overlapping input identity');pins[name]=h
    for name,(path,h) in INVENTORIES.items():need(auth['input_artifacts_sha256'].get(path)==h,'consumed frozen inventory listed: '+name)
    frozen_before={str(inside(root,n)):h for n,h in pins.items()}
    # Closure hashes may read compressed bytes of KR NPZ, but never decode them.
    protected=dict(pins)
    for name,h in canonical_map.items():
        need(name not in protected or protected[name]==h,'canonical/input overlap agrees');protected[name]=h
    for name,h in protected.items():need(sha(inside(root,name))==h,'before complete closure hash '+name)
    seen=result['consumed_artifacts_before_after_sha256']
    need(all(seen.get(name)==h for name,h in frozen_before.items()),'producer complete closure bookend')
    extra=set(seen)-set(frozen_before);need(len(extra)==1,'one external authorization bookend')
    for name in extra:need(seen[name]==args.authorization_sha256 and sha(Path(name))==args.authorization_sha256,'producer authorization bytes')
    canonical_pin=auth['canonical_bindings']['results'];canonical_path=inside(root,canonical_pin['path'])
    need(canonical_pin['sha256']==CANONICAL,'expected root-bound canonical083d')
    canonical=strict(canonical_path.read_bytes());need(canonical['retrospective_superiority_gate']['criteria_pass'] is False,'canonical primary remains false')
    receipt=lambda k,c:strict(inside(root,auth['canonical_bindings'][k][c]['path']).read_bytes())
    us,kr=receipt('assessments','us2024'),receipt('assessments','korea2025')
    need(us['status']=='COMPLETE' and us['events']==EVENTS and len(us['cases'])==273 and Counter(r['status'] for r in us['cases'])=={'SCORED':273},'full US273 metadata')
    need(kr['status']=='HOLD' and kr['events']==KR_EVENTS and len(kr['cases'])==33 and Counter(r['status'] for r in kr['cases'])=={'SCORED':26,'UNAVAILABLE':7},'full KR33 metadata/outcomes')
    for cohort,assessment in [('us2024',us),('korea2025',kr)]:
        payload=strict(inside(root,INVENTORIES[cohort][0]).read_bytes())
        cases=payload['cases'] if cohort=='us2024' else [r['case'] for r in payload['cases']]
        expected={digest(json.dumps(c,sort_keys=True).encode())[:24]:c for c in cases}
        need(len(expected)==len(cases)==len(assessment['cases']),'unique complete case census')
        actual={r['case_id']:r['case'] for r in assessment['cases']}
        need(actual==expected and len(actual)==len(assessment['cases']),'exact frozen case identity join')
    kr_output=result['cohorts']['korea2025']
    need(kr_output['status']=='UNAVAILABLE_COMPLETE_CANONICAL_SUPPORT' and kr_output['metrics'] is None
         and kr_output['original_outcomes']==kr['failed_or_unavailable'] and len(kr_output['original_outcomes'])==7,'no KR subset bootstrap')
    need(kr_output['complete_cohort'] is False and not any(k in kr_output for k in ('models','paired_ap','draw_matrix')),'no hidden KR descriptive subset')
    need(result['status']=='INCOMPLETE_COHORTS_EXPLICITLY_UNAVAILABLE','global subset status')
    need(done['cohort_statuses']=={name:value['status'] for name,value in result['cohorts'].items()}
         and done['promotion_criteria_pass'] is False,'completion cohort statuses/scope')
    record=result['cohorts']['us2024'];need(record['status']=='AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT' and record['fire_order']==EVENTS
        and record['model_order']==MODEL_ORDER and record['entry_count']==1705079 and set(record['models'])==set(MODEL_ORDER),'US fixed complete summary')
    need(record['fire_count']==6 and record['protocol_sha256']==METHOD and record['frozen_primary_unchanged'] is True
         and record['promotion_criteria_pass'] is False and record['artifact_hashes_after']==frozen_before,'US metadata/inner full closure')
    draws=M.plan(6);dpath=output/'us2024_draws.npy'
    saved=np.load(dpath,allow_pickle=False);need(saved.dtype.str=='<i8' and saved.shape==(10000,6) and np.array_equal(saved,draws.matrix),'exact integer draw matrix')
    dmeta=record['draw_matrix'];need(dmeta['dtype']=='<i8' and dmeta['order']=='C' and dmeta['shape']==[10000,6]
        and dmeta['npy_sha256']==sha(dpath) and dmeta['little_endian_int64_payload_sha256']==digest(saved.tobytes(order='C'))
        and dmeta['original_draws']==10000 and dmeta['multiplicity_vectors']==len(draws.vectors)
        and dmeta['repeated_vector_frequencies_restored'] is True,'draw payload/frequencies')
    directory=inside(root,auth['run_relative_path'])/'heldout'
    files=[directory/(event+'.npz') for event in EVENTS]
    labels=[]
    for event,path in zip(EVENTS,files):
        need(sha(path)==us['per_fire_files'][path.name],'US aggregate custody')
        with np.load(path,allow_pickle=False) as data:
            need(set(data.files)=={'row','col','y','interval','t1','hours',*('p_'+n for n in MODEL_ORDER)},'fixed16 aggregate schema')
            y=data['y'];need(y.ndim==1 and np.isin(y,[0,1]).all() and len(y)>0,'US binary labels')
            cases=[r for r in us['cases'] if r['case']['event']==event]
            counts=[r['scored_cells'] for r in cases]
            need(len(y)==sum(counts) and int(y.sum())==sum(r['positives'] for r in cases)
                and np.array_equal(data['interval'],np.repeat(np.arange(len(cases)),counts)),'US case/interval counts')
            need(data['t1'].tolist()==[r['case']['cutoff'] for r in cases] and data['hours'].tolist()==[r['case']['hours'] for r in cases],'US interval metadata')
            labels.append(y.astype(np.float64))
    need(sum(map(len,labels))==1705079,'US exact total entries')
    ap_values={};ap_points={};checks=[];literal=[]
    for name in MODEL_ORDER:
        p=[]
        for path in files:
            with np.load(path,allow_pickle=False) as data:p.append(data['p_'+name].astype(np.float64))
        need(set(record['models'][name])==set(M.FIELDS),name+' exact five diagnostic fields')
        points,values,pos,neg=M.distributions(labels,p,draws)
        for field,raw in zip(M.FIELDS,M.RAW):
            compare_values(points[field],canonical['heldout']['models'][name]['pooled'][raw],name+' original raw '+raw,exact=True)
            kind='ap' if field=='pooled_average_precision' else 'auc' if field=='pooled_roc_auc' else 'finite'
            expected=M.descriptor(values[field],points[field],pos,neg,kind)
            compare_descriptor(record['models'][name][field],expected,name+' '+field)
        if name in LITERAL_MODELS:
            for m in LITERAL_VECTORS:
                reference=M.literal_reference(labels,p,m);v=np.flatnonzero(np.all(draws.vectors==m,axis=1))
                need(len(v)==1,'predeclared multiplicity is present')
                first=np.flatnonzero(draws.inverse==v[0])[0]
                for field in M.FIELDS:
                    a=None if not np.isfinite(values[field][first]) else float(values[field][first])
                    compare_values(a,reference[field],name+' actual literal '+field)
                literal.append(dict(model=name,multiplicity=list(m),status='PASS_LITERAL_AND_SKLEARN'))
        ap_values[name]=values['pooled_average_precision'];ap_points[name]=points['pooled_average_precision']
        checks.append(dict(model=name,status='PASS_5_POINTS_AND_5_FULL_DISTRIBUTION_INTERVALS'))
        print(json.dumps(dict(model=name,review='PASS_INDEPENDENT_RAW_REPLAY')),flush=True)
    expected_pairs={name+'__vs__'+ref for name in MODEL_ORDER for ref in ('persistence','dilation_best')}
    need(set(record['paired_ap'])==expected_pairs,'exact32 paired AP descriptors')
    for name in MODEL_ORDER:
        for ref in ('persistence','dilation_best'):
            point=None if ap_points[name] is None else ap_points[name]-ap_points[ref]
            expected=M.descriptor(ap_values[name]-ap_values[ref],point,pos,neg,'paired_ap')
            got=record['paired_ap'][name+'__vs__'+ref];compare_descriptor(got,expected,name+' paired AP '+ref)
            need(got['candidate']==name and got['reference']==ref and got['favourable_direction']=='positive'
                and got['descriptive_secondary_only'] is True,'paired AP identity/scope')
    for name,h in protected.items():need(sha(inside(root,name))==h,'after complete closure hash '+name)
    need(sha(auth_path)==args.authorization_sha256 and sha(completion)==completion_before,'authorization/completion stable')
    need(sha(result_path)==done['result_sha256'] and sha(output/'README.md')==done['readme_sha256']
         and sha(dpath)==dmeta['npy_sha256'] and sha(output/'supplement_source.py.gz')==source_gzip_before,'all output payloads stable')
    current_head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    need(subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',HEAD,current_head],capture_output=True).returncode==0,'canonical691 ancestor of advanced source head')
    return dict(status='PASS_INDEPENDENT_ACTUAL_DESCRIPTIVE_INTERVAL_REVIEW',source_sha256=SOURCE,method_protocol_sha256=METHOD,
        prerequisite_spec_sha256=SPEC,root_authorization_sha256=args.authorization_sha256,canonical_review_source_head=HEAD,
        sidecar_sha256=sha(result_path),canonical_sha256=canonical_pin['sha256'],canonical_preserved_files=858,frozen_preserved_files=223,current_source_head=current_head,
        closure_files=len(pins),models=checks,actual_literal_controls=literal,paired_ap_descriptors=32,
        us_cases=273,us_entries=1705079,us_fires=6,draws=10000,unique_multiplicities=len(draws.vectors),
        korean_status='UNAVAILABLE_COMPLETE_COHORT_26_SCORED_7_UNAVAILABLE',korean_npz_decoded=False,
        canonical_primary_criteria_pass=False,promotion_criteria_pass=False,model_inference=False,dependencies=versions,
        checker_sha256=sha(Path(__file__)),math_source_sha256=sha(Path(M.__file__)),
        limits=['Independent pooled stored-per-fire interval replay, not raw-source label/support truth or model-prediction replay',
                'Original case-to-fire prediction equality relies additionally on the authenticated prior87eb review; case files are hashed but not redecoded here',
                'Only predeclared actual literal vectors/models are directly duplicated for sklearn checks; all full distributions are independently reconstructed',
                'Conditional mapped-extent descriptive intervals; no physical/2026/routing-safety or promotion conclusion'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorization',type=Path,required=True);p.add_argument('--authorization-sha256',required=True)
    p.add_argument('--canonical-map',type=Path,required=True);p.add_argument('--canonical-map-sha256',required=True)
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    need(args.out.parent.resolve()==Path(__file__).resolve().parent,'review output stays in owned scratch directory')
    need(not args.out.exists(),'preserve earlier review output')
    manifest_path=Path(__file__).parent/'PREPARATION_MANIFEST.json'
    prepared=strict(manifest_path.read_bytes())
    need(args.authorization_sha256==prepared['authorization_sha256'] and args.canonical_map_sha256==prepared['canonical_map_sha256'],'root-pinned prepared review identities')
    for name,h in prepared['files_sha256'].items():need(sha(Path(__file__).parent/name)==h,'unchanged prepared checker '+name)
    try:
        with heavy():result=review(args)
        code=0
    except Exception as error:
        result=dict(status='HOLD_INDEPENDENT_ACTUAL_DESCRIPTIVE_INTERVAL_REVIEW',error_type=type(error).__name__,
                    reason=str(error),checker_sha256=sha(Path(__file__)),math_source_sha256=sha(Path(M.__file__)),
                    root_authorization_sha256=args.authorization_sha256,model_inference=False,promotion_criteria_pass=False)
        code=1
    result['preparation_manifest_sha256']=sha(manifest_path)
    with args.out.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(status=result['status'],output=str(args.out))))
    return code


if __name__=='__main__':raise SystemExit(main())
