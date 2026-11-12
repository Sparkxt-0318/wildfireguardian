"""FDYN_PLAN A3(a): re-check the Yeongdeok witness routes of the A1 run with the unchanged kit checker, one fresh
interpreter per check (F-4.2/fixed_route_check.py), recording the checker lifetime RSS. Usage: fdyn_a3a_recheck.py SCRATCH OUT REPO"""
import json,glob,os,subprocess,sys
S,O,REPO=sys.argv[1],sys.argv[2],sys.argv[3]
seen=set()
for d in sorted(glob.glob(S+'/fdyn_b300_g12k_rss12k/runs/yeongdeok*')):
    j=json.load(open(d+'/RESULT.json')); ws=j.get('rejected_witnesses') or []
    if not ws: continue
    w=ws[0]; tag=os.path.basename(d)
    row=[json.loads(l) for l in open(S+'/fdyn_b300_g12k_rss12k/ROWS.jsonl') if json.loads(l)['fdyn']['tag']==tag][0]['fdyn']
    route=O+'/'+tag+'.route.json'; json.dump({'legs':w['legs'],'destination':w['destination'],'arrival':w['arrival']},open(route,'w'))
    graph=json.load(open(d+'/JOB.json')).get('graph') or None
    cmd=['/usr/bin/time','-v',REPO+'/.venv/bin/python','-I','-B',REPO+'/research/harness-2026-11/F-4.2/fixed_route_check.py','--kit',S+'/window-kit',
         '--packet',row['packet'],'--graph',S+'/fdyn/leo/research/harness-2026-11/F-DYN/_data/graphs_interim/yeongdeok_2025/graph.json',
         '--request',d+'/ORIGINAL_REQUEST.json','--route',route,'--wall','600']
    p=subprocess.run(cmd,capture_output=True,text=True)
    out=json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {'error':p.stderr[-2000:]}
    mx=[l for l in p.stderr.splitlines() if 'Maximum resident' in l]
    out.update(tag=tag,stage=w['stage'],packet=row['packet'],time_max_rss_kb=mx[0].split()[-1] if mx else None,rc=p.returncode)
    out.pop('per_member',None) if False else None
    open(O+'/A3A.jsonl','a').write(json.dumps(out,default=str)+'\n')
    print(tag[-45:],out.get('status'),out.get('reason'),'contact',out.get('contact'),'rad',out.get('radiation'),'adaptive',out.get('adaptive'),'rss',out.get('process_lifetime_rss_mb'),'el %.1f'%(out.get('elapsed_s') or -1),flush=True)
