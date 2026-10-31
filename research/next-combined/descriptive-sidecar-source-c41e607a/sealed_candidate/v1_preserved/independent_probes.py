"""Bounded independent invented-fixture probes. No actual study access."""
from pathlib import Path
import importlib.util
import json
import math
import subprocess
import sys
import numpy as np
import pytest

BASE = Path(__file__).resolve().parent
COPY = BASE/'sealed_candidate'
spec = importlib.util.spec_from_file_location('independent_owner_fixture',COPY/'test_supplement.py')
T = importlib.util.module_from_spec(spec);sys.modules[spec.name]=T;spec.loader.exec_module(T)


def test_expected_help_and_cli_rejection():
    result=subprocess.run([sys.executable,str(COPY/'supplement.py'),'--help'],capture_output=True,text=True)
    assert result.returncode==0 and '--authorization-sha256' in result.stdout
    result=subprocess.run([sys.executable,str(COPY/'supplement.py'),'--unknown-option'],capture_output=True,text=True)
    assert result.returncode==2


@pytest.mark.parametrize('text',['1e999','-1e999','{"unused":{"nested":[1e999]}}'])
def test_nonfinite_exponent_is_rejected(text):
    with pytest.raises(T.S.AdmissionError):
        T.S.strict_json(text)


def test_nonfinite_exponent_cannot_enter_completed_full_chain(tmp_path,monkeypatch):
    f=T.InventedAuthority(tmp_path,monkeypatch)
    # Re-sign all invented outer custody as owner negative controls do. The parser
    # still has an explicit nonfinite-JSON obligation, even in unused metadata.
    original=f.result_path.read_text()
    f.result_path.write_text(original.rstrip()[:-1]+',"invented_unused_nonfinite":1e999}\n')
    f.seal()
    assert math.isinf(json.loads(f.result_path.read_text())['invented_unused_nonfinite'])
    with pytest.raises(f.m.AdmissionError):
        f.m.run_authorized(f.authorize())
    assert not (f.out/'COMPLETION.json').exists()


def test_us_complete_korea26_scored7_unavailable_no_korea_array_decode(tmp_path,monkeypatch):
    f=T.InventedAuthority(tmp_path,monkeypatch);d=f.directory('korea2025')
    a=f.load(d/'ASSESSMENT.json');unavailable=[]
    for record in a['cases'][:7]:
        (d/'cases'/(record['case_id']+'.npz')).unlink()
        record.update(status='UNAVAILABLE',reason='INVENTED no common supported cells',scored_cells=0,
                      scored_mask_sha256=f.m.array_sha(np.zeros(record['rectangle'],bool)))
        record.pop('sha256');record.pop('positives')
        f.dump(d/'cases'/(record['case_id']+'.json'),record)
        unavailable.append(record)
    # Keep an honestly concatenated partial per-fire file; all case time metadata
    # remain represented. This is only an invented fixture, never real admission.
    event=a['cases'][0]['case']['event'];path=d/(event+'.npz')
    with np.load(path,allow_pickle=False) as z: parts={k:z[k] for k in z.files}
    for key in ('row','col','y','interval',*('p_'+n for n in f.m.protocol()['model_order'])):
        parts[key]=parts[key][14:]
    f.npz(path,parts);a['per_fire_files'][path.name]=f.hash(path)
    a.update(status='HOLD',failed_or_unavailable=unavailable);f.dump(d/'ASSESSMENT.json',a)
    report=f.load(f.result_path);report['korean2025_secondary_reconstruction']['assessment_status']='HOLD'
    f.dump(f.result_path,report);f.seal()
    real_npz=f.m.Files.npz
    def reject_korea(self,pin):
        assert not pin.path.is_relative_to(d),'Korean incomplete cohort array decoded'
        return real_npz(self,pin)
    monkeypatch.setattr(f.m.Files,'npz',reject_korea)
    r=f.m.run_authorized(f.authorize())
    assert r['cohorts']['us2024']['status']=='AVAILABLE_DESCRIPTIVE_COMPLETE_COHORT'
    kr=r['cohorts']['korea2025'];assert kr['metrics'] is None
    assert kr['canonical_summary']['statuses']=={'SCORED':26,'UNAVAILABLE':7}
    assert kr['original_outcomes']==unavailable
    assert not (f.out/'korea2025_draws.npy').exists()
    assert (f.out/'COMPLETION.json').exists()


def test_raw_brier_does_not_use_corrected_diagnostic(tmp_path,monkeypatch):
    f=T.InventedAuthority(tmp_path,monkeypatch)
    r=f.load(f.result_path)
    for cohort in ('heldout','korean2025_secondary_reconstruction'):
        for row in r[cohort]['models'].values():row['pooled']['brier_mc_variance_corrected']=123456.
    f.dump(f.result_path,r);f.seal()
    result=f.m.run_authorized(f.authorize())
    point=result['cohorts']['us2024']['models']['c651_mc']['pooled_raw_brier']['point']
    assert point==r['heldout']['models']['c651_mc']['pooled']['brier'] and point!=123456.


def test_single_class_auc_keeps_union_not_double_counted():
    ys=[np.array([1.])]*4;ps=[np.array([.5])]*4
    point,values,pos,neg=T.S.model_draw_values(ys,ps,T.S.draw_plan(['a','b','c','d']))
    out=T.S.interval(values['pooled_roc_auc'],point['pooled_roc_auc'],pos,neg,kind='auc')
    assert out['point'] is None and out['percentile_95_interval'] is None
    assert out['undefined_no_positive_draws']==0 and out['undefined_no_negative_draws']==10000
    assert out['undefined_union_draws']==10000 and out['defined_draws']==0
