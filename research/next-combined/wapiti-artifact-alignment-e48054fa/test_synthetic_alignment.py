"""Tiny schema/concatenation corruption controls; never forecast quality scores."""
from pathlib import Path
import copy,importlib.util,json
import numpy as np
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('alignment',P/'check_alignment.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
parts=[];records=[]
for i in range(2):
 data=dict(row=np.array([0,1],np.int64),col=np.array([i,i],np.int64),y=np.array([0,1],np.int8),**{name:np.array([.25,.75],np.float32) for name in A.P});mask=np.zeros((2,2),bool);mask[data['row'],data['col']]=True;rec=dict(rectangle=[2,2],scored_cells=2,positives=1,excluded_cells=1,reference_cells=3,scored_mask_sha256=A.array_sha(mask),case=dict(cutoff=f'2024-01-0{i+1}T00:00:00+00:00',hours=12.));parts.append(data);records.append(rec)
aggregate={name:np.concatenate([x[name] for x in parts]) for name in ['row','col','y',*A.P]};aggregate.update(interval=np.array([0,0,1,1],np.int64),t1=np.array([r['case']['cutoff'] for r in records]),hours=np.array([12.,12.]))
checks=[]
def note(name,passed,detail=None):checks.append(dict(name=name,passed=bool(passed),detail=detail))
try:
 for r,d in zip(records,parts):A.case_schema(r,d)
 A.aggregate_alignment(aggregate,parts,records);note('typed_two_case_positive',True)
except A.AlignmentError as e:note('typed_two_case_positive',False,str(e))
for name in ['changed_prediction_entry','changed_prediction_dtype','wrong_interval','wrong_t1','wrong_hours','missing_aggregate_model']:
 z=copy.deepcopy(aggregate)
 if name=='changed_prediction_entry':z[A.P[0]][0]=.5
 if name=='changed_prediction_dtype':z[A.P[0]]=z[A.P[0]].astype(np.float64)
 if name=='wrong_interval':z['interval'][0]=1
 if name=='wrong_t1':z['t1'][0]=z['t1'][1]
 if name=='wrong_hours':z['hours'][0]=24
 if name=='missing_aggregate_model':del z[A.P[0]]
 try:A.aggregate_alignment(z,parts,records);note(name,False,'INCORRECT_ACCEPTANCE')
 except A.AlignmentError as e:note(name,True,str(e))
for name in ['wrong_mask_identity','wrong_count_partition','missing_case_model','nonfinite_probability','duplicate_coordinate','wrong_model_shape']:
 r=copy.deepcopy(records[0]);d=copy.deepcopy(parts[0])
 if name=='wrong_mask_identity':r['scored_mask_sha256']='0'*64
 if name=='wrong_count_partition':r['excluded_cells']=2
 if name=='missing_case_model':del d[A.P[0]]
 if name=='nonfinite_probability':d[A.P[0]][0]=np.nan
 if name=='duplicate_coordinate':d['row'][1]=0
 if name=='wrong_model_shape':d[A.P[0]]=d[A.P[0]][:1]
 try:A.case_schema(r,d);note(name,False,'INCORRECT_ACCEPTANCE')
 except A.AlignmentError as e:note(name,True,str(e))
result=dict(scope='Tiny fabricated coordinate/label/probability arrays only; schema and exact equality controls. No model inference or forecast quality metric.',checks=checks,passed=sum(x['passed'] for x in checks),total=len(checks),failures=[x for x in checks if not x['passed']]);(P/'SYNTHETIC_ALIGNMENT_CONTROLS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(result['failures']))
