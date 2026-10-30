from pathlib import Path
import importlib.util,json,sys
v=Path(__file__).parent;repo=v/'repo';inventory=json.loads((v/'WHOLE_CLOSURE_INVENTORY.json').read_text())
spec=importlib.util.spec_from_file_location('v2_closed_source_check',repo/'research/forecast-v2/scripts/audit_fit_coverage.py');F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)
rows=[]
for row in inventory['phases']:
 phase=next(p for p in F.current_phase_identity()['phases'] if p['phase_id']==row['phase'])
 source=inventory['profiles'][row['closure_sha256']]['source_sha256']
 try:proof=F._schedule_contract(repo,source,stage=phase['stage'],variant=phase['variant'],phase_id=phase['phase_id']);status='PASS';error=None
 except (ValueError,FileNotFoundError) as e:proof=None;status='REFUSED';error=str(e)
 rows.append(dict(phase=phase['phase_id'],status=status,error=error,proof=proof))
(v/'ACTUAL_SOURCE_VERSION_CHECK.json').write_text(json.dumps(dict(source_only=True,actual_input_cache_model_or_quality_access=False,actual_coverage_gate_pass=False,phases=rows),indent=2)+'\n')
print(json.dumps(dict(phases=len(rows),passed=sum(r['status']=='PASS' for r in rows),failures=[dict(phase=r['phase'],error=r['error']) for r in rows if r['status']!='PASS']),indent=2))
