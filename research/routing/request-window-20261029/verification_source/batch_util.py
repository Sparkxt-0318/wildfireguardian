"""Source-bound serial dispatcher; requires the parent's active shared lease.

No detached sessions, concurrency, parameter search, source changes, or new
routing runs. Per-case leaf outputs remain the authoritative reference results.
"""
from pathlib import Path
import datetime, hashlib, json, os, signal, subprocess, sys, time

ROOT=Path(__file__).resolve().parent.parent
WS=ROOT.parents[1]
REF=ROOT/'reference'
SEAL=REF/'ACTUAL_BATCH_SOURCE_SEAL.json'
LEASE=WS/'outputs/SHARED_HEAVY_TIMING_LOCK.json'
PREFIX='Codex-thermal-verification-20261028-reference-'
PER_CASE_SECONDS=300
TOTAL_SECONDS=3600
MEMORY_GUARD_MIB=3072
ACTIVE=None

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def check(s):
    for p,h in s['source_sha256'].items():
        if sha(p)!=h:raise RuntimeError('SOURCE_CHANGED:'+p)
def utc():return datetime.datetime.now(datetime.timezone.utc)
def lease(expected):
    value=read(LEASE)
    if value.get('status')!='HELD' or value.get('holder')!=expected or not expected.startswith(PREFIX):raise RuntimeError('EXPECTED_REFERENCE_LEASE_NOT_HELD')
    expiry=datetime.datetime.fromisoformat(value['lease_until_utc'])
    if expiry.tzinfo is None or expiry<=utc():raise RuntimeError('REFERENCE_LEASE_EXPIRED')
    return value
def interrupt(signum,frame):raise InterruptedError('SIGNAL_'+str(signum))

def sample_rss(child,timeout=2):
    """Sample controller + direct scientific leaf; ps RSS uses 1024-byte KiB.

    A leaf that exits during sampling is no longer a live sample obligation.
    Unavailable samples of a still-live process fail closed. The sampling helper
    itself is transient controller overhead, not part of the reported sum.
    """
    wanted={os.getpid(),child.pid}
    measurement=subprocess.run(['/bin/ps','-o','pid=','-o','rss=','-p',','.join(map(str,sorted(wanted)))],capture_output=True,text=True,timeout=timeout)
    values={}
    if measurement.returncode:raise RuntimeError('RSS_PS_FAILED:'+str(measurement.returncode))
    for line in measurement.stdout.splitlines():
        fields=line.split()
        if len(fields)!=2:raise RuntimeError('RSS_PARSE_FAILED')
        pid,kib=map(int,fields)
        if pid not in wanted or pid in values or kib<0:raise RuntimeError('RSS_UNEXPECTED_VALUE')
        values[pid]=kib
    required={os.getpid()}|({child.pid} if child.poll() is None else set())
    if not required.issubset(values):raise RuntimeError('RSS_LIVE_PROCESS_UNAVAILABLE')
    return dict(total_rss_bytes=sum(values.values())*1024,process_rss_kib={str(k):v for k,v in values.items()},leaf_live_at_sample_end=child.poll() is None)

def leaf(command,log_path,seconds,expected):
    global ACTIVE
    lease(expected);started=time.monotonic();hard_deadline=started+seconds;timed_out=False;memory_cap=False;memory_error=None;samples=[]
    log_path=Path(log_path)
    if log_path.exists():raise RuntimeError('LOG_EXISTS:'+str(log_path))
    try:
        with log_path.open('x') as log:
            # Same process group as this controller. The outer guard owns the
            # whole tree; these scientific leaves launch no child processes.
            ACTIVE=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=WS,
              env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            while ACTIVE.poll() is None:
                lease(expected)
                remaining=hard_deadline-time.monotonic()
                if remaining<=0:timed_out=True;ACTIVE.kill();break
                try:
                    sample=sample_rss(ACTIVE,timeout=min(2.0,remaining));sample['elapsed_s']=time.monotonic()-started;samples.append(sample)
                except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
                    if time.monotonic()>=hard_deadline:timed_out=True
                    else:memory_error=type(error).__name__+':'+str(error)
                    if ACTIVE.poll() is None:ACTIVE.kill()
                    break
                if sample['total_rss_bytes']>MEMORY_GUARD_MIB*1024*1024:
                    memory_cap=True
                    if ACTIVE.poll() is None:ACTIVE.kill()
                    break
                remaining=hard_deadline-time.monotonic()
                if remaining<=0:timed_out=True;ACTIVE.kill();break
                try:ACTIVE.wait(timeout=min(1.0,remaining))
                except subprocess.TimeoutExpired:pass
            returncode=ACTIVE.wait(timeout=10)
    except BaseException:
        if ACTIVE is not None and ACTIVE.poll() is None:ACTIVE.kill();ACTIVE.wait(timeout=10)
        raise
    finally:ACTIVE=None
    return dict(command=command,returncode=returncode,hard_timeout=timed_out,memory_cap=memory_cap,memory_sampling_error=memory_error,
      sampled_peak_rss_bytes=max(s['total_rss_bytes'] for s in samples) if samples else None,memory_guard_mib=MEMORY_GUARD_MIB,rss_sample_count=len(samples),rss_samples=samples,
      rss_scope='Sampled controller plus direct active leaf; 1024-byte ps RSS units, nominal 1s loop plus <=2s ps timeout. Not an OS memory ceiling or proof of unsampled peak; short-lived ps helper excluded.',
      elapsed_s=time.monotonic()-started,log_path=str(log_path),log_sha256=sha(log_path))

