"""Tiny negative raw-label/index/coordinate controls, without predictions."""
from pathlib import Path
import copy,importlib.util,json
import numpy as np
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('source_join',P/'check_source_labels.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
times=[A.timestamp(f'2024-01-0{i}T00:00:00+00:00') for i in [1,2,3]];states=np.array([[[1,0],[0,0]],[[1,1],[0,0]],[[1,1],[1,0]]],bool);r=dict(case=dict(cutoff=times[0].isoformat(),endpoint=times[1].isoformat(),hours=24.),rectangle=[2,2],initial_sha256=A.array_sha(states[0]),endpoint_sha256=A.array_sha(states[1]),reference_mask_sha256=A.array_sha(~states[0]),reference_cells=int((~states[0]).sum()));row=np.array([0,1]);col=np.array([1,1]);y=np.array([1,0],np.int8);checks=[]
def note(n,ok,d=None):checks.append(dict(name=n,passed=bool(ok),detail=d))
note('exact_source_join_positive',A.source_join(r,row,col,y,times,states)==(0,1))
for name in ['wrong_endpoint','wrong_timestamp_indices','wrong_coordinate_initial_burn','shifted_coordinate','flipped_label','cropped_rectangle','wrong_initial_hash','wrong_endpoint_hash','wrong_reference_hash','endpoint_not_in_source','out_of_grid_coordinate','duplicate_source_timestamp']:
 rec=copy.deepcopy(r);rr=row.copy();cc=col.copy();label=y.copy();tt=times.copy()
 if name=='wrong_endpoint':rec['case']['endpoint']=times[2].isoformat();rec['case']['hours']=48.
 if name=='wrong_timestamp_indices':tt=[times[1],times[0],times[2]]
 if name=='wrong_coordinate_initial_burn':rr[0]=0;cc[0]=0
 if name=='shifted_coordinate':rr[0]=1
 if name=='flipped_label':label[0]=0
 if name=='cropped_rectangle':rec['rectangle']=[2,1]
 if name=='wrong_initial_hash':rec['initial_sha256']='0'*64
 if name=='wrong_endpoint_hash':rec['endpoint_sha256']='0'*64
 if name=='wrong_reference_hash':rec['reference_mask_sha256']='0'*64
 if name=='endpoint_not_in_source':rec['case']['endpoint']='2024-01-01T12:00:00+00:00';rec['case']['hours']=12.
 if name=='out_of_grid_coordinate':rr[0]=2
 if name=='duplicate_source_timestamp':tt=[times[0],times[1],times[1]]
 try:A.source_join(rec,rr,cc,label,tt,states);note(name,False,'INCORRECT_ACCEPTANCE')
 except A.SourceLabelError as e:note(name,True,str(e))
try:A.timestamp('2024-01-01T00:00:00.000000001+00:00');note('ambiguous_submicrosecond_mapping_refuses',False)
except A.UnresolvedMapping as e:note('ambiguous_submicrosecond_mapping_refuses',True,str(e))
result=dict(scope='Only tiny fabricated original-label arrays, clocks and coordinates; no probability arrays or forecast quality calculations.',checks=checks,passed=sum(x['passed'] for x in checks),total=len(checks),failures=[x for x in checks if not x['passed']]);(P/'SYNTHETIC_SOURCE_JOIN_CONTROLS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(result['failures']))
