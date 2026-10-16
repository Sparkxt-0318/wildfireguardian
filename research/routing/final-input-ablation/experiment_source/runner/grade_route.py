"""Offline dual-policy assessment, no production imports for grammar/centre/contact. Project road-radiation checker is explicitly not independent radiation proof."""
import json,pathlib,sys,time,hashlib,copy
R=pathlib.Path(sys.argv[1]);job=json.loads(pathlib.Path(sys.argv[2]).read_text());result=json.loads(pathlib.Path(sys.argv[3]).read_text());out=pathlib.Path(sys.argv[4]);search=result['result'];route=search if search.get('destination') is not None else search['checked_incumbent'];policy=job['policy'];arm=int(policy[1]);sys.path.insert(0,str(R/'runner'))
import ffi_independent_checker as I
for k,h in job['input_sha256'].items():
 assert hashlib.sha256((R/job[k]).read_bytes()).hexdigest()==h,'INPUT_IDENTITY:'+k
assert hashlib.sha256((R/job['full_request_path']).read_bytes()).hexdigest()==job['full_request_sha256'],'FULL_REQUEST_IDENTITY'
for n,h in job['source_sha256'].items():
 assert hashlib.sha256((R/job['source_directory']/n).read_bytes()).hexdigest()==h,'SOURCE_IDENTITY:'+n
full=json.loads((R/job['full_request_path']).read_text());plan=json.loads((R/job['request_path']).read_text());graph=json.loads((R/job['graph_path']).read_text());G=I.Graph(graph);pk=I.Packet(R/job['source_directory'],G)
gram=I.grammar(G,full,route['legs'],route['destination'],pk.horizon);cm=I.centre_model(pk,full,gram);contact=I.whole_road_contact(pk,gram)
en={'A0':set(),'A1':{'FLAME'},'A2':{'FLAME','PEAK'},'A3':{'FLAME','DOSE'},'A4':{'FLAME','PEAK','DOSE'}}[policy]
viol=[]
for mid,v in cm['per_member'].items():
 for flag,n in [('flame_contact','FLAME'),('peak_violation','PEAK'),('dose_violation','DOSE')]:
  if v[flag]:viol.append(dict(member=mid,constraint=n,value=v.get('dose_total_kj_m2') if n=='DOSE' else v.get('peak_kw_m2')))
own=gram['ok'] and not any(v['constraint'] in en for v in viol) and ('FLAME' not in en or contact['status']=='CLEAR')
# Load the UNCHANGED project source-derived checker only after independently calculating mission/centre/contact.
src=R/job['source_root'];sys.path[:0]=[str(src/'baseline/routing-package'),str(src/'baseline'),str(src/'search'),str(R/'phaseB')]
from arm_check import check_for_arm
import mission_contract,contact_first,hybrid_checker,adaptive_checker
mods=dict(mission_contract=mission_contract,contact_first=contact_first,hybrid_checker=hybrid_checker)
t=time.perf_counter();ownroad=check_for_arm(policy,mods,R/job['source_directory'],graph,full,plan,route['legs'],route['destination'],time.perf_counter()+90,checker_class=adaptive_checker.HybridChecker,sentinel=1e12)
if policy=='A4':
 fullroad=ownroad.get('checker_result') or ownroad
 if ownroad['status']!='CERTIFIED_FOR_ARM': fullroad=dict(status=ownroad['status'],reason=ownroad.get('reason'),secondary=fullroad)
else:fullroad=adaptive_checker.HybridChecker(R/job['source_directory']).check(graph,full,route['legs'],route['destination'],wall_s=90,deadline=time.perf_counter()+90,expected_graph_revision=graph['revision'],expected_graph_sha256=mission_contract.graph_digest(graph))
if contact['status']!='CLEAR':viol.append(dict(member='all',constraint='WHOLE_ROAD_CONTACT',value=None))
if fullroad['status']=='DEFINITE_REJECT' and contact['status']=='CLEAR':viol.append(dict(member='all',constraint='WHOLE_ROAD_THERMAL',value=None))
rec=dict(schema='wfg.final-input-ablation.dual-policy-grade/1',policy=policy,case_id=job['case_id'],cohort=job['cohort'],scope='offline check not charged to request; radiation checker reused from project, not independent radiation enclosure',grammar={k:v for k,v in gram.items() if k not in ('segments',)},independent_centre=cm,independent_contact=contact,own_centre_pass=own,full_centre_pass=gram['ok'] and cm['feasible'],full_failures=viol,own_whole=ownroad,full_whole=fullroad,wall_s=time.perf_counter()-t)
# Keep full source-derived exposure even when selected policy had neutralized centre flux.
def enc(x):
 if hasattr(x,'item'):return x.item()
 return str(x)
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(rec,default=enc,indent=1)+'\n');print(policy,job['case_id'],own,cm['feasible'],fullroad['status'])
