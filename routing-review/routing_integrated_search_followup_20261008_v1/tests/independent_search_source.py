"""Real unchanged v2 source binding and adverse provenance/ledger controls.
No search or physical source constructed; no fresh packet read.
"""
from pathlib import Path
import sys,json,copy,tempfile,shutil,time,hashlib
D=Path(__file__).resolve().parents[1];sys.path[:0]=[str(D/'candidate'),str(D/'candidate/routing-package')]
from search_followup import prepare_epoch,EpochMismatch,_packet_member_ids
p=D/'baseline/timeout_inputs/20220304T030000Z_baseline_difficult';g=json.loads((D/'sample/uljin_graph.json').read_text());h=json.loads((p/'HAZARD.json').read_text());md=json.loads((p/'NATIVE_METADATA.json').read_text());report=json.loads((p/'REPORT.json').read_text());started=time.perf_counter();rows=[]
e=prepare_epoch(g,h,p);assert e.hazard_snapshot()==h and e.graph_snapshot()==g;rows.append({'id':'real_original_v2_epoch','status':'PASS','actual_member_ids':[m['id']for m in h['members']]})
for kind in ['admitted_order','report_incurred_order','report_dose_ids','construction_identity']:
 m,r,z=copy.deepcopy(md),copy.deepcopy(report),copy.deepcopy(h)
 if kind=='admitted_order':z['members'].reverse()
 if kind=='report_incurred_order':r['rows'][0]['request']['incurred']=dict(reversed(list(r['rows'][0]['request']['incurred'].items())))
 if kind=='report_dose_ids':r['rows'][0]['request']['budgets']['dose']={'bad':100}
 if kind=='construction_identity':m['construction_id']='0'*64;new=['construction:'+m['construction_id'][:20]+':'+str(i)for i in range(4)]
 if kind=='construction_identity':
  for i,v in enumerate(z['members']):v['id']=new[i]
  for row in r['rows']:
   for key in ['incurred']:row['request'][key]={new[i]:v for i,v in enumerate(row['request'][key].values())}
   row['request']['budgets']['dose']={new[i]:v for i,v in enumerate(row['request']['budgets']['dose'].values())}
 refused=False
 try:_packet_member_ids(m,r,z)
 except EpochMismatch:refused=True
 assert refused,kind+' invalid provenance/order admitted';rows.append({'id':'negative_packet_member_authority','dependency':kind,'status':'REFUSED'})
for kind in ['graph_content','hazard_content','directory','checker_settings']:
 gg,hh=copy.deepcopy(g),copy.deepcopy(h);directory=p;settings=None
 if kind=='graph_content':gg['nodes'][0]['waitable']=not gg['nodes'][0]['waitable']
 if kind=='hazard_content':hh['members'][0]['flux'][0][0]+=1
 if kind=='directory':directory=D/'baseline/timeout_inputs/20220304T120000Z_baseline_difficult'
 if kind=='checker_settings':settings={'receiver_span_m':17}
 refused=False
 try:e.validate_binding(gg,hh,directory,settings)
 except EpochMismatch:refused=True
 assert refused;rows.append({'id':'changed_real_epoch_dependency','dependency':kind,'status':'REFUSED'})
# Real source-file byte changes and metadata disagreement are checked without touching parent.
with tempfile.TemporaryDirectory()as tmp:
 q=Path(tmp)
 for name in ['REPORT.json','NATIVE_METADATA.json','constructed_arrays.npz']:shutil.copyfile(p/name,q/name)
 owner=prepare_epoch(g,h,q);f=q/'REPORT.json';original=f.read_bytes();f.write_bytes(original+b'\n');refused=False
 try:owner.validate_binding(g,h,q)
 except EpochMismatch:refused=True
 assert refused;f.write_bytes(original);rows.append({'id':'source_report_byte_change','status':'REFUSED'})
 side=copy.deepcopy(md);side['physical_scope']+=' changed';(q/'NATIVE_METADATA.json').write_text(json.dumps(side));refused=False
 try:prepare_epoch(g,h,q)
 except EpochMismatch:refused=True
 assert refused;rows.append({'id':'mandatory_sidecar_disagreement','status':'REFUSED'})
report={'status':'PASS','checks':len(rows),'controls':rows,'wall_s':time.perf_counter()-started,'scope':'Original real v2 source admission only, no route search and no new physical/fresh source construction.'};(D/'review/SOURCE_DEVELOPMENT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='controls'}))
