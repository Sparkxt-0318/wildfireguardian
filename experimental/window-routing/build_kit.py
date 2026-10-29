"""Assemble an opt-in kit for wfg_latest; never modify the frozen release kit."""
from pathlib import Path
import argparse,ast,hashlib,json,shutil
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def source_identity(root):
 p=root/'prepared_reuse.py';tree=ast.parse(p.read_text())
 schema=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='SCHEMA'for t in n.targets))
 sources={p.relative_to(root).as_posix():sha(p)for p in sorted(root.rglob('*.py'))}
 sources['@prepared_reuse.py']=sha(p)
 return hashlib.sha256(json.dumps(dict(schema=schema,sources=sources),sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode('ascii')).hexdigest()
def build(out,base=None):
 out=Path(out).resolve();base=Path(base or HERE.parents[1]/'integration/kit').resolve()
 if out.exists():raise FileExistsError('Use a fresh output directory: '+str(out))
 sealed=json.loads((HERE/'SOURCE_SHA256.json').read_text())
 for p,h in sealed.items():
  if sha(HERE/p)!=h:raise ValueError('Verified source changed: '+p)
 parent=json.loads((base/'CANDIDATE_MANIFEST.json').read_text())
 for p,h in parent['files'].items():
  if sha(base/p)!=h:raise ValueError('Frozen kit changed: '+p)
 out.parent.mkdir(parents=True,exist_ok=True)
 shutil.copytree(base,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for p in sealed:
  rel=Path(p).relative_to('stack');target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/p,target)
 identity=source_identity(out/'routing_candidate/baseline/routing-package/routing')
 for p in (out/'queues').glob('*.json'):
  q=json.loads(p.read_text())
  for j in q.get('jobs',[]):
   if not j.get('source_root'):continue
   j['core_sha256']=sha(out/'routing_candidate/baseline/routing-package/routing/core.py')
   j['preparation_mode_sha256']=sha(out/'phaseB/preparation_mode.py');j['preparation_source_sha256']=identity
   for n in j.get('phaseB_sha256',{}):j['phaseB_sha256'][n]=sha(out/'phaseB'/n)
   for n in j.get('checker_sha256',{}):j['checker_sha256'][n]=sha(out/'routing_candidate/baseline'/n)
  p.write_text(json.dumps(q,indent=2,sort_keys=True)+'\n')
 (out/'README_KIT.md').write_text('# Verified request-window routing kit, 29 October 2026\n\nOpt-in cumulative implementation. The original release kit is preserved. Use RDA_CAND for the verified candidate. Its source is identical to experimental/window-routing/stack. The original paired reference used in the published rerun is the unchanged historical kit, not this overlay kit\'s shared-checker RDA_BASE arm. See research/routing/request-window-20261029 for the exact comparison.\n')
 files={str(p.relative_to(out)):sha(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='CANDIDATE_MANIFEST.json'}
 manifest=dict(schema='wfg.latest-kit.manifest/1',candidate_id='WFG-request-window-routing-20261029',parent_candidate_id=parent['candidate_id'],parent_manifest_sha256=sha(base/'CANDIDATE_MANIFEST.json'),files=files)
 (out/'CANDIDATE_MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--base-kit',type=Path);a=p.parse_args();m=build(a.out,a.base_kit);print(json.dumps({'candidate_id':m['candidate_id'],'files':len(m['files'])}))
