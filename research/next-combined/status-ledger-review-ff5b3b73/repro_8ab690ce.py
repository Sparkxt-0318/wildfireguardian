"""Evaluate the original readiness expression without running the ledger."""
import ast,hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'audit-1b/research/forecast-v2/scripts/status.py'
raw=p.read_bytes();tree=ast.parse(raw)
main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
assignment=next(n for n in main.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='registry_current' for t in n.targets))
registry={'protocol_status':'READY_FOR_OWNER_REGISTRATION'}
expr=ast.Expression(assignment.value);ast.fix_missing_locations(expr)
result=eval(compile(expr,str(p),'eval'),{'registry':registry,'ROOT':Path('/nonexistent'),'digest':lambda p:None})
record={'source_head':'8ab690ce','source_sha256':hashlib.sha256(raw).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'expression':ast.unparse(assignment.value),'input':registry,'registry_current':result,'expected':False,'status':'CONFIRMED_REPORT_ONLY_VACUOUS_TRUTH','actual_data_registry_or_models_accessed':False,'actual_execution_authority_bypassed':False}
Path(__file__).with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
assert result is True
print(record['status'])
