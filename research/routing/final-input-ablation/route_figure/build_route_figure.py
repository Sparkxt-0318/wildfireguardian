"""Source-bound recorded route figure. No routing, fitting, or numerical experiment."""
from pathlib import Path
from fractions import Fraction
import json,csv,hashlib,math,subprocess
from reportlab.graphics.shapes import Drawing,Path as GPath,Line,Rect,Circle,String,Polygon
from reportlab.graphics import renderPDF,renderSVG
from reportlab.lib.colors import HexColor,Color,white
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'routing_final_input_ablation_20261016_v1'
STUDY=BASE/'study'
CASE='20250324T090000Z_FL2'
COHORT='uiseong_andong_2025'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
graph_path=STUDY/f'inputs/latest/{COHORT}/graph.json'
g=read(graph_path);nodes={n['id']:n for n in g['nodes']};edges={e['id']:e for e in g['edges']}
rows=read(BASE/'analysis/ROWS_REVIEWED.json'); jobs=read(STUDY/'queues/ABLATION.json')['jobs']
selected={a:next(r for r in rows if r['case_id']==CASE and r['rep']==1 and r['policy']==a) for a in ['A0','A4']}
job={a:next(j for j in jobs if j['case_id']==CASE and j['rep']==1 and j['arm_key']==a) for a in selected}
assert sha(graph_path)==job['A0']['input_sha256']['graph_path']==job['A4']['input_sha256']['graph_path']
raw={a:STUDY/job[a]['output_path']/'RESULT.json' for a in selected}
results={a:read(p)['result'] for a,p in raw.items()}
request=read(STUDY/job['A4']['full_request_path'])
assert results['A0']['arrival']==1616 and results['A4']['arrival']==2143
assert selected['A0']['independent_contact_status']=='DEFINITE_CONTACT'
assert selected['A4']['full_policy_pass'] is True
assert results['A0']['destination']==results['A4']['destination']
grades={a:read(BASE/selected[a]['grade_path']) for a in selected}
contact=next(iter(grades['A0']['independent_contact']['witnesses'].values()))
ct=Fraction(contact['time_exact']); edge=edges[contact['edge']]
contact_leg=next(l for l in results['A0']['legs'] if l.get('edge')==contact['edge'] and Fraction(str(l['start']))<=ct<=Fraction(str(l['end'])))
frac=float(contact_leg['from_fraction'])+(float(ct)-float(contact_leg['start']))/(float(contact_leg['end'])-float(contact_leg['start']))*(float(contact_leg['to_fraction'])-float(contact_leg['from_fraction']))
u,v=nodes[edge['u']],nodes[edge['v']]
contact_xy=(u['x']+frac*(v['x']-u['x']),u['y']+frac*(v['y']-u['y']))
def xy_at(e,f):
 u,v=nodes[e['u']],nodes[e['v']];return (u['x']+f*(v['x']-u['x']),u['y']+f*(v['y']-u['y']))
segments={}; coords=[]
for arm,r in results.items():
 ss=[]
 for i,l in enumerate(r['legs']):
  if l['kind']!='EDGE':continue
  e=edges[l['edge']];a=xy_at(e,float(l.get('from_fraction',0)));b=xy_at(e,float(l.get('to_fraction',1)))
  ss.append({'leg_index':i,'edge_id':e['id'],'start_s':l['start'],'end_s':l['end'],'x0':a[0],'y0':a[1],'x1':b[0],'y1':b[1]});coords.extend([a,b])
 segments[arm]=ss
assert len(segments['A0'])==269
# Frame uses identical x/y scale in projected metres.
xlo=min(x for x,y in coords);xhi=max(x for x,y in coords);ylo=min(y for x,y in coords);yhi=max(y for x,y in coords)
pad=650;xlo-=pad;xhi+=pad;ylo-=pad;yhi+=pad
W,H=816,615;frame=(36,72,744,470);fx,fy,fw,fh=frame
scale=min(fw/(xhi-xlo),fh/(yhi-ylo));cx=(xlo+xhi)/2;cy=(ylo+yhi)/2
xlo=cx-fw/(2*scale);xhi=cx+fw/(2*scale);ylo=cy-fh/(2*scale);yhi=cy+fh/(2*scale)
def trans(x,y):return (fx+(x-xlo)*scale,fy+(y-ylo)*scale)
d=Drawing(W,H);d.add(Rect(0,0,W,H,fillColor=white,strokeColor=None))
ink=HexColor('#243747');blue=HexColor('#246383');orange=HexColor('#BC7147');grey=HexColor('#D8DFE3');red=HexColor('#B64341')
def text(x,y,s,size=10,color=ink,font='Helvetica',anchor='start'):
 d.add(String(x,y,s,fontSize=size,fontName=font,fillColor=color,textAnchor=anchor))
