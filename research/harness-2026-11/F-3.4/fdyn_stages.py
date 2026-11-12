"""Per-request stage table for an F-DYN profile run directory (needs the raw runs/ folders, not committed):
outcome, bound times, resident/lifetime-peak RSS at the end of bound model / EA bound / solve, and per-stage cap,
status, reason, labels, expansions from SEARCH_RESULT.json.  python fdyn_stages.py RUN_DIR"""
import json,sys,glob,os
D=sys.argv[1]
for l in open(D+'/ROWS.jsonl'):
    r=json.loads(l); tag=r['fdyn']['tag']; d=f"{D}/runs/{tag}"
    sr=json.load(open(d+'/SEARCH_RESULT.json')) if os.path.exists(d+'/SEARCH_RESULT.json') else {}
    st=r.get('worker_stages_s') or {}
    pt={}
    if os.path.exists(d+'/PHASE_TIMERS.json'):
        j=json.load(open(d+'/PHASE_TIMERS.json')); pt=j.get('timers') or j
    def mem(k):
        v=pt.get(k); return '%.2f/%.2f'%(v['max_rss_end_bytes']/2**30,v['highwater_end_bytes']/2**30) if v else '-'
    print('%-62s %-36s arr=%s wall=%.1f peak=%.0f' % (tag[-62:], r['authoritative_status']+'/'+str(r['unresolved_reason'] or ''), r['arrival_s'], r['complete_wall_s'], r['family_peak_rss_mib']))
    print('    BM %.1fs EA %.1fs | mem end/hw GiB: BM %s EA %s solve %s' % (st.get('bound_model_construction_s') or 0, st.get('earliest_arrival_bound_s') or 0, mem('road_bounds.RoadBoundModel.__init__'), mem('zsweep.EarliestArrivalBound.__init__'), mem('road_core.solve')))
    for s in sr.get('stages',[]):
        print('    %-4s cap %6.1f status %-18s reason %-24s labels %s exp %s' % (s.get('stage'), s.get('wall_cap_s') or -1, s.get('status'), s.get('reason'), s.get('labels'), s.get('expansions')))
