"""Immutable-source and synthetic-only compatibility stress checks, no actual arrays."""
import argparse,ast,copy,gzip,hashlib,importlib.util,json,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();here=Path(__file__).resolve().parent;base=here.parent/'coverage-actual-recipe-repair'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
initial=sha(args.candidate);spec=importlib.util.spec_from_file_location('independent_source_recipe_candidate',args.candidate.resolve());F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
archive=json.loads((base/'ARCHIVED_SOURCES.json').read_text());sources={}
for digest,item in archive.items():
 raw=gzip.decompress((base/item['path']).read_bytes());assert hashlib.sha256(raw).hexdigest()==digest;assert sha(base/item['path'])==item['compressed_sha256'];sources[digest]=raw.decode()
current=(here/'candidate_pipeline.py').read_text();rows=[]
def probe(name,fn,refuse=False):
 try:v=fn();okay=not refuse and v is not False;result=dict(state='RETURNED',value=v)
 except (ValueError,TypeError,KeyError) as e:okay=refuse;result=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 rows.append(dict(id=name,pass_check=bool(okay),observed=result))
def recipe(blob,variant):return F._input_recipe_contract(blob,current,variant,F.FIXED_VARIANT_POLICY)
for digest,item in archive.items():
 if item['relative']!='research/forecast-v2/scripts/pipeline.py':continue
 blob=sources[digest]
 for variant in ['base','mixed_base']:
  should_refuse=digest.startswith('fe230450') and variant=='mixed_base'
  probe('immutable_'+digest[:8]+'_'+variant,lambda blob=blob,variant=variant:bool(recipe(blob,variant)),should_refuse)
def mutated(change):
 tree=ast.parse(current);change(tree);return ast.unparse(ast.fix_missing_locations(tree))
def definition(tree,name):return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
def pure_else(tree):
 n=next(n for n in definition(tree,'fit_samples').body if isinstance(n,ast.If) and ast.unparse(n.test)=='mixed');n.orelse=ast.parse('samples = samples[:1]').body
mutations={
 'consumed_else':pure_else,
 'consumed_prefix':lambda t:definition(t,'fit_samples').body.insert(-1,ast.parse('samples = samples[:1]').body[0]),
 'first_prefix_budget':lambda t:definition(t,'fit_samples').body.insert(0,ast.parse('args.max_fit_intervals_per_fire = 1').body[0]),
 'cache_transform':lambda t:definition(t,'load_or_build').body.insert(0,ast.parse('return ["WRONG_BUT_SAME_COUNT"] * 2').body[0]),
 'crop_global':lambda t:next(n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=='MARGIN' for v in n.targets)).__setattr__('value',ast.Constant(value=999)),
 'source_kind':lambda t:next(n for n in ast.walk(definition(t,'perimeter_samples')) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='PerimeterSample').keywords.append(ast.keyword(arg='kind',value=ast.Constant(value='kriged'))),
 'availability_filter':lambda t:definition(t,'available').body.insert(0,ast.parse('return events[:1]').body[0]),
 'model_construction':lambda t:definition(t,'build_model').body.insert(0,ast.parse('return None').body[0]),
 'header_default':lambda t:definition(t,'kriged_samples').args.kw_defaults.__setitem__(0,ast.Constant(value=24.)),
 'header_decorator':lambda t:definition(t,'kriged_samples').decorator_list.append(ast.Name(id='SIDE_EFFECT_DECORATOR',ctx=ast.Load())),
 'copied_crop_helper':lambda t:definition(t,'cropped').body.insert(0,ast.parse('return sample').body[0]),
 'definition_time_global_effect':lambda t:t.body.append(ast.parse('MARGIN = 999').body[0]),
}
for name,mutation in mutations.items():
 blob=mutated(mutation);probe('negative_'+name,lambda blob=blob:bool(recipe(blob,'base')),True)
# Complete historical schedule checks use source hashes/metadata only, never fit results.
with tempfile.TemporaryDirectory(prefix='source-contract-',dir=here) as temp:
 root=Path(temp).resolve();(root/'research/forecast-v2/scripts').mkdir(parents=True);(root/'forecast/wildfire').mkdir(parents=True)
 (root/'research/forecast-v2/scripts/pipeline.py').write_text(current)
 current_survival=(base/'repo/forecast/wildfire/survival.py').read_text();(root/'forecast/wildfire/survival.py').write_text(current_survival)
 original_loader=F._source_blob
 def source_only_loader(root,relative,expected):
  if expected in sources:
   assert archive[expected]['relative']==relative;return sources[expected]
  local=root/relative
  if local.is_file() and sha(local)==expected:return local.read_text()
  raise ValueError('No authenticated source-only archive for '+relative)
 F._source_blob=source_only_loader
 diagnosis=json.loads((base/'DIAGNOSIS.json').read_text())
 for item in diagnosis['phases']:
  source={'research/forecast-v2/scripts/pipeline.py':item['pipeline_sha256'],'forecast/wildfire/survival.py':item['survival_sha256']}
  probe('actual_metadata_source_contract_'+item['phase'],lambda item=item,source=source:bool(F._schedule_contract(root,source,stage=item['stage'],variant=item['variant'])))
 F._source_blob=original_loader
need_same=sha(args.candidate)==initial;probe('candidate_stayed_byte_fixed',lambda:need_same)
result=dict(candidate_sha256=initial,script_sha256=sha(__file__),checks=len(rows),passed=sum(r['pass_check'] for r in rows),observations=rows,actual_data_caches_models_or_heldout_accessed=False,actual_fit_coverage_audit_run=False,status='PASS_SOURCE_ONLY_SCOPED_CONTROLS' if all(r['pass_check'] for r in rows) else 'HOLD_RECOGNIZER')
args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([r for r in rows if not r['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
