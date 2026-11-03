"""English figures (PNG + SVG) and their table twins (CSV), drawn from path A records and checked against NUMBERS.

Verdict encoding = the planner's fixed verdict colours (planner/docs/ARCHITECTURE.md section 7) + text labels, with a
hatch on unresolved (its grey is below 3:1 contrast on white, so it never relies on colour): checked_route green
#1A9E55, model_no_route ink #0B0B0C, unresolved grey #9A9AA0 hatched. The travel-time-only route is never green
(planner README honesty rules); it is drawn in ink with an open marker.

The 1-hour scenario window is shown separately: white dots over a verdict fill mark the window-limited part (fig 1:
departures where even the fastest fire-free trip plus the 120 s stay ends after the window, so no route could be
checked whatever the fire; fig 2: leave-by deadlines set by that window at the next departure). Dots are a pattern,
not a colour, and every dotted part is also counted in text.

Every footer separates the two sources (SOURCES): verdicts, deadlines and travel-only results recorded by the
Route-Check API on the evaluated macOS arm64 host, and what this package computed itself in a Linux container (the
window classification from fire-free trips, route lengths), which is not evaluated-host output.

Drawing is independent of the ambient matplotlib configuration (matplotlibrc, MATPLOTLIBRC): ``draw_all`` starts from
matplotlib's own defaults and pins the settings that shape the output. A figure file is rewritten only when its content
changes (SVG bytes, PNG pixels), because the PNG encoder's compressed bytes can differ between zlib builds.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.style  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from PIL import Image  # noqa: E402  (matplotlib's own PNG dependency)

from . import planner_rules as pr, sources  # noqa: E402

CHECKED_C, NOROUTE_C, UNRES_C, HATCH_C = '#1A9E55', '#0B0B0C', '#9A9AA0', '#FFFFFF'
INK, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#e1e0d9', '#ffffff'
LABEL = {pr.CHECKED: 'Checked route (within the model)',
         pr.NO_ROUTE: 'No route in the model (model_no_route)',
         pr.UNRESOLVED: 'Unresolved: cannot judge, never safe'}
FOOTER = ('Model-relative results for recorded 2025 fire scenarios (4 scenario members per input time, drawn per cell '
          'from the forecast; 1-hour scenario window; OSM roads at an assumed 40 km/h, no congestion). Each place is '
          'checked from its road entry point (the nearest node of the main road network, at most 2 km from the mapped '
          'place; travel to it is not modelled) to each of its three nearest OSM-mapped schools or community halls (not '
          'official shelters; a checked route to any one counts; for one '
          'Yeongdeok place one of the three is an unnamed OSM amenity=shelter point). Not evacuation outcomes. '
          'Planning aid only - not for live evacuation operations.')
_RECORDED = 'Route-Check API results recorded on the evaluated macOS arm64 host (planner cache)'
_COMPUTED = 'computed by this package in a Linux container (not evaluated-host output) from the SHA-verified road graph'
SOURCES = {
    'fig1': f'Sources: verdicts = {_RECORDED}; dotted window-limited parts = {_COMPUTED} and hazard packets.',
    'fig2': f'Sources: leave-by deadlines = {_RECORDED}; dotted "set by the window" = {_COMPUTED} and hazard packets.',
    'fig3': f'Sources: flame contact and arrival times = {_RECORDED}; route lengths (km) = {_COMPUTED}.',
}
# matplotlib 3.9 defaults, pinned explicitly because an ambient matplotlibrc changing them changes every figure
PINNED_RC = {'text.hinting': 'force_autohint', 'text.hinting_factor': 8, 'text.antialiased': True,
             'figure.dpi': 100.0, 'text.kerning_factor': 0}
WINDOW_HATCH = '..'
WINDOW_TEXT = ('even the fastest fire-free trip + the 120 s stay would end after the 1-hour scenario window, so no route '
               'could be checked whatever the fire')
OFFSETS = sources.GRID_OFFSETS_S


def _style():
    """Called inside draw_all's matplotlib.style.context('default'), so nothing ambient leaks in."""
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': '#c3c2b7', 'axes.linewidth': 0.8,
        'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED, 'text.color': INK,
        'axes.spines.top': False, 'axes.spines.right': False, 'svg.hashsalt': 'wfg-solve2027-p4',
        'svg.fonttype': 'none', 'hatch.linewidth': 1.0, 'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE,
        **PINNED_RC,
    })


