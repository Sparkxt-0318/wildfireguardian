"""Reconcile frozen MF/MC saved JSON/CSV/receipts, never fields or model bytes.

Run only after all 12 case receipts and the final aggregate receipt exist and
root has authorized final reconciliation. No NumPy, torch or owner code imports.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,json,math,statistics
from datetime import datetime,timedelta
from pathlib import Path
EPS=2e-6
class Refusal(ValueError):pass
def need(value,reason):
    if not value:raise Refusal(reason)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(),parse_constant=lambda s:(_ for _ in ()).throw(Refusal('NONFINITE_JSON:'+s)))
def number(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def count(x):return type(x) is int and x>=0
def close(a,b,scale=1):return number(a) and number(b) and abs(a-b)<=EPS*max(1,scale)
def utc(s):
    x=datetime.fromisoformat(s.replace('Z','+00:00'));need(x.tzinfo is not None,'NAIVE_TIMESTAMP');return x
def option(cmd,key):
    need(cmd.count(key)==1 and not any(token.startswith(key+'=') for token in cmd),'MISSING_OR_DUPLICATE_OPTION:'+key);i=cmd.index(key);need(i+1<len(cmd),'MISSING_OPTION_VALUE:'+key);return cmd[i+1]
def csv_match(path,rows):
    columns=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open(newline='') as stream:
        reader=csv.DictReader(stream);need(reader.fieldnames==columns,'CSV_COLUMN_ORDER:'+str(path));actual=list(reader)
    need(len(actual)==len(rows),'CSV_ROW_COUNT:'+str(path))
    for i,(actualrow,row) in enumerate(zip(actual,rows)):
        for key in columns:
            expect=row.get(key);got=actualrow[key]
            if expect is None:need(got=='','CSV_NULL:'+str((i,key)))
            elif isinstance(expect,str):need(got==expect,'CSV_STRING:'+str((i,key)))
            elif isinstance(expect,bool):need(got==str(expect),'CSV_BOOL:'+str((i,key)))
            else:
                try:n=float(got)
                except ValueError:raise Refusal('CSV_NUMBER:'+str((i,key)))
                need(number(n) and math.isclose(n,expect,rel_tol=2e-14,abs_tol=1e-14),'CSV_VALUE:'+str((i,key)))
def row_check(row,case,kind,hours,contract):
    need((row.get('country'),row.get('event'),row.get('cutoff'),row.get('horizon_kind'),row.get('hours'))==(case['country'],case['event'],case['cutoff'],kind,hours),'ROW_CASE_HORIZON_IDENTITY')
    need(row.get('n_samples')==contract['n_samples'] and type(row['n_samples']) is int and row.get('seed')==contract['seed'] and type(row['seed']) is int,'ROW_MC_N_OR_SEED')
    need(row.get('timing_scope')==('one joint 24h call, shared across five horizon rows' if kind=='fixed' else 'one fractional survey-endpoint call'),'ROW_TIMING_SCOPE')
    need(all(number(row.get(k)) and row[k]>=0 for k in ('mc_seconds','mf_seconds')),'ROW_RUNTIME_NONFINITE_OR_NEGATIVE')
    n,a=row.get('cells'),row.get('active_cells');need(count(n) and count(a) and a<=n<=math.prod(case['shape']),'ROW_CELL_COUNTS')
    fields=['rmse_all','mean_mc','mean_mf','expected_new_cells_mc','expected_new_cells_mf','max_abs_difference']
    if n==0:
        need(row.get('status')=='UNAVAILABLE_SHARED_SUPPORT' and a==0 and all(k in row and row[k] is None for k in fields+['rmse_active']),'EMPTY_SUPPORT_MUST_BE_UNAVAILABLE_AND_NULL')
    else:
        need(row.get('status')=='COMPARABLE' and all(number(row.get(k)) for k in fields),'COMPARABLE_FIELDS_REQUIRED')
        need(all(-EPS<=row[k]<=1+EPS for k in ['rmse_all','mean_mc','mean_mf','max_abs_difference']),'FIELD_METRIC_RANGE')
        for name in ['mc','mf']:
            need(-EPS<=row['expected_new_cells_'+name]<=n+EPS*n and close(row['expected_new_cells_'+name],row['mean_'+name]*n,n),'MEAN_EXPECTED_COUNT_ARITHMETIC')
        need(abs(row['mean_mc']-row['mean_mf'])<=row['rmse_all']+EPS and row['rmse_all']<=row['max_abs_difference']+EPS,'RMSE_MEAN_OR_MAX_BOUND')
        if a==0:need(row.get('rmse_active') is None and row['max_abs_difference']<=.001+EPS,'NO_ACTIVE_CELLS_METRIC')
        else:
            need(number(row.get('rmse_active')) and -EPS<=row['rmse_active']<=1+EPS,'ACTIVE_RMSE_RANGE')
            part=a/n*row['rmse_active']**2
            need(part-4*EPS<=row['rmse_all']**2<=part+(1-a/n)*1e-6+4*EPS,'ACTIVE_ALL_RMSE_PARTITION_BOUND')
    labeled=case['country']=='KR' or kind=='survey'
    label_fields=['reference_status','label_cells','positives','brier_mc','brier_mf','brier_persistence','label_kind']
    if not labeled:need(not any(k in row for k in label_fields),'UNLABELED_US_FIXED_ROW_MUST_NOT_HAVE_SCORES')
    else:
        need(row.get('label_kind')==('kriged reconstruction (not observed)' if case['country']=='KR' else 'NIROPS mapped extent at the next survey'),'REFERENCE_KIND')
        ln=row.get('label_cells');need(count(ln) and ln<=n,'REFERENCE_CELL_COUNTS')
        if ln==0:need(row.get('reference_status')=='UNAVAILABLE_REFERENCE_SUPPORT' and all(k in row and row[k] is None for k in ['positives','brier_mc','brier_mf','brier_persistence']),'EMPTY_REFERENCE_MUST_BE_UNAVAILABLE_AND_NULL')
        else:
            need(row.get('reference_status')=='SCORED' and count(row.get('positives')) and row['positives']<=ln,'REFERENCE_STATUS_OR_POSITIVES')
            need(all(number(row.get(k)) and -EPS<=row[k]<=1+EPS for k in ['brier_mc','brier_mf','brier_persistence']),'BRIER_RANGE')
            need(close(row['brier_persistence'],row['positives']/ln),'PERSISTENCE_BRIER_ARITHMETIC')
            need(math.sqrt(ln/n)*abs(math.sqrt(max(0,row['brier_mc']))-math.sqrt(max(0,row['brier_mf'])))<=row['rmse_all']+3*EPS,'BRIER_RMSE_CONSISTENCY_BOUND')
    return dict(event=case['event'],country=case['country'],cutoff=case['cutoff'],horizon_kind=kind,hours=hours,derived_endpoint=(utc(case['cutoff'])+timedelta(hours=hours)).isoformat())
def reconcile(repo,run,contract,attempt=6):
    repo,run=Path(repo).resolve(),Path(run).resolve();need(type(attempt) is int and attempt>=5,'FRESH_VERSIONED_ATTEMPT_REQUIRED')
    need(len(contract['source_pins'])==61 and len(contract['cases'])==12,'FIXED_SOURCE_AND_CASE_COUNTS')
    # The parent supplies the pinned source contract. Model/data arrays are never opened.
    for rel,expected in contract['source_pins'].items():need(sha(repo/rel)==expected,'CURRENT_PRODUCER_SOURCE_CHANGED:'+rel)
    need(sha(repo/'research/forecast-v2/SPLIT.json')==contract['split_sha256'],'SPLIT_SOURCE_CHANGED')
    receipts=repo/'research/forecast-v2/executions';aggregate=run/'meanfield_vs_mc/meanfield_vs_mc.json';aggregate_csv=aggregate.with_suffix('.csv');final_receipt=receipts/f'a{attempt:02d}_compare.json'
    need(final_receipt.is_file() and aggregate.is_file(),'FINAL_AGGREGATE_RECEIPT_REQUIRED')
    final=load(final_receipt);joined=load(aggregate);need(final.get('job')==f'a{attempt:02d}_compare' and final.get('exit_code')==0 and Path(final.get('output','')).resolve()==aggregate and final.get('output_sha256')==sha(aggregate),'FINAL_AGGREGATE_RECEIPT_BINDING')
    need(final.get('source_sha256')==contract['source_pins'],'FINAL_SOURCE_PHASE_BINDING')
    case_receipts=[];allrows=[];identities=[];timing=[];hosts=[];previous_finish=None
    for i,case in enumerate(contract['cases']):
        name=f'a{attempt:02d}_compare_case{i:02d}';receipt_path=receipts/(name+'.json');out=run/f'meanfield_vs_mc/case_{i:02d}_a{attempt:02d}/meanfield_vs_mc.json'
        need(receipt_path.is_file() and out.is_file(),'ALL12_CASE_OUTPUTS_AND_RECEIPTS_REQUIRED')
        receipt=load(receipt_path);result=load(out);need(receipt.get('job')==name and receipt.get('exit_code')==0 and Path(receipt.get('output','')).resolve()==out and receipt.get('output_sha256')==sha(out),'CASE_RECEIPT_OUTPUT_BINDING')
        need(receipt.get('source_sha256')==contract['source_pins'] and receipt.get('data_manifest_sha256')==contract['data_manifest_sha256'],'CASE_SOURCE_OR_INPUT_MANIFEST_BINDING')
        need(sha(receipt_path.with_suffix('.log'))==receipt.get('log_sha256'),'CASE_LOG_HASH')
        cmd=receipt['command'];need(len(cmd)>3 and Path(cmd[1]).resolve()==repo/'research/forecast-v2/scripts/pipeline.py' and cmd[2]=='compare','CASE_EXECUTED_COMMAND')
        for key,wanted in {'--compare-case-index':str(i),'--artifact-suffix':f'_a{attempt:02d}','--n-samples':str(contract['n_samples']),'--seed':str(contract['seed']),'--threads':str(contract['threads']),'--data-manifest-sha256':contract['data_manifest_sha256']}.items():need(option(cmd,key)==wanted,'CASE_EXECUTED_ARGUMENT:'+key)
        need(Path(option(cmd,'--run')).resolve()==run and '--events' not in cmd,'CASE_RUN_OR_EVENT_OVERRIDE')
        need(result.get('checkpoint_sha256')==contract['checkpoint_sha256'],'CASE_CHECKPOINT_ASSERTION')
        host=result['host'];need(all(str(host.get(k))==v for k,v in contract['pinned_versions'].items()) and host.get('torch_threads')==contract['threads'],'CASE_RUNTIME_VERSION_OR_THREADS')
        need(isinstance(host.get('platform'),str) and count(host.get('cpu_count')) and len(host.get('load_average_1_5_15',[]))==3 and all(number(x) and x>=0 for x in host['load_average_1_5_15']),'CASE_HOST_EVIDENCE')
        need(all(receipt.get('host',{}).get(k)==host.get(k) for k in ['platform','python','cpu_count']),'CASE_RECEIPT_HOST_BINDING')
        hosts.append(host);rows=result['rows'];expected=[('fixed',float(h)) for h in contract['horizons_hours']]+([('survey',case['survey_hours'])] if case['country']=='US' else [])
        need(len(rows)==len(expected),'EXACT_PERCASE_HORIZON_ROWS')
        for row,(kind,hours) in zip(rows,expected):identities.append(row_check(row,case,kind,hours,contract))
        fixed=rows[:5];need(len({(r['mc_seconds'],r['mf_seconds']) for r in fixed})==1,'FIXED_JOINT_RUNTIMES_MUST_BE_SHARED')
        unique_cost=fixed[0]['mc_seconds']+fixed[0]['mf_seconds']+sum(r['mc_seconds']+r['mf_seconds'] for r in rows[5:]);elapsed=receipt.get('elapsed_seconds')
        need(number(elapsed) and elapsed>=unique_cost-EPS and elapsed>=0,'UNIQUE_NUMERIC_COST_EXCEEDS_CHILD_ELAPSED')
        started,finished=utc(receipt['started_utc']),utc(receipt['finished_utc']);need(finished>=started and (finished-started).total_seconds()>=elapsed-.05,'CASE_WALLCLOCK_EVIDENCE')
        need(previous_finish is None or started>=previous_finish,'CASE_ORDERED_RECEIPT_TIMESTAMPS');previous_finish=finished
        timing.append(dict(case_index=i,event=case['event'],cutoff=case['cutoff'],joint24h_mc_seconds=fixed[0]['mc_seconds'],joint24h_mf_seconds=fixed[0]['mf_seconds'],survey_mc_seconds=rows[-1]['mc_seconds'] if case['country']=='US' else None,survey_mf_seconds=rows[-1]['mf_seconds'] if case['country']=='US' else None,complete_child_seconds=elapsed))
        csv_match(out.with_suffix('.csv'),rows);allrows.extend(rows);case_receipts.append(dict(path=str(receipt_path.relative_to(repo)),sha256=sha(receipt_path)))
    need(len(allrows)==66 and joined.get('rows')==allrows,'AGGREGATE_MUST_EXACTLY_CONCATENATE66_ROWS')
    need(joined.get('checkpoint_sha256')==contract['checkpoint_sha256'] and joined.get('host')==hosts[-1] and joined.get('timing')=='Each fixed-horizon group shares one joint24h MC and MF call','AGGREGATE_IDENTITY_HOST_TIMING')
    need(joined.get('case_receipts')==case_receipts and final.get('case_receipts')==case_receipts,'AGGREGATE_ALL12_RECEIPT_PINS')
    csv_match(aggregate_csv,allrows)
    need(len({tuple(h[k] for k in ['python','torch','numpy','platform','cpu_count','torch_threads']) for h in hosts})==1,'MIXED_EXECUTION_HOSTS_OR_VERSIONS')
    # Sources are authenticated from saved content-addressed code snapshots, not model weights.
    for rel,expected in contract['source_pins'].items():
        snapshot=repo/'research/forecast-v2/source_snapshots'/expected/(Path(rel).name+'.gz');need(hashlib.sha256(gzip.decompress(snapshot.read_bytes())).hexdigest()==expected,'SOURCE_SNAPSHOT_CUSTODY:'+rel)
    groups={}
    for row in allrows:groups.setdefault((row['country'],row['horizon_kind'],row['hours']),[]).append(row)
    summaries=[]
    for (country,kind,hours),rs in groups.items():
        comparable=[r for r in rs if r['status']=='COMPARABLE'];scored=[r for r in rs if r.get('reference_status')=='SCORED']
        summaries.append(dict(country=country,horizon_kind=kind,hours=hours,rows=len(rs),comparable_rows=len(comparable),unavailable_rows=len(rs)-len(comparable),sum_common_cells=sum(r['cells'] for r in rs),active_cells=sum(r['active_cells'] for r in rs),descriptive_median_saved_rmse_all=statistics.median(r['rmse_all'] for r in comparable) if comparable else None,scored_reference_rows=len(scored),reference_unavailable_rows=sum(r.get('reference_status')=='UNAVAILABLE_REFERENCE_SUPPORT' for r in rs),saved_label_cells=sum(r.get('label_cells',0) for r in rs)))
    return dict(status='PASS_SAVED_METRIC_RECONCILIATION',scope='Complete saved JSON/CSV/receipt/source reconciliation only. No field-array RMSE or Brier replay, MC rerun, model-byte hash audit, inference or heldout access.',attempt=attempt,case_count=12,row_count=66,KR_cutoffs=6,KR_events=3,US_cutoffs=6,US_events=6,row_status_counts=dict(collections.Counter(r['status'] for r in allrows)),reference_status_counts=dict(collections.Counter(r.get('reference_status','NOT_SCORED_NO_REFERENCE_AT_FIXED_HORIZON') for r in allrows)),source_files=61,producer_writes_field_arrays=False,field_arrays_opened=False,raw_field_replay=False,checkpoint_hash_scope='Producer assertion matches pinned source constant; actual checkpoint file not opened or rehashed.',backend_scope='CPU execution inferred from pinned command_compare source load_model(device=cpu), CPU tensors and numpy extraction; host metadata retained.',no_promotion_or_speed_claim=True,aggregate_sha256=sha(aggregate),aggregate_receipt_sha256=sha(final_receipt),case_receipts=case_receipts,derived_row_identities=identities,unique_call_costs=timing,descriptive_groups=summaries)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True,type=Path);p.add_argument('--run',required=True,type=Path);p.add_argument('--contract',type=Path,default=Path(__file__).with_name('SOURCE_CONTRACT.json'));p.add_argument('--attempt',type=int,default=6);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    result=reconcile(a.repo,a.run,load(a.contract),a.attempt);result.update(contract_sha256=sha(a.contract),checker_sha256=sha(Path(__file__)));a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','case_count','row_count','row_status_counts','reference_status_counts']}))
if __name__=='__main__':main()
