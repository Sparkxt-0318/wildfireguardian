# Figure style reference — what the manuscript figures should look like

*Knowledge note · written 2026-09-04 · applies to `paper/style.py` and `paper/make_figures.py` · the author asked for the look of Moreno et al. (2025) and this note turns that look into rules*

## 1. The reference

Moreno, M., Steger, S., Bozzoli, L., Terzi, S., Trucchia, A., van Westen, C., Lombardo, L. (2025) *Space-time modelling of wildfire initiation with static and dynamic drivers* (preprint, Trentino–South Tyrol; GAMs in R; code https://github.com/mmorenoz/Wildfire_EarlyWarning). Ten figures; all drawn in R base graphics. The author supplied the PDF on 2026-09-04 and said the figures are the aesthetic target for the WildfireGuardian paper.

## 2. What the figures have in common (the rules)

1. **Framed panels.** Every panel sits in a thin black box — all four spines, about 0.6 pt. No floating axes, no dropped spines.
2. **Panel letters inside the frame.** `a)`, `b)` … at the top-left (top-right when a legend needs the left), plain weight, same size as tick labels.
3. **Titles are short and centred**, inside or just above the frame ("Wildfire frequency per year"). Interpretation lives in the caption, set in the manuscript in grey italic; figures never carry a sentence.
4. **A small warm palette, three or four hues per figure.** Fire red for fire / presence / the arm we argue for; steel blue for the second arm or the year series; neutral grey for absences and controls; mauve, teal, brown and slate for extra categories. Yellow appears once, as a star marking the optimum.
5. **Bars are filled with a hairline black edge**, stacked when the parts sum to a whole, and carry their values as small dark numbers inside the bar. Legends sit inside the panel at the top-left as filled squares, and their labels carry counts ("Presences (998)").
6. **Uncertainty is either a filled band with a white centre line** (partial effects) **or a dot with a horizontal error bar** (importance) — never both, never shading plus a dashed line plus a marker.
7. **Continuous fields use a yellow→red sequential map** (YlOrRd); thresholds are drawn as labelled contour lines in distinct colours (green dashed, red solid, blue dashed); the colour bar is a small white boxed legend inside the panel.
8. **Maps** put classed data on a hillshade or satellite ground, add a lat/lon graticule with labels on the outer edges, a scale bar bottom-right, and a boxed legend; exceedance classes run teal → light teal → tan → brown; event points are circles graded by size and colour with a five-step legend.
9. **Small multiples share axes**, and the panel variable is written inside each panel as text ("South Tyrol", "Trentino").
10. **Typography.** One Helvetica-like sans, 8–9 pt, horizontal tick labels, sentence-case axis labels with the unit in parentheses, subscripts as real math (Te₀, P₂₈).
11. **Proportions.** Bar figures about 2:1, heatmaps square, maps taller than wide; everything full column width.

## 3. How WildfireGuardian implements it

- `paper/style.py` — `PALETTE` (fire, blue, grey, mauve, teal, brown, slate, sky, yellow), boxed axes, hairline patch edges, framed legends, YlOrRd default map, `label_panels(axes)` (letters just above the frame's left edge so they never cover data; `inside=True` puts them inside as Moreno does), `boxed_legend(ax)`, `EXCEEDANCE` four-class ramp. The legacy `OKABE[...]` names are kept as aliases so older figure code still runs, but they now resolve to the new palette.
- `paper/make_figures.py` — every multi-panel figure calls `style.label_panels`; bar figures keep in-bar value labels; the grid is off by default and switched on only where a value must be read off an axis.
- **Done 2026-09-04 (WFG-060, first half):** `F8_routing_map` — the canonical Yeongdeok case on the SRTM hillshade, YlOrRd forecast field, 0.5 isolines, refuges, all scanned origins classed, three example origins with fire-blind vs forecast-aware routes, WGS84 graticule, scale bars, boxed legend; fully offline from the committed snapshots.
- **Blocked:** the Moreno-Fig.-1 style six-fire **study-area map** needs per-fire burned-area registry keys and the other five fires' DEMs, which are laptop-only; it waits for those (see WFG-060).

## 4. Things we deliberately do not copy

- R's rotated y-tick labels (we keep them horizontal).
- Titles typed inside the plotting area over data.
- Any figure whose numbers are not in `docs/NUMBERS.json` — the style changes; the registry rule does not.

## Update 2026-09-06

*Research routine, sandbox.* **No change, and the reason is worth recording rather than leaving as silence.** This run's scan surfaced no new figure-style reference and no new source bearing on `paper/style.py`. The rules in §2 and the implementation in §3 are unchanged and stay in force.

One observation the scan does support, filed here because it is where a lap would look for it: the strongest new external result this run found (Farajpoor & Narimani 2026, `PYROGEOGRAPHY.md` §Update 2026-09-06) is a **paired** comparison of the same model under two validation schemes, and its whole rhetorical force is that the two numbers sit side by side. That is the same shape as this project's every headline — fire-blind versus forecast-aware on the same origins — and §2's rule that a comparison figure must share axes, scale and colour mapping across its panels is what makes that shape legible. Nothing to change; the rule is doing its job, and this is the kind of figure it exists for.
