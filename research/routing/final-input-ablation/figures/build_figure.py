"""Publication figure from completed, independently reviewed ablation rows only."""
from pathlib import Path
from collections import defaultdict
import json, hashlib, subprocess, csv
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics import renderSVG, renderPDF
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white

ROOT = Path(__file__).resolve().parent
STUDY = ROOT.parent/'routing_final_input_ablation_20261016_v1'
OUT = ROOT/'curated'/'figures'
NODE = '/Users/jp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
SHARP = '/Users/jp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    rows = json.loads((STUDY/'analysis/ROWS_REVIEWED.json').read_text())
    summary = json.loads((STUDY/'analysis/SUMMARY.json').read_text())
    assert len(rows) == 200 and summary['rows'] == 200
    OUT.mkdir(parents=True, exist_ok=True)
    labels = {'A0':'Travel time only', 'A1':'Flame avoidance',
              'A2':'Flame + peak flux', 'A3':'Flame + cumulative exposure',
              'A4':'Full policy'}
    colors = {'full':'#246383','other':'#C26443','refusal':'#C19038',
              'unresolved':'#DCE3E7','ink':'#192E3C','muted':'#576975','grid':'#DFE6EA'}
    col = lambda k: HexColor(colors.get(k,k))
    d = Drawing(1040,470)
    d.add(Rect(0,0,1040,470,fillColor=white,strokeColor=None))
    def text(x,y,s,size=17,bold=False,anchor='start',color='ink'):
        d.add(String(x,y,str(s),fontName='Helvetica-Bold' if bold else 'Helvetica',
                     fontSize=size,textAnchor=anchor,fillColor=col(color)))
    def rect(x,y,w,h,color):
        d.add(Rect(x,y,w,h,fillColor=col(color),strokeColor=None))
    legend=[('Route passes full rules','full'),('Route violates full rules','other'),
            ('No admissible route (model)','refusal')]
    for i,(label,color) in enumerate(legend):
        x=20+(i%2)*510; y=438-(i//2)*29
        rect(x,y-3,17,17,color); text(x+27,y,label)
    x0=324; width=560; bottom=64; top=360
    for v in range(0,21,5):
        x=x0+width*v/20
        d.add(Line(x,bottom,x,top,strokeColor=col('grid'),strokeWidth=1))
        text(x,39,v,16,anchor='middle')
    chart=[]
    for i,a in enumerate(['A0','A1','A2','A3','A4']):
        groups=defaultdict(list)
        for r in rows:
            if r['policy']==a: groups[(r['cohort'],r['case_id'])].append(r)
        assert len(groups)==20 and all(len(g)==2 for g in groups.values())
        counts=dict(full=0,other=0,refusal=0,unresolved=0)
        for group in groups.values():
            if all(r['own_outcome']=='CHECKED_ROUTE' for r in group):
                if not all(r['full_policy_pass'] is True for r in group):
                    assert all(r['full_failure_components'] for r in group), 'Do not label an unconfirmed check as a violation.'
                counts['full' if all(r['full_policy_pass'] is True for r in group) else 'other']+=1
            elif all(r['own_outcome']=='SCOPED_REFUSAL' for r in group): counts['refusal']+=1
            else: counts['unresolved']+=1
        s=next(s for s in summary['arms'] if s['policy']==a)
        assert counts['full']==s['stable_full_passing_routes']
        assert counts['full']+counts['other']==s['stable_own_routes']
        assert counts['refusal']==s['stable_scoped_refusals'] and sum(counts.values())==20
        y=330-i*55
        text(15,y+7,labels[a],18,bold=a=='A4')
        x=x0
        for key in ['full','other','refusal','unresolved']:
            n=counts[key]
            if not n: continue
            w=width*n/20;rect(x,y-2,w,32,key)
            text(x+w/2,y+7,n,18,bold=True,anchor='middle',color='#FFFFFF' if key in ['full','other'] else 'ink')
            x+=w
        text(920,y+7,f"{counts['full']}/20",18,bold=True)
        chart.append({'policy':a,'label':labels[a],**counts,'denominator':20})
    assert all(v['unresolved']==0 for v in chart), 'Add unresolved legend if the recorded data contain such outcomes.'
    text(920,373,'Pass full rules',16,bold=True)
    text(x0+width/2,10,'Missions with the same outcome in both repetitions',17,anchor='middle')
    key='final_input_constraint_ablation'
    svg=OUT/(key+'.svg');renderSVG.drawToFile(d,str(svg))
    pdf=OUT/(key+'.pdf');scale=489.6/d.width
    c=canvas.Canvas(str(pdf),pagesize=(489.6,d.height*scale));c.scale(scale,scale);renderPDF.draw(d,c,0,0);c.showPage();c.save()
    png=OUT/(key+'.png')
    js=f"const sharp=require({json.dumps(SHARP)});sharp({json.dumps(str(svg))}).resize(3060).png().withMetadata({{density:450}}).toFile({json.dumps(str(png))});"
    subprocess.run([NODE,'-e',js],check=True)
    with (OUT/'FIGURE_DATA.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(chart[0]));w.writeheader();w.writerows(chart)
    (OUT/'FIGURE_CAPTION.md').write_text('''Final-input routing constraint ablation. Each bar represents 20 designed missions on the final input set, with two executions per policy and mission (200 executions total). A mission is assigned to a category only when both repetitions meet it. The eight orange travel-only routes satisfy their selected travel rules but violate the full hazard policy: all eight encounter flame and four also exceed a cumulative-exposure limit. Each constrained policy returns 15 full-policy-passing routes and five independently corroborated model refusals. Full-policy passage combines independent centre/contact checks and the project whole-road thermal checker; independent continuous-road radiation enclosure remains open. No unresolved or mixed outcomes occurred. This panel is separate from both the earlier-input 300-execution ablation and the final 80-execution solver comparison.\n''')
    (OUT/'FIGURE_MANIFEST.json').write_text(json.dumps({'data_scope':'20 missions,5 policies,2 repetitions;200 final-input executions',
        'source_rows_sha256':sha(STUDY/'analysis/ROWS_REVIEWED.json'),'source_summary_sha256':sha(STUDY/'analysis/SUMMARY.json'),
        'counts_independently_recomputed_from_rows':chart,
        'assets':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in [svg,pdf,png,OUT/'FIGURE_DATA.csv',OUT/'FIGURE_CAPTION.md']}},indent=2)+'\n')
    print(json.dumps(chart,indent=2))

if __name__=='__main__': main()
