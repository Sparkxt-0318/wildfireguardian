"""Invented data only. No ROOT import, source mutation, or real HEAVY lease."""
from contextlib import nullcontext
from collections import Counter
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('scratch_descriptive_candidate', HERE/'supplement.py')
S = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = S
spec.loader.exec_module(S)


def invented(fires):
    labels = [np.array([0, 1, 1, 0, 1][:2+i % 4], float) for i in range(fires)]
    values = [np.array([.1, .5, .5, .9, 1.][:len(y)], float) for y in labels]
    # Include unequal fire sizes, exact ties, class-pure fires and zero-weight groups.
    labels[0] = np.array([0., 0.]); labels[1] = np.array([1., 1., 1.])
    values[0] = np.array([0., .5]); values[1] = np.array([.5, .5, 1.])
    return labels, values


@pytest.mark.parametrize('fires', [4, 6])
def test_all_cached_vectors_equal_literal_and_sklearn(fires):
    ys, ps = invented(fires)
    draws = S.draw_plan([str(i) for i in range(fires)])
    point, values, no_pos, no_neg = S.model_draw_values(ys, ps, draws)
    assert np.array_equal(draws.matrix, np.random.default_rng(20261030).integers(0, fires, (10000, fires)))
    assert len(draws.vectors) <= {4:35, 6:462}[fires]
    assert np.array_equal(draws.vectors[draws.inverse], draws.multiplicities)
    assert np.array_equal(np.bincount(draws.inverse), draws.frequencies)
    assert draws.frequencies.sum() == 10000
    engine = S.frozen_point_engine()
    for index, m in enumerate(draws.vectors):
        y = np.concatenate([np.tile(a, n) for a, n in zip(ys, m)])
        p = np.concatenate([np.tile(a, n) for a, n in zip(ps, m)])
        expected = engine.score(y, p)
        draw_index = np.flatnonzero(draws.inverse == index)[0]
        for field, key in S.ABSOLUTE.items():
            actual = values[field][draw_index]
            if expected[key] is None:
                assert np.isnan(actual)
            else:
                np.testing.assert_allclose(actual, expected[key], rtol=1e-12, atol=1e-14)
        if y.sum():
            np.testing.assert_allclose(values['pooled_average_precision'][draw_index], average_precision_score(y,p), rtol=1e-12, atol=1e-14)
        if 0 < y.sum() < len(y):
            np.testing.assert_allclose(values['pooled_roc_auc'][draw_index], roc_auc_score(y,p), rtol=1e-12, atol=1e-14)
    for field, key in S.ABSOLUTE.items():
        assert point[field] == engine.score(np.concatenate(ys), np.concatenate(ps))[key]
    assert np.array_equal(no_pos, draws.multiplicities @ np.array([y.sum() for y in ys]) == 0)
    assert np.array_equal(no_neg, draws.multiplicities @ np.array([(1-y).sum() for y in ys]) == 0)
    # Unique vectors are not equally likely; retaining frequencies changes an estimand.
    assert len(set(draws.frequencies)) > 1
    unique = values['pooled_raw_brier'][np.unique(draws.inverse, return_index=True)[1]]
    assert abs(unique.mean() - values['pooled_raw_brier'].mean()) > 1e-6


def test_bins_clipping_ties_and_raw_brier():
    p = np.array([0., np.nextafter(.1,0), .1, .2, .5, .5, 1.])
    y = np.array([1.,0.,1.,0.,1.,0.,0.])
    labels, values = [y]*4, [p]*4
    d = S.draw_plan(['a','b','c','d'])
    point, boot, pos, neg = S.model_draw_values(labels, values, d)
    expected = S.frozen_point_engine().score(y,p)
    assert point['pooled_raw_brier'] == S.frozen_point_engine().score(np.concatenate(labels),np.concatenate(values))['brier']
    for field, key in S.ABSOLUTE.items():
        np.testing.assert_allclose(boot[field], expected[key], rtol=1e-12, atol=1e-14)
    assert np.all(np.isfinite(boot['pooled_clipped_nll']))
    _, tied, _, _ = S.model_draw_values([np.array([0,1])]*4,[np.array([.5,.5])]*4,d)
    assert np.all(tied['pooled_roc_auc'] == .5)


