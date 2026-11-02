"""English figures (PNG + SVG) and their table twins (CSV), drawn from path A records and checked against NUMBERS.

Verdict encoding = the planner's fixed verdict colours (planner/docs/ARCHITECTURE.md section 7) + text labels, with a
hatch on unresolved (its grey is below 3:1 contrast on white, so it never relies on colour): checked_route green
#1A9E55, model_no_route ink #0B0B0C, unresolved grey #9A9AA0 hatched. The travel-time-only route is never green
(planner README honesty rules); it is drawn in ink with an open marker.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from . import planner_rules as pr, sources  # noqa: E402

CHECKED_C, NOROUTE_C, UNRES_C, HATCH_C = '#1A9E55', '#0B0B0C', '#9A9AA0', '#FFFFFF'
INK, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#e1e0d9', '#ffffff'
LABEL = {pr.CHECKED: 'Checked route (within the model)',
         pr.NO_ROUTE: 'No route in the model (model_no_route)',
         pr.UNRESOLVED: 'Unresolved: cannot judge, never safe'}
FOOTER = ('Model-relative results for recorded 2025 fire scenarios (4 scenario members per input time, drawn per cell '
          'from the forecast; 1-hour horizon; OSM roads at an assumed 40 km/h, no congestion). Not evacuation outcomes. '
          'Planning aid only - not for live evacuation operations.')
OFFSETS = sources.GRID_OFFSETS_S


def _style():
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': '#c3c2b7', 'axes.linewidth': 0.8,
        'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED, 'text.color': INK,
        'axes.spines.top': False, 'axes.spines.right': False, 'svg.hashsalt': 'wfg-solve2027-p4',
        'svg.fonttype': 'none', 'hatch.linewidth': 1.0, 'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE,
    })


def _save(fig, out_dir: Path, stem: str) -> list[Path]:
    paths = []
    for ext in ('png', 'svg'):
        p = out_dir / f'{stem}.{ext}'
        kw = {'metadata': {'Date': None}} if ext == 'svg' else {'metadata': {'Software': None}}
        fig.savefig(p, dpi=150, bbox_inches='tight', **kw)
        paths.append(p)
    plt.close(fig)
    return paths


def _bar(ax, x, bottom, height, verdict, width):
    """One verdict segment: solid fill with a 1.5 px surface gap; unresolved additionally hatched."""
    color = {pr.CHECKED: CHECKED_C, pr.NO_ROUTE: NOROUTE_C, pr.UNRESOLVED: UNRES_C}[verdict]
    if height <= 0:
        return
    ax.bar(x, height, width, bottom=bottom, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=2)
    if verdict == pr.UNRESOLVED:
        ax.bar(x, height, width, bottom=bottom, color='none', edgecolor=HATCH_C, hatch='////', linewidth=0, zorder=3)


def _legend_handles():
    return [Patch(facecolor=CHECKED_C, label=LABEL[pr.CHECKED]),
            Patch(facecolor=NOROUTE_C, label=LABEL[pr.NO_ROUTE]),
            Patch(facecolor=UNRES_C, edgecolor=HATCH_C, hatch='////', label=LABEL[pr.UNRESOLVED])]


def _osm(records):
    return [r for r in records if r['origin_type'] in ('village', 'care_facility')]


def fig_checked_share(records, numbers, metas, out_dir: Path, table_dir: Path) -> list[Path]:
    _style()
    recs = _osm(records)
    scopes = [m['scope'] for m in metas]
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.6), sharey=True)
    rows = []
    for i, region in enumerate(sources.REGIONS):
        reg_scopes = [s for s in scopes if s.startswith(region)]
        for j, sc in enumerate(reg_scopes):
            ax = axes[i][j]
            rr = [r for r in recs if r['scope'] == sc]
            n = len(rr)
            for k, t in enumerate(OFFSETS):
                c = {v: sum(1 for r in rr if r['cells'][t] == v) for v in pr.VERDICTS}
                for v in pr.VERDICTS:      # every displayed count equals NUMBERS.json
                    assert numbers[f'cell.{v}.offset_{t:04d}s@{sc}']['numerator'] == c[v]
                assert sum(c.values()) == n
                bottom = 0.0
                for v in pr.VERDICTS:
                    h = 100.0 * c[v] / n
                    _bar(ax, k, bottom, h, v, 0.68)
                    bottom += h
                share = 100.0 * c[pr.CHECKED] / n
                if t in (0, OFFSETS[-1]):
                    ax.text(k, share - 3, f'{share:.0f}%', ha='center', va='top', color='#ffffff', fontsize=7.5,
                            fontweight='bold', zorder=4)
                rows.append({'scope': sc, 'region': region, 'input_time_utc': metas[scopes.index(sc)]['input_time'],
                             'input_kst': metas[scopes.index(sc)]['input_kst'], 'depart_offset_s': t,
                             'depart_offset_min': t // 60, 'n_origins': n, 'checked_route': c[pr.CHECKED],
                             'model_no_route': c[pr.NO_ROUTE], 'unresolved': c[pr.UNRESOLVED],
                             'checked_share': round(c[pr.CHECKED] / n, 4),
                             'numbers_key': f'cell.checked_route.offset_{t:04d}s@{sc}'})
            m = metas[scopes.index(sc)]
            ax.set_title(f'{m["input_kst"]}  (n = {n})', fontsize=9, color=INK, loc='left')
            ax.set_xticks(range(len(OFFSETS)), [f'+{t // 60}' for t in OFFSETS])
            ax.set_ylim(0, 100)
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
            ax.set_axisbelow(True)
            if j == 0:
                ax.set_ylabel(f'{sources.REGION_NAMES[region]}\n% of checked origins', fontsize=9)
            if i == 1:
                ax.set_xlabel('Departure, minutes after the recorded input time')
    fig.suptitle('Survival of the checked departure window: share of villages and care facilities with a checked route',
                 x=0.01, ha='left',
                 fontsize=12, fontweight='bold')
    fig.text(0.01, 0.935, 'Green = the survival of the checked departure window (no origin had a gap: the share checked '
             'at a departure time equals the share whose leave-by deadline is at or after it).', fontsize=8.5, color=MUTED)
    fig.legend(handles=_legend_handles(), loc='upper left', bbox_to_anchor=(0.01, 0.925), ncol=3, frameon=False, fontsize=8.5)
    fig.text(0.01, -0.02, FOOTER, fontsize=7.5, color=MUTED, wrap=True)
    fig.tight_layout(rect=(0, 0.01, 1, 0.88))
    _write_csv(table_dir / 'fig1_checked_share_by_offset.csv', rows)
    return _save(fig, out_dir, 'fig1_checked_share_by_offset')


DEADLINE_LABELS = [(f'latest_{t:04d}s', f'+{t // 60}') for t in OFFSETS[:-1]] + \
    [(f'latest_{OFFSETS[-1]:04d}s', f'+{OFFSETS[-1] // 60}*'), ('none_model_no_route', 'none:\nno route'),
     ('none_unresolved', 'none:\nunresolved')]


def fig_deadlines(records, numbers, out_dir: Path, table_dir: Path) -> list[Path]:
    _style()
    recs = _osm(records)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 6.8))
    rows = []
    types = [('village', 'Villages and hamlets'), ('care_facility', 'Care facilities')]
    for i, (otype, tname) in enumerate(types):
        for j, region in enumerate(sources.REGIONS):
            ax = axes[i][j]
            rr = [r for r in recs if r['region'] == region and r['origin_type'] == otype]
            places = len({r['origin_id'] for r in rr})
            if not rr:
                ax.axis('off')
                ax.text(0.5, 0.5, f'{tname} - {sources.REGION_NAMES[region]}:\nnone in the OSM extract (0 origins)',
                        ha='center', va='center', transform=ax.transAxes, color=MUTED, fontsize=9)
                continue
            key_scope = f'{region}/pooled#{otype}'
            ymax = 0
            for k, (cat, lab) in enumerate(DEADLINE_LABELS):
                c = sum(1 for r in rr if r['deadline_category'] == cat)
                assert numbers[f'deadline.{cat}@{key_scope}']['numerator'] == c
                v = pr.NO_ROUTE if cat == 'none_model_no_route' else pr.UNRESOLVED if cat == 'none_unresolved' else pr.CHECKED
                _bar(ax, k, 0, c, v, 0.68)
                ax.text(k, c, str(c), ha='center', va='bottom', fontsize=8, color=INK)
                ymax = max(ymax, c)
                rows.append({'region': region, 'origin_type': otype, 'places': places, 'cases': len(rr),
                             'deadline_category': cat, 'label': lab.replace('\n', ' '), 'cases_in_category': c,
                             'numbers_key': f'deadline.{cat}@{key_scope}'})
            ax.set_xticks(range(len(DEADLINE_LABELS)), [lab for _, lab in DEADLINE_LABELS], fontsize=8)
            ax.set_ylim(0, ymax * 1.15 + 1)
            ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
            ax.set_axisbelow(True)
            ax.set_title(f'{tname} - {sources.REGION_NAMES[region]} ({places} places x 3 input times = {len(rr)} cases)',
                         loc='left', fontsize=9)
            if j == 0:
                ax.set_ylabel('cases (place x input time)')
            if i == 1:
                ax.set_xlabel('Leave-by deadline: latest departure (min after input time) with a checked route')
            elif otype == 'village':
                ax.set_xlabel('Leave-by deadline (min after input time)', fontsize=8.5)
    fig.suptitle('Leave-by deadline by origin type', x=0.01, ha='left', fontsize=12, fontweight='bold')
    fig.text(0.01, 0.935, '* +50 = still checked at the last checked departure (+50 min); the 1-hour scenario window '
             'gives no later limit. Departures are checked every 10 min; times in between are not checked.',
             fontsize=8.5, color=MUTED)
    fig.legend(handles=_legend_handles(), loc='upper left', bbox_to_anchor=(0.01, 0.925), ncol=3, frameon=False, fontsize=8.5)
    fig.text(0.01, -0.02, FOOTER, fontsize=7.5, color=MUTED, wrap=True)
    fig.tight_layout(rect=(0, 0.01, 1, 0.88))
    _write_csv(table_dir / 'fig2_deadline_by_origin_type.csv', rows)
    return _save(fig, out_dir, 'fig2_deadline_by_origin_type')


def fig_travel_only(pairs, numbers, metas, out_dir: Path, table_dir: Path) -> list[Path]:
    _style()
    kst = {m['scope']: m['input_kst'] for m in metas}
    comp = [p for p in pairs if p['has_comparison'] and p['same_start_destination_offset']]
    flame = sorted([p for p in comp if p['fastest_meets_flames']], key=lambda p: (p['input_time'], p['depart_offset_s'], p['origin_id']))
    assert numbers['travel_only.fastest_meets_flames@all/pooled']['numerator'] == len(flame)
    assert numbers['travel_only.fastest_meets_flames@all/pooled']['denominator'] == len(comp)
    fig, ax = plt.subplots(figsize=(11.5, 0.55 * len(flame) + 2.6))
    rows = []
    for y, p in enumerate(reversed(flame)):
        dep = p['depart_offset_s']
        fast = (p['fastest_arrival_s'] - dep) / 60.0
        chk = (p['checked_arrival_s'] - dep) / 60.0
        ax.plot([fast, chk], [y, y], color='#c3c2b7', linewidth=2, zorder=1, solid_capstyle='round')
        ax.scatter([fast], [y], s=58, facecolor=SURFACE, edgecolor=NOROUTE_C, linewidth=1.8, zorder=3)
        ax.scatter([chk], [y], s=58, color=CHECKED_C, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.text(max(fast, chk) + 0.6, y, f'+{p["extra_arrival_s"] / 60:.1f} min, +{p["extra_length_m"] / 1000:.1f} km '
                f'(flame contact in {p["fastest_contact_members"]} of 4 members)', va='center', fontsize=8, color=INK)
        name = p['name_en'] or 'unnamed place'      # English figure: OSM name:en (Korean name in the CSV)
        label = f'{name} ({p["origin_id"]})\n{kst[p["scope"]]}, departing +{dep // 60} min'
        ax.text(-0.01, y, label, transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=7.8, color=INK)
        rows.append({'scope': p['scope'], 'input_kst': kst[p['scope']], 'origin_id': p['origin_id'], 'name': p['name'],
                     'name_en': p['name_en'] or '',
                     'origin_type': p['origin_type'], 'depart_offset_s': dep, 'destination_id': p['destination_id'],
                     'fastest_route_minutes_after_departure': round(fast, 3), 'checked_route_minutes_after_departure': round(chk, 3),
                     'extra_arrival_s': p['extra_arrival_s'], 'extra_length_m': round(p['extra_length_m'], 1),
                     'fastest_contact_members_of_4': p['fastest_contact_members'],
                     'fastest_whole_road_contact': p['fastest_whole_road_contact']})
    ax.set_yticks([])
    ax.spines['left'].set_visible(False)
    ax.set_xlim(0, max(r['checked_route_minutes_after_departure'] for r in rows) * 1.6)
    ax.set_ylim(-2.0, len(flame) - 0.3)          # room below the last row for the legend
    ax.xaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel('Travel time to the same destination, minutes after departure (same departure time)')
    clear = numbers['travel_only.clear_pairs_equal_arrival@all/pooled']
    ax.set_title(f'Where the fastest route meets predicted flames: {len(flame)} of {len(comp)} comparisons '
                 f'(all in {sources.REGION_NAMES["uiseong_andong_2025"]})\n'
                 f'In the other {clear["denominator"]}, the travel-time-only route had no predicted flame contact and '
                 f'arrived at the same second as the checked route ({clear["numerator"]} of {clear["denominator"]}).',
                 loc='left', fontsize=10)
    handles = [plt.Line2D([], [], marker='o', linestyle='none', markerfacecolor=SURFACE, markeredgecolor=NOROUTE_C,
                          markeredgewidth=1.8, markersize=8,
                          label='Travel-time-only route (comparison only; meets predicted flames in >= 1 of 4 members)'),
               plt.Line2D([], [], marker='o', linestyle='none', markerfacecolor=CHECKED_C, markeredgecolor=SURFACE,
                          markersize=8, label='Checked route (within the model), same destination')]
    ax.legend(handles=handles, loc='lower right', frameon=True, framealpha=1.0, edgecolor=GRID, fontsize=8.5)
    fig.text(0.01, -0.02, 'Comparison at each place\'s leave-by deadline toward the destination of its default checked '
             'route. ' + FOOTER, fontsize=7.5, color=MUTED, wrap=True)
    fig.tight_layout()
    _write_csv(table_dir / 'fig3_travel_only_vs_checked.csv', rows)
    return _save(fig, out_dir, 'fig3_travel_only_vs_checked')


def _write_csv(path: Path, rows: list[dict]):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def draw_all(result: dict, numbers: dict, out_dir: Path, table_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    paths = fig_checked_share(result['records'], numbers, result['metas'], out_dir, table_dir)
    paths += fig_deadlines(result['records'], numbers, out_dir, table_dir)
    paths += fig_travel_only(result['pairs'], numbers, result['metas'], out_dir, table_dir)
    return paths