def line(x1,y1,x2,y2,color,width=1,dash=None):
 ob=Line(x1,y1,x2,y2,strokeColor=color,strokeWidth=width)
 if dash:ob.strokeDashArray=dash
 d.add(ob)
# Header doubles as direct legend; no decorative headline.
line(38,583,65,583,orange,2.6,[5,3]);text(73,579,'Travel only',12,font='Helvetica-Bold');text(73,561,'1,616 s arrival',10.5)
line(284,583,311,583,blue,3);text(319,579,'Full hazard policy',12,font='Helvetica-Bold');text(319,561,'2,143 s arrival',10.5)
text(778,579,'+527 s',19,blue,'Helvetica-Bold','end');text(778,561,'arrival increase',9.7,ink,anchor='end')
d.add(Rect(fx,fy,fw,fh,fillColor=HexColor('#FBFCFC'),strokeColor=HexColor('#CFD7DC'),strokeWidth=.7))
# Actual recorded local road graph; no tiles, fabricated terrain or invented boundaries.
bg=[]; seen=set()
for e in g['edges']:
 key=tuple(sorted([e['u'],e['v']]))
 if key in seen:continue
 seen.add(key);a=nodes[e['u']];b=nodes[e['v']]
 if not(xlo<=a['x']<=xhi and ylo<=a['y']<=yhi and xlo<=b['x']<=xhi and ylo<=b['y']<=yhi):continue
 x1,y1=trans(a['x'],a['y']);x2,y2=trans(b['x'],b['y']);line(x1,y1,x2,y2,grey,.42)
 bg.append({'edge_id':e['id'],'x0':a['x'],'y0':a['y'],'x1':b['x'],'y1':b['y']})
# Blue full-route beneath dashed travel-only path keeps shared segments legible.
for arm,color,width,dash in [('A4',blue,2.9,None),('A0',orange,2.1,[5,3])]:
 p=GPath(strokeColor=white,strokeWidth=width+2.8,fillColor=None)
 for s in segments[arm]:
  a=trans(s['x0'],s['y0']);b=trans(s['x1'],s['y1']);p.moveTo(*a);p.lineTo(*b)
 if arm=='A4': d.add(p)
 p=GPath(strokeColor=color,strokeWidth=width,fillColor=None)
 if dash:p.strokeDashArray=dash
 last=None
 for s in segments[arm]:
  a=trans(s['x0'],s['y0']);b=trans(s['x1'],s['y1'])
  if last is None or math.dist(a,last)>1e-7:p.moveTo(*a)
  p.lineTo(*b);last=b
 d.add(p)
start=nodes[request['position']['node']];goal=nodes[results['A4']['destination']]
for n,label,dx,dy,anchor in [(start,'Start',-12,-17,'end'),(goal,'Destination',13,9,'start')]:
 x,y=trans(n['x'],n['y']);d.add(Circle(x,y,5.0,fillColor=white,strokeColor=ink,strokeWidth=1.7));d.add(Circle(x,y,1.7,fillColor=ink,strokeColor=None));text(x+dx,y+dy,label,11,ink,'Helvetica-Bold',anchor)
