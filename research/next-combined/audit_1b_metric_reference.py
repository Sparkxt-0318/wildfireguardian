"""Synthetic unequal-fire metric reference; no study data read."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--track-b',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
root=a.track_b.resolve();source=root/'forecast/wildfire/baselines.py'
s=importlib.util.spec_from_file_location('metric_reference_audit',source);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
f=np.array(['a']+['b']*9);y=np.ones(10);c=np.array([0]+[1]*9);r=1-c
x=m.paired_fire_bootstrap(f,y,c,r,draws=10000,seed=20261030)
z=m.calibration_table(np.array([0,1,1,0]),np.array([0.,.05,.1,.999]))
passed=bool(np.isclose(x['point_difference'],-.8) and x['percentile_95_interval']==[-1.,1.] and z[0]['count']==2 and z[1]['count']==1 and z[9]['count']==1)
out=dict(scope=__doc__,head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),pooled_point_expected=-.8,equal_fire_point_would_be=0.,observed=x,fixed_bin_boundary_counts=[row['count'] for row in z],pass_check=passed)
a.out.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(pass_check=passed)));raise SystemExit(0 if passed else 1)