@pytest.mark.parametrize('all_value', [0,1])
def test_class_absence_exact_counts_and_full_null(all_value):
    d = S.draw_plan(['a','b','c','d'])
    point, values, pos, neg = S.model_draw_values([np.array([all_value])]*4,[np.array([.3])]*4,d)
    ap = S.interval(values['pooled_average_precision'], point['pooled_average_precision'],pos,neg,kind='ap')
    auc = S.interval(values['pooled_roc_auc'], point['pooled_roc_auc'],pos,neg,kind='auc')
    assert auc['percentile_95_interval'] is None and auc['undefined_union_draws'] == 10000
    assert auc['undefined_no_positive_draws'] == (10000 if all_value == 0 else 0)
    assert auc['undefined_no_negative_draws'] == (10000 if all_value == 1 else 0)
    if all_value:
        assert ap['point'] == 1 and ap['percentile_95_interval'] == [1,1]
    else:
        assert ap['point'] is None and ap['percentile_95_interval'] is None


def test_some_undefined_draws_keep_full_interval_null():
    labels, values = invented(4)
    d = S.draw_plan(['a','b','c','d'])
    point, boot, pos, neg = S.model_draw_values(labels,values,d)
    r = S.interval(boot['pooled_average_precision'],point['pooled_average_precision'],pos,neg,kind='ap')
    assert 0 < r['undefined_union_draws'] < 10000
    assert r['percentile_95_interval'] is None
    assert r['conditional_on_defined_draws_interval'] is not None
    assert r['defined_draws'] + r['undefined_union_draws'] == 10000


def points_for(labels, values):
    raw = S.frozen_point_engine().score(np.concatenate(labels),np.concatenate(values))
    return {key:raw[key] for key in S.ABSOLUTE.values()}


def test_fixed16_models_same_draws_and32_paired_ap():
    labels, values = invented(4)
    names = S.protocol()['model_order']
    canonical = {n:points_for(labels,values) for n in names}
    result, d = S.compute_cohort('korea2025',labels,lambda n:values,canonical)
    assert list(result['models']) == names and len(result['paired_ap']) == 32
    for record in result['paired_ap'].values():
        assert record['point'] == 0
        assert record['percentile_95_interval'] is None
        assert record['conditional_on_defined_draws_interval'] == [0,0]
    assert result['promotion_criteria_pass'] is False


@pytest.mark.parametrize('change', ['ulp','bool','missing_model','extra_model'])
def test_canonical_points_and_model_set_exact(change):
    labels, values = invented(4)
    canonical = {n:points_for(labels,values) for n in S.protocol()['model_order']}
    first = next(iter(canonical))
    if change == 'ulp': canonical[first]['brier'] = float(np.nextafter(canonical[first]['brier'],1))
    if change == 'bool': canonical[first]['average_precision'] = True
    if change == 'missing_model': canonical.pop(first)
    if change == 'extra_model': canonical['extra'] = canonical[first]
    with pytest.raises(S.AdmissionError): S.compute_cohort('korea2025',labels,lambda n:values,canonical)


@pytest.mark.parametrize('change', ['nan','inf','below','above','empty','label','shape'])
def test_invalid_vectors_never_trimmed(change):
    ys, ps = invented(4)
    if change in ['nan','inf','below','above']: ps[0][0] = dict(nan=np.nan,inf=np.inf,below=-.001,above=1.001)[change]
    if change == 'empty': ys[0]=ys[0][:0]; ps[0]=ps[0][:0]
    if change == 'label': ys[0][0]=.5
    if change == 'shape': ps[0]=ps[0][:-1]
    with pytest.raises(S.AdmissionError): S.model_draw_values(ys,ps,S.draw_plan(['a','b','c','d']))


def test_draw_artifact_payload_and_exclusive_output(tmp_path):
    d = S.draw_plan(['a','b','c','d'])
    path = tmp_path/'draws.npy'; r = S.save_draws(path,d)
    assert r['npy_sha256'] == S.sha_bytes(path.read_bytes())
    assert r['little_endian_int64_payload_sha256'] == S.sha_bytes(np.asarray(d.matrix,dtype='<i8',order='C').tobytes())
    assert r['dtype'] == '<i8' and r['shape'] == [10000,4]
    assert np.array_equal(np.load(path,allow_pickle=False),d.matrix)
    with pytest.raises(FileExistsError): S.save_draws(path,d)


