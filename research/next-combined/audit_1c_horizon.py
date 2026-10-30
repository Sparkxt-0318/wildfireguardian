"""Pure finite-run horizon boundary probe, not Wapiti or a native execution."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

p=argparse.ArgumentParser();p.add_argument('--track-c',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
root=a.track_c.resolve();sys.path.insert(0,str(root/'experimental/synthetic-truth/src'))
import numpy as np
from wfg_synthetic_truth.adapters import external_simulator
with tempfile.TemporaryDirectory(prefix='bounded-arrival-audit-') as d:
    d=Path(d); affine=np.array([10.,0.,0.,0.,-10.,20.])
    np.savez(d/'ref.npz',burned_area=np.zeros((1,1,2,2)),affine_transform=affine,epsg=np.array(5070),time_utc=np.array([100]))
    meta=dict(model_family='FARSITE',method='farsite_deterministic',arrival_units='minutes',grid_alignment='caller_verified_no_resampling_in_importer',arrival_origin_time_utc=100,no_burn_value=-9999.,exact_duration_minutes=1470)
    np.savez(d/'out.npz',arrival_minutes=np.array([[0.,60.],[1470.,-9999.]]),valid=np.ones((2,2),bool),metadata_json=np.array(json.dumps(meta)),affine_transform=affine,epsg=np.array(5070))
    t=external_simulator(d/'out.npz',reference_path=d/'ref.npz',cutoff_utc=100,source_id='synthetic')
    cases=[]
    for horizon,expected in [(None,'UNSCORABLE'),(3600,'MODEL_RELATIVE_BOUNDED_ARRIVAL_ONLY'),(88200,'MODEL_RELATIVE_BOUNDED_ARRIVAL_ONLY'),(88201,'UNSCORABLE')]:
        q=t.exact_ignition(horizon_s=horizon)
        cases.append(dict(horizon_s=horizon,status=q['status'],expected=expected,pass_check=q['status']==expected,arrival_if_supported=None if q['ignition_time_s'] is None else [['inf' if np.isposinf(x) else float(x) for x in row] for row in q['ignition_time_s']]))
    result=dict(scope='synthetic 1470-minute finite-run boundary only, no actual Wapiti file read',track_head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),host=platform.platform(),python=sys.version,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),adapter_sha256=hashlib.sha256((root/'experimental/synthetic-truth/src/wfg_synthetic_truth/adapters.py').read_bytes()).hexdigest(),cases=cases,global_never_cells=int(t.never.sum()),right_censored_cells=int(t.censored.sum()),valid_until_s=t.valid_until_s)
    result['pass_check']=all(c['pass_check'] for c in cases) and result['global_never_cells']==0 and result['right_censored_cells']==1
    a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(pass_check=result['pass_check'],cases=len(cases))));sys.exit(0 if result['pass_check'] else 1)