def existing(path,job):
    value=read(path)
    if value.get('status')!='COMPLETE_SCOPED' or value.get('source_seal_sha256')!=job['leaf_seal_sha256']:raise RuntimeError('EXISTING_OUTPUT_UNBOUND:'+str(path))
    result=value['result']
    if result['case_id']!=job['case_id'] or result['mode']!='radial':raise RuntimeError('EXISTING_OUTPUT_CONTEXT:'+str(path))
    return dict(output_path=str(path),output_sha256=sha(path),all_members_within_thermal_thresholds=result['all_members_within_thermal_thresholds'])

def queue(s):
    current=read(REF/'ACTUAL_ROUTES_SOURCE_SEAL.json');extra=read(REF/'EXTRA_ORIGINAL_SOURCE_SEAL.json');jobs=[]
    for c in current['contexts']:
        case=read(c['job'])['case_id']
        jobs.append(dict(case_id=case,origin='CURRENT_NATIVE_CONTEXT',script='actual_routes.py',args=['run','--case',case,'--mode','radial'],
          output='ACTUAL_'+case+'_RADIAL.json',leaf_seal_sha256=sha(REF/'ACTUAL_ROUTES_SOURCE_SEAL.json')))
    for row in extra['extra']:
        case=row['case_id']
        jobs.append(dict(case_id=case,origin='THREE_EXTRA_ORIGINAL_WITNESSES',script='extra_original_routes.py',args=['run','--case',case],
          output='ORIGINAL_EXTRA_'+case+'_RADIAL.json',leaf_seal_sha256=sha(REF/'EXTRA_ORIGINAL_SOURCE_SEAL.json')))
    if len(jobs)!=18 or len({j['output'] for j in jobs})!=18:raise RuntimeError('FIXED_18_QUEUE_REQUIRED')
    return jobs

def prerequisites():
    paths=[REF/'CONTROL_RESULTS.json',ROOT/'coordination/ACTUAL_ADAPTER_CONTROLS_BATCH_RECEIPT.json',ROOT/'coordination/ACTUAL_TRIANGLE_PILOT_BATCH_RECEIPT.json',REF/'ACTUAL_20220304T030000Z_FX1_TRIANGLE.json']
    core,adapter,pilot,triangle=map(read,paths)
    if core.get('status')!='PASS_SCOPED' or core.get('controls_run')!=12 or core.get('failures') or core.get('errors') or core.get('skipped'):raise RuntimeError('REFERENCE_CONTROLS_NOT_PASSED')
    if adapter.get('returncode')!=0 or 'test_actual_adapter.py' not in adapter.get('command',[]) or not adapter.get('ended_utc'):raise RuntimeError('ADAPTER_CONTROLS_NOT_PASSED')
    if pilot.get('returncode')!=0 or not pilot.get('ended_utc') or triangle.get('status')!='COMPLETE_SCOPED' or triangle.get('source_seal_sha256')!=sha(REF/'ACTUAL_ROUTES_SOURCE_SEAL.json'):raise RuntimeError('TRIANGLE_PILOT_NOT_COMPLETED')
    for receipt in (adapter,pilot):
        if receipt.get('surviving_observed_owned_processes') or receipt.get('detached_group_contract_violated'):raise RuntimeError('PREREQUISITE_CLEANUP_NOT_CLEAR')
    return {str(p):sha(p) for p in paths}

def freeze():
    inherited=read(REF/'EXTRA_ORIGINAL_SOURCE_SEAL.json');check(inherited)
    files=set(inherited['source_sha256'])|{str(REF/'EXTRA_ORIGINAL_SOURCE_SEAL.json'),str(Path(__file__).resolve()),str(REF/'ACTUAL_BATCH_PROTOCOL.md')}
    write_new(SEAL,dict(status='FROZEN_BEFORE_SERIAL_18_REFERENCE_BATCH',source_sha256={p:sha(p) for p in sorted(files)},per_case_hard_seconds=PER_CASE_SECONDS,total_hard_seconds=TOTAL_SECONDS,
      queue_order='15 original sealed context order, then three extra original index order; no outcome-based sorting',expected_lease_prefix=PREFIX))
    print('SEALED',len(files),'files')

