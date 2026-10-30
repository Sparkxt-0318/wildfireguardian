from pathlib import Path
import importlib.util,json,tempfile,sys
import numpy as np
import pytest
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');ROOT=TASK/'work/audit-1b'
spec=importlib.util.spec_from_file_location('ownersynthetic',ROOT/'forecast/tests/test_farsite_matched_subset.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
spec=importlib.util.spec_from_file_location('audit',ROOT/'research/forecast-v2/scripts/audit_farsite.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
with tempfile.TemporaryDirectory(prefix='farsite-independent-',dir=TASK/'work/farsite-subset-review-6ae52ab2') as td:
 made=t.fixture(a,Path(td)); missing='p_d4_seed0'
 for path in [made.assessment/'cases/synthetic_case_00.npz',made.assessment/(made.event+'.npz')]:
  with np.load(path) as z: arrays={n:z[n].copy() for n in z.files if n!=missing}
  np.savez_compressed(path,**arrays)
 receipt=json.loads((made.assessment/'ASSESSMENT.json').read_text());receipt['cases'][0]['sha256']=a.sha(made.assessment/'cases/synthetic_case_00.npz');receipt['per_fire_files'][made.event+'.npz']=a.sha(made.assessment/(made.event+'.npz'))
 t.write(made.assessment/'cases/synthetic_case_00.json',receipt['cases'][0]);t.write(made.assessment/'ASSESSMENT.json',receipt)
 with pytest.MonkeyPatch.context() as mp:r=t.run(a,made,mp)
 result=dict(removed=missing,accepted=r['status'],scores_available=r['scores_available'],model_names=list(r['scores']['models']),missing_model_silently_omitted='d4_seed0' not in r['scores']['models'],superiority_criteria_pass=r['superiority_criteria_pass'])
 (TASK/'work/farsite-subset-review-6ae52ab2/missing_model_probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
