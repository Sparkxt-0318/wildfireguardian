from pathlib import Path
import ast,gzip,hashlib,importlib.util,json,shutil,sys
v=Path(__file__).parent;r=v.parent.parent/'track-1b';s=v/'repo'
x=json.loads((v/'WHOLE_CLOSURE_INVENTORY.json').read_text())
baseline=next(p['source_sha256'] for p in x['profiles'].values() if p['source_sha256']['research/forecast-v2/scripts/pipeline.py'].startswith('88d376'))
spec=importlib.util.spec_from_file_location('v2_source_archive',v.parent/'original/audit_fit_coverage.py');F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
archive={}
for row in x['profiles'].values():
 for relative,digest in row['source_sha256'].items():
  if digest in archive:continue
  blob=F._source_blob(r,relative,digest).encode();assert hashlib.sha256(blob).hexdigest()==digest
  p=s/'research/forecast-v2/source_snapshots'/digest/(Path(relative).name+'.gz');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(blob,mtime=0))
  archive[digest]=dict(path=str(p.relative_to(s)),source_path=relative,compressed_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
for relative,digest in baseline.items():
 if relative.endswith('/audit_fit_coverage.py'):continue
 assert F.sha(r/relative)==digest,relative
 p=s/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(r/relative,p)
(v/'ARCHIVED_SOURCE_V2.json').write_text(json.dumps(archive,indent=2)+'\n')
p=s/'research/forecast-v2/scripts/audit_fit_coverage.py';text=p.read_text();tree=ast.parse(text)
node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_RECIPE_PIPELINE_VERSIONS' for t in n.targets))
versions=ast.literal_eval(node.value);versions['88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67']=['base','d4','d4_wind','ellipse','burnout','burnout_spotting','mixed_base']
import pprint
lines=text.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=['_RECIPE_PIPELINE_VERSIONS = '+pprint.pformat(versions,width=110,sort_dicts=True)+'\n'];p.write_text(''.join(lines))
print('preserved source bytes',len(archive))
