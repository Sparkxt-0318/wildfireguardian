"""Serial source-bound new-fire routing controller; parent guard/lease required.

No detached worker sessions. No retries, parameter changes or on-the-fly input
generation. Manifest and source gate must be frozen before execution.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
WS=ROOT.parents[1]
LEASE=WS/'outputs/SHARED_HEAVY_TIMING_LOCK.json'
BUDGET=30.0
MEMORY_BYTES=3072*1024*1024
TOTAL_SECONDS=3600.0
ACTIVE=None


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc)
def write_new(p,value):
    with Path(p).open('x') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')


def check_sources(pins):
    for p,h in pins.items():
        if not Path(p).is_absolute() or sha(p)!=h:
            raise RuntimeError('SOURCE_IDENTITY_MISMATCH:'+p)


def check_job_identity(row,job):
    if job['case_id']!=row['case_id'] or type(job.get('rep')) is not int or job['rep']!=row['rep']:
        raise RuntimeError('JOB_CASE_OR_REPETITION_MISMATCH')


def lease(expected):
    value=read(LEASE)
    if value.get('status')!='HELD' or value.get('holder')!=expected:
        raise RuntimeError('EXPECTED_SHARED_LEASE_NOT_HELD')
    expiry=datetime.datetime.fromisoformat(value['lease_until_utc'])
    if expiry.tzinfo is None or expiry<=utc():
        raise RuntimeError('SHARED_LEASE_EXPIRED')
    return value


def snapshot(timeout):
    """Read bounded native process identities; exclude the owned ps helper."""
    helper=subprocess.Popen(['/bin/ps','-A','-o','pid=,ppid=,pgid=,rss=,stat=,lstart='],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        out,err=helper.communicate(timeout=timeout)
    except BaseException:
        helper.kill();helper.wait(timeout=2);raise
    if helper.returncode:
        raise RuntimeError('PS_FAILED:'+str(helper.returncode)+':'+err[:200])
    rows={}
    for line in out.splitlines():
        p=line.split(None,9)
        if len(p)!=10 or not all(x.lstrip('-').isdigit() for x in p[:4]):
            raise RuntimeError('PROCESS_CENSUS_MALFORMED')
        pid,ppid,pgid,rss=map(int,p[:4])
        if pid in rows or min(pid,ppid,pgid,rss)<0:
            raise RuntimeError('PROCESS_CENSUS_DUPLICATE_OR_NEGATIVE')
        if pid!=helper.pid:
            rows[pid]={'pid':pid,'ppid':ppid,'pgid':pgid,'rss_kib':rss,
                'state':p[4],'start':' '.join(' '.join(p[5:]).split())}
    if os.getpid() not in rows:
        raise RuntimeError('CONTROLLER_CENSUS_MISSING')
    return rows


def owned(rows,group,controller,lineage):
    """Isolated owned group plus identity-verified observed descendants only."""
    live={p:r for p,r in rows.items() if p!=controller and not r['state'].startswith('Z')}
    selected={p for p,r in live.items() if r['pgid']==group}
    for p,old in lineage.items():
        if p in live and p not in selected:
            if not old.get('start') or not live[p].get('start'):
                raise RuntimeError('TRACKED_PROCESS_IDENTITY_UNKNOWN')
            if live[p]['start']==old['start']:
                selected.add(p)
    while True:
        kids={p for p,r in live.items() if r['ppid'] in selected}
        if kids<=selected:break
        selected|=kids
    for p in selected:
        lineage[p]={k:live[p][k] for k in ('ppid','pgid','start')}
    detached=[p for p in selected if live[p]['pgid']!=group]
    return selected,detached


def interrupt(sig,frame):
    raise InterruptedError('SIGNAL_'+str(sig))


def clean(child,group,lineage):
    record={'status':'UNKNOWN','signals':[],'census':[]}
    try:
        for sig,duration in ((signal.SIGTERM,2.0),(signal.SIGKILL,3.0)):
            end=time.perf_counter()+duration
            while True:
                rows=snapshot(min(1.0,max(.01,end-time.perf_counter())))
                pids,detached=owned(rows,group,os.getpid(),lineage)
                record['census'].append({'utc':utc().isoformat(),'pids':sorted(pids),'detached':detached})
                if not pids:break
                for pid in sorted(pids):
                    try:os.kill(pid,sig);record['signals'].append({'pid':pid,'signal':int(sig)})
                    except ProcessLookupError:pass
                if time.perf_counter()>=end:break
                time.sleep(min(.05,max(0,end-time.perf_counter())))
            if not pids:break
        if child is not None:
            if child.poll() is None:child.kill()
            child.wait(timeout=2)
        rows=snapshot(1.0);pids,detached=owned(rows,group,os.getpid(),lineage)
        record.update(status='CLEAN' if not pids else 'SURVIVORS',remaining=sorted(pids),detached=detached)
    except BaseException as error:
        record['error']=type(error).__name__+':'+str(error)
        if child is not None and child.poll() is None:
            child.kill();child.wait(timeout=2)
    return record


def deadline_stop_reason(error,now,deadline):
    # A ps helper can exhaust its final sub-millisecond allowance while the
    # primary request deadline expires. The attempt stays unresolved and is
    # never published; verified cleanup permits the fixed queue to continue.
    if isinstance(error,subprocess.TimeoutExpired) and now>=deadline:
        return 'COMPLETE_REQUEST_TIME_CAP'
    return type(error).__name__+':'+str(error)


def run_attempt(row,manifest,expected):
    global ACTIVE
    job_path=Path(row['job_file']);job=read(job_path)
    if sha(job_path)!=row['job_sha256'] or float(job['complete_budget_s'])!=BUDGET or job['arm'] not in ('RDA_CAND','RDA_BASE'):
        raise RuntimeError('JOB_BINDING_OR_30S_POLICY_MISMATCH')
    if job.get('checker_module')!='adaptive_checker' or job.get('preparation_mode')!='COLD_FAST':
        raise RuntimeError('BASE_CHECKER_AND_COLD_PREPARATION_REQUIRED')
    variant=manifest['variants'][row['variant']]
    stack=Path(variant['stack_root']).resolve()
    source=Path(job['source_root'])
    source=(Path(job['root'])/source).resolve() if not source.is_absolute() else source.resolve()
    if source!=stack/'routing_candidate':raise RuntimeError('WORKER_SOURCE_ROOT_MISMATCH')
    root=Path(job['root']).resolve();out=Path(job['output_path'])
    out=(root/out).resolve() if not out.is_absolute() else out.resolve()
    if out!=Path(row['output_path']).resolve():raise RuntimeError('OUTPUT_DIRECTORY_MISMATCH')
    receipt=Path(row.get('receipt_path',str(out/'COMPLETE_PROCESS_RECEIPT.json'))).resolve()
    if receipt!=out/'COMPLETE_PROCESS_RECEIPT.json':raise RuntimeError('FIXED_RECEIPT_LOCATION_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    write_new(out/'JOB.json',job)
    env={k:v for k,v in os.environ.items() if not k.startswith('PYTHON')}
    env.pop('WFG_OWNER_PREPARED_CACHE',None)
    env.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    command=[manifest['python_executable'],'-B',row['worker_path'],'--job-file',str(job_path)]
    group=os.getpgrp();lineage={};samples=[];reason=None;returncode=None;elapsed=None
    start=time.perf_counter();deadline=start+BUDGET
    env['WFG_OUTER_MONOTONIC_START']=repr(start)
    rec={'schema':'wfg.new-fire.complete-process-receipt/1','execution_id':row['execution_id'],
        'job_sha256':row['job_sha256'],'command':command,'started_utc':utc().isoformat(),
        'complete_budget_s':BUDGET,'memory_guard_mib':3072,'origin_monotonic':start,
        'on_time_complete_publication':False,'status':'STARTED','lease_holder':expected}
    try:
        with (out/'WORKER.log').open('x') as log:
            ACTIVE=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                cwd=WS,env=env)  # inherits controller's outer-owned isolated group
            while ACTIVE.poll() is None:
                lease(expected)
                remaining=deadline-time.perf_counter()
                if remaining<=0:reason='COMPLETE_REQUEST_TIME_CAP';break
                rows=snapshot(min(1.0,remaining));pids,detached=owned(rows,group,os.getpid(),lineage)
                if ACTIVE.poll() is None and ACTIVE.pid not in pids:
                    raise RuntimeError('ACTIVE_WORKER_CENSUS_MISSING')
                rss=sum(rows[p]['rss_kib'] for p in pids|{os.getpid()})*1024
                samples.append({'elapsed_s':time.perf_counter()-start,'rss_bytes':rss,
                    'pids':sorted(pids),'detached':detached})
                if detached:reason='DETACHED_PROCESS_CONTRACT_VIOLATION';break
                if rss>MEMORY_BYTES:reason='SAMPLED_PROCESS_FAMILY_RSS_CAP';break
                if time.perf_counter()>=deadline:reason='COMPLETE_REQUEST_TIME_CAP';break
                try:ACTIVE.wait(timeout=min(.1,max(.001,deadline-time.perf_counter())))
                except subprocess.TimeoutExpired:pass
            if reason is None:
                returncode=ACTIVE.wait(timeout=.1);elapsed=time.perf_counter()-start
                if elapsed>BUDGET:reason='COMPLETE_REQUEST_TIME_CAP'
    except BaseException as error:
        reason=deadline_stop_reason(error,time.perf_counter(),deadline)
    finally:
        elapsed=time.perf_counter()-start if elapsed is None else elapsed
        cleanup=clean(ACTIVE,group,lineage)
        if ACTIVE is not None:returncode=ACTIVE.returncode
        ACTIVE=None
    try:
        check_sources(manifest['source_sha256'])
        if sha(job_path)!=row['job_sha256']:raise RuntimeError('JOB_CHANGED_DURING_ATTEMPT')
    except BaseException as error:
        reason=type(error).__name__+':'+str(error)
    if reason is None and not samples:reason='NO_PROCESS_FAMILY_RSS_SAMPLE'
    rec.update(status='COMPLETE' if reason is None and returncode==0 and cleanup['status']=='CLEAN' else 'UNRESOLVED_ATTEMPT',
        stop_reason=reason,returncode=returncode,elapsed_s=elapsed,cleanup=cleanup,
        ended_utc=utc().isoformat(),rss_samples=samples,
        sampled_family_peak_rss_bytes=max(x['rss_bytes'] for x in samples) if samples else None,
        rss_scope='Sampled isolated controller plus worker family; ps KiB*1024. ps helper excluded. Not an OS ceiling or proof of unsampled peak.')
    result_path=out/'RESULT.json';boundary_path=out/'PUBLICATION_BOUNDARY.json'
    if result_path.exists() and boundary_path.exists():
        try:
            result=read(result_path);boundary=read(boundary_path)
            rec['on_time_complete_publication']=bool(rec['status']=='COMPLETE' and elapsed<=BUDGET
                and result.get('authority_final') is True and boundary.get('result_published_before_deadline') is True)
            rec.update(result_sha256=sha(result_path),publication_boundary_sha256=sha(boundary_path),
                primary_status=result.get('primary_status'),primary_reason=result.get('primary_reason'))
        except (ValueError,TypeError,KeyError,OSError) as error:
            rec.update(status='UNRESOLVED_ATTEMPT',stop_reason='INVALID_PUBLICATION_RECORD:'+str(error),
                on_time_complete_publication=False)
    write_new(receipt,rec)
    return rec


def validate_queue(manifest):
    original=read(manifest['original_queue_path'])
    if sha(manifest['original_queue_path'])!=manifest['original_queue_sha256']:
        raise RuntimeError('ORIGINAL_QUEUE_CHANGED')
    jobs=manifest['jobs']; archived=original['jobs']
    if len(jobs)!=80 or len(archived)!=80:
        raise RuntimeError('EXACT_ORIGINAL_80_QUEUE_REQUIRED')
    if [(j['case_id'],j['rep'],j['arm']) for j in jobs]!=[(j['case_id'],j['rep'],j['arm']) for j in archived]:
        raise RuntimeError('ORIGINAL_ORDER_OR_REPETITIONS_CHANGED')
    if len({j['execution_id'] for j in jobs})!=80 or len({j['output_path'] for j in jobs})!=80:
        raise RuntimeError('DISTINCT_EXECUTIONS_REQUIRED')
    for row,old in zip(jobs,archived):
        job=read(row['job_file'])
        for key in ('input_sha256','source_sha256','original_limits','complete_budget_s','memory_guard_mib','preparation_mode'):
            if job[key]!=old[key]:raise RuntimeError('FROZEN_PROTOCOL_CHANGED:'+key)
        if row['arm']!=job['arm']:raise RuntimeError('ARM_BINDING')
        worker=Path(row['worker_path'])
        expected='baseline_worker.py' if row['arm']=='RDA_BASE' else 'rda_worker_v1_1.py'
        if worker!=Path(manifest['variants'][row['variant']]['stack_root'])/'phaseB'/expected:
            raise RuntimeError('WORKER_BINDING')


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output-summary',type=Path,required=True)
    p.add_argument('--lane',choices=['broader','audit'],default='broader');args=p.parse_args()
    if args.output_summary.exists():raise RuntimeError('SUMMARY_ALREADY_EXISTS')
    if os.getpgrp()!=os.getpid() or os.getsid(0)!=os.getpid():
        raise RuntimeError('REQUIRES_OUTER_GUARD_ISOLATED_CONTROLLER_SESSION')
    manifest_bytes=args.manifest.read_bytes()
    manifest=json.loads(manifest_bytes)
    manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest()
    if manifest.get('schema')!='wfg.new-fire.routing-run-manifest/1':raise RuntimeError('MANIFEST_SCHEMA')
    pins=manifest['source_sha256'];check_sources(pins)
    if pins.get(str(Path(__file__).resolve()))!=sha(__file__):raise RuntimeError('CONTROLLER_NOT_SOURCE_BOUND')
    if manifest['python_executable']!=sys.executable:raise RuntimeError('INTERPRETER_PATH_MISMATCH')
    validate_queue(manifest)
    jobs=manifest['jobs']
    for row in jobs:
        if Path(row['output_path']).exists():raise RuntimeError('EXISTING_ATTEMPT_NEVER_RERUN:'+row['execution_id'])
        if pins.get(str(Path(row['job_file']).resolve()))!=row['job_sha256']:raise RuntimeError('JOB_NOT_IN_MANIFEST_SOURCE_BINDING')
        check_job_identity(row,read(row['job_file']))
    expected='Codex-thermal-verification-20261028-'+args.lane+'-'+str(os.getppid())
    lease(expected)
    for name in ('SIGTERM','SIGINT'):signal.signal(getattr(signal,name),interrupt)
    summary={'schema':'wfg.new-fire.serial-run-summary/1','status':'RUNNING',
        'manifest_sha256':manifest_sha256,'lease_holder':expected,'jobs':[],
        'scope':'Fresh paired baseline/candidate; original80 input queue; no independent thermal proof in this controller'}
    reason=None;batch_deadline=time.perf_counter()+TOTAL_SECONDS
    try:
        for row in jobs:
            if sha(args.manifest)!=manifest_sha256:raise RuntimeError('MANIFEST_CHANGED')
            check_sources(pins);lease(expected)
            if batch_deadline-time.perf_counter()<BUDGET:
                reason='TOTAL_CONTROLLER_CAP';break
            rec=run_attempt(row,manifest,expected);summary['jobs'].append(rec)
            if sha(args.manifest)!=manifest_sha256:raise RuntimeError('MANIFEST_CHANGED')
            check_sources(pins);lease(expected)
            if rec['cleanup']['status']!='CLEAN' or rec.get('stop_reason') not in (None,'COMPLETE_REQUEST_TIME_CAP','SAMPLED_PROCESS_FAMILY_RSS_CAP'):
                reason='CLEANUP_OR_CENSUS_UNKNOWN';break
    except BaseException as error:
        reason=type(error).__name__+':'+str(error)
    finally:
        done={j['execution_id'] for j in summary['jobs']}
        summary['not_run']=[dict(execution_id=j['execution_id'],output_path=j['output_path'],
            status='INTERRUPTED_ATTEMPT_NO_RECEIPT' if Path(j['output_path']).exists() else 'NOT_LAUNCHED',
            reason=reason or 'NOT_REACHED') for j in jobs if j['execution_id'] not in done]
        summary.update(status='COMPLETE_QUEUE' if reason is None and not summary['not_run'] else 'STOPPED_QUEUE',
            stop_reason=reason,ended_utc=utc().isoformat())
        write_new(args.output_summary,summary)
    print(json.dumps({'status':summary['status'],'attempted':len(summary['jobs']),'not_run':len(summary['not_run'])}))
    if summary['status']!='COMPLETE_QUEUE':raise SystemExit(1)


if __name__=='__main__':
    main()
