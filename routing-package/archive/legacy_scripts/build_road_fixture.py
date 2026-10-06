"""Export entire pinned historical mapped chord graph with labelled fixtures only."""
from pathlib import Path
import csv,hashlib,json,math
from routing.validation import chord_segments,validate_request
ROOT=Path(__file__).resolve().parent
SOURCE=Path('/Users/jp/Documents/Codex/2026-09-24/fu/outputs/korean_realfire_study_20261002_v1/workers/graph_nangok_r1')
def build():
    hashes={};expected={}
    for line in (SOURCE/'MANIFEST.sha256').read_text().splitlines():
        digest,path=line.split(None,1);expected[path.lstrip('*')]=digest
    for name in ['graph/nodes.csv','graph/edges.csv','graph/banned_turns.csv','graph/build_report.json','GRAPH_CARD.md']:
        p=SOURCE/name;h=hashlib.sha256(p.read_bytes()).hexdigest();hashes[str(p)]=h
        if expected.get(name)!=h:raise RuntimeError('source hash mismatch '+name)
    raw_nodes=list(csv.DictReader((SOURCE/'graph/nodes.csv').open()));raw_edges=list(csv.DictReader((SOURCE/'graph/edges.csv').open()))
    nodes=[{'id':n['node_id'],'x':float(n['x']),'y':float(n['y']),'waitable':False} for n in raw_nodes]
    ns={n['id']:n for n in nodes};r=500.;x0=math.floor(min(n['x'] for n in nodes)/r)*r;y0=math.floor(min(n['y'] for n in nodes)/r)*r
    grid={'x0':x0,'y0':y0,'resolution':r,'width':math.floor((max(n['x'] for n in nodes)-x0)/r)+1,'height':math.floor((max(n['y'] for n in nodes)-y0)/r)+1}
    reverse_by={(e['u'],e['v']):e['edge_id'] for e in raw_edges};edges=[]
    for e in raw_edges:
        ticks=float(e['minutes'])*1024
        if ticks!=int(ticks):raise RuntimeError('nonlattice frozen travel')
        q={'id':e['edge_id'],'u':e['u'],'v':e['v'],'travel_ticks':int(ticks),'segments':chord_segments(grid,ns[e['u']],ns[e['v']])}
        if (e['v'],e['u']) in reverse_by:q['reverse_edge']=reverse_by[e['v'],e['u']]
        edges.append(q)
    into={n['id']:[] for n in nodes};out={n['id']:[] for n in nodes}
    for e in edges:into[e['v']].append(e);out[e['u']].append(e)
    banned={}
    for t in csv.DictReader((SOURCE/'graph/banned_turns.csv').open()):
        for a in into[t['via']]:
            for b in out[t['via']]:
                if a['u']==t['a'] and b['v']==t['c']:banned[a['id'],b['id']]=True
    uturn={n['node_id']:n['uturn_permitted']=='True' for n in raw_nodes}
    for n in ns:
        if not uturn[n]:
            for a in into[n]:
                for b in out[n]:
                    if a['u']==b['v']:banned[a['id'],b['id']]=True
    graph={'revision':'nangok-r1-chord-fixture-adapter-'+hashes[str(SOURCE/'graph/edges.csv')][:16],'crs':'EPSG:5179','grid':grid,'nodes':nodes,'edges':edges,'forbidden_turns':[list(x) for x in sorted(banned)],'mid_edge_reversal':False}
    N=grid['width']*grid['height'];dt=60/1024.;horizon=2048*dt;until=4096*dt;origin='2026-10-04T00:00:00+08:00';members=[]
    for m,f in [('road-fixture-m0',1.),('road-fixture-m1',2.)]:members.append({'id':m,'breakpoints':[0.,until],'flux':[[f]*N],'flame':[[False]*N],'support':[[True]*N]})
    hazard={'schema':'wfg.routing.edgegrid/1','version':1,'graph_revision':graph['revision'],'crs':graph['crs'],'grid':grid.copy(),'dt':dt,'time_origin':origin,'issued_at':origin,'available_at':origin,'valid_from':0.,'valid_until':until,'evidence_class':'LABELLED_FIXTURE','provenance':{'source':'full Nangok r1 historical OSM chord roads + GENERATED uniform heat flux','interpretation':'engineering smoke fixture; no observed fire/road safety/passability or forecast output'},'channels':['flame_contact','incident_heat_flux'],'unsupported_channels':['embers','secondary_ignition'],'members':members}
    edge=next(e for e in edges if e['travel_ticks']<=256 and uturn[e['u']])
    request={'position':{'node':edge['u']},'incoming_edge':None,'departure':0.,'horizon':horizon,'destinations':[{'node':edge['v'],'dwell':16*dt,'open_intervals':[[0.,until]]}],'incurred':{m['id']:0. for m in members},'hazard_version':1,'as_of':origin,'objective':'earliest_arrival','exposure_scope':'route_only','budgets':{'peak':10.,'dose':{m['id']:500. for m in members}},'limits':{'wall_s':10.,'max_labels':100000,'max_expansions':100000,'frontier_width':4096,'rss_limit_mb':3072},'solver':'baseline'}
    validate_request(graph,hazard,request)
    result={'graph':graph,'hazard':hazard,'request':request,'source_hashes':hashes,'evidence_class':'REAL_ROAD_LABELLED_FIXTURE_HAZARD','limits':['full graph no edges omitted','waits disallowed in this declared smoke fixture (not prior benchmark protocol)','all encoded node-triple restrictions and original uturn flags preserved','unencoded viaway/conditional/malformed restrictions remain permissive gaps','generated uniform hazards, assumed40km/h, chord geometry, no actual forecasting']}
    (ROOT/'fixtures/nangok_full_graph_fixture.json').write_text(json.dumps(result,separators=(',',':')))
    (ROOT/'evidence/ROAD_FIXTURE_PROVENANCE.json').write_text(json.dumps({'source_hashes':hashes,'nodes':len(nodes),'edges':len(edges),'encoded_forbidden_pairs':len(banned),'dt_seconds':dt,'evidence_class':result['evidence_class'],'limits':result['limits']},indent=2))
    print(json.dumps({'nodes':len(nodes),'edges':len(edges),'forbidden_pairs':len(banned),'fixture_bytes':(ROOT/'fixtures/nangok_full_graph_fixture.json').stat().st_size}))
if __name__=='__main__':build()
