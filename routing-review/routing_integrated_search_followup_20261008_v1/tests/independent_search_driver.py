"""Negative schema/watchdog controls for the driver, without fresh inputs."""
from pathlib import Path
import importlib.util,sys,tempfile,json,types,subprocess
from unittest.mock import patch
D=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('search_panel_reviewed',D/'tools/search_panel.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
rows=[]
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);case={'id':'known-control','kind':'reference','case_path':'CASE.json','source_directory':None};(root/'DEV.json').write_text(json.dumps([case]));clock=[0.]
 def tick():clock[0]+=1;return clock[0]
 def fake_run(args,**kwargs):
  mode=args[args.index('--mode')+1];path=Path(args[args.index('--worker-output')+1])
  if mode=='baseline':raise subprocess.TimeoutExpired(args,180)
  if mode=='cache':path.write_text('{malformed');return types.SimpleNamespace(returncode=0)
  phases=['cold']if mode=='heuristic'else['cold','warm'];result={'primary_search_status':'TIMEOUT','whole_road_check':{'status':'NOT_RUN'}};path.write_text(json.dumps({'case':case,'mode':mode,'records':{p:{'result':result}for p in phases}}));return types.SimpleNamespace(returncode=0)
 seq=[0]
 def ru(_):seq[0]+=1;return types.SimpleNamespace(ru_utime=seq[0]*2.,ru_stime=seq[0]*3.)
 with patch.object(driver,'S',root),patch.object(driver,'subprocess',types.SimpleNamespace(run=fake_run,TimeoutExpired=subprocess.TimeoutExpired,STDOUT=subprocess.STDOUT)),patch.object(driver,'time',types.SimpleNamespace(perf_counter=tick)),patch.object(driver,'resource',types.SimpleNamespace(getrusage=ru,RUSAGE_CHILDREN=1)):
  driver.run('DEV.json','known-output',False)
  for roster,confirmation in [('CONFIRMATION_CASES.json',False),('other.json',True)]:
   try:driver.run(roster,'must-not-open',confirmation);raise AssertionError('opening guard missing')
   except ValueError:pass
 out=root/'known-output';r=json.loads((out/'ROWS.json').read_text());c=json.loads((out/'COMPLETION.json').read_text());assert len(r)==4 and c['worker_slots']==4 and c['valid_complete_workers']==1 and c['worker_failures']==3,c
 assert r[0]['launcher']['watchdog'] and not r[0]['records'] and r[1]['worker_failure'] and not r[1]['records'];assert len(r[2]['records'])==1 and len(r[3]['records'])==2
 assert c['total_child_user_CPU_s']==8 and c['total_child_system_CPU_s']==12
 rows=[{'id':'watchdog_retained','status':'PASS'},{'id':'rc0_malformed_retained','status':'PASS'},{'id':'missing_warm_unresolved','status':'PASS'},{'id':'valid_complete_count','status':'PASS'},{'id':'all_failed_cpu_work','status':'PASS'},{'id':'development_confirmation_guard','status':'PASS'},{'id':'exact_roster_guard','status':'PASS'}]
 report={'status':'PASS','checks':len(rows),'controls':rows,'negative_completion':c,'scope':'Fake process/timing/schema controls only; no numerical correctness or fresh outcome evaluation.'};(D/'review/DRIVER_DEVELOPMENT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
