"""Once-only native ablation launcher. Proven final-v3 process controller; no schedules."""
import pathlib,sys,json,hashlib,argparse,os,time,datetime,fcntl,subprocess
R=pathlib.Path(__file__).resolve().parents[1]; S=R.parent; W=S.parents[1]
sys.path.insert(0,str(R/'runner'));import wfg_native as N;import wfg_controller as C
N.RUN=R;N.LOGS=R/'logs';N.LOGS.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def save(p,o):N.write_new(p,o)
def controls(py,lease):
 out=C.run_queue(R,R/'queues/ABLATION_CONTROLS.json',py,lease.check,log=N.LOGS/'controls.jsonl');assert not out['stopped'],out
 records={}
 for j in json.loads((R/'queues/ABLATION_CONTROLS.json').read_text())['jobs']:
  records[j['control']]=json.loads((R/j['output_path']/'COMPLETE_PROCESS_RECEIPT.json').read_text())
 d=records;checks=dict(normal=d['normal']['on_time_complete_publication'] and d['normal']['exit_code']==0,fail=d['fail']['exit_code']==3,deadline=d['deadline']['deadline_termination_requested'] and not d['deadline']['forced_kill'],stubborn=d['stubborn']['forced_kill'],memory=d['memory']['memory_guard_triggered'],desc=len(d['desc']['descendants_after_exit'])>=2 and not d['desc']['descendants_remaining_after_cleanup'],cleanup=all(v['cleanup_state']=='CLEAN' and v['cleanup_ok'] for v in d.values()))
 save(S/'LIFECYCLE_GATE.json',dict(PASS=all(checks.values()),checks=checks));assert all(checks.values()),checks
 out=C.run_queue(R,R/'queues/ABLATION_PREFLIGHT.json',py,lease.check,log=N.LOGS/'preflight.jsonl');assert not out['stopped'],out
 gate=[]
 for j in json.loads((R/'queues/ABLATION_PREFLIGHT.json').read_text())['jobs']:
  p=R/j['output_path'];rec=json.loads((p/'COMPLETE_PROCESS_RECEIPT.json').read_text());r=json.loads((p/'RESULT.json').read_text())
  gate.append(dict(policy=j['policy'],on_time=rec['on_time_complete_publication'],cleanup=rec['cleanup_state'],exit_code=rec['exit_code'],result=r['primary_status'],route=(r['result'] or {}).get('destination'),own_check=r['whole_road_check']['status'],decision=r.get('decision')))
 ok=all(v['on_time'] and v['cleanup']=='CLEAN' and v['exit_code']==0 and v['route'] is not None and v['own_check']=='CERTIFIED_ADMISSIBLE' for v in gate)
 save(S/'REAL_PREFLIGHT_GATE.json',dict(PASS=ok,records=gate,scope='unscored; first mission repeated acrosspolicies; nativeprimarycounts exclude'))
 assert ok,gate

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--python',required=True);ap.add_argument('--stage',choices=['preflight','primary'],required=True);a=ap.parse_args()
 assert sys.platform=='darwin','nativeMac required'
 freeze=json.loads((S/'FREEZE.json').read_text());bad=[p for p,h in freeze['files'].items() if sha(S/p)!=h];assert not bad,bad
 if a.stage=='primary':
  review=json.loads((S/'review/PRE_RUN_REVIEW.json').read_text());assert review['PASS'];assert review['freeze_sha256']==sha(S/'FREEZE.json')
  assert json.loads((S/'REAL_PREFLIGHT_GATE.json').read_text())['PASS'];assert json.loads((S/'LIFECYCLE_GATE.json').read_text())['PASS']
 lock=N.LocalLock();lease=N.Lease(W,'Codex-final-input-routing-ablation-20261016','200attempt5policyfinalinputroutingablation');lock.acquire();clean=True
 try:
  lease.acquire();save(S/'ENVIRONMENT.json',dict(utc=N.utc().isoformat(),python=N.probe(a.python),host=N.host_identity(),stage=a.stage,freeze_sha256=sha(S/'FREEZE.json')))
  if a.stage=='preflight':controls(pathlib.Path(a.python),lease)
  else:
   out=C.run_queue(R,R/'queues/ABLATION.json',pathlib.Path(a.python),lease.check,log=N.LOGS/'primary.jsonl');save(S/'EXECUTION_STATUS.json',out);assert not out['stopped'],out
 except BaseException as exc:
  clean=getattr(C,'CURRENT',None) is None
  save(S/'LAUNCH_FAILURE.json',dict(stage=a.stage,error=repr(exc),CURRENT=str(getattr(C,'CURRENT',None)),utc=N.utc().isoformat()));raise
 finally:
  save(S/'POWER_END.json',dict(stage=a.stage,host=N.host_identity(),utc=N.utc().isoformat()))
  if clean and getattr(C,'CURRENT',None) is None:lease.release()
  else:save(S/'LEASE_WITHHELD.json',dict(reason='controller not proven clean',CURRENT=str(getattr(C,'CURRENT',None))))
  lock.release()
if __name__=='__main__':main()
