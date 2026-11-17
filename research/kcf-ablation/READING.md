# READING (half page)

Only one fire carries real weight: Gyeongbuk 2025 has 507 places with a leave-by (V2); Uljin, Hongseong and Miryang have 4
missions each (V1). Numbers are model output on frozen inputs, not outcomes. A single number holds at all three dose budgets
(92 / 105 / 290 TDU). Sources: `TABLE.md`, `cells.json`.

**Matters most: the forecast hazard (row 2).** It is the only clean one-change row that moves many leave-bys. Persistence in
place of the forecast changes **21 of 507** (median 362 s, largest 1,744 / 1,717 / 1,581 s) and gives 63–69 more of 9,722 jobs a
route. All 21 are in the two Uiseong windows where the forecast adds 15 and 21 burning cells; the other four windows are
unchanged. On V1 it moves 1 of 15 (Uiseong 24 Mar FL2, +527 s). This is influence, not accuracy: c651 as scored in
`canonical-summary-691cc162/RESULTS.json` is worse than persistence on the six held-out US fires (BSS −0.97; its rollout setup was
not checked against the routing packets), while P2 reports +8.17% on Wapiti. Two rows are larger on their own metric but not
comparable: the reference router resolves 13 of 20 P1 missions against 20 (row 6, decisions), and recorded checks differ from the
field at 154 of 507 places (median 348 s), but that arm also lacks heat and dose and uses a 10-minute grid (footnote 4).

**Matters least: heat closure and dose budget, not separable here.** Heat off moves 1 / 1 / 4 of 507 (≤ 317 s); dose off moves
4 / 4 / 3 (≤ 453 s; recorded multi-hour 22 / 21 / 16 of 286, ≤ 529 s). Neither moved any of the 15 V1 leave-bys. They overlap: heat
alone moves 6 of 508 with dose off (kcf-heat) but 1 / 1 / 4 with dose on.

**Could not be judged.** The **measured reach margin (row 3) is NOT RUN everywhere**: its frozen rule covers 5 h and 8 h, the
forecast arm exists at 1 h on other issue times, and a run would need a rule chosen after seeing the full-system output (LAYOUT
§7). That needs your decision. Also unjudged: the router's effect on leave-by times; the deadline field on Uljin, Hongseong and
Miryang (no recorded checks); heat-off in the multi-hour runs; Caldor 2021; the 12 forecast and calibration fires with no road
inputs. Zero changes on the three 4-mission fires cannot show absence.

Caveats: inputs V1–V5 are never added; NEW RUN times came from three arms sharing 4 cores; P1 and P2 do not describe the margin,
heat, dose or deadline field, so "the full system" is Main at `a697d14` (LAYOUT §0).
