"""Exact immutable source closure inventory, no input arrays or checkpoints."""
from pathlib import Path
import ast,difflib,hashlib,importlib.util,json,sys
v=Path(__file__).parent;w=v.parent;r=w.parent/'track-1b'
spec=importlib.util.spec_from_file_location('closure_recipe_metadata',w/'original/audit_fit_coverage.py')
F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
receipt=json.loads((w/'final_fit_coverage_audit_original.json').read_text());run=Path(receipt['command'][receipt['command'].index('--run-root')+1])
blobs={};profiles={};phase_rows=[]
def blob(relative,digest):
 key=(relative,digest)
 if key not in blobs:blobs[key]=F._source_blob(r,relative,digest)
 return blobs[key]
def declarations(source):
 tree=ast.parse(source);out={}
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)):
   out[n.name]=n
   if isinstance(n,ast.ClassDef):
    for method in n.body:
     if isinstance(method,ast.FunctionDef):out[n.name+'.'+method.name]=method
  else:out['GLOBAL:'+str(len(out))]=n
 return out
source_delta={};diffs=[]
for phase in F.current_phase_identity()['phases']:
 _,_,rp,receipt,_=F.phase_result(r,run,phase['variant'],phase['stage'],phase.get('fold'))
 source=receipt['source_sha256'];digest=F.object_sha(source)
 row=profiles.setdefault(digest,dict(source_sha256=source,phases=[],changed_files={}))
 row['phases'].append(phase['phase_id'])
 phase_rows.append(dict(phase=phase['phase_id'],closure_sha256=digest,source_files=len(source),pipeline_sha256=source['research/forecast-v2/scripts/pipeline.py']))
 for relative,pinned in source.items():
  assert Path(relative).suffix in ('.py','.json')
  original=blob(relative,pinned);assert hashlib.sha256(original.encode()).hexdigest()==pinned
  current=(r/relative).read_text()
  current_sha=hashlib.sha256(current.encode()).hexdigest()
  if current_sha==pinned:continue
  key=relative+'@'+pinned
  if key not in source_delta:
   detail=dict(path=relative,immutable_sha256=pinned,current_sha256=current_sha)
   if relative.endswith('.py'):
    a,b=declarations(original),declarations(current)
    detail['changed_declarations']=[name for name in sorted(set(a)|set(b)) if name not in a or name not in b or ast.dump(a[name],include_attributes=False)!=ast.dump(b[name],include_attributes=False)]
   else:detail['json_value_equal']=json.loads(original)==json.loads(current)
   source_delta[key]=detail
   diffs.append('FILE '+relative+' ORIGINAL '+pinned+'\n'+''.join(difflib.unified_diff(original.splitlines(keepends=True),current.splitlines(keepends=True),fromfile='immutable',tofile='current'))+'\n')
  row['changed_files'][relative]=source_delta[key]
(v/'WHOLE_CLOSURE_INVENTORY.json').write_text(json.dumps(dict(phases=phase_rows,profiles=profiles,deltas=source_delta),indent=2)+'\n')
(v/'WHOLE_SOURCE_DELTAS.diff').write_text('\n'.join(diffs))
summary=dict(phases=len(phase_rows),profiles=len(profiles),verified_source_bytes=len(blobs),profile_file_counts={k:len(p['source_sha256']) for k,p in profiles.items()},changed_files=sorted(set(d['path'] for d in source_delta.values())))
(v/'CLOSURE_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
