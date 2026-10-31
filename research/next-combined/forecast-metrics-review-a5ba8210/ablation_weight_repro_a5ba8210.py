"""Synthetic reporting-only arithmetic repro; no study/model/prediction access."""
import hashlib,importlib.util,json,sys,tempfile
from pathlib import Path
import pytest
repo=Path(__file__).resolve().parents[1]/'audit-1b'
sys.dont_write_bytecode=True
sys.path.insert(0,str(repo/'forecast'));sys.path.insert(0,str(repo/'research/forecast-v2/scripts'))
spec=importlib.util.spec_from_file_location('independent_metric_report',repo/'research/forecast-v2/scripts/report.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
with tempfile.TemporaryDirectory(prefix='wfg-report-arithmetic-') as temp,pytest.MonkeyPatch.context() as mp:
 run=Path(temp); phases=[p for p in r.F.current_phase_identity()['phases'] if p['stage']=='fold' and p['fold']=='2020' and p['variant'] in ('base','burnout')]
 fixtures={}
 for phase in phases:
  path=run/phase['result'];path.parent.mkdir(parents=True);path.write_text('{}')
  fixtures[phase['variant']]=dict(variant=phase['variant'],fold='2020',seed=0,validation_per_fire={'SYNTHETIC_FIRE':dict(brier=.1,weight=100 if phase['variant']=='base' else 50,clipped_nll=.2)},fit_seconds=1,parameters=1)
 mp.setattr(r.F,'phase_result',lambda root,run,variant,stage,fold:(None,fixtures[variant],None,None,None))
 result=r.ablation(run,draws=16,seed=20261030)
 output=dict(source_head='a5ba82108c44956c01071d8450751b5d2defa387',report_source_sha256=hashlib.sha256((repo/'research/forecast-v2/scripts/report.py').read_bytes()).hexdigest(),expected_difference_of_identical_brier=0.,observed=result['burnout']['difference_vs_base'],observed_interval=result['burnout']['interval_95'],ablation=result,actual_study_inputs_or_models_accessed=False)
 Path(__file__).with_suffix('.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))
