"""Independent driver cap/accounting controls on fake engine records, no fresh inputs."""
from pathlib import Path
import json,sys,hashlib,tempfile,time,importlib.util,copy
from unittest.mock import patch
import numpy as np
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'candidate'))
spec=importlib.util.spec_from_file_location('independent_driver_under_review',D/'tools/confirmation_panel.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
with tempfile.TemporaryDirectory(prefix='driver-review-',dir=D/'review') as tmp:
 p=Path(tmp);np.savez(p/'constructed_arrays.npz',ignition_time_s=np.full((2,1,1),np.inf),current_active=np.zeros((1,1),bool),support=np.ones((2,1,1),bool));(p/'REPORT.json').write_text('{}')
 case={'id':'HAND_DRIVER_ONLY','kind':'control','source_directory':str(p),'source_history_sha256':m.sha(p/'constructed_arrays.npz'),'report_sha256':m.sha(p/'REPORT.json'),'graph':{'revision':'HAND','nodes':[],'edges':[]},'request':{},'legs':[],'destination':'unused','radiation_settings_override':None}
 realread=m.read
 def read(path):return {'original_road_settings':{}} if path.name=='IMPLEMENTATION_FREEZE.json' else realread(path)
 for engine in ('baseline','practical','hybrid'):
  value=[0.];calls=[0];captured=[]
  class Fake:
   def __init__(self,*a,**kw):pass
   def check(self,*a,**kw):captured.append(kw);return {'status':'CERTIFIED_ADMISSIBLE','timing_s':{}}
  def rss():
   calls[0]+=1
   if calls[0]==(1 if engine=='baseline' else 4):value[0]=31.
   return 1.
  def baseline(*a,**kw):return {'primary_status':'CERTIFIED_ADMISSIBLE','raw':{'status':'CERTIFIED_ACCEPT'},'primary_cap_s':30,'elapsed_s':0,'process_lifetime_rss_mb':1},None,None
  with patch.object(m,'verify_seal',return_value={}),patch.object(m,'cases',return_value=[case]),patch.object(m,'read',side_effect=read),patch.object(m,'PracticalChecker',Fake),patch.object(m,'HybridChecker',Fake),patch.object(m,'baseline_check',side_effect=baseline),patch.object(m,'rss_mb',side_effect=rss),patch.object(m.time,'perf_counter',side_effect=lambda:value[0]):m.worker(case['id'],engine,p/(engine+'.json'))
  out=realread(p/(engine+'.json'));cold=out['records']['cold'];assert cold['primary_status']=='UNRESOLVED' and cold['late_or_rss_result_secondary'] and cold['elapsed_s']==31 and cold['raw']['status'] in ('CERTIFIED_ACCEPT','CERTIFIED_ADMISSIBLE');checks.append({'name':'final RSS/metadata clock charged '+engine,'pass':True,'cold':cold})
 for engine in ('practical','hybrid'):
  value=[0.];captured=[]
  class Constructor:
   def __init__(self,*a,**kw):value[0]=31.
   def check(self,*a,**kw):captured.append(kw);return {'status':'CERTIFIED_ADMISSIBLE','timing_s':{}}
  with patch.object(m,'verify_seal',return_value={}),patch.object(m,'cases',return_value=[case]),patch.object(m,'read',side_effect=read),patch.object(m,'PracticalChecker',Constructor),patch.object(m,'HybridChecker',Constructor),patch.object(m,'rss_mb',return_value=1),patch.object(m.time,'perf_counter',side_effect=lambda:value[0]):m.worker(case['id'],engine,p/('constructor-'+engine+'.json'))
  out=realread(p/('constructor-'+engine+'.json'));assert out['records']['cold']['primary_status']=='UNRESOLVED' and captured[0]['wall_s']==0 and captured[0]['deadline']==30;checks.append({'name':'cold constructor shares30s '+engine,'pass':True})
 summary=m.summarize([{'case':{'kind':'incident'},'baseline':{},'practical':{},'hybrid':{}}],[{'elapsed_s':80,'watchdog':True,'returncode':None,'complete_child_user_cpu_s':3,'complete_child_system_cpu_s':2}]);assert summary['complete_launcher_wall_s']==80 and summary['worker_failures']==1 and summary['complete_worker_user_cpu_s']==3 and summary['complete_worker_system_cpu_s']==2
 for engine in ('baseline','practical','hybrid'):
  for phase in ('cold','warm'):
   row=summary['incident'][engine+'_'+phase];assert row['outcomes']=={'UNRESOLVED':1} and row['missing_phase_count']==row['missing_cpu_count']==row['missing_rss_count']==1 and row['max_rss_mb'] is None
 checks.append({'name':'watchdogs charged missing measurement UNKNOWN','pass':True,'summary':summary})
r={'schema':'wfg.hybrid.independent.driver-development/1','scope':'Fake resource/metadata controls only, no hazard/candidate accuracy claim or fresh source opening.','passed':len(checks),'failed':0,'checks':checks,'driver_sha256':hashlib.sha256((D/'tools/confirmation_panel.py').read_bytes()).hexdigest()};(D/'review/DRIVER_DEVELOPMENT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':r['passed'],'failed':0}))
