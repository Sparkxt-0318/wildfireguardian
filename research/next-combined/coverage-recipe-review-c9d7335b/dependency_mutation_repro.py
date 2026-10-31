"""Read-only conditional input-recipe recognition dependency stress probes."""
import ast,hashlib,importlib.util,json,sys
from pathlib import Path
here=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('independent_recipe_dependencies',here/'candidate_F.py');F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
current=(here/'candidate_pipeline.py').read_text();rows=[]
for name,mutation in [('consumed_cache_loader',lambda t:next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='load_or_build').body.insert(0,ast.parse('return ["WRONG_BUT_SAME_COUNT"] * 2').body[0])),('crop_global',lambda t:next(n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id=='MARGIN' for v in n.targets)).__setattr__('value',ast.Constant(value=999)))]:
 tree=ast.parse(current);mutation(tree);mutated=ast.unparse(ast.fix_missing_locations(tree))
 try:F._input_recipe_contract(mutated,current,'base',F.FIXED_VARIANT_POLICY);admitted=True;error=None
 except ValueError as e:admitted=False;error=str(e)
 rows.append(dict(mutation=name,admitted=admitted,error=error,source_sha256=hashlib.sha256(mutated.encode()).hexdigest()))
value=dict(candidate_sha256=hashlib.sha256((here/'candidate_F.py').read_bytes()).hexdigest(),scope='Source recognizer only; no live fit-coverage artifact/data/model/scoring access. Actual historical immutable bytes were separately compared and do not contain these mutations.',observations=rows)
(here/'dependency_mutation_repro.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