def _png_pixels(data: bytes) -> tuple:
    with Image.open(io.BytesIO(data)) as im:
        return im.size, im.mode, im.tobytes()


def _same_content(ext: str, a: bytes, b: bytes) -> bool:
    """SVG: identical bytes. PNG: identical decoded pixels (size, mode, RGBA bytes); the compressed stream may differ
    between zlib builds without any visible difference."""
    if ext == 'svg':
        return a == b
    return a == b or _png_pixels(a) == _png_pixels(b)


def same_figure(new: Path, committed: Path) -> bool:
    return committed.is_file() and _same_content(new.suffix[1:], new.read_bytes(), committed.read_bytes())


def _save(fig, out_dir: Path, stem: str) -> list[Path]:
    paths = []
    for ext in ('png', 'svg'):
        p = out_dir / f'{stem}.{ext}'
        kw = {'metadata': {'Date': None}} if ext == 'svg' else {'metadata': {'Software': None}}
        buf = io.BytesIO()
        fig.savefig(buf, format=ext, dpi=150, bbox_inches='tight', **kw)
        data = buf.getvalue()
        if not (p.is_file() and _same_content(ext, data, p.read_bytes())):   # never rewrite an unchanged figure
            p.write_bytes(data)
        paths.append(p)
    plt.close(fig)
    return paths


def _bar(ax, x, bottom, height, verdict, width, window=False):
    """One verdict segment: solid fill with a 1.5 px surface gap; unresolved additionally hatched; the window-limited
    (fig 1) or window-set (fig 2) part additionally dotted."""
    color = {pr.CHECKED: CHECKED_C, pr.NO_ROUTE: NOROUTE_C, pr.UNRESOLVED: UNRES_C}[verdict]
    if height <= 0:
        return
    ax.bar(x, height, width, bottom=bottom, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=2)
    hatch = ('////' if verdict == pr.UNRESOLVED else '') + (WINDOW_HATCH if window else '')
    if hatch:
        ax.bar(x, height, width, bottom=bottom, color='none', edgecolor=HATCH_C, hatch=hatch, linewidth=0, zorder=3)


def _legend_handles(window_label: str | None = None, window_face: str = NOROUTE_C):
    h = [Patch(facecolor=CHECKED_C, label=LABEL[pr.CHECKED]),
         Patch(facecolor=NOROUTE_C, label=LABEL[pr.NO_ROUTE]),
         Patch(facecolor=UNRES_C, edgecolor=HATCH_C, hatch='////', label=LABEL[pr.UNRESOLVED])]
    if window_label:
        h.append(Patch(facecolor=window_face, edgecolor=HATCH_C, hatch=WINDOW_HATCH, label=window_label))
    return h


def _osm(records):
    return [r for r in records if r['origin_type'] in ('village', 'care_facility')]


