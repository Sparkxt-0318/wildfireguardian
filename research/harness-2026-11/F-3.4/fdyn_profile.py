"""F-3.4 multi-hour profile on F-DYN v3: the fixed 12-request set of FDYN_PLAN.md through the unchanged controller.

Requests are built with the repository's own api.requests_build.build_request, as Leo's smoke_check does:
- first 3 origins in INSTANCE.json order for the region/start, horizon 5 h;
- departure 0, each origin's first destination;
- limits 10 kW/m² and 100 kJ/m²; incurred 0; destination window [0, H].

Each request goes through run_profile.run_one (instrumented phase worker; kit controller with GNU time, RSS sampler,
memory guard and outer deadline).

  python fdyn_profile.py --kit KIT --leo LEO_WORKTREE --out OUT --budget 30 [--mode phase|plain] [--memory-guard-mib 3072]
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(HERE), str(REPO)]
import run_profile as RP  # noqa: E402
from api.requests_build import build_request  # noqa: E402

PACKETS = [('uiseong_andong_2025', '20250325T170000Z', 'kriged_mean'), ('uiseong_andong_2025', '20250325T170000Z', 'firms_early'),
           ('yeongdeok_2025', '20250325T230000Z', 'kriged_mean'), ('yeongdeok_2025', '20250325T230000Z', 'firms_early')]
H_HOURS = 5
N_ORIGINS = 3


def requests(leo, out):
    F = Path(leo) / 'research/harness-2026-11/F-DYN/_data'
    inst = json.loads((F / 'INSTANCE.json').read_text())['instances']
    jobs = []
    for region, start, variant in PACKETS:
        pk = F / 'packets_v31' / region / ('%s_h%d_%s_central_q300' % (start, H_HOURS, variant))
        graph = F / 'graphs_interim' / region / 'graph.json'
        hz = json.loads((pk / 'HAZARD.json').read_text())
        I = next(i for i in inst if i['region'] == region and i['start_tag'] == start and i['horizon_s'] == H_HOURS * 3600)
        ids = [m['id'] for m in hz['members']]
        for o in I['origins'][:N_ORIGINS]:
            d = o['destinations'][0]
            req = build_request(start_node=o['entry_node'], dest_node=d['node'], depart_offset_s=0, dwell_s=d['dwell_s'],
                                window=I['destination_window_s'], limits={'peak_kw_m2': 10, 'dose_kj_m2': 100, 'incurred_dose_kj_m2': 0},
                                scenario_ids=ids, horizon_s=hz['valid_until'], valid_from=hz['valid_from'],
                                hazard_version=hz['version'], as_of_iso=hz['issued_at'])
            tag = '%s__%s_%s__%s' % (region, start, variant, o['origin_id'].replace('/', '_').replace(':', '_'))
            rp = out / 'requests' / (tag + '.json'); rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(json.dumps(req))
            jobs.append((tag, region, graph, pk, rp, o['origin_id'], d['destination_id']))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', type=Path, required=True); ap.add_argument('--leo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True); ap.add_argument('--budget', type=float, required=True)
    ap.add_argument('--mode', choices=['phase', 'plain'], default='phase')
    ap.add_argument('--memory-guard-mib', type=float, default=3072)
    ap.add_argument('--only', default=None)
    ap.add_argument('--python', default=sys.executable)
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists():
        raise SystemExit('Output exists: %s' % out)
    out.mkdir(parents=True)
    for tag, region, graph, pk, rp, origin, dest in requests(a.leo, out):
        if a.only and tag not in a.only.split(','):
            continue
        row = RP.run_one(a.kit.resolve(), None, region, tag, out / 'runs' / tag, a.budget, a.mode, a.python,
                         paths=(graph, pk, rp), memory_guard_mib=a.memory_guard_mib)
        row.update(fdyn={'tag': tag, 'origin': origin, 'destination': dest, 'packet': str(pk), 'request': str(rp)})
        with (out / 'ROWS.jsonl').open('a') as f:
            f.write(json.dumps(row, sort_keys=True, default=str) + '\n')
        print('%-80s %-16s %-30s wall=%.1f mem_stop=%s fam_peak=%.0f MiB' % (tag, row['primary_status'], row['authoritative_status'],
              row['complete_wall_s'] or -1, row.get('memory_guard_triggered'), row['family_peak_rss_mib']), flush=True)


if __name__ == '__main__':
    main()