def run():
    seal=read(SEAL);check(seal);expected=PREFIX+str(os.getppid());lease_at_start=lease(expected);prereq=prerequisites();jobs=queue(seal)
    summary_path=REF/'ACTUAL_RADIAL_BATCH_SUMMARY.json';progress_path=REF/'ACTUAL_RADIAL_BATCH_PROGRESS.json';logs=REF/'ACTUAL_RADIAL_BATCH_LOGS'
    if summary_path.exists() or progress_path.exists() or logs.exists():raise RuntimeError('BATCH_OUTPUT_ALREADY_EXISTS')
    logs.mkdir();started=time.monotonic();deadline=started+TOTAL_SECONDS
    result=dict(schema='wfg.independent-thermal.serial-batch/1',status='RUNNING',source_seal_sha256=sha(SEAL),expected_lease_holder=expected,
      lease_at_start=lease_at_start,prerequisite_sha256=prereq,started_utc=utc().isoformat(),per_case_hard_seconds=PER_CASE_SECONDS,total_hard_seconds=TOTAL_SECONDS,memory_guard_mib=MEMORY_GUARD_MIB,jobs=[],controls=None)
    def progress():
        temporary=progress_path.with_suffix('.tmp');temporary.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n');temporary.replace(progress_path)
    for name in ('SIGTERM','SIGINT'):signal.signal(getattr(signal,name),interrupt)
    stop_reason=None
    try:
        progress()
        command=[sys.executable,'-B','-m','unittest','discover','-s',str(REF),'-p','test_extra_original.py']
        control=leaf(command,logs/'00_EXTRA_ORIGINAL_CONTROLS.log',min(60,deadline-time.monotonic()),expected);result['controls']=control
        if control['returncode'] or control['hard_timeout'] or control['memory_cap'] or control['memory_sampling_error'] or 'Ran 4 tests' not in Path(control['log_path']).read_text():raise RuntimeError('FOUR_STRICT_EXTRA_CONTROLS_FAILED')
        for index,job in enumerate(jobs,1):
            check(seal);lease(expected);remaining=deadline-time.monotonic()
            if remaining<=0:stop_reason='TOTAL_HARD_CAP';break
            row=dict(index=index,case_id=job['case_id'],origin=job['origin'])
            output=REF/job['output']
            if output.exists():row.update(status='ALREADY_PRESENT_SOURCE_BOUND',**existing(output,job))
            else:
                command=[sys.executable,'-B',str(REF/job['script']),*job['args']]
                execution=leaf(command,logs/(str(index).zfill(2)+'_'+job['origin']+'_'+job['case_id']+'.log'),min(PER_CASE_SECONDS,remaining),expected)
                row.update(execution)
                if execution['memory_sampling_error']:row['status']='CASE_MEMORY_SAMPLE_UNAVAILABLE'
                elif execution['memory_cap']:row['status']='CASE_MEMORY_CAP'
                elif execution['hard_timeout']:row['status']='CASE_HARD_CAP'
                elif execution['returncode']:row['status']='CASE_EXECUTION_ERROR'
                elif not output.exists():row['status']='CASE_OUTPUT_MISSING'
                else:row.update(status='COMPLETE_SOURCE_BOUND',**existing(output,job))
                if row['status']!='COMPLETE_SOURCE_BOUND' and output.exists():row['present_unvalidated_output']=str(output)
            result['jobs'].append(row);progress();print(json.dumps({k:row[k] for k in ('index','case_id','origin','status')}),flush=True)
            if row['status']=='CASE_MEMORY_SAMPLE_UNAVAILABLE':stop_reason='MEMORY_SAMPLING_UNAVAILABLE';break
        check(seal)
        for p,h in prereq.items():
            if sha(p)!=h:raise RuntimeError('PREREQUISITE_EVIDENCE_CHANGED:'+p)
        lease(expected)
    except (Exception,KeyboardInterrupt) as error:stop_reason=type(error).__name__+':'+str(error)
    finally:
        if ACTIVE is not None and ACTIVE.poll() is None:ACTIVE.kill();ACTIVE.wait(timeout=10)
        covered={row['index'] for row in result['jobs']}
        for index,job in enumerate(jobs,1):
            if index not in covered:result['jobs'].append(dict(index=index,case_id=job['case_id'],origin=job['origin'],status='NOT_RUN',reason=stop_reason or 'UNEXPECTED_MISSING'))
        successful={row['index'] for row in result['jobs'] if row['status'] in ('COMPLETE_SOURCE_BOUND','ALREADY_PRESENT_SOURCE_BOUND')}
        missing=[str(REF/job['output']) for index,job in enumerate(jobs,1) if index not in successful]
        result.update(status=('BATCH_COMPLETE' if not missing else 'BATCH_COMPLETE_WITH_MISSING') if stop_reason is None else 'BATCH_STOPPED',stop_reason=stop_reason,ended_utc=utc().isoformat(),elapsed_s=time.monotonic()-started,
          missing_outputs=missing,scope='Serial source-bound fixed-trajectory reference batch; process caps and missing outputs explicit; not a route campaign or timing comparison')
        progress();write_new(summary_path,result)
    print(json.dumps(dict(status=result['status'],jobs=len(result['jobs']),missing=len(result['missing_outputs']),stop_reason=stop_reason)),flush=True)
    if stop_reason or result['missing_outputs']:raise SystemExit(1)

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('seal','run'):raise SystemExit('usage: run_actual_batch.py seal|run')
    (freeze if sys.argv[1]=='seal' else run)()
