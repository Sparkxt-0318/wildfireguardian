from collections import Counter, defaultdict

def candidate_plans(q,route,W):
    nodes=[q['position']['node']];edges=[];dt=[];holds=Counter()
    for l in route['legs']:
        if l['kind']=='EDGE':
            e=W.edges[l['edge']];nodes.append(e['v']);edges.append(e['id']);dt.append(e['travel_ticks'])
        else:holds[len(edges)]+=l['end']-l['start']
    if not edges:return []
    visits=defaultdict(list)
    for i,n in enumerate(nodes):visits[n].append(i)
    options=[];cs=[0]
    for t in dt:cs.append(cs[-1]+t)
    for n,pos in visits.items():
        for j_idx,j in enumerate(pos):
            for i in pos[:j_idx]:
                suffix=j<len(edges);last=i if suffix else i-1
                if last<0:continue
                h=next((k for k in reversed(range(last+1)) if W.nodes[nodes[k]]['waitable']),None)
                if h is None:continue
                incoming=edges[i-1] if i else q['incoming_edge']
                if suffix and (incoming,edges[j]) in W.turns:continue
                options.append((-(cs[j]-cs[i]),i-h,i,j,h))
    unique=set();out=[]
    for neg,_,i,j,h in sorted(options):
        shortened=edges[:i]+edges[j:]
        if not shortened:continue
        # Keep existing time spent at other nodes. The interval erased includes every wait before an erased edge.
        adjustment=-neg+sum(holds[k] for k in range(i,j))
        remaining=Counter({(k if k<i else k-j+i):v for k,v in holds.items() if not i<=k<j})
        remaining[h]+=adjustment
        start=q['departure'];legs=[];node=nodes[0]
        for k,eid in enumerate(shortened):
            if remaining[k]:
                assert W.nodes[node]['waitable'];end=start+remaining[k]
                legs.append(dict(kind='WAIT',node=node,start=start,end=end));start=end
            edge=W.edges[eid];assert edge['u']==node;end=start+edge['travel_ticks']
            legs.append(dict(kind='EDGE',edge=eid,start=start,end=end,from_fraction=0,to_fraction=1))
            node=edge['v'];start=end
        assert start==route['arrival'] and node==route['destination']
        key=tuple((k['kind'],k.get('edge',k.get('node')),k['end']) for k in legs)
        if key in unique:continue
        unique.add(key);out.append((-neg,dict(legs=legs,arrival=start,destination=node)))
        if len(out)==3:break
    return out
