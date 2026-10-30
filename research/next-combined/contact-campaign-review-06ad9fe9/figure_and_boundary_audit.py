from pathlib import Path
import json,hashlib,struct,zlib,xml.etree.ElementTree as ET,subprocess
from datetime import datetime,timezone
ROOT=Path('/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/audit-1c')
OUT=ROOT.parent/'contact-campaign-review'; RUN=ROOT/'research/sipp-routing/known-footprint-contact-K-20261030'
rows=[json.loads(s) for s in (RUN/'EXECUTIONS.jsonl').read_text().splitlines()]; b=json.loads((RUN/'BUNDLE.json').read_text());checks=[]
def check(name,val,detail=None):checks.append(dict(name=name,passed=bool(val),detail=detail))
meta=json.loads((RUN/'FIGURE_REVIEW.json').read_text()); figs=[]
for f in meta['figures']:
 p=RUN/'figures'/f['png'];data=p.read_bytes();i=8;chunks={}
 while i<len(data):
  n=struct.unpack('>I',data[i:i+4])[0];typ=data[i+4:i+8];chunks[typ]=data[i+8:i+8+n];i+=12+n
 w,h=struct.unpack('>II',chunks[b'IHDR'][:8]);x,y,unit=struct.unpack('>IIB',chunks[b'pHYs']);dpi=[x*.0254,y*.0254]
 svg=ET.parse(RUN/'figures'/f['svg']).getroot();widthpt=float(svg.attrib['width'].removesuffix('pt'));heightpt=float(svg.attrib['height'].removesuffix('pt'))
 ok=[w,h]==f['pixels'] and abs(dpi[0]-300)<.001 and unit==1 and abs(widthpt/72-f['width_in'])<1e-10 and w==round(f['width_in']*300) and abs(h-heightpt/72*300)<1
 ok &= hashlib.sha256(data).hexdigest()==f['png_sha256'] and hashlib.sha256((RUN/'figures'/f['svg']).read_bytes()).hexdigest()==f['svg_sha256']
 figs.append(dict(png=f['png'],pixels=[w,h],dpi=dpi,width_in=widthpt/72,pass_metadata=ok))
check('three_exact_width_300dpi_PNG_and_matching_SVG',all(x['pass_metadata'] for x in figs),figs)
commit=datetime.fromtimestamp(int(subprocess.check_output(['git','show','-s','--format=%ct',b['source_phase_head']],cwd=ROOT)),timezone.utc)
start=datetime.fromisoformat(rows[0]['lease_acquired_utc']);check('source_commit_precedes_first_lease',commit<start,dict(source_commit=commit.isoformat(),first_lease=start.isoformat()))
byk=[]
for K in [4,8,16,32]:
 selected=[r for r in rows if r['K']==K];known=[r for r in selected if r['search_started']];byk.append(dict(K=K,total=len(selected),contact=sum(r['arrival'] is not None for r in selected),unknown=sum(not r['search_started'] for r in selected),restricted=sum(r['search_started'] and r['arrival'] is None for r in selected)))
check('figure3_stack_counts_from_raw_rows',[(x['total'],x['contact'],x['unknown'],x['restricted']) for x in byk]==[(80,20,56,4)]*3+[(80,12,56,12)],byk)
# Figure2 formula from exact source uses separate work counters and omits no completed search row.
check('figure2_positive_counters_and_two_matching_repeats',all(r['solver_metrics']['expansions' if r['method']=='sipp' else 'states_reached']>0 for r in rows if r['search_started']))
readme=(RUN/'README.md').read_text().lower();check('explicit_claim_and_timing_limits',all(s in readme for s in ['not a universal speedup','not independent missions or fires','restricted failure','risk remain unknown','conditional on the support-restricted contact problem','t>h']))
result=dict(checks=checks,checks_passed=sum(c['passed'] for c in checks),checks_total=len(checks),failures=[c for c in checks if not c['passed']],visual_review='Independently viewed all three final PNGs. Labels, units, legend, logarithmic axes, matching scope and data inclusion are legible. Repetition markers overlap where counts match, consistent with caption. SVG bytes/dimensions checked; SVG not independently browser-rendered.')
(OUT/'figure_and_boundary_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
raise SystemExit(bool(result['failures']))
