from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]
ORIGINAL=WS/'outputs/latest_forecast_routing_completion_20261015_v1/execution/run/WFG-latest-completion-kit-20261015-v3'
CAND=WS/'work/wfg-verified-routing-20261029/experimental/window-routing/stack'
QUEUE=ORIGINAL/'queues/LATEST_PRIMARY.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with p.open('x')as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
q=json.loads(QUEUE.read_text());jobs=[];pins={}
for index,old in enumerate(q['jobs'],1):
 j=dict(old);candidate=j['arm']=='RDA_CAND';stack=CAND if candidate else ORIGINAL
 j.update(root=str(ORIGINAL),source_root=str(stack/'routing_candidate'),decision_dir=str(stack/'decision'),execution_id=f'{index:02d}__'+old['label'],output_path=str(ROOT/'runs'/old['label']))
 for key in ('graph_path','hazard_path','request_path'):
  p=ORIGINAL/j[key];assert sha(p)==j['input_sha256'][key];pins[str(p)]=sha(p)
 for name,h in j['source_sha256'].items():
  p=ORIGINAL/j['source_directory']/name;assert sha(p)==h;pins[str(p)]=h
 if candidate:
  j['phaseB_sha256']={n:sha(stack/'phaseB'/n)for n in j['phaseB_sha256']}
  j['checker_sha256']={n:sha(stack/'routing_candidate/baseline'/n)for n in j['checker_sha256']}
  # Preparation admission changed only by the previously verified strict numerical input guard.
  sys.path.insert(0,str(stack/'routing_candidate/baseline/routing-package'))
  from routing import prepared_reuse
  j['preparation_source_sha256']=prepared_reuse.source_identity()
  j['preparation_mode_sha256']=sha(stack/'phaseB/preparation_mode.py')
 p=ROOT/'jobs'/(str(index).zfill(2)+'.json');save(p,j);pins[str(p)]=sha(p)
 jobs.append(dict(execution_id=j['execution_id'],case_id=j['case_id'],cohort=j['cohort'],rep=j['rep'],arm=j['arm'],variant='CANDIDATE'if candidate else'BASELINE',job_file=str(p),job_sha256=sha(p),output_path=j['output_path'],worker_path=str(stack/'phaseB'/old['worker'].split('/')[-1]),original_label=old['label']))
for root in (ORIGINAL,CAND):
 for group in ('routing_candidate','phaseB','decision'):
  for p in (root/group).rglob('*.py'):pins[str(p)]=sha(p)
for p in (ROOT/'runner/run_jobs.py',ROOT/'coordination/guarded_run.py',Path(__file__).resolve(),QUEUE):pins[str(p)]=sha(p)
manifest=dict(schema='wfg.new-fire.routing-run-manifest/1',python_executable=str(WS/'outputs/routing_native_confirmation_20261014_v1/WFG-integrated-preparation-candidate-20261014/env/bin/python'),original_queue_path=str(QUEUE),original_queue_sha256=sha(QUEUE),variants={k:dict(stack_root=str(v))for k,v in [('BASELINE',ORIGINAL),('CANDIDATE',CAND)]},cases=[dict(case_id=c,cohort=next(j['cohort']for j in jobs if j['case_id']==c))for c in dict.fromkeys(j['case_id']for j in jobs)],jobs=jobs,source_sha256=pins,scope='Original 20 missions and original ABBA 80-run order. Baseline unchanged; verified candidate repo sources. Cold preparation, full original policy, same 30s/3072MiB and label limits.')
save(ROOT/'MANIFEST.json',manifest);print('SEALED',len(jobs),'jobs',len(pins),'pins')
