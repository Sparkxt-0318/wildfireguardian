"""Independent closed-version source-only recipe recheck, never actual data/model access."""
import argparse,ast,copy,gzip,hashlib,importlib.util,json,shutil,sys,tempfile
from pathlib import Path
here=Path(__file__).resolve().parent;base=here.parents[1]/'coverage-actual-recipe-repair/v2';candidate=here/'guard_under_review.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
need_sha='65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536';assert sha(candidate)==need_sha
spec=importlib.util.spec_from_file_location('independent_closed_recipe_v2',candidate);F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
archive=json.loads((base/'ARCHIVED_SOURCE_V2.json').read_text());inventory=json.loads((base/'WHOLE_CLOSURE_INVENTORY.json').read_text());manifest=json.loads((base/'SOURCE_RECIPE_V2.json').read_text());raws={};observations=[]
def probe(name,fn,refuse=False):
 try:v=fn();passed=not refuse and v is not False;result=dict(state='RETURNED',value=v)
 except (ValueError,TypeError,KeyError,FileNotFoundError) as e:passed=refuse;result=dict(state='RAISED',type=type(e).__name__,reason=str(e))
 observations.append(dict(id=name,pass_check=bool(passed),observed=result))
for digest,item in archive.items():
 path=base/'repo'/item['path'];compressed=path.read_bytes();raw=gzip.decompress(compressed)
 assert hashlib.sha256(compressed).hexdigest()==item['compressed_sha256'] and hashlib.sha256(raw).hexdigest()==digest;raws[digest]=raw
probe('81_immutable_source_and_compressed_hashes',lambda:len(raws)==81)
probe('final_manifest_and_patch_pins',lambda:sha(base/'SOURCE_RECIPE_V2.json')=='9113c63b83d196a4875ea137ecbe89afff75ba3e44a8c6252af55d4b4f5db31a' and sha(base/'SOURCE_RECIPE_V2.patch')=='5c640e3e3710d6fac8324f46cc22950ebdf7f28a89afd31ba23f304d0dde977d' and all(sha(base/'repo'/name)==record['sha256'] for name,record in manifest['files'].items()))
probe('all_manifest_evidence_pins',lambda:all(sha(base/name)==digest for name,digest in manifest['evidence_sha256'].items()))
probe('six_profile_digests_and_exact_phase_inventory',lambda:set(inventory['profiles'])==set(F._RECIPE_SOURCE_VERSIONS) and len(inventory['phases'])==28 and all(F.object_sha(item['source_sha256'])==digest and item['phases']==F._RECIPE_SOURCE_VERSIONS[digest] for digest,item in inventory['profiles'].items()))
current=(base/'repo/research/forecast-v2/scripts/pipeline.py').read_text()
def recipe(blob,variant='base'):return F._input_recipe_contract(blob,current,variant,F.FIXED_VARIANT_POLICY)
for digest,variants in F._RECIPE_PIPELINE_VERSIONS.items():
 for variant in ['base','mixed_base']:
  probe('known_pipeline_'+digest[:8]+'_'+variant,lambda digest=digest,variant=variant:bool(recipe(raws[digest].decode(),variant)),variant not in variants)