def fig_checked_share(records, numbers, metas, out_dir: Path, table_dir: Path) -> list[Path]:
    _style()
    recs = _osm(records)
    scopes = [m['scope'] for m in metas]
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.9), sharey=True)
    rows = []
    for i, region in enumerate(sources.REGIONS):
        reg_scopes = [s for s in scopes if s.startswith(region)]
        for j, sc in enumerate(reg_scopes):
            ax = axes[i][j]
            rr = [r for r in recs if r['scope'] == sc]
            n = len(rr)
            for k, t in enumerate(OFFSETS):
                c = {v: sum(1 for r in rr if r['cells'][t] == v) for v in pr.VERDICTS}
                split = {(v, fits): sum(1 for r in rr if r['cells'][t] == v and r['fits'][t] == fits)
                         for v in (pr.NO_ROUTE, pr.UNRESOLVED) for fits in (True, False)}
                for v in pr.VERDICTS:      # every displayed count equals NUMBERS.json
                    assert numbers[f'cell.{v}.offset_{t:04d}s@{sc}']['numerator'] == c[v]
                for (v, fits), x in split.items():
                    cls = 'fits' if fits else 'limited'
                    assert numbers[f'cell_window.{v}.{cls}.offset_{t:04d}s@{sc}']['numerator'] == x
                assert sum(c.values()) == n and not any(r['cells'][t] == pr.CHECKED and not r['fits'][t] for r in rr)
                wl = split[(pr.NO_ROUTE, False)] + split[(pr.UNRESOLVED, False)]
                assert numbers[f'window_limited.offset_{t:04d}s@{sc}']['numerator'] == wl
                segments = [(pr.CHECKED, c[pr.CHECKED], False), (pr.NO_ROUTE, split[(pr.NO_ROUTE, True)], False),
                            (pr.UNRESOLVED, split[(pr.UNRESOLVED, True)], False),
                            (pr.NO_ROUTE, split[(pr.NO_ROUTE, False)], True),
                            (pr.UNRESOLVED, split[(pr.UNRESOLVED, False)], True)]
                bottom = 0.0
                for v, x, window in segments:
                    h = 100.0 * x / n
                    _bar(ax, k, bottom, h, v, 0.68, window=window)
                    if window and 0 < h < 6:   # a 1-2 case sliver is thinner than the hatch lattice: one row of
                        # explicit white dots, outlined so they stay visible where they overlap the gap or background
                        ax.scatter([k - 0.2, k, k + 0.2], [bottom + h / 2] * 3, s=9, facecolor=HATCH_C, edgecolor=INK,
                                   linewidths=0.5, zorder=4)
                    bottom += h
                share = 100.0 * c[pr.CHECKED] / n
                if t in (0, OFFSETS[-1]):
                    ax.text(k, share - 3, f'{share:.0f}%', ha='center', va='top', color='#ffffff', fontsize=7.5,
                            fontweight='bold', zorder=4)
                if wl:     # boxed count of window-limited places: in the dotted part, or just above the bar if thin
                    inside = 100.0 * wl / n >= 9
                    ax.text(k, 100.0 - 50.0 * wl / n if inside else 102.0, str(wl), ha='center',
                            va='center' if inside else 'bottom', fontsize=7.5, color=INK, zorder=5,
                            bbox={'boxstyle': 'round,pad=0.18', 'facecolor': SURFACE, 'edgecolor': NOROUTE_C,
                                  'linewidth': 0.6})
                rows.append({'scope': sc, 'region': region, 'input_time_utc': metas[scopes.index(sc)]['input_time'],
                             'input_kst': metas[scopes.index(sc)]['input_kst'], 'depart_offset_s': t,
                             'depart_offset_min': t // 60, 'n_places': n, 'checked_route': c[pr.CHECKED],
                             'model_no_route': c[pr.NO_ROUTE], 'unresolved': c[pr.UNRESOLVED],
                             'checked_share': round(c[pr.CHECKED] / n, 4),
                             'model_no_route_trip_fits': split[(pr.NO_ROUTE, True)],
                             'unresolved_trip_fits': split[(pr.UNRESOLVED, True)],
                             'model_no_route_window_limited': split[(pr.NO_ROUTE, False)],
                             'unresolved_window_limited': split[(pr.UNRESOLVED, False)], 'window_limited': wl,
                             'numbers_key': f'cell.checked_route.offset_{t:04d}s@{sc}',
                             'numbers_key_window_limited': f'window_limited.offset_{t:04d}s@{sc}'})
            m = metas[scopes.index(sc)]
            ax.set_title(f'{m["input_kst"]}  (n = {n} places)', fontsize=9, color=INK, loc='left', pad=4)
            ax.set_xticks(range(len(OFFSETS)), [f'+{t // 60}' for t in OFFSETS])
            ax.set_ylim(0, 111)                    # room above 100 % for the boxed counts of thin dotted parts
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.spines['left'].set_bounds(0, 100)
            ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
            ax.set_axisbelow(True)
            if j == 0:
                ax.set_ylabel(f'{sources.REGION_NAMES[region]}\n% of places (villages + care facilities)', fontsize=8.5)
            if i == 1:
                ax.set_xlabel('Departure, minutes after the forecast time')
    fig.suptitle('Share of villages and care facilities with a checked route, by departure time',
                 x=0.01, ha='left', fontsize=12, fontweight='bold')
    fig.text(0.01, 0.945, 'Dotted, with boxed count = window-limited: even the fastest fire-free trip + the 120 s stay '
             'would end after the 1-hour scenario window,\nso no route could be checked whatever the fire. At +50 min '
             'only places within 8 min (480 s) of a destination can be checked.\nSolid ink or grey = no checked route '
             'although a fire-free trip would fit the window (fire scenarios, model limits or an unresolved check).',
             fontsize=8.3, color=MUTED, va='top', linespacing=1.3)
    fig.legend(handles=_legend_handles('Window-limited (dotted on either verdict)'), loc='upper left',
               bbox_to_anchor=(0.01, 0.875), ncol=4, frameon=False, fontsize=8.3)
    fig.text(0.01, -0.01, SOURCES['fig1'] + ' ' + FOOTER, fontsize=7.5, color=MUTED, wrap=True, va='top')
    fig.tight_layout(rect=(0, 0.01, 1, 0.865))
    _write_csv(table_dir / 'fig1_checked_share_by_offset.csv', rows)
    return _save(fig, out_dir, 'fig1_checked_share_by_offset')


