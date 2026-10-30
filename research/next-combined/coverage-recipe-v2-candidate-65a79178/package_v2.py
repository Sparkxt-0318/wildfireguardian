from pathlib import Path
import difflib,hashlib,json,subprocess
v=Path(__file__).parent;w=v.parent;s=v/'repo';live=w.parent/'track-1b'
paths={'research/forecast-v2/scripts/audit_fit_coverage.py':w/'original/audit_fit_coverage.py',
       'forecast/tests/test_source_recipe_compatibility.py':None,
       'forecast/tests/test_blind_forecast_protocol.py':w/'repo/forecast/tests/test_blind_forecast_protocol.py'}
records={};diffs=[]
for relative,before in paths.items():
 p=s/relative;data=p.read_bytes();compile(data,str(p),'exec')
 assert '\u2014' not in data.decode();assert all(line.rstrip()==line for line in data.decode().splitlines())
 original=before.read_bytes() if before else b''
 records[relative]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),before_sha256=hashlib.sha256(original).hexdigest() if before else None)
 diffs.extend(difflib.unified_diff(original.decode().splitlines(keepends=True),data.decode().splitlines(keepends=True),
 fromfile='a/'+relative if before else '/dev/null',tofile='b/'+relative))
patch=v/'SOURCE_RECIPE_V2.patch';patch.write_text(''.join(diffs))
preserved=json.loads((v/'PRESERVED_C9_HASHES.json').read_text())
for relative,expected in preserved.items():assert hashlib.sha256((w/relative).read_bytes()).hexdigest()==expected
livehash={}
for relative,baseline in [('research/forecast-v2/scripts/audit_fit_coverage.py','audit_fit_coverage.py'),('research/forecast-v2/scripts/pipeline.py','pipeline.py')]:
 expected=hashlib.sha256((w/'original'/baseline).read_bytes()).hexdigest();actual=hashlib.sha256((live/relative).read_bytes()).hexdigest();assert expected==actual;livehash[relative]=actual
for relative,before in paths.items():
 if before:
  p=v/'patch_baseline'/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(before.read_bytes())
r=subprocess.run(['patch','--dry-run','-p1','-i',str(patch)],cwd=v/'patch_baseline',text=True,capture_output=True);(v/'PATCH_DRY_RUN.txt').write_text(r.stdout+r.stderr);assert r.returncode==0
manifest=dict(scope='SCRATCH_V2_ONLY_PENDING_INDEPENDENT_REVIEW',files=records,patch=dict(path=str(patch),sha256=hashlib.sha256(patch.read_bytes()).hexdigest()),
 preserved_c9=preserved,live_unchanged=livehash,
 tests=dict(bounded_passed=133,deselected=131,seconds=94.97,output='TESTS_V2_BOUNDED_FINAL.txt',source_only_adapted_matrix_passed=54,actual_source_profiles_passed=28),
 source_inventory=dict(profiles=6,files_per_profile=[58,59,60,61],verified_original_source_identities=81,changed_paths=9),
 conditions=['Only exact whole-P byte pairs and complete source/profile/phase bindings','Actual bytes recomputed; no caller assertions or new version CLI flags',
 'Current declared dependencies and auditor numerical/member surfaces remain bound','Exact mixed branch without nonempty else; def-time headers/defaults/decorators/returns retained',
 'Known old UTC source never admitted for mixed or wrong phase','Independent source/cache complete membership/values/schema/dtype/names/order mandatory before recipe compatibility'],
 evidence_sha256={name:hashlib.sha256((v/name).read_bytes()).hexdigest() for name in ['V2_DIAGNOSIS.md','WHOLE_CLOSURE_INVENTORY.json','WHOLE_SOURCE_DELTAS.diff','ACTUAL_SOURCE_VERSION_CHECK.json','MATRIX_V2_FINAL.json','TESTS_V2_BOUNDED_FINAL.txt','ARCHIVED_SOURCE_V2.json']},
 test_boundary='Only synthetic fixtures install explicit fixture-local version catalogs, frozen before mutation; fresh registry auditor loaders retain the real verifier. Production has no such fallback.',
 integration='No live application before all12 a06 cases AND aggregate/receipt closure; independent review, actual preflight/main gate and broad regression remain separate',
 limits=['No live repo/data/Git mutations','No raw actual arrays, caches, checkpoints, heldout quality or numerical jobs','No universal equivalence or historical runtime replay claim','Original c9 gaps and 53-control results preserved; adapted54 is not independent clearance','Actual coverage remains HOLD until real admission completes'])
p=v/'SOURCE_RECIPE_V2.json';p.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(patch=manifest['patch'],manifest=str(p),manifest_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),files=records,live_unchanged=livehash),indent=2))
