"""Bookend the exact prepared command; no numerical logic or array decoding."""
from pathlib import Path
from datetime import datetime,timezone
import fcntl,hashlib,json,os,platform,resource,subprocess,time
base=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on')
out=base/'work/descriptive-interval-actual-independent-review'
root=base/'work/track-1b'
sidecar=root/'research/forecast-v2/supplements/current_descriptive_intervals_output_20261031_v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name,h in [('DESCRIPTIVE_INTERVALS.json','060cb9db4ab4918dde57adbff478ae68437de91b0b0efdc0e7cb75ad32e25e5c'),('COMPLETION.json','05864ec95b0f042bbdba86dbb43374b591afbb8e56ab779730272fae70d863a9'),('us2024_draws.npy','4943b1da8411684b19dd71885aabfcbac304bc840f4c85bfb1a68c65a0c9d42e')]:assert sha(sidecar/name)==h
lock=Path('/tmp/wfg/HEAVY.lock')
def available():
 with lock.open('a+') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
 return True
argv=[str(base/'work/venv-forecast/bin/python'),str(out/'review_actual.py'),
 '--authorization',str(base/'work/DESCRIPTIVE_INTERVAL_ACTUAL_AUTHORIZATION_ATTEMPT2.json'),
 '--authorization-sha256','3195c8c789954f845622e35f7fbe43d792bfa8a432700507fea4c6df7d195ebc',
 '--canonical-map',str(base/'work/CANONICAL_PROTECTED_858.json'),
 '--canonical-map-sha256','4406548a90d179bbfbbbd2af23c3759ceb167c4bad951e73fd4788a8144a5803',
 '--out',str(out/'ACTUAL_REVIEW_ATTEMPT2.json')]
assert available()
record={'scope':'whole checker process envelope; exact internal lease timestamps not instrumented',
 'review_authorization_sha256':'941f619595697f83f4899b3606eed2a0228df83eec852eab29e92ed8c645a045',
 'argv':argv,'preparation_manifest_sha256':sha(out/'PREPARATION_MANIFEST.json'),
 'heavy_available_before':True,'started_utc':datetime.now(timezone.utc).isoformat(),
 'host':{'system':platform.system(),'machine':platform.machine()},'model_inference':False}
(out/'ACTUAL_REVIEW_PROCESS_START.json').write_text(json.dumps(record,indent=2)+'\n')
env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
t=time.monotonic()
with (out/'ACTUAL_REVIEW_ATTEMPT2.log').open('x') as log:
 proc=subprocess.run(argv,env=env,cwd=str(out),stdout=log,stderr=subprocess.STDOUT)
r=resource.getrusage(resource.RUSAGE_CHILDREN)
record.update(ended_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-t,
 returncode=proc.returncode,maxrss=r.ru_maxrss,maxrss_units='bytes' if platform.system()=='Darwin' else 'KiB',
 user_seconds=r.ru_utime,system_seconds=r.ru_stime,heavy_available_after=available(),
 prepared_checker_sha256=sha(out/'review_actual.py'),prepared_math_sha256=sha(out/'review_math.py'))
if (out/'ACTUAL_REVIEW_ATTEMPT2.json').exists():record['result_sha256']=sha(out/'ACTUAL_REVIEW_ATTEMPT2.json')
(out/'ACTUAL_REVIEW_PROCESS_RESOURCES.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
raise SystemExit(proc.returncode)