def test_strict_json_duplicate_nonfinite_and_paths(tmp_path):
    for data in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
        with pytest.raises(S.AdmissionError): S.strict_json(data)
    for path in ['../x','a/../x','a//x','/x','a\\x','./x']:
        with pytest.raises(S.AdmissionError): S.relative_path(tmp_path,path)
    (tmp_path/'link').symlink_to(tmp_path)
    with pytest.raises(S.AdmissionError): S.relative_path(tmp_path,'link/file')


class InventedAuthority:
    """Isolated in-process mocks: invented inventory/proof hashes + no HEAVY lease.

    Production code has no fixture flag or way to set these values. This is not
    a claim that the external independent prerequisites have actually occurred.
    """
    def __init__(self, base, monkeypatch):
        self.root = base/'invented-root'; self.root.mkdir()
        self.bundle = self.root/'research/forecast-v2/supplements/candidate-source'
        self.bundle.mkdir(parents=True)
        shutil.copy(HERE/'supplement.py',self.bundle/'supplement.py')
        shutil.copytree(HERE/'method',self.bundle/'method')
        shutil.copytree(HERE/'frozen_source',self.bundle/'frozen_source')
        self.module_name = 'invented_authority_'+str(id(self))
        sp = importlib.util.spec_from_file_location(self.module_name,self.bundle/'supplement.py')
        self.m = importlib.util.module_from_spec(sp); sys.modules[sp.name]=self.m; sp.loader.exec_module(self.m)
        monkeypatch.setattr(self.m,'exclusive_heavy',nullcontext)
        self.run = self.root/'research/forecast-v2/executions/INVENTED_ONLY'
        self.out = self.root/'research/forecast-v2/supplements/INVENTED_ONLY'
        self.result_path = self.run/'RESULTS.json'
        self.auth_path = self.root/'INVENTED_AUTHORIZATION.json'
        self.census_path = self.root/'INVENTED_CENSUS.json'
        self.review_path = self.root/'INVENTED_CANONICAL_REVIEW.json'
        self.source_review = self.root/'INVENTED_SUPPLEMENT_REVIEW.txt'
        self.put(self.source_review,b'INVENTED fixture identity, no actual independent review\n')
        self.selection = self.root/'research/forecast-v2/INVENTED_SELECTION.json'
        self.registry = self.root/'research/forecast-v2/INVENTED_REGISTRY.json'
        self.dump(self.selection,{'fixture':'not an actual model selection'})
        self.dump(self.registry,{'fixture':'not an actual registry'})
        self.frozen_names = [self.selection,self.registry]
        for i in range(221):
            p=self.root/f'INVENTED_FROZEN/{i:03}.txt';self.put(p,f'invented source {i}\n'.encode());self.frozen_names.append(p)
        self.proof = self.root/'FREEZE_PARENT_VERIFICATION.json'
        self.dump(self.proof,{'verified_file_sha256':{self.rel(p):self.hash(p) for p in self.frozen_names}})
        monkeypatch.setattr(self.m,'ROOT_PROOF_SHA256',self.hash(self.proof))
        self.assessments = {}; self.inventory_paths={}
        self.report={'model_selection_sha256':self.hash(self.selection),'current_phase':{'fixture':'fixed invented phase'},
                     'primary_criteria_pass':False,'figure_evidence':{}}
        for stem in self.m.FIGURES:
            pair={}
            for ext in ('png','svg'):
                p=self.result_path.parent/'figures'/(stem+'.'+ext)
                self.put(p,b'INVENTED metadata-only figure placeholder, not a rendered study figure\n'+stem.encode()+ext.encode())
                pair[ext]=self.hash(p)
            self.report['figure_evidence'][stem]={'files_sha256':pair}
        method=self.m.protocol(); self.inventories={}
        for cohort, counts in [('us2024',[46,46,46,45,45,45]),('korea2025',[9,8,8,8])]:
            folder='heldout' if cohort=='us2024' else 'korean2025'
            directory=self.run/folder; records=[]; originals=[]; fire_files={}; all_labels=[]; all_p={n:[] for n in method['model_order']}
            frozen_path=directory/'FROZEN_ASSESSMENT.json'
            frozen={'cohort':cohort,'selection_sha256':self.hash(self.selection),'registry':self.pin(self.registry),
                    'source_sha256':{self.rel(self.frozen_names[-1]):self.hash(self.frozen_names[-1])},'current_phase':self.report['current_phase']}
            self.dump(frozen_path,frozen)
            for fi,(event,count) in enumerate(zip(method['cohorts'][cohort]['fire_order'],counts)):
                blocks=[]; ps={n:[] for n in method['model_order']}; cutoffs=[]
                for ci in range(count):
                    start=datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(hours=ci)
                    case={'event':event,'cutoff':start.isoformat(),
                          'endpoint':(start+timedelta(hours=1)).isoformat(),'hours':1.0}
                    originals.append(case)
                    cid=self.m.sha_bytes(json.dumps(case,sort_keys=True).encode())[:24]
                    row=np.array([0,1],dtype=np.int64);col=np.array([0,1],dtype=np.int64);y=np.array([0,1],dtype=np.uint8)
                    values={n:np.array([.1+mi*.01,.7+mi*.01],dtype=np.float64) for mi,n in enumerate(method['model_order'])}
                    arrays={'row':row,'col':col,'y':y,**{'p_'+n:v for n,v in values.items()}}
                    npz=directory/'cases'/(cid+'.npz');self.npz(npz,arrays)
                    mask=np.eye(2,dtype=bool)
                    record={'receipt_version':'wfg.forecast-assessment-case/2','case_id':cid,'case':case,'status':'SCORED',
                            'assessment_sha256':self.hash(frozen_path),'sha256':self.hash(npz),'scored_mask_sha256':self.m.array_sha(mask),
                            'scored_cells':2,'excluded_cells':2,'positives':1,'rectangle':[2,2],'reference_cells':4,'weather_hour':case['cutoff']}
                    for key in self.m.SOURCE_FIELDS-{'rectangle','reference_cells','weather_hour'}:record[key]='a'*64
                    self.dump(directory/'cases'/(cid+'.json'),record);records.append(record);blocks.append(arrays);cutoffs.append(case['cutoff'])
                    for n in ps:ps[n].append(values[n])
                aggregate={k:np.concatenate([b[k] for b in blocks]) for k in ('row','col','y')}
                aggregate.update(interval=np.repeat(np.arange(count),2),t1=np.array(cutoffs),hours=np.ones(count))
                aggregate.update({'p_'+n:np.concatenate(v) for n,v in ps.items()})
                path=directory/(event+'.npz');self.npz(path,aggregate);fire_files[path.name]=self.hash(path)
                all_labels.append(aggregate['y'])
                for n in all_p:all_p[n].append(aggregate['p_'+n])
            assessment={'receipt_version':'wfg.forecast-assessment/2','status':'COMPLETE','cohort':cohort,'events':method['cohorts'][cohort]['fire_order'],
                        'cases':records,'frozen_sha256':self.hash(frozen_path),'per_fire_files':fire_files,'failed_or_unavailable':[]}
            self.assessments[cohort]=assessment;self.dump(directory/'ASSESSMENT.json',assessment)
            reportkey='heldout' if cohort=='us2024' else 'korean2025_secondary_reconstruction'
            self.report[reportkey]={'assessment_status':'COMPLETE','models':{n:{'pooled':points_for(all_labels,p)} for n,p in all_p.items()}}
            ip=self.root/self.m.INVENTORIES[cohort][0]
            inventory={'case_count':len(originals),'cases':originals}
            if cohort=='korea2025':
                ids=[self.m.sha_bytes(json.dumps(c,sort_keys=True).encode())[:24] for c in originals]
                inventory.update(cases=[dict(case_id=i,case=c) for i,c in zip(ids,originals)],case_ids=ids)
            self.dump(ip,inventory);self.inventory_paths[cohort]=ip
            self.inventories[cohort]=(self.rel(ip),self.hash(ip))
        monkeypatch.setattr(self.m,'INVENTORIES',self.inventories)
        self.dump(self.result_path,self.report)
        self.seal()

    def put(self,path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    def dump(self,path,value):self.put(path,(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
    def npz(self,path,value):path.parent.mkdir(parents=True,exist_ok=True);np.savez(path,**value)
    def rel(self,p):return str(p.relative_to(self.root))
    def hash(self,p):return self.m.sha_bytes(p.read_bytes())
    def pin(self,p):return {'path':self.rel(p),'sha256':self.hash(p)}
    def directory(self,cohort):return self.run/('heldout' if cohort=='us2024' else 'korean2025')
    def load(self,p):return json.loads(p.read_text())
    def seal(self):
        spec=self.m.fixed_prerequisites(); bindings={'results':self.pin(self.result_path),'selection':self.pin(self.selection),'registry':self.pin(self.registry),
          'assessments':{},'frozen_assessments':{},'figures':{}}
        children={}; summaries={}
        for cohort in ('us2024','korea2025'):
            d=self.directory(cohort);a=self.load(d/'ASSESSMENT.json');self.assessments[cohort]=a
            bindings['assessments'][cohort]=self.pin(d/'ASSESSMENT.json');bindings['frozen_assessments'][cohort]=self.pin(d/'FROZEN_ASSESSMENT.json')
            inv=self.load(self.inventory_paths[cohort]);originals=inv['cases'] if cohort=='us2024' else [r['case'] for r in inv['cases']]
            ids=[r['case_id'] for r in a['cases']];expected=[self.m.sha_bytes(json.dumps(c,sort_keys=True).encode())[:24] for c in originals]
            events=list(dict.fromkeys(c['event'] for c in originals));statuses=dict(Counter(r['status'] for r in a['cases']))
            children[cohort]={'status':'COMPLETE_FROZEN_CASE_CENSUS','cohort':cohort,'expected_cases':len(originals),'represented_cases':len(ids),'unique_cases':len(set(ids)),
              'expected_fires':len(events),'per_fire_counts':dict(Counter(c['event'] for c in originals)),'outcome_counts':statuses,'assessment_status':a['status'],
              'case_order_matches_inventory':ids==expected,'declared_event_order_matches_inventory':a['events']==events,
              'case_population_sha256':self.m.sha_bytes(json.dumps(sorted(ids),separators=(',',':')).encode()),
              'inventory_path':self.rel(self.inventory_paths[cohort]),'inventory_sha256':self.hash(self.inventory_paths[cohort])}
            folder='heldout' if cohort=='us2024' else 'korean2025'
            summaries[folder]={'assessment_status':a['status'],'events':len(events),'cases':len(ids),'statuses':statuses,
              'scored_fires':len(a['per_fire_files']),'entries':sum(r.get('scored_cells',0) for r in a['cases'] if r['status']=='SCORED')}
        for stem in self.m.FIGURES:bindings['figures'][stem]={ext:self.pin(self.result_path.parent/'figures'/(stem+'.'+ext)) for ext in ('png','svg')}
        census={**spec['census_receipt']['required_fields'],'assessment_sha256':{c:p['sha256'] for c,p in bindings['assessments'].items()},'cohorts':children}
        review={**spec['canonical_result_review']['required_fields'],'authorized_source_head':'1'*40,'results_sha256':bindings['results']['sha256'],
          'selection_sha256':bindings['selection']['sha256'],'registry_sha256':bindings['registry']['sha256'],'cohorts':summaries}
        self.dump(self.census_path,census);self.dump(self.review_path,review)
        inputs={self.rel(p):self.hash(p) for p in self.root.rglob('*') if p.is_file() and p!=self.auth_path and not p.is_relative_to(self.out)}
        auth={**spec['root_actual_authorization']['fixed_values'],'receipt_version':'wfg.current-descriptive-interval-authorization/1','status':'AUTHORIZED_SAVED_OUTPUT_ONLY',
          'issued_utc':'2026-10-30T17:20:00+00:00','prerequisite_spec_sha256':self.m.PREREQUISITE_SHA256,'canonical_review_source_head':'1'*40,
          'model_root':str(self.root),'run_relative_path':self.rel(self.run),'supplement_source':self.pin(self.bundle/'supplement.py'),
          'independent_source_review':self.pin(self.source_review),'canonical_bindings':bindings,
          'prerequisite_receipts':{'census':self.pin(self.census_path),'canonical_result':self.pin(self.review_path)},
          'frozen_files_sha256':{self.rel(p):self.hash(p) for p in self.frozen_names},'input_artifacts_sha256':inputs,'model_order':self.m.protocol()['model_order'],
          'checker_sources':{'census':self.pin(self.bundle/'method/check_census.source.txt'),'canonical_result':self.pin(self.bundle/'method/check_results.source.txt')},
          'output_relative_directory':self.rel(self.out)}
        self.dump(self.auth_path,auth);self.auth_sha=self.hash(self.auth_path)
        return auth
    def authorize(self):return self.m.authorize(self.root,self.run,self.result_path,self.out,self.auth_path,self.auth_sha)


@pytest.fixture
def authority(tmp_path,monkeypatch):return InventedAuthority(tmp_path,monkeypatch)


def test_invented_full_chain_both_complete_and_primary_hold(authority):
    f=authority;m=f.m
    authorized=f.authorize()
    # Later unrelated sidecar additions do not rewrite the frozen review head.
    f.put(f.root/'LATER_SUPPLEMENT_ONLY.txt',b'invented later sidecar')
    result=m.run_authorized(authorized)
    assert result['status']=='COMPLETE_DESCRIPTIVE_SUPPLEMENT'
    assert result['promotion_criteria_pass'] is False and result['model_inference'] is False
    for cohort in ('us2024','korea2025'):
        record=result['cohorts'][cohort]
        assert len(record['models'])==16 and len(record['paired_ap'])==32
        assert record['entry_count']==m.protocol()['cohorts'][cohort]['expected_cases']*2
        assert record['status']=='AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT'
        assert record['draw_matrix']['original_draws']==10000
    assert result['canonical_bindings']==authorized.bindings
    assert f.load(f.result_path)['primary_criteria_pass'] is False
    assert (f.out/'DESCRIPTIVE_INTERVALS.json').exists()
    completion=f.load(f.out/'COMPLETION.json')
    assert completion['result_sha256']==f.hash(f.out/'DESCRIPTIVE_INTERVALS.json')
    assert completion['promotion_criteria_pass'] is False
    with pytest.raises(m.AdmissionError):f.authorize()


@pytest.mark.parametrize('change',['external_hash','boolean','review_head','source','proof','checker','canonical','unlisted_array','existing_out','escape'])
def test_outer_custody_refuses_before_array_load(authority,monkeypatch,change):
    f=authority;m=f.m
    auth=f.load(f.auth_path)
    if change=='external_hash':f.auth_sha='0'*64
    elif change=='boolean':auth['approved']=True
    elif change=='review_head':auth['canonical_review_source_head']='2'*40
    elif change=='source':f.put(f.bundle/'supplement.py',(f.bundle/'supplement.py').read_bytes()+b'\n# changed source\n')
    elif change=='proof':f.dump(f.proof,{'verified_file_sha256':{}})
    elif change=='checker':f.put(f.bundle/'method/check_census.source.txt',b'changed checker')
    elif change=='canonical':f.dump(f.result_path,{'invented':'changed canonical results'})
    elif change=='unlisted_array':
        extra=f.root/'UNLISTED.npy';np.save(extra,np.array([0]),allow_pickle=False);auth['input_artifacts_sha256'][f.rel(extra)]=f.hash(extra)
    elif change=='existing_out':f.out.mkdir(parents=True)
    elif change=='escape':auth['output_relative_directory']='research/forecast-v2/supplements/../escape'
    if change in ['boolean','review_head','unlisted_array','escape']:
        f.dump(f.auth_path,auth);f.auth_sha=f.hash(f.auth_path)
    def forbidden(*args,**kwargs):raise AssertionError('NPZ load before root/prerequisite admission')
    monkeypatch.setattr(m.np,'load',forbidden)
    with pytest.raises(m.AdmissionError):f.authorize()


def test_re_signed_missing_population_refused_before_array(authority,monkeypatch):
    f=authority;path=f.directory('us2024')/'ASSESSMENT.json';a=f.load(path)
    a['cases'].pop();f.dump(path,a);f.seal()
    monkeypatch.setattr(f.m.np,'load',lambda *a,**k:pytest.fail('arrays opened before case census'))
    with pytest.raises(f.m.AdmissionError):f.m.run_authorized(f.authorize())


def test_honest_hold_keeps_other_complete_cohort(authority):
    f=authority;d=f.directory('us2024');a=f.load(d/'ASSESSMENT.json');r=a['cases'][0]
    r.update(status='UNAVAILABLE',reason='INVENTED source support unavailable')
    r.pop('sha256');(d/'cases'/(r['case_id']+'.npz')).unlink();f.dump(d/'cases'/(r['case_id']+'.json'),r)
    a.update(status='HOLD',failed_or_unavailable=[r]);f.dump(d/'ASSESSMENT.json',a)
    report=f.load(f.result_path);report['heldout']['assessment_status']='HOLD';f.dump(f.result_path,report);f.seal()
    result=f.m.run_authorized(f.authorize())
    assert result['status']=='INCOMPLETE_COHORTS_EXPLICITLY_UNAVAILABLE'
    assert result['cohorts']['us2024']['metrics'] is None
    assert result['cohorts']['us2024']['original_outcomes']==[r]
    assert result['cohorts']['korea2025']['status']=='AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT'
    assert not (f.out/'us2024_draws.npy').exists()


@pytest.mark.parametrize('change',['nan','inf','out_of_range','fractional_row','mask_drop','aggregate_mismatch','missing_model','extra_model','label_mismatch'])
def test_resigned_case_data_cannot_create_available_subset(authority,change):
    f=authority;m=f.m;d=f.directory('us2024');a=f.load(d/'ASSESSMENT.json');record=a['cases'][0]
    path=d/'cases'/(record['case_id']+'.npz')
    with np.load(path,allow_pickle=False) as raw: data={k:raw[k] for k in raw.files}
    if change in ['nan','inf','out_of_range']:data['p_c651_mc'][0]={'nan':np.nan,'inf':np.inf,'out_of_range':1.1}[change]
    if change=='fractional_row':data['row']=np.array([0.,.5])
    if change=='mask_drop':data={k:v[:1] for k,v in data.items()}
    if change=='aggregate_mismatch':data['p_c651_mc'][0]=.99
    if change=='missing_model':data.pop('p_d4_seed0')
    if change=='extra_model':data['p_unregistered']=np.array([.1,.2])
    if change=='label_mismatch':data['y']=np.array([1,0],dtype=np.uint8)
    f.npz(path,data);record['sha256']=f.hash(path);f.dump(d/'cases'/(record['case_id']+'.json'),record);f.dump(d/'ASSESSMENT.json',a);f.seal()
    result=m.run_authorized(f.authorize())
    assert result['cohorts']['us2024']['status']=='UNAVAILABLE_ADMISSION_FAILURE'
    assert result['cohorts']['us2024']['metrics'] is None
    assert result['cohorts']['korea2025']['status']=='AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT'
    assert result['promotion_criteria_pass'] is False


def test_protected_input_bookend_refuses_changed_bytes(authority):
    f=authority;a=f.authorize();f.put(f.frozen_names[-1],b'changed after admission')
    with pytest.raises(f.m.AdmissionError):a.files.unchanged()


def test_nonzero_paired_ap_uses_same_literal_fire_draws():
    labels=[np.array([0.,1.]),np.array([1.,0.,1.]),np.array([0.,0.,1.,1.]),np.array([1.,0.])]
    good=[.1+.8*y for y in labels]; bad=[1-p for p in good]
    names=S.protocol()['model_order']
    predictions={n:(bad if n in S.REFERENCES else good) for n in names}
    canonical={n:points_for(labels,predictions[n]) for n in names}
    result,d=S.compute_cohort('korea2025',labels,predictions.__getitem__,canonical)
    literal=[]
    for m in d.vectors:
        y=np.concatenate([np.tile(a,n) for a,n in zip(labels,m)])
        pg=np.concatenate([np.tile(a,n) for a,n in zip(good,m)])
        pb=np.concatenate([np.tile(a,n) for a,n in zip(bad,m)])
        literal.append(average_precision_score(y,pg)-average_precision_score(y,pb))
    full=np.array(literal)[d.inverse]
    record=result['paired_ap']['base_seed0__vs__persistence']
    assert record['point']>0 and record['undefined_union_draws']==0
    np.testing.assert_allclose(record['percentile_95_interval'],np.quantile(full,[.025,.975],method='linear'),rtol=1e-12,atol=1e-14)
    assert result['paired_ap']['persistence__vs__dilation_best']['percentile_95_interval']==[0,0]


@pytest.mark.parametrize('change',['duplicate_case','wrong_event','extra_case','suppressed_reason','missing_point'])
def test_resigned_population_and_null_field_refusals(authority,change):
    f=authority;m=f.m;d=f.directory('us2024');a=f.load(d/'ASSESSMENT.json')
    if change=='duplicate_case':a['cases'][-1]=a['cases'][0]
    if change=='wrong_event':a['cases'][0]['case']['event']='INVENTED_UNDECLARED_FIRE'
    if change=='extra_case':a['cases'].append(copy.deepcopy(a['cases'][0]))
    if change=='suppressed_reason':
        a['cases'][0].update(status='UNAVAILABLE',reason='INVENTED unavailable')
        a.update(status='HOLD',failed_or_unavailable=[])
    if change=='missing_point':
        report=f.load(f.result_path);del report['heldout']['models']['c651_mc']['pooled']['roc_auc'];f.dump(f.result_path,report)
    f.dump(d/'ASSESSMENT.json',a);f.seal()
    if change=='missing_point':
        result=m.run_authorized(f.authorize())
        assert result['cohorts']['us2024']['status']=='UNAVAILABLE_ADMISSION_FAILURE'
        assert result['cohorts']['korea2025']['status']=='AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT'
    else:
        with pytest.raises(m.AdmissionError):m.run_authorized(f.authorize())


def test_exact_dependency_versions_and_source_bytes(authority,monkeypatch):
    f=authority;m=f.m
    monkeypatch.setattr(m.np,'__version__','1.26.5')
    with pytest.raises(m.AdmissionError):m.dependencies()
    monkeypatch.undo()
    source=f.bundle/'frozen_source'/m.BASELINES_SHA256/'baselines.py.gz'
    source.write_bytes(__import__('gzip').compress(b'changed frozen AST source',mtime=0))
    with pytest.raises(m.AdmissionError):m.frozen_point_engine()


def test_source_after_check_detects_mutation_even_with_cached_estimator(authority):
    f=authority;m=f.m;m.frozen_point_engine()
    p=f.bundle/'frozen_source'/m.BASELINES_SHA256/'baselines.py.gz'
    p.write_bytes(__import__('gzip').compress(b'changed after compile',mtime=0))
    with pytest.raises(m.AdmissionError):m.frozen_point_engine()


def test_cli_has_no_test_or_numerical_policy_override():
    import ast
    tree=ast.parse((HERE/'supplement.py').read_text())
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    args=[n.args[0].value for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
          and n.func.attr=='add_argument' and n.args and isinstance(n.args[0],ast.Constant)]
    assert args==['--protocol','--model-root','--run','--results','--authorization','--authorization-sha256','--out']
    assert 'git' not in ast.unparse(main)


def test_late_bookend_failure_has_no_completion(authority,monkeypatch):
    f=authority;a=f.authorize();original=a.files.unchanged;calls=0
    def late_change():
        nonlocal calls
        calls+=1
        if calls==2:f.put(f.frozen_names[-1],b'INVENTED late protected-input mutation')
        return original()
    monkeypatch.setattr(a.files,'unchanged',late_change)
    with pytest.raises(f.m.AdmissionError):f.m.run_authorized(a)
    assert not (f.out/'COMPLETION.json').exists()
    assert (f.out/'DESCRIPTIVE_INTERVALS.json').exists()  # Preserved partial, not success.
