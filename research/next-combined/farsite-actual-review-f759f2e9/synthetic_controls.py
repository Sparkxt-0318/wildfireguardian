"""Tiny independent saved-entry join and metric controls, no actual input access."""
from pathlib import Path
import copy,importlib.util,json,math
import numpy as np
import pandas as pd
OWN=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('independent_farsite_reconciliation',OWN/'reconcile_farsite.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
checks=[]
def check(name,fn,refuse=False):
 try:value=fn();ok=not refuse and value is not False;reason='returned'
 except (ValueError,KeyError,TypeError) as e:ok=refuse;reason=str(e)
 checks.append(dict(check=name,passed=ok,reason=reason))
start=pd.Timestamp('2024-01-01T00:00:00Z')
check('48h_exact_eligible',lambda:M.duration_ok(start,start+pd.Timedelta(hours=48)))
check('48h_plus_1ns_refused',lambda:not M.duration_ok(start,start+pd.Timedelta(hours=48,nanoseconds=1)))
check('zero_duration_refused',lambda:not M.duration_ok(start,start))
check('4489min_outside48h',lambda:not M.duration_ok(start,start+pd.Timedelta(minutes=4489)))
initial=np.array([[1,0,0],[0,0,0]],bool);endpoint=np.array([[1,1,0],[0,1,0]],bool)
rr=np.array([0,0,1,1,1]);cc=np.array([1,2,0,1,2]);y=endpoint[rr,cc]
current=dict(row=rr,col=cc,y=y,**{'p_'+n:np.full(5,.25) for n in M.EXPECTED})
aggregate={k:v.copy() for k,v in current.items()};aggregate.update(t1=np.array([start.isoformat()]),hours=np.array([12.]),interval=np.zeros(5,int))
mask=np.zeros((2,3),bool);mask[rr,cc]=True
record=dict(case=dict(event='SYNTHETIC'),initial_sha256=M.ash(initial),endpoint_sha256=M.ash(endpoint),rectangle=[2,3],scored_mask_sha256=M.ash(mask),scored_cells=5,positives=int(y.sum()))
fv=np.ones((2,3),bool);fv[0,2]=False;reference=np.ones((2,3),bool);reference[1,2]=False;fp=np.zeros((2,3));fp[0,1]=1
args=(current,aggregate,record,initial,endpoint,fp,fv,reference,start,start+pd.Timedelta(hours=12))
entry,digest=M.row_join(*args)
check('exact_three_cell_intersection',lambda:len(entry['y'])==3 and entry['y'].tolist()==[True,False,True])
check('native_binary_comparator_exact_join',lambda:entry['predictions']['farsite_scenario'].tolist()==[1.,0.,0.])
check('all16_current_plus_native_columns',lambda:set(entry['predictions'])==M.EXPECTED|{'farsite_scenario'})
def changed_current(fn):a=copy.deepcopy(list(args));fn(a[0]);return M.row_join(*a)
check('wrong_endpoint_label_refused',lambda:changed_current(lambda d:d['y'].__setitem__(0,False)),True)
check('duplicate_coordinates_refused',lambda:changed_current(lambda d:d['col'].__setitem__(1,1)),True)
check('unlisted_model_column_refused',lambda:changed_current(lambda d:d.update(p_unlisted=np.ones(5))),True)
check('missing_model_column_refused',lambda:changed_current(lambda d:d.pop('p_base_seed0')),True)
check('nonfinite_model_refused',lambda:changed_current(lambda d:d['p_base_seed0'].__setitem__(0,np.nan)),True)
def changed_aggregate():a=copy.deepcopy(list(args));a[1]['p_base_seed0'][0]=.9;return M.row_join(*a)
check('case_perfire_prediction_mismatch_refused',changed_aggregate,True)
def changed_time():a=copy.deepcopy(list(args));a[1]['hours'][0]=11;return M.row_join(*a)
check('endpoint_hour_join_mismatch_refused',changed_time,True)
y=np.array([0.,1.,0.,1.]);p=np.array([.2,.2,.8,.8]);m=M.metric(y,p)
for name,want in [('brier',.34),('average_precision',.5),('roc_auc',.5),('ece_10_bins',.3),('clipped_nll',-(math.log(.2)+math.log(.8))/2)]:check('manual_tied_'+name,lambda name=name,want=want:math.isclose(m[name],want,rel_tol=0,abs_tol=1e-14))
check('zero_positive_AP_AUC_null',lambda:M.metric(np.zeros(2),np.array([0.,.2]))['average_precision'] is None and M.metric(np.zeros(2),np.array([0.,.2]))['roc_auc'] is None)
check('all_positive_AUC_null',lambda:M.metric(np.ones(2),np.array([.2,.2]))['roc_auc'] is None)
fire=np.array(['A','B','B','B']);y=np.array([1.,0.,0.,1.]);p=np.array([.8,.1,.4,.7]);ref=np.zeros(4);paired=M.paired(fire,y,p,ref,draws=127)
manual=[]
for draw in np.random.default_rng(20261030).integers(0,2,size=(127,2)):
 ids=[i for event in draw for i,f in enumerate(fire) if f==['A','B'][event]];manual.append(sum((p[i]-y[i])**2-(ref[i]-y[i])**2 for i in ids)/len(ids))
check('manual_unequal_fire_whole_cluster_CI',lambda:np.allclose(paired['percentile_95_interval'],np.quantile(manual,[.025,.975]),rtol=0,atol=1e-14))
check('material_wrong_CI_refused',lambda:M.compare([-.9,-.8],paired['percentile_95_interval'],'CI'),True)
check('unavailable_null_stays_null',lambda:M.compare(None,None))
check('fabricated_unavailable_zero_refused',lambda:M.compare(0.,None),True)
result=dict(status='PASS_SYNTHETIC_CONTROLS' if all(c['passed'] for c in checks) else 'HOLD',checks=len(checks),passed=sum(c['passed'] for c in checks),observations=checks,actual_inputs_accessed=False)
(OWN/'SYNTHETIC_CONTROLS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','passed']}));print(json.dumps([c for c in checks if not c['passed']],indent=2));raise SystemExit(0 if result['checks']==result['passed'] else 1)
