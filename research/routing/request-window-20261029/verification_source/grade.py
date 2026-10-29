"""Independent original-panel verifier: imports no production search/checker."""
from pathlib import Path
from fractions import Fraction as Q
import argparse,hashlib,json,sys,time
import numpy as np
import oracle as O
import actual_routes as A
from extra_original_routes import decode
import ffi_independent_checker as F
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x')as f:json.dump(F._jsonable(O.encode(x)),f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def checkpins(m):
 for p,h in m['source_sha256'].items():
  if sha(p)!=h:raise RuntimeError('SEALED_SOURCE_CHANGED:'+p)
def load(row):
 j=read(row['job_file']);base=Path(j['root']);resolve=lambda p:Path(p)if Path(p).is_absolute()else base/p
 graph=read(resolve(j['graph_path']));request=read(resolve(j['request_path']));packet=resolve(j['source_directory'])
 raw=decode(read(Path(row['output_path'])/'RESULT.json'));return j,graph,request,packet,raw

def source_members(packet,request):
 report=read(packet/'REPORT.json');md=report['native_metadata'];a=md['construction']['assumptions'];ids=tuple(request['incurred'])
 assert read(packet/'NATIVE_METADATA.json')==md
 assert tuple(report['rows'][0]['request']['incurred'])==ids and tuple(md['construction']['scenario_ids'])==ids
 assert set(ids)==set(request['budgets']['dose']) and len(ids)==4 and a['version']=='wfg.hazard.construction/1'
 duration,remaining,horizon=(O.number(a[k])for k in ('burning_duration_s','initial_remaining_s','horizon_s'))
 assert 0<=remaining<=duration and duration>0 and O.number(request['horizon'])<=horizon
 f,c,h,T,r,t=(float(a[k])for k in ('fuel_load_kg_m2','consumed_fraction','heat_of_combustion_j_kg','burning_duration_s','radiative_fraction','atmospheric_transmissivity'))
 density=O.number((((f*c)*h)/T)*r*t);height=O.number(float(a['emission_height_m'])-float(a['receiver_height_m']))
 assert density>=0 and height>0 and 0<=r<=1 and 0<=t<=1
 dx,b,x0,d,dy,y0=map(O.number,md['affine_transform']);assert b==d==0 and dx and dy
 with np.load(packet/'constructed_arrays.npz',allow_pickle=False)as z:ev=z['ignition_time_s'].copy();cur=z['current_active'].copy();sup=z['support'].copy()
 assert ev.ndim==3 and len(ids)==ev.shape[0] and cur.dtype==np.bool_ and cur.shape==ev.shape[1:] and sup.dtype==np.bool_ and sup.all()
 assert not np.isnan(ev).any() and not (ev<0).any() and not np.isfinite(ev[:,cur]).any()
 H,W=cur.shape;assert md['shape']==[H,W]
 def rect(row,col):
  xa,xb=x0+col*dx,x0+(col+1)*dx;ya,yb=y0+row*dy,y0+(row+1)*dy
  return min(xa,xb),max(xa,xb),min(ya,yb),max(ya,yb)
 members=[]
 for axis,mid in enumerate(ids):
  sources=[]
  for row,col in zip(*np.nonzero(cur)):
   if remaining>0:sources.append(O.Source(rect(int(row),int(col)),height,density,0,remaining))
  for row,col in zip(*np.nonzero(np.isfinite(ev[axis]))):
   birth=O.number(float(ev[axis,row,col]));assert 0<=birth<horizon
   sources.append(O.Source(rect(int(row),int(col)),height,density,birth,birth+duration))
  members.append((mid,tuple(sources)))
 return members,density

def grade(index):
 seal=read(ROOT/'reference/VERIFICATION_INPUTS.json');checkpins(seal);m=read(ROOT/'MANIFEST.json');checkpins(m);row=m['jobs'][index];j,g,r,packet,raw=load(row);result=raw['result'];route=result if result.get('destination')is not None else result.get('checked_incumbent')
 fg=F.Graph(g);pk=F.Packet(packet,fg)
 relaxation=F.relaxation(fg,pk,r,want_witness=True)
 out=dict(index=index,execution_id=row['execution_id'],manifest_sha256=sha(ROOT/'MANIFEST.json'),job_sha256=sha(row['job_file']),result_sha256=sha(Path(row['output_path'])/'RESULT.json'),relaxation={k:v for k,v in relaxation.items()if k!='witness'},route_present=route is not None,scope='Independent fixed-journey model verification; no physical validation.')
 if route is not None:
  gram=F.grammar(fg,r,route['legs'],route['destination'],pk.horizon);out['grammar']={k:v for k,v in gram.items()if k in ('ok','errors','arrival','finish')}
  assert gram['ok'],gram['errors']
  out['centre_model']=F.centre_model(pk,r,gram);out['whole_road_contact']=F.whole_road_contact(pk,gram)
  out['metric_agreement']=F.compare_router(pk,out['centre_model'],route.get('per_member'),r)
  legs=A.witness(g,r,route);members,density=source_members(packet,r);memo={};bounds=[]
  for mid,sources in members:
   key=tuple((s.rect,s.height,s.density,s.birth,s.expiry)for s in sources)
   if key not in memo:memo[key]=A.radial_trajectory(sources,legs,density=density,max_records=100000,wall_s=60)
   b=memo[key];dose=(b['dose']+O.number(r['incurred'][mid])*1000)/1000;peak=b['peak']/1000
   bounds.append(dict(id=mid,dose_kj_m2=dose,peak_kw_m2=peak,dose_budget_kj_m2=O.number(r['budgets']['dose'][mid]),peak_budget_kw_m2=O.number(r['budgets']['peak']),proved=dose.hi<=O.number(r['budgets']['dose'][mid])and peak.hi<=O.number(r['budgets']['peak']),refinement={k:v for k,v in b.items()if k not in ('dose','peak')}))
  out['thermal_members']=bounds
  out['verified_journey']=bool(out['centre_model']['feasible']and out['whole_road_contact']['status']=='CLEAR'and out['metric_agreement']['status']!='DISAGREE'and all(b['proved']for b in bounds))
  out['arrival_matches_independent_lower_bound']=relaxation.get('lower_bound_arrival')==route['arrival']
 else:
  members,density=source_members(packet,r)
  out['global_peak_cap_kw_m2']=density/2000
  out['verified_no_route']=relaxation['status']=='NO_ADMISSIBLE_ARRIVAL' and density/2000<=O.number(r['budgets']['peak'])
 checkpins(seal);checkpins(m);save(ROOT/'reference/grades'/(str(index).zfill(2)+'.json'),out)
 print(json.dumps({'index':index,'route':out.get('verified_journey'),'no_route':out.get('verified_no_route')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);grade(p.parse_args().index)
