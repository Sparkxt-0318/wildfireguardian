"""Synthetic corruption controls for the independent reconciler, no study inputs."""
from pathlib import Path
import copy,csv,gzip,hashlib,importlib.util,json,tempfile
from datetime import datetime,timedelta,timezone
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('independent_reconcile',HERE/'reconcile.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
TEMPLATE=json.loads((HERE/'SOURCE_CONTRACT.json').read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def dumpcsv(p,rows):
 cols=list(dict.fromkeys(k for row in rows for k in row))
 with p.open('w',newline='') as f:w=csv.DictWriter(f,cols);w.writeheader();w.writerows(rows)
def make(base):
 repo=base/'repo';run=repo/'forecast/runs/SYNTHETIC';c=copy.deepcopy(TEMPLATE)
 for name in c['source_pins']:
  p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# synthetic custody placeholder: '+name+'\n');c['source_pins'][name]=R.sha(p)
  z=repo/'research/forecast-v2/source_snapshots'/c['source_pins'][name]/(p.name+'.gz');z.parent.mkdir(parents=True,exist_ok=True);z.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
 p=repo/'research/forecast-v2/SPLIT.json';write(p,dict(synthetic_only=True));c['split_sha256']=R.sha(p)
 host=dict(python='3.12.1',torch='2.5.1',numpy='1.26.4',platform='SYNTHETIC_PLATFORM',cpu_count=4,torch_threads=2,load_average_1_5_15=[1.,2.,3.])
 for i,case in enumerate(c['cases']):
  out=run/f'meanfield_vs_mc/case_{i:02d}_a06/meanfield_vs_mc.json';rows=[]
  hs=[('fixed',float(h)) for h in c['horizons_hours']]+([('survey',case['survey_hours'])] if case['country']=='US' else [])
  for kind,h in hs:
   r=dict(country=case['country'],event=case['event'],cutoff=case['cutoff'],horizon_kind=kind,hours=h,mc_seconds=1. if kind=='fixed' else .6,mf_seconds=.2 if kind=='fixed' else .1,n_samples=1024,seed=0,timing_scope='one joint 24h call, shared across five horizon rows' if kind=='fixed' else 'one fractional survey-endpoint call',status='COMPARABLE',cells=4,active_cells=4,rmse_all=.1,rmse_active=.1,mean_mc=.5,mean_mf=.5,expected_new_cells_mc=2.,expected_new_cells_mf=2.,max_abs_difference=.1)
   if case['country']=='KR' or kind=='survey':r.update(reference_status='SCORED',label_cells=4,positives=2,brier_mc=.1,brier_mf=.09,brier_persistence=.5,label_kind='kriged reconstruction (not observed)' if case['country']=='KR' else 'NIROPS mapped extent at the next survey')
   if i==0 and h==24:
    r.update(status='UNAVAILABLE_SHARED_SUPPORT',cells=0,active_cells=0,reference_status='UNAVAILABLE_REFERENCE_SUPPORT',label_cells=0,positives=None,brier_mc=None,brier_mf=None,brier_persistence=None)
    for k in ['rmse_all','rmse_active','mean_mc','mean_mf','expected_new_cells_mc','expected_new_cells_mf','max_abs_difference']:r[k]=None
   rows.append(r)
  write(out,dict(rows=rows,host=host,checkpoint_sha256=c['checkpoint_sha256']))
  name=f'a06_compare_case{i:02d}';receipt=repo/'research/forecast-v2/executions'/(name+'.json');log=receipt.with_suffix('.log');log.parent.mkdir(parents=True,exist_ok=True);log.write_text('Synthetic log, no numerical experiment.\n');start=datetime(2026,10,30,tzinfo=timezone.utc)+timedelta(seconds=i*4)
  cmd=['synthetic-python',str(repo/'research/forecast-v2/scripts/pipeline.py'),'compare','--compare-case-index',str(i),'--artifact-suffix','_a06','--n-samples','1024','--seed','0','--threads','2','--data-manifest-sha256',c['data_manifest_sha256'],'--run',str(run),'--data-root',str(base/'NO_DATA_READ'),'--perimeters',str(base/'NO_DATA_READ')]
  write(receipt,dict(job=name,command=cmd,exit_code=0,elapsed_seconds=2.,started_utc=start.isoformat(),finished_utc=(start+timedelta(seconds=2)).isoformat(),source_sha256=c['source_pins'],output=str(out),output_sha256=R.sha(out),log_sha256=R.sha(log),data_manifest_sha256=c['data_manifest_sha256'],host={k:host[k] for k in ['platform','python','cpu_count']}))
 resign(repo,run,c);return repo,run,c
def resign(repo,run,c):
 rows=[];refs=[];last=None
 for i in range(12):
  out=run/f'meanfield_vs_mc/case_{i:02d}_a06/meanfield_vs_mc.json';d=R.load(out);dumpcsv(out.with_suffix('.csv'),d['rows']);receipt=repo/f'research/forecast-v2/executions/a06_compare_case{i:02d}.json';r=R.load(receipt);r['output_sha256']=R.sha(out);write(receipt,r);refs.append(dict(path=str(receipt.relative_to(repo)),sha256=R.sha(receipt)));rows+=d['rows'];last=d
 aggregate=run/'meanfield_vs_mc/meanfield_vs_mc.json';write(aggregate,dict(rows=rows,checkpoint_sha256=c['checkpoint_sha256'],case_receipts=refs,host=last['host'],timing='Each fixed-horizon group shares one joint24h MC and MF call'));dumpcsv(aggregate.with_suffix('.csv'),rows);write(repo/'research/forecast-v2/executions/a06_compare.json',dict(job='a06_compare',exit_code=0,output=str(aggregate),output_sha256=R.sha(aggregate),case_receipts=refs,source_sha256=c['source_pins']))
def mutate_json(p,fn):d=R.load(p);fn(d);write(p,d)
results=[]
with tempfile.TemporaryDirectory(prefix='SYNTHETIC-',dir=HERE) as td:
 base=Path(td);repo,run,c=make(base/'positive');r=R.reconcile(repo,run,c);results.append(dict(name='positive_complete66_with_honest_unavailable',passed=r['row_count']==66 and r['row_status_counts']==dict(COMPARABLE=65,UNAVAILABLE_SHARED_SUPPORT=1) and r['KR_events']==3 and r['raw_field_replay'] is False))
 changes=['omitted_case_row','reordered_horizons','wrong_cutoff','wrong_N','wrong_seed','rmse_out_of_bounds','active_count_impossible','empty_support_zeroed_as_success','persistence_brier_wrong','fixed_runtime_varies','unique_cost_exceeds_elapsed','missing_reference_status','US_fixed_reference_leak','checkpoint_wrong','source_phase_mixed','command_N_wrong','CSV_value_changed','aggregate_value_changed','missing_case_receipt','missing_final_receipt','source_file_changed','source_snapshot_missing','nonfinite_metric']
 for name in changes:
  repo,run,c=make(base/name);out=run/'meanfield_vs_mc/case_00_a06/meanfield_vs_mc.json';rec=repo/'research/forecast-v2/executions/a06_compare_case00.json';last_resign=True
  if name=='omitted_case_row':mutate_json(out,lambda d:d['rows'].pop())
  if name=='reordered_horizons':mutate_json(out,lambda d:d['rows'].reverse())
  if name=='wrong_cutoff':mutate_json(out,lambda d:d['rows'][0].update(cutoff='2024-01-01T00:00:00+00:00'))
  if name=='wrong_N':mutate_json(out,lambda d:d['rows'][0].update(n_samples=1))
  if name=='wrong_seed':mutate_json(out,lambda d:d['rows'][0].update(seed=1))
  if name=='rmse_out_of_bounds':mutate_json(out,lambda d:d['rows'][0].update(rmse_all=1.1))
  if name=='active_count_impossible':mutate_json(out,lambda d:d['rows'][0].update(active_cells=5))
  if name=='empty_support_zeroed_as_success':mutate_json(out,lambda d:d['rows'][4].update(status='COMPARABLE',rmse_all=0,mean_mc=0,mean_mf=0,expected_new_cells_mc=0,expected_new_cells_mf=0,max_abs_difference=0))
  if name=='persistence_brier_wrong':mutate_json(out,lambda d:d['rows'][0].update(brier_persistence=.1))
  if name=='fixed_runtime_varies':mutate_json(out,lambda d:d['rows'][0].update(mc_seconds=1.1))
  if name=='unique_cost_exceeds_elapsed':mutate_json(rec,lambda d:d.update(elapsed_seconds=.1))
  if name=='missing_reference_status':mutate_json(out,lambda d:d['rows'][0].pop('reference_status'))
  if name=='US_fixed_reference_leak':out=run/'meanfield_vs_mc/case_06_a06/meanfield_vs_mc.json';mutate_json(out,lambda d:d['rows'][0].update(reference_status='SCORED'))
  if name=='checkpoint_wrong':mutate_json(out,lambda d:d.update(checkpoint_sha256='0'*64))
  if name=='source_phase_mixed':mutate_json(rec,lambda d:d['source_sha256'].update({'research/forecast-v2/scripts/pipeline.py':'0'*64}))
  if name=='command_N_wrong':mutate_json(rec,lambda d:d['command'].__setitem__(d['command'].index('--n-samples')+1,'12'))
  if name in ['CSV_value_changed','aggregate_value_changed','missing_case_receipt','missing_final_receipt','source_file_changed','source_snapshot_missing']:last_resign=False
  if last_resign:resign(repo,run,c)
  if name=='CSV_value_changed':p=out.with_suffix('.csv');p.write_text(p.read_text().replace('COMPARABLE','BROKEN',1))
  if name=='aggregate_value_changed':
   p=run/'meanfield_vs_mc/meanfield_vs_mc.json';mutate_json(p,lambda d:d['rows'][0].update(mean_mc=.1));mutate_json(repo/'research/forecast-v2/executions/a06_compare.json',lambda d:d.update(output_sha256=R.sha(p)))
  if name=='missing_case_receipt':rec.unlink()
  if name=='missing_final_receipt':(repo/'research/forecast-v2/executions/a06_compare.json').unlink()
  if name=='source_file_changed':(repo/'research/forecast-v2/scripts/pipeline.py').write_text('changed synthetic producer')
  if name=='source_snapshot_missing':h=c['source_pins']['research/forecast-v2/scripts/pipeline.py'];(repo/'research/forecast-v2/source_snapshots'/h/'pipeline.py.gz').unlink()
  if name=='nonfinite_metric':
   # A literal JSON NaN must refuse even before artifact reconciliation.
   p=out;p.write_text(p.read_text().replace('"rmse_all": 0.1','"rmse_all": NaN',1))
   mutate_json(rec,lambda d:d.update(output_sha256=R.sha(p)))
  try:R.reconcile(repo,run,c);results.append(dict(name=name,passed=False,reason='INCORRECT_ACCEPTANCE'))
  except (R.Refusal,FileNotFoundError) as e:results.append(dict(name=name,passed=True,reason=str(e)))
result=dict(scope='Synthetic 12-case/66-row JSON/CSV/61-source/snapshot/receipt fixtures only; no actual study files or arrays opened.',checks=results,passed=sum(x['passed'] for x in results),total=len(results),failures=[x for x in results if not x['passed']]);write(HERE/'SYNTHETIC_RESULTS.json',result);print(json.dumps(result,indent=2));raise SystemExit(bool(result['failures']))
