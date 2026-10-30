"""Synthetic prefix probes stop before any cohort; current evidence never opened."""
from pathlib import Path
import ast,copy,hashlib,importlib.util,json,math,tempfile
import numpy as np
OWN=Path(__file__).resolve().parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
C=module('precision_checker_candidate',OWN/'v2/check_results.py')
O=module('precision_checker_original',OWN/'original/check_results.py')
# Reuse only the original synthetic bundle constructor, not actual read/run logic.
tree=ast.parse((OWN/'v2/selftest.py').read_text());defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['write','make']]
namespace=dict(C=C,Path=Path,np=np,json=json,hashlib=hashlib);exec(compile(ast.Module(body=defs,type_ignores=[]),'original_synthetic_fixture_definitions','exec'),namespace)
OBS=[]
class ReachedCohort(RuntimeError):pass
def stop_before_cohort(*args,**kwargs):raise ReachedCohort('Synthetic prefix accepted; no cohort was read')
C.cohort=O.cohort=stop_before_cohort

def probe(name,fn,accept):
 try:fn();ok=False;reason='Unexpected return'
 except ReachedCohort as e:ok=accept;reason=str(e)
 except (C.AuditError,O.AuditError,TypeError,KeyError) as e:ok=not accept;reason=str(e)
 OBS.append(dict(check=name,passed=ok,reason=reason))

with tempfile.TemporaryDirectory(prefix='synthetic-target-',dir=OWN) as tmp:
 root,run,path=namespace['make'](Path(tmp)/'bundle','empty')
 pristine={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
 def restore():
  for p in root.rglob('*'):
   if p.is_file() and p not in pristine:p.unlink()
  for p,data in pristine.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 def change_report(fn):
  r=C.load(path);fn(r);path.write_text(json.dumps(r,allow_nan=True))
 def check(name,mutate,accept=False,checker=C):
  restore();mutate();probe(name,lambda:checker.audit(root,run,path,synthetic=True),accept);restore()
 check('unchanged_prefix_accepts',lambda:None,True)
 for v in C.VARIANTS:
  for direction in [-math.inf,math.inf]:
   check(v+'_one_ULP_'+('down' if direction<0 else 'up'),lambda v=v,direction=direction:change_report(lambda r:r['ablation'][v].update(mean_fire_brier=math.nextafter(r['ablation'][v]['mean_fire_brier'],direction))),True)
  check(v+'_material_development_drift_refuses',lambda v=v:change_report(lambda r:r['ablation'][v].update(mean_fire_brier=r['ablation'][v]['mean_fire_brier']+1e-5)))
  for field in ['difference_vs_base','interval_95','excludes_zero','fires_better_than_base']:
   check(v+'_nonnull_'+field+'_refuses',lambda v=v,field=field:change_report(lambda r:r['ablation'][v].update({field:0})))
 # The old failure reproduces on generic adjacent floats without any actual outcome.
 check('original_checker_rejects_one_ULP',lambda:change_report(lambda r:r['ablation']['d4_wind'].update(mean_fire_brier=math.nextafter(r['ablation']['d4_wind']['mean_fire_brier'],-math.inf))),False,O)
 for value,label in [(math.nan,'NaN'),(math.inf,'Inf'),(-math.inf,'negativeInf'),(True,'boolean'),('0.1','string'),(None,'null')]:
  check('invalid_numeric_'+label+'_refuses',lambda value=value:change_report(lambda r:r['ablation']['base'].update(mean_fire_brier=value)))
 check('missing_development_mean_refuses',lambda:change_report(lambda r:r['ablation']['base'].pop('mean_fire_brier')))
 check('changed_report_primary_selection_refuses',lambda:change_report(lambda r:r['primary_candidate'].update(variant='d4')))
 check('changed_report_selection_digest_refuses',lambda:change_report(lambda r:r.update(model_selection_sha256='0'*64)))
 def change_selection(fn):
  p=root/'research/forecast-v2/MODEL_SELECTION.json';s=C.load(p);fn(s);p.write_text(json.dumps(s))
 check('changed_frozen_selected_variant_refuses',lambda:change_selection(lambda s:s.update(selected_variant='d4')))
 check('frozen_selection_minimum_still_exact_refuses',lambda:change_selection(lambda s:s['development_brier'].update(d4=0.)))
 # Exact same pre-existing comparison policy, no reselected tolerance constants.
 compare_old=ast.get_source_segment((OWN/'original/check_results.py').read_text(),next(n for n in ast.parse((OWN/'original/check_results.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='compare'))
 compare_new=ast.get_source_segment((OWN/'v2/check_results.py').read_text(),next(n for n in ast.parse((OWN/'v2/check_results.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='compare'))
 OBS.append(dict(check='pre_existing_comparison_policy_byte_identical',passed=compare_old==compare_new))
result=dict(status='PASS_SYNTHETIC_PRECISION_CONTROLS' if all(o['passed'] for o in OBS) else 'HOLD',checks=len(OBS),passed=sum(o['passed'] for o in OBS),observations=OBS,checker_sha256=C.sha(OWN/'v2/check_results.py'),actual_current_outputs_accessed=False,corrected_checker_actual_run=False)
(OWN/'TARGETED_CONTROLS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']},indent=2));print(json.dumps([o for o in OBS if not o['passed']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