# Exact witness: member 2's first independently checked contact on the travel route.
px,py=trans(*contact_xy);d.add(Circle(px,py,7.5,fillColor=white,strokeColor=red,strokeWidth=1.7));line(px-3.2,py-3.2,px+3.2,py+3.2,red,1.7);line(px-3.2,py+3.2,px+3.2,py-3.2,red,1.7)
# Contact label is placed clear of the path, with one leader.
lx=px+73;ly=py+70;line(px+8,py+6,lx-8,ly-4,red,.85)
d.add(Rect(lx-7,ly-28,171,43,fillColor=white,strokeColor=HexColor('#E6D1CF'),strokeWidth=.7))
text(lx,ly,'Checked flame contact',10.5,red,'Helvetica-Bold');text(lx,ly-16,f'{float(ct):.2f} s  |  scenario member 2',9.6,ink)
# Scale and north indicator use true projected metric geometry.
bx,by=fx+20,fy+21;sl=2000*scale;line(bx,by,bx+sl,by,ink,1.7);line(bx,by-3,bx,by+3,ink,1.1);line(bx+sl,by-3,bx+sl,by+3,ink,1.1);text(bx+sl/2,by+8,'2 km',9.3,ink,anchor='middle')
nx,ny=fx+fw-25,fy+fh-44;line(nx,ny-8,nx,ny+12,ink,1);d.add(Polygon([nx-3,ny+7,nx,ny+15,nx+3,ny+7],fillColor=ink,strokeColor=None));text(nx,ny+21,'N',9.4,ink,'Helvetica-Bold','middle')
text(37,48,'Uiseong-Andong, Korea | 24 March 2025, 09:00 UTC input | mission FL2, repetition 1',10)
text(37,30,'Recorded OSM-derived road graph; EPSG:5179. Map shows route geometry, not a static fire perimeter.',9.0,HexColor('#5E6E78'))
renderPDF.drawToFile(d,str(HERE/'route_overlay.pdf'));renderSVG.drawToFile(d,str(HERE/'route_overlay.svg'))
# Export the exact geometry used in each layer.
for arm,ss in segments.items():
 with (HERE/f'{arm}_route_geometry.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(ss[0]));w.writeheader();w.writerows(ss)
with (HERE/'background_road_geometry.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(bg[0]));w.writeheader();w.writerows(bg)
contact_record={**contact,'interpolation_fraction':frac,'x_epsg5179':contact_xy[0],'y_epsg5179':contact_xy[1],'edge_occupied_by_leg':contact_leg,'mapping':'constant speed on recorded straight road edge between supplied nodes; exact independent contact time retained above'}
(HERE/'contact_witness.json').write_text(json.dumps(contact_record,indent=2)+'\n')
caption='Recorded route comparison for Uiseong-Andong mission 20250324T090000Z_FL2 (repetition 1). The travel-only route arrives at 1,616 s but intersects predicted active flame in scenario member 2; the marked position is reconstructed from the independent contact witness at 794.3383812623694 s. Routing with the full hazard policy returns a different route arriving at 2,143 s, a 527 s increase, and passes independent centre/contact checks and the project whole-road thermal checker. The continuous-road radiation enclosure is not independently validated. Both routes include a separate 120 s destination stay after arrival. Coordinates and background roads come from the exact recorded EPSG:5179 OSM-derived graph; no external basemap or invented fire perimeter is used. Route results are conditional on the supplied model, not evidence of physical safety.'
(HERE/'CAPTION.md').write_text(caption+'\n')
sources=[graph_path,BASE/'analysis/ROWS_REVIEWED.json',BASE/'analysis/ARRIVAL_DELTAS.json',STUDY/'queues/ABLATION.json']+list(raw.values())+[BASE/selected[a]['grade_path'] for a in selected]+[STUDY/job['A4']['full_request_path']]
manifest={'schema':'wfg.recorded-route-figure/1','case_id':CASE,'rep':1,'graph_sha256':sha(graph_path),'graph_revision':g['revision'],'crs':g['crs'],'source_files':{str(p.relative_to(BASE)):sha(p) for p in sources},'arrival_s':{a:results[a]['arrival'] for a in results},'delta_arrival_s':527,'driving_legs':{a:len(segments[a]) for a in segments},'contact':contact_record,'plot_bounds_epsg5179':[xlo,ylo,xhi,yhi],'background_unique_road_segments':len(bg),'policy_states':{a:{k:selected[a][k] for k in ['full_policy_pass','independent_contact_status','full_whole_status']} for a in selected},'scope':'actual recorded road graph and routes; no new numerical experiment; project radiation checker reused'}
(HERE/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Created vectors, source geometry and manifest. Contactxy:',contact_xy,'Figureboundingbox',manifest['plot_bounds_epsg5179'])
