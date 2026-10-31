"""Independent V2 lineage and JSON controls, invented data only."""
from pathlib import Path
import importlib.util
import json
import math
import sys
import pytest

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_v2_fixture',BASE/'sealed_candidate/test_supplement.py')
T=importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)


@pytest.mark.parametrize('token',[
    'NaN','Infinity','-Infinity','1e999','-1E9999','[1e309]',
    '{"a":[0,{"b":-1.8e308}]}','1.7976931348623159e308',
])
def test_full_nonfinite_rejection(token):
    with pytest.raises(T.S.AdmissionError):T.S.strict_json(token)


@pytest.mark.parametrize('text',[
    '1.7976931348623157e308','-1e308','5e-324','-1e-999',
    '"1e999"','{"diagnostic":"Infinity","text":"NaN"}','[null,true,false,0.0]',
])
def test_valid_values_keep_native_semantics(text):
    expected=json.loads(text);actual=T.S.strict_json(text)
    assert actual==expected and type(actual) is type(expected)
    if isinstance(expected,float) and expected==0:
        assert math.copysign(1,actual)==math.copysign(1,expected)


def test_positive_lineage_roles_literal(tmp_path,monkeypatch):
    f=T.InventedAuthority(tmp_path,monkeypatch);a=f.authorize();m=f.m
    assert a.review['checker_sha256']=='87eb9a2467f4e8011e960273ca77a6878a7807173f5869041905363214a297aa'
    assert a.census['companion_metric_checker_sha256']=='b3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8'
    assert a.authorization['checker_sources']['original_canonical_result']['sha256']==a.census['companion_metric_checker_sha256']
    hold=f.load(f.original_hold)
    assert hold['status']=='HOLD_INDEPENDENT_RESULT_AUDIT' and hold['checker_sha256']==m.ORIGINAL_RESULT_CHECKER_SHA256
    assert hold['reason']==m.ORIGINAL_METRIC_HOLD_REASON
    assert a.authorization['precision_repair_review']['sha256']=='f4ecf98761130e5162c615870768446212b732d46db2b4e54e801789c348f0f4'


@pytest.mark.parametrize('change',[
    'forged_original_pass','wrong_original_checker','missing_original_hold','missing_original_source',
    'forged_current_b3_pass','current_hold','wrong_current_source','missing_precision_review',
    'changed_precision_bytes','changed_legacy_census_role','wrong_census_source',
])
def test_resigned_lineage_refuses_before_arrays(tmp_path,monkeypatch,change):
    f=T.InventedAuthority(tmp_path,monkeypatch);m=f.m;auth=f.load(f.auth_path)
    if change in ('forged_original_pass','wrong_original_checker'):
        value=f.load(f.original_hold)
        if change=='forged_original_pass':value['status']='PASS_INDEPENDENT_SAVED_RESULT_AUDIT'
        else:value['checker_sha256']=m.RESULT_CHECKER_SHA256
        f.dump(f.original_hold,value)
        auth['original_metric_hold']=f.pin(f.original_hold)
        auth['input_artifacts_sha256'][f.rel(f.original_hold)]=f.hash(f.original_hold)
    elif change=='missing_original_hold':del auth['original_metric_hold']
    elif change=='missing_original_source':del auth['checker_sources']['original_canonical_result']
    elif change in ('forged_current_b3_pass','current_hold'):
        value=f.load(f.review_path)
        if change=='forged_current_b3_pass':value['checker_sha256']=m.ORIGINAL_RESULT_CHECKER_SHA256
        else:value['status']='HOLD_INDEPENDENT_RESULT_AUDIT'
        f.dump(f.review_path,value)
        auth['prerequisite_receipts']['canonical_result']=f.pin(f.review_path)
        auth['input_artifacts_sha256'][f.rel(f.review_path)]=f.hash(f.review_path)
    elif change=='wrong_current_source':
        auth['checker_sources']['canonical_result']=auth['checker_sources']['original_canonical_result']
    elif change=='missing_precision_review':del auth['precision_repair_review']
    elif change=='changed_precision_bytes':
        p=f.bundle/'method/PRECISION_REPAIR_REVIEW.md';f.put(p,p.read_bytes()+b'\nINVENTED corrupted lineage\n')
        auth['precision_repair_review']=f.pin(p);auth['input_artifacts_sha256'][f.rel(p)]=f.hash(p)
    elif change=='changed_legacy_census_role':
        value=f.load(f.census_path);value['companion_metric_checker_sha256']=m.RESULT_CHECKER_SHA256
        f.dump(f.census_path,value);auth['prerequisite_receipts']['census']=f.pin(f.census_path)
        auth['input_artifacts_sha256'][f.rel(f.census_path)]=f.hash(f.census_path)
    elif change=='wrong_census_source':
        auth['checker_sources']['census']=auth['checker_sources']['original_canonical_result']
    f.dump(f.auth_path,auth);f.auth_sha=f.hash(f.auth_path)
    monkeypatch.setattr(m.np,'load',lambda *args,**kwargs:pytest.fail('array decode before lineage admission'))
    with pytest.raises(m.AdmissionError):f.authorize()
    assert not f.out.exists()