# The exact original consumed-else counterexample now refuses internally and publicly.
def defn(tree,name):return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
def consumed_else(tree):next(n for n in defn(tree,'fit_samples').body if isinstance(n,ast.If) and ast.unparse(n.test)=='mixed').orelse=ast.parse('samples = samples[:1]').body
mutations={
 'consumed_else':consumed_else,
 'consumed_cache_transform':lambda t:defn(t,'load_or_build').body.insert(0,ast.parse('return ["WRONG_BUT_SAME_COUNT"] * 2').body[0]),
 'crop_global':lambda t:next(n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=='MARGIN' for v in n.targets)).__setattr__('value',ast.Constant(value=999)),
 'copied_crop_helper':lambda t:defn(t,'cropped').body.insert(0,ast.parse('return sample').body[0]),
 'definition_time_reassignment':lambda t:t.body.append(ast.parse('MARGIN = 999').body[0]),
 'consumed_prefix':lambda t:defn(t,'fit_samples').body.insert(-1,ast.parse('samples = samples[:1]').body[0]),
 'header_default':lambda t:defn(t,'kriged_samples').args.kw_defaults.__setitem__(0,ast.Constant(value=24.)),
 'header_decorator':lambda t:defn(t,'kriged_samples').decorator_list.append(ast.Name(id='SIDE_EFFECT_DECORATOR',ctx=ast.Load())),
 'source_kind':lambda t:next(n for n in ast.walk(defn(t,'perimeter_samples')) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='PerimeterSample').keywords.append(ast.keyword(arg='kind',value=ast.Constant(value='kriged'))),
 'availability_order':lambda t:defn(t,'available').body.insert(0,ast.parse('return events[::-1]').body[0]),
 'model_construction':lambda t:defn(t,'build_model').body.insert(0,ast.parse('return None').body[0]),
}
for name,mutate in mutations.items():
 tree=ast.parse(current);mutate(tree);blob=ast.unparse(ast.fix_missing_locations(tree));probe('refuse_unknown_pipeline_'+name,lambda blob=blob:bool(recipe(blob)),True)
