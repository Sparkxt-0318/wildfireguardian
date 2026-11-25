# Legibility check

Each PNG scaled to its slot (slide px). Text: cap height >= 22 px (Helvetica Neue cap height 0.714 em; text with mathtext measured with STIXGeneral, 0.662 em). Axis tick labels: font size >= 24 px. Sizes from the layout JSON of each figure (`layout/<name>.json`), every text item.

| figure | slot (px) | smallest text (cap height, slide px) | smallest tick label (font size, slide px) | result |
|---|---|---|---|---|
| F04a_overview_forecast | 1700 x 620 | 22.1 (“10$^{-3}$ h$^{-1}$”) | 25.0 (“0”) | PASS |
| F04b_overview_roads | 1700 x 620 | 22.8 (“원당리”) | 25.0 (“18:00”) | PASS |
| F07_map | 1700 x 640 | 22.8 (“원당리 leaves 18:00”) | none | PASS |
| F08_map | 760 x 600 | 22.8 (“원당리: leave by 18:15:21”) | none | PASS |
| F12_forecast_maps | 900 x 520 | 22.8 (“5 km”) | 25.0 (“0”) | PASS |
| F14_reliability | 760 x 600 | 22.8 (“perfect”) | 25.0 (“0”) | PASS |
| F09_speed | 1100 x 560 | 22.8 (“521×”) | 25.0 (“1 min”) | PASS |
| F10_camp_fire | 1212 x 560 | 22.8 (“Paradise”) | 25.0 (“0”) | PASS |
