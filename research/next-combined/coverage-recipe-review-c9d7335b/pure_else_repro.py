"""Independent source-only consumed-else normalization counterexample."""
import ast,hashlib,importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
here=Path(__file__).resolve().parent;path=here/'candidate_F.py';spec=importlib.util.spec_from_file_location('independent_candidate_recipe',path);F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
current=(here/'candidate_pipeline.py').read_text();tree=ast.parse(current);fit=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fit_samples');branch=next(n for n in fit.body if isinstance(n,ast.If) and ast.unparse(n.test)=='mixed');branch.orelse=ast.parse('samples = samples[:1]').body
mutated=ast.unparse(ast.fix_missing_locations(tree))
try:proof=F._input_recipe_contract(mutated,current,'base',F.FIXED_VARIANT_POLICY);admitted=True;error=None
except ValueError as e:proof=None;admitted=False;error=str(e)
namespace=dict(Path=Path,Environment=object,PerimeterSample=object,SPLIT=dict(fit=dict(korean_kriged_only=[])),load_or_build=lambda work,name,builder:builder(),perimeter_samples=lambda *a,**k:['sample-1','sample-2'])
def tiny_execute(source):
 node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='fit_samples');scope=dict(namespace);exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-fit-recipe>','exec'),scope);return scope['fit_samples'](SimpleNamespace(max_fit_intervals_per_fire=0,work=Path('SYNTHETIC'),perimeters=Path('SYNTHETIC'),data_root=Path('SYNTHETIC')),['FAKE'],None,mixed=False)
value=dict(candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),mutated_source_sha256=hashlib.sha256(mutated.encode()).hexdigest(),admitted=admitted,error=error,expected=tiny_execute(current),actual=tiny_execute(mutated),actual_data_or_models_accessed=False,reason='An else branch executes under mixed=False but the recognizer removes the entire if mixed node including its else branch.')
(here/'pure_else_repro.json').write_text(json.dumps(value,indent=2)+'\n');(here/'mutated_pipeline_consumed_else.py').write_text(mutated);print(json.dumps(value))
