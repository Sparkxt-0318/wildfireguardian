"""Reviewer-owned labelled centre-contract controls; no physical source invented.
All payloads known before confirmation. Every road check must be UNRESOLVED
SOURCE_CONTRACT_UNAVAILABLE, not zero-filled from these abstract cell channels.
"""
from pathlib import Path
import copy,json,sys
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'review'))
from search_reference import spans

def fixtures():
 grid={'x0':0,'y0':0,'resolution':10,'width':6,'height':4}
 ns=[{'id':n,'x':x,'y':y,'waitable':n=='A'}for n,x,y in [('A',5,5),('B',15,5),('C',5,15),('M',15,15),('D',25,15)]]
 graph={'revision':'reference/diamond','crs':'EPSG:5179','grid':grid,'nodes':ns,'edges':[],'forbidden_turns':[],'mid_edge_reversal':False}
 for eid,u,v in [('AB','A','B'),('BM','B','M'),('AC','A','C'),('CM','C','M'),('MD','M','D')]:
  e={'id':eid,'u':u,'v':v,'travel_ticks':1,'segments':[]};graph['edges'].append(e)
  for c,a,b in sorted((x for x in spans(graph,{'kind':'EDGE','edge':eid,'start':0,'end':1,'from_fraction':0,'to_fraction':1})if x[1]<x[2]),key=lambda x:x[1]):e['segments'].append({'cell':c,'start':float(a),'end':float(b)})
 h={'schema':'wfg.routing.edgegrid/1','version':1,'graph_revision':graph['revision'],'crs':graph['crs'],'grid':grid,'channels':['flame_contact','incident_heat_flux'],'units':{'time':'s','flux':'kW/m2','dose':'kJ/m2'},'unsupported_channels':[],'evidence_class':'LABELLED_FIXTURE','provenance':{'source':'independent abstract finite search fixture','interpretation':'Centre/cell channels are hand-specified; continuous physical source contract unavailable, never infer road feasibility.'},'time_origin':'2026-10-08T00:00:00Z','issued_at':'2026-10-08T00:00:00Z','available_at':'2026-10-08T00:00:00Z','valid_from':0,'valid_until':12,'dt':1,'members':[{'id':m,'breakpoints':[0,2,4,8,12],'flux':[[0]*24 for _ in range(4)],'flame':[[False]*24 for _ in range(4)],'support':[[True]*24 for _ in range(4)]}for m in ['m0','m1']]}
 q={'hazard_version':1,'as_of':'2026-10-08T00:00:00Z','position':{'node':'A'},'incoming_edge':None,'departure':0,'horizon':12,'destinations':[{'node':'D','dwell':2,'open_intervals':[[0,12]]}],'incurred':{'m0':0,'m1':0},'budgets':{'peak':10,'dose':{'m0':100,'m1':100}},'limits':{'wall_s':30,'max_labels':1000000,'max_expansions':1000000,'frontier_width':16384,'rss_limit_mb':3072},'solver':'baseline','objective':'earliest_arrival','exposure_scope':'including_dwell'}
 def one(name,status,arrival=None):
  x={'id':name,'kind':'reference','graph':copy.deepcopy(graph),'hazard':copy.deepcopy(h),'request':copy.deepcopy(q),'source_directory':None,'source_contract_unavailable':True,'expected':{'center_status':status,'arrival':arrival,'physical_road_status':'UNRESOLVED','authority':'Independent exact known finite reference, not unseen incident gain'}};x['graph']['revision']='reference/'+name;x['hazard']['graph_revision']=x['graph']['revision'];return x
 out=[]
 x=one('clear_multiedge','CONDITIONAL_OPTIMUM',3);out.append(x)
 x=one('mandatory_wait_opening','CONDITIONAL_OPTIMUM',6);x['request']['destinations'][0]['open_intervals']=[[6,12]];out.append(x)
 x=one('contact_requires_wait','CONDITIONAL_OPTIMUM',5)
 for m in x['hazard']['members']:
  for k in [0,1]:m['flame'][k][8]=True
 out.append(x)
 x=one('member_tradeoff_dwell','CONDITIONAL_OPTIMUM',3);x['request']['budgets']['dose']={'m0':10,'m1':10}
 for row in x['hazard']['members'][0]['flux']:row[1]=4
 for row in x['hazard']['members'][1]['flux']:row[6]=4;row[8]=3
 out.append(x)
 x=one('dose_refusal','PROVEN_INFEASIBLE');x['request']['incurred']={'m0':6,'m1':6};x['request']['budgets']['dose']={'m0':10,'m1':10}
 for m in x['hazard']['members']:m['flux']=[[1]*24 for _ in range(4)]
 out.append(x)
 x=one('peak_refusal','PROVEN_INFEASIBLE')
 for m in x['hazard']['members']:
  for row in m['flux']:row[8]=11
 out.append(x)
 x=one('destination_dwell_refusal','PROVEN_INFEASIBLE');x['request']['budgets']['dose']={'m0':1,'m1':1}
 for m in x['hazard']['members']:
  for row in m['flux']:row[8]=1
 out.append(x)
 x=one('missing_global_support','CHECKED_ROUTE',3)
 for m in x['hazard']['members']:
  for row in m['support']:row[23]=False
 out.append(x)
 x=one('missing_issue_support','UNSUPPORTED')
 for m in x['hazard']['members']:
  for row in m['support']:row[0]=False
 out.append(x)
 x=one('at_issue_flame','AT_ISSUE_FAILURE')
 for m in x['hazard']['members']:
  for row in m['flame']:row[0]=True
 out.append(x)
 x=one('incurred_over_budget','AT_ISSUE_FAILURE');x['request']['incurred']['m0']=101;out.append(x)
 x=one('stale_version','INVALID_INPUT');x['request']['hazard_version']=2;out.append(x)
 x=one('member_identity_mismatch','UNSUPPORTED');x['request']['incurred']={'m0':0,'wrong':0};out.append(x)
 x=one('incoming_turn_refusal','DISCONNECTED');x['request']['position']={'node':'M'};x['request']['incoming_edge']='BM';x['graph']['forbidden_turns']=[['BM','MD']];x['expected']['reference_status']='PROVEN_INFEASIBLE';out.append(x)
 x=one('turn_chooses_other_branch','CONDITIONAL_OPTIMUM',3);x['graph']['forbidden_turns']=[['AB','BM']];out.append(x)
 x=one('destination_wait_is_not_admission','PROVEN_INFEASIBLE');x['request']['destinations'][0]['open_intervals']=[[4,12]]
 for n in x['graph']['nodes']:n['waitable']=n['id']=='D'
 out.append(x)
 x=one('incurred_boundary_equality','CONDITIONAL_OPTIMUM',3);x['request']['incurred']={'m0':100,'m1':100};out.append(x)
 return out

def write_cases(destination):
 root=Path(destination);root.mkdir(parents=True,exist_ok=False);rows=[]
 for case in fixtures():
  p=root/case['id'];p.mkdir();(p/'CASE.json').write_text(json.dumps(case,indent=2,allow_nan=False)+'\n');rows.append({'id':case['id'],'kind':'reference','case_path':str(p/'CASE.json'),'source_directory':None,'source_contract_unavailable':True})
 return rows
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--out',required=True);args=a.parse_args();print(json.dumps(write_cases(args.out),indent=2))