DEADLINE_LABELS = [(f'latest_{t:04d}s', f'+{t // 60}') for t in OFFSETS[:-1]] + \
    [(f'latest_{OFFSETS[-1]:04d}s', f'+{OFFSETS[-1] // 60}*'), ('none_model_no_route', 'none:\nno route'),
     ('none_unresolved', 'none:\nunresolved')]


def fig_deadlines(records, numbers, out_dir: Path, table_dir: Path) -> list[Path]:
    _style()
    recs = _osm(records)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.1))
    rows = []
    types = [('village', 'Villages and hamlets'), ('care_facility', 'Care facilities')]
    for i, (otype, tname) in enumerate(types):
        for j, region in enumerate(sources.REGIONS):
            ax = axes[i][j]
            rr = [r for r in recs if r['region'] == region and r['origin_type'] == otype]
            places = len({r['origin_id'] for r in rr})
            if not rr:
                ax.axis('off')
                ax.text(0.5, 0.5, f'{tname} - {sources.REGION_NAMES[region]}:\nnone in the OSM extract (0 places)',
                        ha='center', va='center', transform=ax.transAxes, color=MUTED, fontsize=9)
                continue
            key_scope = f'{region}/pooled#{otype}'
            ymax = 0
            for k, (cat, lab) in enumerate(DEADLINE_LABELS):
                sel = [r for r in rr if r['deadline_category'] == cat]
                c = len(sel)
                assert numbers[f'deadline.{cat}@{key_scope}']['numerator'] == c
                w = sum(1 for r in sel if r['deadline_set_by'] == 'window')
                f = sum(1 for r in sel if r['deadline_set_by'] == 'fire_or_limits')
                split = cat.startswith('latest_') and cat != f'latest_{OFFSETS[-1]:04d}s'
                if split:
                    assert w + f == c
                    assert numbers[f'deadline.{cat}.set_by_window@{key_scope}']['numerator'] == w
                    assert numbers[f'deadline.{cat}.set_by_fire_or_limits@{key_scope}']['numerator'] == f
                    _bar(ax, k, 0, f, pr.CHECKED, 0.68)
                    _bar(ax, k, f, w, pr.CHECKED, 0.68, window=True)
                else:
                    assert w == f == 0
                    v = pr.NO_ROUTE if cat == 'none_model_no_route' else pr.UNRESOLVED if cat == 'none_unresolved' else pr.CHECKED
                    _bar(ax, k, 0, c, v, 0.68)
                ax.text(k, c, str(c) + (f'\n({w} window)' if split and w else ''), ha='center', va='bottom',
                        fontsize=8 if not (split and w) else 7.2, color=INK, linespacing=1.05)
                ymax = max(ymax, c)
                rows.append({'region': region, 'origin_type': otype, 'places': places, 'cases': len(rr),
                             'deadline_category': cat, 'label': lab.replace('\n', ' '), 'cases_in_category': c,
                             'set_by_window': w if split else '', 'set_by_fire_or_limits': f if split else '',
                             'numbers_key': f'deadline.{cat}@{key_scope}',
                             'numbers_key_window': f'deadline.{cat}.set_by_window@{key_scope}' if split else ''})
            ax.set_xticks(range(len(DEADLINE_LABELS)), [lab for _, lab in DEADLINE_LABELS], fontsize=8)
            ax.set_xlim(-0.6, len(DEADLINE_LABELS) - 0.4)
            ax.set_ylim(0, ymax * 1.22 + 1)
            ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
            ax.set_axisbelow(True)
            ax.set_title(f'{tname} - {sources.REGION_NAMES[region]} ({places} places x 3 forecast times = {len(rr)} cases)',
                         loc='left', fontsize=9)
            if j == 0:
                ax.set_ylabel('cases (place x forecast time)')
            if i == 1:
                ax.set_xlabel('Leave-by deadline: latest departure (min after the forecast time) with a checked route')
            elif otype == 'village':
                ax.set_xlabel('Leave-by deadline (min after the forecast time)', fontsize=8.5)
    fig.suptitle('Leave-by deadline by origin type, and whether the 1-hour window set it', x=0.01, ha='left',
                 fontsize=12, fontweight='bold')
    fig.text(0.01, 0.945, 'Dotted = deadline set by the window: at the next departure (10 min later) even the fastest '
             'fire-free trip + the 120 s stay would end\nafter the 1-hour scenario window, so no later route could be '
             'checked whatever the fire. Solid green before +50 = set by the fire scenarios\nor model limits (a '
             'fire-free trip would still fit at the next departure). * +50 = checked at the last checked departure; '
             'the window gives no later limit.', fontsize=8.3, color=MUTED, va='top', linespacing=1.3)
    fig.legend(handles=_legend_handles('Checked route, deadline set by the window (dotted)', CHECKED_C),
               loc='upper left', bbox_to_anchor=(0.01, 0.875), ncol=4, frameon=False, fontsize=8.3)
    fig.text(0.01, -0.01, SOURCES['fig2'] + ' ' + FOOTER, fontsize=7.5, color=MUTED, wrap=True, va='top')
    fig.tight_layout(rect=(0, 0.01, 1, 0.865))
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
    early = numbers['travel_only.fastest_meets_flames@all/pooled#leave_by_before_3000s']
    late = numbers['travel_only.fastest_meets_flames@all/pooled#leave_by_3000s']
    assert early['numerator'] == len(flame) and late['numerator'] == 0
    assert early['denominator'] + late['denominator'] == len(comp)
    assert all(p['depart_offset_s'] < OFFSETS[-1] for p in flame)
    ax.set_title(f'Where the fastest route meets predicted flames: {len(flame)} of the {early["denominator"]} '
                 f'comparisons at leave-by deadlines before +{OFFSETS[-1] // 60} min\n(all in '
                 f'{sources.REGION_NAMES["uiseong_andong_2025"]}), none of the {late["denominator"]} at '
                 f'+{OFFSETS[-1] // 60} min. In the other {clear["denominator"]} comparisons the travel-time-only '
                 f'route had no\npredicted flame contact and arrived at the same second as the checked route '
                 f'({clear["numerator"]} of {clear["denominator"]}).', loc='left', fontsize=10)
    handles = [plt.Line2D([], [], marker='o', linestyle='none', markerfacecolor=SURFACE, markeredgecolor=NOROUTE_C,
                          markeredgewidth=1.8, markersize=8,
                          label='Travel-time-only route (comparison only; meets predicted flames in >= 1 of 4 members)'),
               plt.Line2D([], [], marker='o', linestyle='none', markerfacecolor=CHECKED_C, markeredgecolor=SURFACE,
                          markersize=8, label='Checked route (within the model), same destination')]
    ax.legend(handles=handles, loc='lower right', frameon=True, framealpha=1.0, edgecolor=GRID, fontsize=8.5)
    fig.text(0.01, -0.01, 'Comparison at each place\'s leave-by deadline toward the destination of its default checked '
             'route. ' + SOURCES['fig3'] + ' ' + FOOTER, fontsize=7.5, color=MUTED, wrap=True, va='top')
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
    # matplotlib's own defaults whatever matplotlibrc / MATPLOTLIBRC say (restored on exit); _style() pins the rest
    with matplotlib.style.context('default'):
        paths = fig_checked_share(result['records'], numbers, result['metas'], out_dir, table_dir)
        paths += fig_deadlines(result['records'], numbers, out_dir, table_dir)
        paths += fig_travel_only(result['pairs'], numbers, result['metas'], out_dir, table_dir)
    return paths
