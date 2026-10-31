"""Bounded synthetic registry/wiring check; no real future or heldout inputs.

Uses the pinned owner's synthetic fixture constructors to create tiny SHP/TIF,
receipt and model-identity files. Assertions/mutations below are independent;
numerical producers are mocked and no shared heavy lease is acquired.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import pytest


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def run(repo):
 t=load('wiring_fixture_constructors',repo/'forecast/tests/test_blind_forecast_protocol.py')
 observations=[]
 def probe(name,fn,refuse=False,reason=None):
  try:
   result=fn();passed=not refuse and result is not False;observed=dict(state='RETURNED',value=result)
  except (ValueError,KeyError,TypeError,FileNotFoundError) as e:
   passed=refuse and (reason is None or reason in str(e));observed=dict(state='RAISED',type=type(e).__name__,reason=str(e))
  observations.append(dict(id=name,pass_check=bool(passed),observed=observed))
 with tempfile.TemporaryDirectory(prefix='wfg-wiring-review-') as temporary:
  root=Path(temporary).resolve()
  # Complete valid model freeze first. Synthetic bytes are never model-loaded.
  with pytest.MonkeyPatch.context() as mp:
   f=t.freezer.__wrapped__();folder=root/'freeze';folder.mkdir()
   fr=t.freeze_inputs.__wrapped__(f,folder,mp);modelroot,runroot,selection,comparator,sel=fr
   def build():return f.build_registry(modelroot,runroot,selection,comparator)
   good=build();probe('complete_registry_positive_control',lambda:good['protocol_status']=='READY_FOR_OWNER_REGISTRATION' and good['execution_status']=='NOT_READY_FOR_2026_EXECUTION' and not good['future_inputs_pinned'])
   saved=selection.read_bytes();bad=copy.deepcopy(sel);bad['selected_variant']='ellipse';frozen=dict(bad['development_brier']);bad['development_brier']=frozen;selection.write_text(json.dumps(bad));probe('registry_wrong_tie_selection',build,True,'Primary selection');selection.write_bytes(saved)
   receipt=modelroot/'research/forecast-v2/executions/a03_final_base.json';old=receipt.read_bytes();receipt.unlink();probe('registry_missing_full_fit_receipt',build,True,'Exactly one authenticated');receipt.write_bytes(old)
   baseline=runroot/'baselines/logistic.pkl';old=baseline.read_bytes();baseline.write_bytes(b'different execution baseline');probe('registry_changed_executed_baseline',build,True,'Frozen identity');baseline.write_bytes(old)
   split=modelroot/'research/forecast-v2/SPLIT.json';old=split.read_bytes();obj=json.loads(old);obj['fit']['us_perimeter_and_kriged'].append('second_declared_fit_fire');split.write_text(json.dumps(obj))
   try:
    partial=build();observed=dict(state='ADMITTED',declared_fit_events=obj['fit']['us_perimeter_and_kriged'],all_seven_recorded_train_events=['synthetic_fit'],protocol_status=partial['protocol_status']);passed=False
   except (ValueError,KeyError,TypeError) as e:observed=dict(state='RAISED',reason=str(e));passed=True
   observations.append(dict(id='registry_incomplete_declared_fit_event_set',pass_check=passed,observed=observed));split.write_bytes(old)

  # Actual unchanged inventory adapter and tiny valid baseline terrain.
  with pytest.MonkeyPatch.context() as mp:
   b=t.blind.__wrapped__();folder=root/'raw';folder.mkdir();registered=t.registered.__wrapped__(b,folder,mp)
   full=t.complete_inventory_fixture.__wrapped__(b,registered,mp,folder)
   modelroot,release,rp,cp,registry,cohort=full
   def validate():return b.validate(rp,cp,modelroot,release.root)
   good=validate();probe('actual_raw_inventory_positive_control',lambda:len(good[2])==2 and good[1]['_inventory_validation']['raw_inventory']['raw_record_count']==3)
   saved=cp.read_bytes();bad=copy.deepcopy(cohort);bad['inventory']['exclusions']=[{'event':'SYNTHETIC_A','reason':'caller omission'}];b.write(cp,bad);probe('invented_exclusion_refused',validate,True,'complete raw-derived exclusion');cp.write_bytes(saved)
   bad=copy.deepcopy(cohort);bad['input_sha256'].pop('publisher.zip');b.write(cp,bad);probe('raw_archive_pin_mandatory',validate,True,'every inventory');cp.write_bytes(saved)
   terrain=release.root/'baseline-terrain/SYNTHETIC_A/elevation_m_375m.tif'
   import numpy as np
   import rasterio
   with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=False):
    with rasterio.open(terrain,'r+') as r:r.write_mask(np.full((3,3),255,np.uint8))
   side=Path(str(terrain)+'.msk');assert side.is_file()
   for p in terrain.parent.rglob('*'):
    if p.is_file():cohort['input_sha256'][str(p.relative_to(release.root))]=b.sha(p)
   b.write(cp,cohort);good=validate();probe('pinned_baseline_mask_positive_control',lambda:len(good[2])==2)
   old=side.read_bytes();borrowed=release.root/'unregistered-mask.tif';borrowed.write_bytes(old)
   from rasterio.shutil import copy as raster_copy
   raster_copy(borrowed,side,driver='VRT');cohort['input_sha256'][str(side.relative_to(release.root))]=b.sha(side);b.write(cp,cohort)
   probe('baseline_mask_vrt_dependency_refused',validate,True,'must be GeoTIFF');side.write_bytes(old)

  # Human-review checks on a separate simple synthetic catalog, no external truth.
  with pytest.MonkeyPatch.context() as mp:
   b=t.blind.__wrapped__();folder=root/'documentary';folder.mkdir();registered=t.registered.__wrapped__(b,folder,mp)
   modelroot,inputs,rp,cp,registry,cohort=registered
   args=SimpleNamespace(registry=rp,cohort=cp,model_root=modelroot,input_root=inputs,out=folder/'never-produced')
   b.load_pipeline=lambda: (_ for _ in ()).throw(AssertionError('unapproved run reached model loading'))
   probe('missing_pre_run_clearance_blocks_loading',lambda:b.run(args),True,'NOT_READY_FOR_2026_EXECUTION')
   path,review=t.attach_documentary_fixture(b,registered)
   positive=b.validate(rp,cp,modelroot,inputs)[1]['_documentary_clearance'];probe('bound_human_receipt_positive_control',lambda:positive['state']=='HUMAN_ATTESTED_DOCUMENTARY_CLEARANCE' and positive['machine_authentication'] is False)
   saved=path.read_bytes();savedcp=cp.read_bytes()
   for name,value in [('caller_boolean',dict(approved=True)),('caller_url',dict(approved=True,url='https://osf.io/synthetic'))]:
    b.write(path,value);cohort['documentary_clearance']['sha256']=b.sha(path);b.write(cp,cohort);probe(name+'_refused',lambda:b.validate(rp,cp,modelroot,inputs),True,'scope-specific human');path.write_bytes(saved);cp.write_bytes(savedcp)
   cohort=json.loads(savedcp);registered=(modelroot,inputs,rp,cp,registry,cohort)
   for field in ['registry_sha256','source_closure_sha256','input_closure_sha256','case_membership_sha256']:
    bad=copy.deepcopy(review);bad['bindings'][field]='0'*64;b.write(path,bad);cohort['documentary_clearance']['sha256']=b.sha(path);b.write(cp,cohort);probe('clearance_'+field+'_refused',lambda:b.validate(rp,cp,modelroot,inputs),True,'scope-specific human');path.write_bytes(saved);cp.write_bytes(savedcp)
   cohort=json.loads(savedcp);registered=(modelroot,inputs,rp,cp,registry,cohort)
   calls=t.numerical_fixture.__wrapped__(b,registered,mp)
   final,approval,approvalpath=t.finalize_fixture.__wrapped__(b,registered,calls,folder)
   b.finalize(final);approved=json.loads(final.out.read_text());probe('separate_post_score_positive_control_no_claim',lambda:approved['status']=='COMPLETE_REVIEW_NO_SUPERIORITY_CLAIM' and not approved['superiority_claim_permitted'] and approved['machine_authentication'] is False)
   score=json.loads(final.scores.read_text());probe('score_remains_pending_independent_review',lambda:not score['superiority_claim_permitted'] and score['completion']=='SCORED_PENDING_INDEPENDENT_DOCUMENTARY_APPROVAL_AND_RELOCATED_REPLAY')
   original=approvalpath.read_bytes();original_sha=final.approval_sha256;original_replay=final.replay;final.out=folder/'negative-final.json'
   bad=copy.deepcopy(approval);bad['independent_replay']['source_root']=str(modelroot);b.write(approvalpath,bad);final.approval_sha256=b.sha(approvalpath);probe('same_source_root_not_relocated',lambda:b.finalize(final),True,'relocated tree');approvalpath.write_bytes(original);final.approval_sha256=original_sha
   final.replay=final.scores;probe('same_artifact_not_independent_replay',lambda:b.finalize(final),True,'distinct scored artifact');final.replay=original_replay
   bad=copy.deepcopy(approval);bad['scored_artifacts']['score_sha256']='0'*64;b.write(approvalpath,bad);final.approval_sha256=b.sha(approvalpath);probe('post_score_exact_artifact_binding',lambda:b.finalize(final),True,'both exact scores');approvalpath.write_bytes(original);final.approval_sha256=original_sha
   # Re-sign only tiny synthetic prediction bytes to reach the older deep guards.
   scoreargs=SimpleNamespace(registry=rp,cohort=cp,model_root=modelroot,input_root=inputs,entries=folder/'predictions',out=folder/'negative-scores.json')
   receiptpath=scoreargs.entries/'RECEIPT.json';original_receipt=receiptpath.read_bytes();receipt=json.loads(original_receipt)
   npz=scoreargs.entries/receipt['cases'][0]['file'];original_npz=npz.read_bytes()
   for name,change in [('old_ordered_integer_coordinates',lambda v:v.update(row=v['row'].astype(float)+.25)),('old_exact_endpoint_labels',lambda v:v.update(y=1-v['y']))]:
    with np.load(npz) as values:arrays={n:values[n].copy() for n in values.files}
    change(arrays);np.savez(npz,**arrays);receipt['cases'][0]['sha256']=b.sha(npz);b.write(receiptpath,receipt)
    probe(name,lambda:b.score(scoreargs),True)
    npz.write_bytes(original_npz);receiptpath.write_bytes(original_receipt);receipt=json.loads(original_receipt)
 source_paths=['research/forecast-v2/scripts/blind_test.py','research/forecast-v2/scripts/freeze_registry.py','research/forecast-v2/scripts/blind_inventory.py','forecast/tests/test_blind_forecast_protocol.py','forecast/tests/test_blind_inventory.py']
 return dict(source_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),scope=__doc__,host=platform.platform(),python=sys.version,script_sha256=sha(__file__),source_sha256={p:sha(repo/p) for p in source_paths},observations=observations,checks=len(observations),passed=sum(r['pass_check'] for r in observations))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--track-b',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=run(a.track_b.resolve());result['status']='PASS_SCOPED_WIRING_REVIEW' if result['checks']==result['passed'] else 'FAIL_SCOPED_WIRING_REVIEW';a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([r for r in result['observations'] if not r['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
