"""Serial offline verifier; routing batch must have ended and released its lease."""
from pathlib import Path
import hashlib,json,os,sys
import batch_util as B
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def prepare():
 m=read(ROOT/'MANIFEST.json');summary=read(ROOT/'CAMPAIGN_SUMMARY.json');guard=read(ROOT/'coordination/CAMPAIGN_RECEIPT.json')
 assert summary['status']=='COMPLETE_QUEUE' and len(summary['jobs'])==80 and not summary['not_run']
 assert guard['cleanup_verified']and guard['lease_release']=='RELEASED'and guard['returncode']==0
 pins=dict(m['source_sha256']);groups={};rows=[]
 for index,row in enumerate(m['jobs']):
  j=read(row['job_file']);p=Path(row['output_path']);raw=read(p/'RESULT.json');r=raw['result'];route=r if r.get('destination')is not None else r.get('checked_incumbent')
  witness=None if route is None else{k:route[k]for k in ('legs','arrival','destination','per_member')}
  key=hashlib.sha256(json.dumps(dict(inputs=j['input_sha256'],sources=j['source_sha256'],witness=witness),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
  groups.setdefault(key,dict(index=index,executions=[]))['executions'].append(index);rows.append(dict(index=index,context=key))
  for name in ('RESULT.json','PUBLICATION_BOUNDARY.json','COMPLETE_PROCESS_RECEIPT.json','JOB.json'):
   f=p/name
   if f.exists():pins[str(f)]=sha(f)
 for f in list((ROOT/'reference').glob('*.py'))+[ROOT/'PROTOCOL.md',ROOT/'CAMPAIGN_SUMMARY.json',ROOT/'coordination/CAMPAIGN_RECEIPT.json',ROOT/'MANIFEST.json']:pins[str(f)]=sha(f)
 save(ROOT/'reference/VERIFICATION_INPUTS.json',dict(groups=groups,rows=rows,source_sha256=pins))
 print('FROZEN',len(groups),'independent contexts for',len(rows),'executions')
def run():
 seal=read(ROOT/'reference/VERIFICATION_INPUTS.json');B.check(seal);expected='Codex-thermal-verification-20261028-reference-'+str(os.getppid());B.lease(expected)
 (ROOT/'reference/grades').mkdir();records=[]
 for key,g in seal['groups'].items():
  B.check(seal);index=g['index'];command=[sys.executable,'-B',str(ROOT/'reference/grade.py'),'--index',str(index)]
  record=B.leaf(command,ROOT/'reference/grades'/(str(index).zfill(2)+'.log'),300,expected)
  out=ROOT/'reference/grades'/(str(index).zfill(2)+'.json');record.update(context=key,index=index,grade_sha256=sha(out)if out.exists()else None)
  records.append(record)
  if record['returncode'] or record['hard_timeout']or record['memory_cap']or record['memory_sampling_error']:
   save(ROOT/'reference/VERIFICATION_BATCH.json',dict(status='STOPPED',records=records));raise RuntimeError('INDEPENDENT_LEAF_FAILED:'+str(index))
 B.check(seal);save(ROOT/'reference/VERIFICATION_BATCH.json',dict(status='COMPLETE',records=records))
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='run':run()
 else:raise ValueError('prepare or run')
