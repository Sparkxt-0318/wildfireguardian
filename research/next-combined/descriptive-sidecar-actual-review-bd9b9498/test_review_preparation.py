"""Invented arithmetic/corruption controls only, no actual sidecar or data reads."""
from pathlib import Path
import ast
import hashlib
import types
import numpy as np
import pytest
import review_math as M
import review_actual as R


def frozen_toy_engine():
    p=Path(__file__).resolve().parents[1]/'final-interval-field-review/source/forecast/wildfire/baselines.py'
    source=p.read_bytes();assert hashlib.sha256(source).hexdigest()=='325abbe79ba7c22ed3eb60391a68d2becdbfd0aa4c6659debb94db6a34afbb1f'
    tree=ast.parse(source);names={'score','_average_precision','_auc','calibration_table'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    nodes=[ast.parse('import numpy as np').body[0],ast.parse('LOG_FLOOR=1e-7\nBINS=np.linspace(0.,1.,11)').body[0],
           ast.parse('LOG_FLOOR=1e-7\nBINS=np.linspace(0.,1.,11)').body[1],*nodes]
    out=types.ModuleType('frozen_toy_points');exec(compile(ast.Module(body=nodes,type_ignores=[]),'frozen_toy','exec'),out.__dict__)
    return out


@pytest.mark.parametrize('f',[4,6])
def test_every_observed_vector_independent_vs_literal_sklearn(f):
    labels=[np.array([0.,1.,1.,0.,1.][:2+i%4]) for i in range(f)]
    labels[0]=np.array([0.,0.]);labels[1]=np.array([1.,1.,1.])
    values=[np.array([0.,.1,.5,.5,1.][:len(y)]) for y in labels]
    d=M.plan(f);point,boot,pos,neg=M.distributions(labels,values,d)
    raw=frozen_toy_engine().score(np.concatenate(labels),np.concatenate(values))
    for field,key in zip(M.FIELDS,M.RAW):assert point[field]==raw[key]
    for i,m in enumerate(d.vectors):
        expected=M.literal_reference(labels,values,m);first=np.flatnonzero(d.inverse==i)[0]
        for field in M.FIELDS:
            actual=None if not np.isfinite(boot[field][first]) else float(boot[field][first])
            R.compare_values(actual,expected[field],f'independent {field}')
    assert np.array_equal(d.matrix,np.random.default_rng(20261030).integers(0,f,size=(10000,f)))
    assert np.array_equal(d.vectors[d.inverse],d.multiplicities) and d.frequencies.sum()==10000
    assert len(set(d.frequencies))>1


def test_predetermined_actual_literal_vectors_are_in_fixed_matrix():
    d=M.plan(6)
    for m in R.LITERAL_VECTORS:assert np.any(np.all(d.vectors==m,axis=1))


@pytest.mark.parametrize('all_y',[0,1])
def test_class_absence_and_full_null(all_y):
    d=M.plan(4);ys=[np.array([all_y])]*4;ps=[np.array([.3])]*4
    point,values,pos,neg=M.distributions(ys,ps,d)
    ap=M.descriptor(values['pooled_average_precision'],point['pooled_average_precision'],pos,neg,'ap')
    auc=M.descriptor(values['pooled_roc_auc'],point['pooled_roc_auc'],pos,neg,'auc')
    assert auc['point'] is None and auc['percentile_95_interval'] is None and auc['undefined_union_draws']==10000
    assert (ap['point'],ap['percentile_95_interval'])==((1.,[1.,1.]) if all_y else (None,None))


@pytest.mark.parametrize('field',['point','percentile_95_interval','status','defined_draws','undefined_union_draws'])
def test_descriptor_corruption_refused(field):
    expected=M.descriptor(np.linspace(0.,1.,10000),.5,np.zeros(10000,bool),np.zeros(10000,bool),'finite')
    actual={**expected,'draws':10000,'seed':20261030,'quantile_method':'linear','interval_unit':'whole fire, pooled canonical cell-interval entries'}
    if field=='point':actual[field]=float(np.nextafter(.5,1))
    elif field=='percentile_95_interval':actual[field]=[0.,1.]
    elif field=='status':actual[field]='UNAVAILABLE'
    else:actual[field]+=1
    with pytest.raises(AssertionError):R.compare_descriptor(actual,expected,'corrupted')


@pytest.mark.parametrize('text',['NaN','Infinity','1e999','{"nested":[-1e999]}','{"a":1,"a":2}'])
def test_strict_input_refuses_nonfinite_duplicates(text):
    with pytest.raises((AssertionError,ValueError)):R.strict(text)


def test_raw_vs_corrected_point_is_not_substituted():
    p=M.exact_points(np.array([0.,1.]),np.array([.1,.7]))
    assert p['pooled_raw_brier']==np.mean((np.array([.1,.7])-np.array([0.,1.]))**2)
    with pytest.raises(AssertionError):R.compare_values(.1,p['pooled_raw_brier'],'corrected substitute',exact=True)


def test_manual_pooled_brier_and_all10000_draws():
    counts=np.array([1,3,2,4]);ys=[np.zeros(n) for n in counts]
    ps=[np.ones(1),np.zeros(3),np.zeros(2),np.zeros(4)]
    d=M.plan(4);point,values,pos,neg=M.distributions(ys,ps,d)
    assert point['pooled_raw_brier']==.1 and point['pooled_raw_brier']!=.25
    literal_numerator=(d.matrix==0).sum(axis=1)
    literal_denominator=counts[d.matrix].sum(axis=1)
    assert np.array_equal(values['pooled_raw_brier'],literal_numerator/literal_denominator)
    desc=M.descriptor(values['pooled_raw_brier'],.1,pos,neg,'finite')
    assert desc['percentile_95_interval']==np.quantile(literal_numerator/literal_denominator,[.025,.975],method='linear').tolist()
    assert len(values['pooled_raw_brier'])==10000


def test_partial_absence_requires_conditional_label_and_null_full_interval():
    ys=[np.array([0.,0.]),np.array([1.,1.]),np.array([0.,1.]),np.array([0.,1.])]
    ps=[np.array([.1,.5])]*4;d=M.plan(4)
    point,values,pos,neg=M.distributions(ys,ps,d)
    desc=M.descriptor(values['pooled_average_precision'],point['pooled_average_precision'],pos,neg,'ap')
    assert 0<desc['undefined_union_draws']<10000 and desc['percentile_95_interval'] is None
    assert desc['conditional_on_defined_draws_interval'] is not None
    assert desc['conditional_scope']=='conditional on a draw containing positive labels'


@pytest.mark.parametrize('count',[0,857,859])
def test_missing_or_wrong_canonical_population_map_refused(count):
    value={'files_sha256':{f'p{i}':'a'*64 for i in range(count)}}
    with pytest.raises(AssertionError):R.map858(value)


def test_canonical_map_ambiguity_refused():
    mapping={f'p{i}':'a'*64 for i in range(858)}
    with pytest.raises(AssertionError):R.map858({'first':mapping,'second':mapping})
