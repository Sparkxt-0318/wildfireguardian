from pathlib import Path
import importlib.util,json,tempfile
import numpy as np,pandas as pd,pytest
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');ROOT=TASK/'work/audit-1b'
def mod(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
t=mod('ownersynthetic',ROOT/'forecast/tests/test_farsite_matched_subset.py');a=mod('audit',ROOT/'research/forecast-v2/scripts/audit_farsite.py')
with tempfile.TemporaryDirectory(prefix='farsite-independent-long-',dir=TASK/'work/farsite-subset-review-6ae52ab2') as td:
 m=t.fixture(a,Path(td));h=m.historical[0];start=pd.Timestamp('2024-01-01T00:00:00Z');end=start+pd.Timedelta(hours=49)
 p=h/'protocol.json';d=json.loads(p.read_text());d.update(endpoint=end.isoformat(),hours=49);t.write(p,d)
 p=h/'report.json';d=json.loads(p.read_text());d['native_clock_verification'].update(end_hhmm=100,duration_minutes=2940);d['farsite_execution'].update(elapsed_minutes=2940,native_clock_verification=d['native_clock_verification'],endpoint_selection='0 <= arrival <= 2940');t.write(p,d)
 p=h/'farsite_prediction.npz'
 with np.load(p) as z: arr={n:z[n].copy() for n in z.files}
 meta=json.loads(str(arr['metadata_json']));meta['exact_duration_minutes']=2940;arr['metadata_json']=np.array(json.dumps(meta));np.savez_compressed(p,**arr)
 p=m.data/'perimeters'/m.event/'states.npz'
 with np.load(p) as z: arr={n:z[n].copy() for n in z.files}
 arr['times']=np.array([start.isoformat(),end.isoformat()]);np.savez_compressed(p,**arr)
 p=m.assessment/(m.event+'.npz')
 with np.load(p) as z:arr={n:z[n].copy() for n in z.files}
 arr['hours']=np.array([49.]);np.savez_compressed(p,**arr)
 r=json.loads((m.assessment/'ASSESSMENT.json').read_text());r['cases'][0]['case'].update(endpoint=end.isoformat(),hours=49);r['per_fire_files'][p.name]=a.sha(p);t.write(m.assessment/'ASSESSMENT.json',r);t.write(m.assessment/'cases/synthetic_case_00.json',r['cases'][0]);t.resign_historical(a,h)
 with pytest.MonkeyPatch.context() as mp:res=t.run(a,m,mp)
 out=dict(interval_hours=49,accepted_status=res['status'],scores_available=res['scores_available'],row_status=res['cases'][0]['status'],native_horizon=res['cases'][0]['native_horizon'],superiority_criteria_pass=res['superiority_criteria_pass'])
 (TASK/'work/farsite-subset-review-6ae52ab2/long_interval_probe.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
