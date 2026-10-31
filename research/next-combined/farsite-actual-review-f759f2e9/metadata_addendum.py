"""Metadata-only unavailable/null and current admission completeness checks."""
from pathlib import Path
import hashlib,json
import pandas as pd
OWN=Path(__file__).resolve().parent;ROOT=OWN.parent/'track-1b';E=ROOT/'research/forecast-v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def need(value,name):
 checks.append(dict(check=name,passed=bool(value)))
 if not value:raise ValueError(name)
p=E/'FARSITE_SCORES.json';need(sha(p)=='f0aa554c2312f3e177eb5d2a165e4aa50a986c3e883beda56510b201bcb3f6e2','exact scored supplement pin')
o=json.loads(p.read_text());u=[r for r in o['cases'] if r['status']!='SCORED_COMMON_SUBSET'];need(len(u)==1,'exact one unavailable row')
for name in ['brier','average_precision','roc_auc','clipped_nll','ece_10_bins','exact_nll','current_prediction_sha256','exact_row_col_sha256','current_case']:
 need(u[0].get(name) is None,'unavailable has no fabricated '+name)
need(u[0]['cells']==0 and u[0]['reason']=='HISTORICAL_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY','unavailable reason and zero population')
run=ROOT/'forecast/runs/20261030_perimeter_trained/execution_v3/heldout';a=json.loads((run/'ASSESSMENT.json').read_text());events=json.loads((E/'SPLIT.json').read_text())['held_out']['us_2024']
for r in a['cases']:
 c=r['case'];start,end=pd.Timestamp(c['cutoff']),pd.Timestamp(c['endpoint']);need(c['event'] in events and 0<end.value-start.value<=48*3600*10**9 and c['hours']==(end-start).total_seconds()/3600,'complete current metadata duration/event admission '+r['case_id'])
 need(r['case_id']==hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:24],'complete current metadata case descriptor ID '+r['case_id'])
need(o['rejected_current_cases']==[] and o['current_case_admission_pass'] is True,'current source admission flags unchanged')
selection=json.loads((E/'MODEL_SELECTION.json').read_text());registry=json.loads((E/'BLIND_REGISTRY.json').read_text());receipt=json.loads((E/'executions/final_farsite_saved_scenarios.json').read_text());protected=receipt['frozen_files_sha256']
for variant,identity in selection['checkpoints'].items():
 need(registry['models'][variant+'_seed0']==identity and protected[identity['path']]==identity['sha256'],'unopened checkpoint pointer chain '+variant)
for name,identity in [('c651',registry['models']['c651_mc']),('logistic',selection['baselines']['logistic'])]:
 need(protected[identity['path']]==identity['sha256'],'unopened comparator/baseline pointer chain '+name)
result=dict(status='PASS_METADATA_COMPLETENESS_ADDENDUM',checks=len(checks),passed=sum(x['passed'] for x in checks),current_us_cases=len(a['cases']),observations=checks,arrays_read=False,artifact_sha256=sha(p),script_sha256=sha(Path(__file__)))
(OWN/'METADATA_ADDENDUM.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed','current_us_cases']}))
