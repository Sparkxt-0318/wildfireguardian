from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, os, platform, subprocess, sys, time
ROOT=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b')
DATA=ROOT.parent/'data/forecast-v2'
RUN=ROOT/'forecast/runs/20261030_perimeter_trained/execution_v3'
E=ROOT/'research/forecast-v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
parser=argparse.ArgumentParser()
parser.add_argument('--freeze-commit',required=True)
a=parser.parse_args()
freeze=subprocess.check_output(['git','rev-parse',a.freeze_commit],cwd=ROOT,text=True).strip()
authorization_path=ROOT.parent/'CURRENT_COHORT_AUTHORIZATION.json'
parent_verification_path=ROOT.parent/'FREEZE_PARENT_VERIFICATION.json'
assert sha(authorization_path)=='554e4fb0fefb2aae290143631f63d2f1b2a24b75cfe4dac250f89a54a31ed2ef'
assert sha(parent_verification_path)=='1e9def628deb2e7f1035aea691c39f8acf27f606bcdccffd0e6d3dff4f344db6'
authorization=json.loads(authorization_path.read_text())
assert authorization['freeze_commit']==freeze and authorization['authorization']=='EXECUTE_FROZEN_CURRENT_COHORT_ASSESSMENTS'
frozen_union=json.loads(parent_verification_path.read_text())['verified_file_sha256']
assert len(frozen_union)==223
assert all(sha(ROOT/name)==digest for name,digest in frozen_union.items()), 'The complete parent-verified frozen union changed before inference'
identities={}
for relative in ['research/forecast-v2/MODEL_SELECTION.json','research/forecast-v2/BLIND_REGISTRY.json','research/forecast-v2/FIT_COVERAGE.json','forecast/documents/preregistration_blind_test.md']:
 original=subprocess.check_output(['git','show',freeze+':'+relative],cwd=ROOT)
 assert hashlib.sha256(original).hexdigest()==sha(ROOT/relative), 'Committed freeze differs from consumed file: '+relative
 identities[relative]=sha(ROOT/relative)
registry=json.loads((E/'BLIND_REGISTRY.json').read_text())
assert registry['protocol_status']=='READY_FOR_OWNER_REGISTRATION'
assert registry['execution_status']=='NOT_READY_FOR_2026_EXECUTION'
assert registry['producer_source_sha256']
for relative,digest in registry['producer_source_sha256'].items():
 assert sha(ROOT/relative)==digest, 'Frozen source changed: '+relative
commands=[]
for cohort in ['us2024','korea2025']:
 receipt=E/'executions'/('current_assessment_'+cohort+'.json')
 log=receipt.with_suffix('.log')
 assert not receipt.exists() and not log.exists(), 'Preserve an existing cohort execution receipt/log'
 command=[sys.executable,str(E/'scripts/score_cohorts.py'),'--cohort',cohort,'--data',str(DATA),'--work',str(DATA/'campaign-work'),'--run',str(RUN),'--registry',str(E/'BLIND_REGISTRY.json')]
 assert all(sha(ROOT/name)==digest for name,digest in frozen_union.items()), 'Frozen union changed before next cohort'
 record=dict(schema='wfg.current-frozen-cohort-execution/2',cohort=cohort,command=command,pid=os.getpid(),started_utc=now(),freeze_commit=freeze,frozen_identities=identities,producer_source_sha256=registry['producer_source_sha256'],frozen_union_sha256=frozen_union,authorization_sha256=sha(authorization_path),parent_verification_sha256=sha(parent_verification_path),driver_sha256=sha(__file__),host=dict(platform=platform.platform(),python=platform.python_version(),interpreter=sys.executable,cpu_count=os.cpu_count()),lease_policy='Scorer acquires one HEAVY lease per case; no outer lease.')
 print(json.dumps(dict(cohort=cohort,status='STARTING',started_utc=record['started_utc'])),flush=True)
 begin=time.perf_counter()
 with log.open('x') as output:
  result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'forecast'),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',PYTHONUNBUFFERED='1'),stdout=output,stderr=subprocess.STDOUT)
 source_changes=[relative for relative,digest in registry['producer_source_sha256'].items() if sha(ROOT/relative)!=digest]
 freeze_changes=[relative for relative,digest in identities.items() if sha(ROOT/relative)!=digest]
 union_changes=[relative for relative,digest in frozen_union.items() if sha(ROOT/relative)!=digest]
 out=RUN/('heldout' if cohort=='us2024' else 'korean2025')/'ASSESSMENT.json'
 record.update(finished_utc=now(),elapsed_seconds=time.perf_counter()-begin,exit_code=result.returncode,changed_sources=source_changes,changed_frozen_identities=freeze_changes,changed_frozen_union=union_changes,log=str(log.relative_to(ROOT)),log_sha256=sha(log),assessment=str(out.relative_to(ROOT)) if out.exists() else None,assessment_sha256=sha(out) if out.exists() else None,status='COMPLETED_COMMAND' if not source_changes and not freeze_changes and not union_changes else 'SOURCE_CUSTODY_FAILURE')
 receipt.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
 print(json.dumps(dict(cohort=cohort,exit_code=result.returncode,receipt_sha256=sha(receipt),status=record['status'])),flush=True)
 commands.append(record)
 if source_changes or freeze_changes or union_changes:
  raise RuntimeError('Stop on changed numerical/frozen source, retaining outputs')
print(json.dumps(dict(status='BOTH_CURRENT_COHORT_COMMANDS_EXECUTED',exit_codes={c['cohort']:c['exit_code'] for c in commands})),flush=True)
# HOLD exits are retained independently, not converted into scientific success.
raise SystemExit(0 if all(c['exit_code']==0 for c in commands) else 1)