node=copy.deepcopy(F._function(current,'fit_samples'));next(n for n in node.body if isinstance(n,ast.If) and ast.unparse(n.test)=='mixed').orelse=ast.parse('samples=samples[:1]').body
probe('internal_normalizer_keeps_consumed_else_refused',lambda:F._normalized_input_recipe(node,'fit_samples',pure=True),True)
with tempfile.TemporaryDirectory(prefix='source-only-shadow-',dir=here) as temp:
 root=Path(temp).resolve()
 for relative in F._RECIPE_CURRENT_BASELINE:
  path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((base/'repo'/relative).read_bytes())
 split=root/'research/forecast-v2/SPLIT.json';split.write_bytes((base/'repo/research/forecast-v2/SPLIT.json').read_bytes())
 for digest,item in archive.items():
  path=root/item['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((base/'repo'/item['path']).read_bytes())
 # Read only actual execution SOURCE metadata, never output/result artifacts.
 diagnosis=json.loads((base.parent/'DIAGNOSIS.json').read_text());source_rows={row['phase']:row for row in diagnosis['phases']}
 for item in inventory['phases']:
  phase=item['phase'];source=inventory['profiles'][item['closure_sha256']]['source_sha256'];metadata=source_rows[phase]
  actual_receipt=json.loads((here.parents[1]/'track-1b'/metadata['receipt_path']).read_text())
  probe('source_receipt_mapping_'+phase,lambda actual_receipt=actual_receipt,source=source:actual_receipt['source_sha256']==source)
  probe('actual_phase_source_contract_'+phase,lambda phase=phase,source=source,metadata=metadata:bool(F._schedule_contract(root,source,stage=metadata['stage'],variant=metadata['variant'],phase_id=phase)))
 representative=inventory['profiles']['7379571bc4168bf9c4b383084a8bfb1ffb5df8dd121b28873d4ee437980952d6']['source_sha256'];phase='base_fold2020_seed0'
 for mode in ['missing_file','extra_file','changed_model_hash','known_wrong_phase']:
  changed=dict(representative)
  if mode=='missing_file':changed.pop('forecast/wildfire/models.py')
  if mode=='extra_file':changed['forecast/wildfire/UNDECLARED.py']='0'*64
  if mode=='changed_model_hash':changed['forecast/wildfire/models.py']='0'*64
  probe('refuse_profile_'+mode,lambda changed=changed,mode=mode:F._verified_producer_version(root,changed,'mixed_base_fold2020_seed0_utc_fixed' if mode=='known_wrong_phase' else phase),True)
 probe('refuse_wrong_variant_phase_context',lambda:F._schedule_contract(root,representative,stage='fold',variant='mixed_base',phase_id=phase),True)
 probe('refuse_wrong_stage_phase_context',lambda:F._schedule_contract(root,representative,stage='final',variant='base',phase_id=phase),True)
 # Preserved historical bytes cannot conceal current unreviewed dependencies.
 for relative in ['forecast/wildfire/models.py','research/forecast-v2/scripts/pipeline.py','research/forecast-v2/scripts/audit_fit_coverage.py']:
  path=root/relative;original=path.read_bytes();path.write_bytes(original+b'\nUNREVIEWED_GLOBAL=1\n')
  probe('refuse_current_dependency_drift_'+Path(relative).name,lambda:F._verified_producer_version(root,representative,phase),True);path.write_bytes(original)
 # Source byte recomputation is independent of a matching caller-supplied digest.
 victim=representative['forecast/wildfire/models.py'];path=root/archive[victim]['path'];original=path.read_bytes();path.write_bytes(gzip.compress(raws[victim]+b'\n# corrupted archived bytes\n',mtime=0))
 probe('refuse_corrupted_preserved_source_bytes',lambda:F._verified_producer_version(root,representative,phase),True);path.write_bytes(original)
 # Current SPLIT is a first-party input inventory, authenticated without raw data access.
 original=split.read_bytes();split.write_bytes(original+b'\n');probe('refuse_changed_protocol_split_pin',lambda:F._verified_producer_version(root,representative,phase),True);split.write_bytes(original)
 original=F._source_blob
 def altered(root,relative,expected):
  source=original(root,relative,expected);return source+'\n# untrusted loader bytes\n' if relative=='forecast/wildfire/models.py' else source
 F._source_blob=altered;probe('refuse_loader_hash_assertion_without_matching_bytes',lambda:F._verified_producer_version(root,representative,phase),True);F._source_blob=original
 # Explicit trust boundary: the surface check protects unchanged audit dependencies,
 # while the new repair implementation itself is externally pinned/reviewed.
 original_source=raws[F._RECIPE_CURRENT_BASELINE['research/forecast-v2/scripts/audit_fit_coverage.py']].decode();current_F=candidate.read_text()
 probe('auditor_unchanged_member_numeric_surface',lambda:F._auditor_numeric_surface(original_source)==F._auditor_numeric_surface(current_F))
 altered_F=current_F.replace('if declared not in _RECIPE_SOURCE_VERSIONS or phase_id not in _RECIPE_SOURCE_VERSIONS[declared]:','if False:',1)
 probe('repair_surface_is_not_self_authentication',lambda:altered_F!=current_F and F._auditor_numeric_surface(altered_F)==F._auditor_numeric_surface(current_F))
probe('externally_reviewed_executable_stayed_byte_fixed',lambda:sha(candidate)==need_sha and sha(base/'repo/research/forecast-v2/scripts/audit_fit_coverage.py')==need_sha)
result=dict(status='PASS_SCOPED_CLOSED_VERSION_SOURCE_RECHECK' if all(r['pass_check'] for r in observations) else 'HOLD',checks=len(observations),passed=sum(r['pass_check'] for r in observations),candidate_sha256=need_sha,script_sha256=sha(__file__),source_receipt_metadata_read=28,source_archive_identities_verified=len(raws),profile_file_counts={k:len(v['source_sha256']) for k,v in inventory['profiles'].items()},observations=observations,actual_input_cache_model_or_heldout_quality_accessed=False,actual_fit_coverage_audit_run=False,limits=['Trusted reviewer-pinned executable context is required; numeric surface comparison is not authentication of the new auditor implementation.','Known source-only profile compatibility remains conditional on actual complete input/cache/value/schema membership authentication; no runtime IDs are inferred as logged.'])
(here/'RECHECK_V2.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([r for r in observations if not r['pass_check']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
