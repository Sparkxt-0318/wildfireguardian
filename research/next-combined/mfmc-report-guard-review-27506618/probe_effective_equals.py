from pathlib import Path
import importlib.util,json,tempfile,sys
import pytest
TASK=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on');ROOT=TASK/'work/audit-1b';OUT=TASK/'work/mfmc-report-guard-independent-review'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'forecast'))
from forecast.tests import test_report_comparison as T
s=importlib.util.spec_from_file_location('review_report',ROOT/'research/forecast-v2/scripts/report.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
with tempfile.TemporaryDirectory(prefix='synthetic-equals-',dir=OUT) as d,pytest.MonkeyPatch.context() as mp:
 f=T.fixture_comparison(R,Path(d),mp)
 receipt=json.loads(f.receipts[0].read_text());receipt['command'].append('--seed=7');T.write(f.receipts[0],receipt);T.resign(R,f)
 _,result=R.load_comparison(f.run)
 out=dict(appended_command_override='--seed=7',recorded_row_seed=result['rows'][0]['seed'],accepted_execution_complete=result['execution_complete'],source='Tiny synthetic fixture only; no actual comparison or model accessed.')
 (OUT/'probe_effective_equals.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
